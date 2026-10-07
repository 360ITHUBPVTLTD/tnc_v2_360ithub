# Copyright (c) 2026, 360ITHub and contributors
"""Syllabus Progress: how far each subject has been taught, per batch.

Source of truth is the Teachers Timesheet class row (batch, subject, chapter, chapter completed).
A chapter is Done for a batch once an approved timesheet names it with "Completed" ticked; classes
on it before that make it Started. "Count classes waiting for approval" also counts pending timesheets.

Summary mode: one row per subject and batch: chapters done of total, time taught, the last class.
Time comes from the row's quantity: minutes as teachers fill it in the app, other time units converted
to minutes through the UOM conversion table; count-based rows (Nos) add no time.
With a Period, only subjects and batches that had classes in it are listed, and the counts cover
that period only.
"Show chapters" (subject required; batch taken from the classes when only one batch has any): one row per chapter with status, classes, time, last
date and teachers; the chapter's classes open in a dialog (chapter_classes).
"""
import frappe
from frappe import _
from frappe.utils import cint, flt, getdate


def _to_minutes(rows):
	"""Set c.minutes on each class row; units without a conversion to Minute count as 0."""
	from erpnext.stock.get_item_details import get_uom_conv_factor
	factor = {"Minute": 1}
	for c in rows:
		if c.uom not in factor:
			factor[c.uom] = flt(get_uom_conv_factor(c.uom, "Minute")) if c.uom else 0
		c.minutes = round(flt(c.qty) * factor[c.uom])
	return rows


def fmt_minutes(m):
	"""95 -> '1h 35m', 45 -> '0h 45m', 0 -> ''."""
	m = cint(m)
	if not m:
		return ""
	h, r = divmod(m, 60)
	return f"{h}h {r:02d}m"


def _period(f):
	"""DateRange filter -> (from, to) dates, or (None, None)."""
	p = f.period
	if isinstance(p, str):
		p = frappe.parse_json(p) if p.startswith("[") else [x.strip() for x in p.split(",")]
	if not p or not all(p):
		return None, None
	start, end = getdate(p[0]), getdate(p[-1])
	if start > end:
		frappe.throw(_("The period starts after it ends. Please pick the dates again."))
	return start, end


def execute(filters=None):
	f = frappe._dict(filters or {})
	f.from_date, f.to_date = _period(f)
	if cint(f.show_chapters):
		# never a popup here: filters change one at a time, so half-filled states are normal
		if not f.subject:
			return chapter_columns(), [], _("Pick a Subject to see its chapters.")
		if not f.batch:
			# one batch taught so far: use it; none: plain chapter list; several: ask which
			batches = sorted({c.batch for c in _classes(f) if c.batch})
			if len(batches) > 1:
				return chapter_columns(), [], _("This subject is taught in {0}. Pick the Batch to see its chapters.").format(", ".join(batches))
			f.batch = batches[0] if batches else None
		message = _("Batch: {0}").format(f.batch) if f.batch else None
		return chapter_columns(), chapter_rows(f), message
	return summary_columns(), summary_rows(f)


def _classes(f):
	"""Timesheet class rows that name a subject and chapter, within the filters."""
	statuses = ["Approved", "Pending"] if cint(f.include_pending) else ["Approved"]
	cond, vals = ["ts.status in %(statuses)s", "a.subject is not null and a.subject != ''", "ifnull(a.chapter_seq, 0) > 0"], {"statuses": statuses}
	if f.batch:
		cond.append("a.batch = %(batch)s"); vals["batch"] = f.batch
	if f.subject:
		cond.append("a.subject = %(subject)s"); vals["subject"] = f.subject
	if f.teacher:
		cond.append("ts.teacher_id = %(teacher)s"); vals["teacher"] = f.teacher
	if f.from_date:
		cond.append("ts.date >= %(from_date)s"); vals["from_date"] = f.from_date
	if f.to_date:
		cond.append("ts.date <= %(to_date)s"); vals["to_date"] = f.to_date
	rows = frappe.db.sql(f"""
		select a.batch, a.subject, a.qty, a.uom, a.chapter, a.chapter_seq, ifnull(a.chapter_completed, 0) as completed, ts.date, ts.teacher_id, ts.teacher_name, ts.name as timesheet, ts.status
		from `tabActivities` a join `tabTeachers Timesheet` ts on ts.name = a.parent
		where {" and ".join(cond)}
		order by ts.date, ts.creation""", vals, as_dict=True)
	return _to_minutes(rows)


def summary_columns():
	return [
		{"fieldname": "subject", "label": _("Subject"), "fieldtype": "Data", "width": 190},
		{"fieldname": "batch", "label": _("Batch"), "fieldtype": "Data", "width": 140},
		{"fieldname": "teacher_name", "label": _("Usual Teacher"), "fieldtype": "Data", "width": 120},
		{"fieldname": "done_text", "label": _("Chapters Done"), "fieldtype": "Data", "width": 130},
		{"fieldname": "pct", "label": _("Progress"), "fieldtype": "Percent", "width": 130},
		{"fieldname": "time_taught", "label": _("Time Taught"), "fieldtype": "Data", "width": 110},
		{"fieldname": "last_chapter", "label": _("Last Chapter Taught"), "fieldtype": "Data", "width": 200},
		{"fieldname": "last_date", "label": _("Last Class"), "fieldtype": "Date", "width": 110},
		{"fieldname": "last_by", "label": _("By"), "fieldtype": "Data", "width": 120},
	]


def summary_rows(f):
	subjects = frappe.get_all("Subject", filters={"disabled": 0, **({"name": f.subject} if f.subject else {}), **({"teacher": f.teacher} if f.teacher else {})},
		fields=["name", "teacher_name", "chapter_count", "sort_order"], order_by="sort_order asc, name asc")
	groups = {}
	for c in _classes(f):
		g = groups.setdefault((c.subject, c.batch or ""), {"done": set(), "classes": 0, "minutes": 0, "last": None})
		g["classes"] += 1; g["minutes"] += c.minutes
		if c.completed:
			g["done"].add(c.chapter_seq)
		if not g["last"] or (c.date, c.chapter_seq) >= (g["last"].date, g["last"].chapter_seq):
			g["last"] = c
	rows = []
	for s in subjects:
		batches = sorted({b for (subj, b) in groups if subj == s.name}) or [""]
		if f.batch and f.batch not in batches:
			batches = [f.batch]
		for b in batches:
			g = groups.get((s.name, b), {"done": set(), "classes": 0, "minutes": 0, "last": None})
			if f.from_date and not g["classes"]:
				continue
			done, total, last = len(g["done"]), cint(s.chapter_count), g["last"]
			rows.append({
				"subject": s.name, "batch": b or None, "teacher_name": s.teacher_name,
				"done_text": _("{0} of {1}").format(done, total), "pct": round(flt(done) / total * 100, 1) if total else 0,
				"time_taught": fmt_minutes(g["minutes"]),
				"last_chapter": last.chapter if last else None, "last_date": last.date if last else None,
				"last_by": last.teacher_name if last else None, "classes": g["classes"],
			})
	# subjects being taught first, untouched ones after; each group keeps the syllabus order
	return sorted(rows, key=lambda r: not r["classes"])


def chapter_columns():
	return [
		{"fieldname": "seq", "label": _("No."), "fieldtype": "Int", "width": 60},
		{"fieldname": "chapter", "label": _("Chapter"), "fieldtype": "Data", "width": 340},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 110},
		{"fieldname": "classes", "label": _("Classes"), "fieldtype": "Int", "width": 80},
		{"fieldname": "time", "label": _("Time"), "fieldtype": "Data", "width": 90},
		{"fieldname": "last_date", "label": _("Last Taught"), "fieldtype": "Date", "width": 110},
		{"fieldname": "teachers", "label": _("Teacher"), "fieldtype": "Data", "width": 220},
	]


def chapter_rows(f):
	chapters = frappe.get_all("Subject Chapter", filters={"parent": f.subject}, fields=["seq", "chapter_name"], order_by="seq asc")
	by_seq = {}
	for c in _classes(f):
		by_seq.setdefault(c.chapter_seq, []).append(c)
	rows = []
	for ch in chapters:
		hits = by_seq.get(ch.seq, [])
		row = {"seq": ch.seq, "chapter": ch.chapter_name, "status": _("Not started")}
		if hits:
			row.update({
				"status": _("Done") if any(h.completed for h in hits) else _("Started"),
				"classes": len(hits), "time": fmt_minutes(sum(h.minutes for h in hits)),
				"last_date": max(h.date for h in hits),
				"teachers": ", ".join(dict.fromkeys(h.teacher_name for h in hits if h.teacher_name)),
			})
		rows.append(row)
	return rows


@frappe.whitelist()
def chapter_classes(filters, seq=None, subject=None, batch=None):
	"""Classes behind a report row: one chapter (seq), or a whole subject and batch (summary row)."""
	if not frappe.has_permission("Teachers Timesheet", "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	f = frappe._dict(frappe.parse_json(filters) if isinstance(filters, str) else filters)
	f.from_date, f.to_date = _period(f)
	if subject:
		f.subject, f.batch = subject, batch
	if not f.subject:
		return []
	return [{"date": c.date, "teacher": c.teacher_name, "time": fmt_minutes(c.minutes), "completed": c.completed,
		"timesheet": c.timesheet, "status": c.status, "chapter": c.chapter}
		for c in _classes(f) if not seq or c.chapter_seq == cint(seq)]
