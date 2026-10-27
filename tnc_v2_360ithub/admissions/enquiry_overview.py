"""Enquiry Overview page: the enquiry pipeline at a glance for one batch, one counsellor, or
everything. Counts come straight from Student Enquiry, Student Follow-Up and Demo Class; nothing
is stored. Counsellors (no manager role) only ever see their own enquiries."""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate, date_diff

MANAGER_ROLES = {"TNC Manager", "TNC Super Admin", "System Manager"}
OPEN = ("New", "Demo Scheduled", "Demo Attended")


def _outcome(notes):
	"""What was said on the call: the text after the last 'Outcome:' (log_outcome appends it), else the whole note."""
	n = (notes or "").strip()
	return n.rsplit("Outcome:", 1)[-1].strip() if "Outcome:" in n else n


def _plan(notes):
	"""What the pending call is for: the note without any earlier outcome lines."""
	return (notes or "").split("Outcome:", 1)[0].strip()


def _rate(converted, total):
	return round(flt(converted) / total * 100, 1) if total else 0


def is_manager(user=None):
	return bool(MANAGER_ROLES & set(frappe.get_roles(user)))


@frappe.whitelist()
def batch_options():
	"""Batch filter choices: every batch."""
	return [{"value": b.name, "label": b.batch_name or b.name} for b in frappe.get_all("Student Batch", fields=["name", "batch_name"], order_by="status, batch_name")]


@frappe.whitelist()
def get_overview(batch=None, counsellor=None, from_date=None, to_date=None):
	manager = is_manager()
	if not manager:
		counsellor = frappe.session.user  # a counsellor sees their own enquiries whatever the request says
	filters = {}
	if batch:
		filters["batch_interested"] = batch
	if counsellor:
		filters["counsellor"] = counsellor
	if from_date and to_date:
		filters["enquiry_date"] = ["between", [getdate(from_date), getdate(to_date)]]
	enquiries = frappe.get_all("Student Enquiry", filters=filters, order_by="enquiry_date desc, creation desc",
		fields=["name", "student_name", "mobile", "status", "enquiry_date", "counsellor", "next_follow_up", "batch_interested", "course_interested",
			"preferred_mode", "source", "converted_on", "lost_reason", "lost_on", "student", "creation"])
	names = [e.name for e in enquiries]
	today = getdate(nowdate())

	# follow-ups per enquiry: how many were done, what is still open and when it is due
	fups = frappe.get_all("Student Follow-Up", filters={"reference_type": "Student Enquiry", "reference_name": ["in", names or [""]]},
		fields=["name", "reference_name", "status", "purpose", "followup_type", "follow_up_date", "next_follow_up_date", "notes", "assigned_to", "modified"],
		order_by="modified desc")
	by_enq = {}
	for f in fups:
		x = by_enq.setdefault(f.reference_name, {"done": 0, "open": 0, "last_on": None, "last_notes": None, "next_on": None, "open_name": None, "open_notes": None})
		if f.status == "Closed":
			x["done"] += 1
			if not x["last_on"] or (f.follow_up_date and getdate(f.follow_up_date) > getdate(x["last_on"])):
				x["last_on"], x["last_notes"] = f.follow_up_date, _outcome(f.notes)
		else:
			x["open"] += 1
			if f.next_follow_up_date and (not x["next_on"] or getdate(f.next_follow_up_date) < getdate(x["next_on"])):
				x["next_on"], x["open_name"], x["open_notes"] = f.next_follow_up_date, f.name, _plan(f.notes)

	# demos per enquiry
	demos = frappe.get_all("Demo Class", filters={"enquiry": ["in", names or [""]]}, fields=["enquiry", "result", "demo_date", "batch"], order_by="demo_date desc")
	demo_of = {}
	for d in demos:
		x = demo_of.setdefault(d.enquiry, {"scheduled": 0, "attended": 0, "last": None})
		x["scheduled"] += 1
		x["attended"] += 1 if d.result == "Attended" else 0
		x["last"] = x["last"] or d

	user_names = {u.name: u.full_name for u in frappe.get_all("User", filters={"name": ["in", list({e.counsellor for e in enquiries if e.counsellor} | {f.assigned_to for f in fups if f.assigned_to} or {""})]}, fields=["name", "full_name"])}
	batch_names = {b.name: b.batch_name for b in frappe.get_all("Student Batch", fields=["name", "batch_name"])}

	enq_of = {e.name: e for e in enquiries}
	rows = []
	for e in enquiries:
		f = by_enq.get(e.name, {"done": 0, "open": 0, "last_on": None, "last_notes": None, "next_on": None, "open_name": None, "open_notes": None})
		dm = demo_of.get(e.name, {"scheduled": 0, "attended": 0, "last": None})
		nxt = f["next_on"] or (e.next_follow_up if e.status in OPEN else None)
		due = None
		if e.status in OPEN and nxt:
			due = "overdue" if getdate(nxt) < today else "today" if getdate(nxt) == today else "upcoming"
		rows.append({
			"name": e.name, "student_name": e.student_name, "mobile": e.mobile, "status": e.status, "enquiry_date": e.enquiry_date, "creation": e.creation,
			"counsellor": e.counsellor, "counsellor_name": user_names.get(e.counsellor) or e.counsellor or "", "batch": e.batch_interested,
			"batch_name": batch_names.get(e.batch_interested) or e.batch_interested or "", "mode": e.preferred_mode, "source": e.source,
			"converted_on": e.converted_on, "lost_reason": e.lost_reason, "student": e.student,
			"followups_done": f["done"], "followups_open": f["open"], "last_followup_on": f["last_on"], "last_followup_notes": f["last_notes"],
			"next_followup_on": nxt, "next_followup": f["open_name"], "next_followup_notes": f["open_notes"], "due": due,
			"demo_attended": dm["attended"] > 0 or e.status == "Demo Attended", "demos": dm["scheduled"],
			"hot": e.status in OPEN and (dm["attended"] > 0 or e.status == "Demo Attended"),  # attended a demo, not yet admitted or lost
			"days_open": date_diff(today, e.enquiry_date) if e.status in OPEN and e.enquiry_date else None,
		})

	def bucket(key, label_of):
		out = {}
		for r in rows:
			k = r[key] or ""
			x = out.setdefault(k, {"key": k, "label": label_of(k), "total": 0, "open": 0, "demo": 0, "converted": 0, "lost": 0, "due_today": 0, "overdue": 0, "no_followup": 0})
			x["total"] += 1
			x["converted" if r["status"] == "Converted" else "lost" if r["status"] == "Lost" else "open"] += 1
			x["demo"] += 1 if r["hot"] else 0
			x["due_today"] += 1 if r["due"] == "today" else 0
			x["overdue"] += 1 if r["due"] == "overdue" else 0
			x["no_followup"] += 1 if r["status"] in OPEN and not r["followups_done"] and not r["followups_open"] else 0
		for x in out.values():
			x["rate"] = _rate(x["converted"], x["total"])
		return sorted(out.values(), key=lambda x: (-x["total"], x["label"]))

	status_counts = {k: sum(1 for r in rows if r["status"] == k) for k in ("New", "Demo Scheduled", "Demo Attended", "Converted", "Lost")}
	total = len(rows)
	converted = status_counts["Converted"]
	# enquiries over time: by day when the span is short, by month otherwise
	dates = [getdate(r["enquiry_date"]) for r in rows if r["enquiry_date"]]
	by_month = bool(dates) and date_diff(max(dates), min(dates)) > 62
	trend = {}
	for r in rows:
		if not r["enquiry_date"]:
			continue
		d = getdate(r["enquiry_date"])
		k = d.strftime("%Y-%m") if by_month else str(d)
		t = trend.setdefault(k, {"key": k, "total": 0, "converted": 0})
		t["total"] += 1
		t["converted"] += 1 if r["status"] == "Converted" else 0
	# fill the gaps so the chart has one bar per day (or month) over the whole span
	if dates:
		from frappe.utils import add_days, add_months
		lo, hi = min(dates), max(max(dates), today if not to_date else getdate(to_date))
		if by_month:
			k, end = lo.replace(day=1), hi.replace(day=1)
			while k <= end:
				trend.setdefault(k.strftime("%Y-%m"), {"key": k.strftime("%Y-%m"), "total": 0, "converted": 0})
				k = add_months(k, 1)
		else:
			k = lo
			while k <= hi:
				trend.setdefault(str(k), {"key": str(k), "total": 0, "converted": 0})
				k = add_days(k, 1)
	lost_reasons = {}
	for r in rows:
		if r["status"] == "Lost":
			lost_reasons[r["lost_reason"] or _("(no reason)")] = lost_reasons.get(r["lost_reason"] or _("(no reason)"), 0) + 1
	b = frappe.db.get_value("Student Batch", batch, ["batch_name", "mode", "status", "seats"], as_dict=True) if batch else None
	enrolled = frappe.db.count("Student Batch Enrollment", {"batch": batch, "docstatus": 1, "status": ["in", ["Active", "On Hold"]]}) if b else None
	from tnc_v2_360ithub.branding import institute_logo
	return {
		"logo": institute_logo(), "manager": manager, "batch": dict(b, name=batch) if b else None, "counsellor": counsellor, "counsellor_name": user_names.get(counsellor) or (frappe.db.get_value("User", counsellor, "full_name") if counsellor else None),
		"from_date": from_date or None, "to_date": to_date or None, "enrolled": enrolled,
		"total": total, "converted": converted, "lost": status_counts["Lost"], "open": total - converted - status_counts["Lost"],
		"demo_attended": sum(1 for r in rows if r["hot"]), "rate": _rate(converted, total),
		"open_new": sum(1 for r in rows if r["status"] in OPEN and not r["hot"] and r["status"] != "Demo Scheduled"), "open_scheduled": sum(1 for r in rows if r["status"] == "Demo Scheduled" and not r["hot"]),
		"due_today": sum(1 for r in rows if r["due"] == "today"), "overdue": sum(1 for r in rows if r["due"] == "overdue"),
		"upcoming": sum(1 for r in rows if r["due"] == "upcoming"),
		"no_followup": sum(1 for r in rows if r["status"] in OPEN and not r["followups_done"] and not r["followups_open"]),
		"followups_done": sum(r["followups_done"] for r in rows),
		"done_list": [{"name": f.name, "enquiry": f.reference_name, "student_name": enq_of.get(f.reference_name, {}).get("student_name"), "mobile": enq_of.get(f.reference_name, {}).get("mobile"),
			"purpose": f.purpose, "followup_type": f.followup_type, "follow_up_date": f.follow_up_date, "notes": f.notes, "done_by": user_names.get(f.assigned_to) or f.assigned_to or ""}
			for f in sorted((f for f in fups if f.status == "Closed"), key=lambda f: str(f.follow_up_date or ""), reverse=True)],
		"status_counts": status_counts, "trend": sorted(trend.values(), key=lambda t: t["key"]), "trend_by_month": by_month,
		"by_batch": bucket("batch", lambda k: batch_names.get(k) or k or _("(no batch)")),
		"by_counsellor": bucket("counsellor", lambda k: user_names.get(k) or k or _("(no counsellor)")),
		"by_source": bucket("source", lambda k: k or _("(no source)")),
		"lost_reasons": sorted(({"reason": k, "count": v} for k, v in lost_reasons.items()), key=lambda x: -x["count"]),
		"enquiries": rows,
	}


@frappe.whitelist()
def log_call(enquiry, notes, followup_type="Call", next_date=None, planned=0):
	"""Record a follow-up on an open enquiry, straight from the Enquiry Overview.
	Default: a call made now: one Closed follow-up with what was said, and an Open one for the
	next date when given. `planned`: no call yet, only an Open follow-up for `next_date` with
	what to do; an already pending one is re-dated instead of closed."""
	enq = frappe.get_doc("Student Enquiry", enquiry)
	enq.check_permission("write")
	if not (notes or "").strip():
		frappe.throw(_("Write what to discuss.") if cint(planned) else _("Write what was said."))
	assignee = enq.counsellor or frappe.session.user
	# an open follow-up on this enquiry is the call being made: close it with the outcome
	pending = frappe.get_all("Student Follow-Up", filters={"reference_type": "Student Enquiry", "reference_name": enquiry, "status": "Open", "purpose": ["!=", "Fee"]},
		order_by="next_follow_up_date asc, creation asc", limit=1, pluck="name")
	if cint(planned):
		if not next_date:
			frappe.throw(_("Choose the follow-up date."))
		if pending:
			f = frappe.get_doc("Student Follow-Up", pending[0])
			f.update({"next_follow_up_date": getdate(next_date), "notes": notes.strip(), "followup_type": followup_type})
			f.save()
			return {"done": None, "next": f.name, "updated": True}
		nxt = frappe.get_doc({"doctype": "Student Follow-Up", "reference_type": "Student Enquiry", "reference_name": enquiry, "purpose": "Enquiry",
			"follow_up_date": nowdate(), "next_follow_up_date": next_date, "followup_type": followup_type, "notes": notes.strip(), "assigned_to": assignee, "status": "Open"}).insert()
		return {"done": None, "next": nxt.name}
	if pending:
		from tnc_v2_360ithub.admissions.followups import log_outcome
		r = log_outcome(pending[0], notes.strip(), next_follow_up_date=next_date or None, followup_type=followup_type, close=1)
		return {"done": r["closed"], "next": r["next"]}
	done = frappe.get_doc({"doctype": "Student Follow-Up", "reference_type": "Student Enquiry", "reference_name": enquiry, "purpose": "Enquiry",
		"follow_up_date": nowdate(), "followup_type": followup_type, "notes": notes.strip(), "done_by": frappe.session.user, "assigned_to": assignee, "status": "Closed"}).insert()
	nxt = None
	if next_date:
		nxt = frappe.get_doc({"doctype": "Student Follow-Up", "reference_type": "Student Enquiry", "reference_name": enquiry, "purpose": "Enquiry",
			"follow_up_date": nowdate(), "next_follow_up_date": next_date, "followup_type": followup_type, "notes": notes.strip(), "assigned_to": assignee, "status": "Open"}).insert()
	return {"done": done.name, "next": nxt.name if nxt else None}

