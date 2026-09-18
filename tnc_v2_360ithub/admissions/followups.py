# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Follow-ups: fee reminders created by the daily job, the pending queue for the
Follow-ups page, and calendar events (SOW 1 and 3: pending follow-ups, automatic
instalment follow-up, payment follow-up calendar)."""
import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, nowdate

LEAD_DAYS = 3  # create the "Upcoming" fee follow-up this many days before the due date


def _counsellor_for(student):
	return frappe.db.get_value("Student", student, "counsellor") or frappe.db.get_value("Student Enquiry", frappe.db.get_value("Student", student, "enquiry") or "", "counsellor") or "Administrator"


def create_fee_followups(today=None):
	"""Daily. For every unpaid instalment of a submitted enrolment order:
	- due within LEAD_DAYS (or today): one 'Upcoming' fee follow-up dated the due date
	- past due and still unpaid: one 'Overdue' fee follow-up dated today
	Never two open ones of the same kind for the same instalment. Paid instalments
	close their follow-ups."""
	today = getdate(today or nowdate())
	created = closed = 0
	rows = frappe.db.sql("""
		select so.name as sales_order, so.custom_student as student, so.custom_student_batch as student_batch, ps.payment_term, ps.due_date, ps.payment_amount, ps.paid_amount, ps.outstanding
		from `tabSales Order` so join `tabPayment Schedule` ps on ps.parent = so.name and ps.parenttype = 'Sales Order'
		where so.docstatus = 1 and so.status not in ('Closed', 'Completed') and ifnull(so.custom_student, '') != ''""", as_dict=True)
	for r in rows:
		out = flt(r.outstanding) if r.outstanding is not None else flt(r.payment_amount) - flt(r.paid_amount)
		open_ones = frappe.get_all("Student Follow-Up", filters={"purpose": "Fee", "sales_order": r.sales_order, "payment_term": r.payment_term, "status": "Open"}, fields=["name", "fee_kind"])
		if out <= 0.5:
			for f in open_ones:
				frappe.db.set_value("Student Follow-Up", f.name, "status", "Closed", update_modified=False); closed += 1
			continue
		due = getdate(r.due_date)
		kind = "Overdue" if due < today else ("Upcoming" if (due - today).days <= LEAD_DAYS else None)
		if not kind or any(f.fee_kind == kind for f in open_ones):
			continue
		if kind == "Overdue":  # the Upcoming one is superseded
			for f in open_ones:
				frappe.db.set_value("Student Follow-Up", f.name, "status", "Closed", update_modified=False); closed += 1
		frappe.get_doc({"doctype": "Student Follow-Up", "reference_type": "Student", "reference_name": r.student, "purpose": "Fee", "fee_kind": kind,
			"sales_order": r.sales_order, "payment_term": r.payment_term, "instalment_due_date": r.due_date, "amount_pending": out,
			"follow_up_date": today, "next_follow_up_date": (today if kind == "Overdue" else due), "followup_type": "Call", "status": "Open",
			"assigned_to": _counsellor_for(r.student), "done_by": "Administrator",
			"notes": _("{0}: {1} of {2} due {3} on {4}").format(kind, frappe.format_value(out, {"fieldtype": "Currency"}), r.payment_term or "", frappe.format_value(r.due_date, {"fieldtype": "Date"}), r.student_batch or r.sales_order)}).insert(ignore_permissions=True)
		created += 1
	if not frappe.flags.in_test:
		frappe.db.commit()
	return {"created": created, "closed": closed}


FORM_WAIT_DAYS = 3  # after admission, chase the admission form from this many days


def create_form_followups(today=None):
	"""Daily. An Active student whose admission form has not come back FORM_WAIT_DAYS after
	admission gets one General follow-up for the counsellor. Never twice; closes when the form arrives."""
	today = getdate(today or nowdate())
	created = closed = 0
	for st in frappe.get_all("Student", filters={"status": "Active", "terms_accepted": 0, "creation": ["<=", add_days(today, -FORM_WAIT_DAYS)]},
			fields=["name", "student_name", "mobile", "counsellor", "enquiry"]):
		if frappe.db.exists("Student Follow-Up", {"reference_type": "Student", "reference_name": st.name, "purpose": "General", "status": "Open", "notes": ["like", "Admission form not submitted%"]}):
			continue
		frappe.get_doc({"doctype": "Student Follow-Up", "reference_type": "Student", "reference_name": st.name, "purpose": "General",
			"student_name": st.student_name, "mobile": st.mobile, "follow_up_date": today, "next_follow_up_date": today, "followup_type": "Call", "status": "Open",
			"assigned_to": st.counsellor, "notes": _("Admission form not submitted. Student has not filled the form sent on WhatsApp, details are missing. Ask them to fill it, or send it again from enquiry {0}.").format(st.enquiry or "")}).insert(ignore_permissions=True)
		created += 1
	# form arrived: close the chase
	for f in frappe.get_all("Student Follow-Up", filters={"reference_type": "Student", "purpose": "General", "status": "Open", "notes": ["like", "Admission form not submitted%"]}, fields=["name", "reference_name"]):
		if frappe.db.get_value("Student", f.reference_name, "terms_accepted"):
			frappe.db.set_value("Student Follow-Up", f.name, "status", "Closed", update_modified=False); closed += 1
	if not frappe.flags.in_test:
		frappe.db.commit()
	return {"created": created, "closed": closed}


def close_paid_followups(sales_order):
	"""After a receipt: close fee follow-ups whose instalment is now settled."""
	for ps in frappe.get_all("Payment Schedule", filters={"parent": sales_order, "parenttype": "Sales Order"}, fields=["payment_term", "outstanding", "payment_amount", "paid_amount"]):
		out = flt(ps.outstanding) if ps.outstanding is not None else flt(ps.payment_amount) - flt(ps.paid_amount)
		if out <= 0.5:
			for name in frappe.get_all("Student Follow-Up", filters={"purpose": "Fee", "sales_order": sales_order, "payment_term": ps.payment_term, "status": "Open"}, pluck="name"):
				frappe.db.set_value("Student Follow-Up", name, "status", "Closed", update_modified=False)
		else:
			frappe.db.sql("update `tabStudent Follow-Up` set amount_pending=%s where purpose='Fee' and sales_order=%s and payment_term=%s and status='Open'", (out, sales_order, ps.payment_term))


@frappe.whitelist()
def get_pending(scope="mine", user=None, purpose=None, reference_type=None, reference_name=None):
	"""Rows for the Follow-ups page, bucketed Overdue / Today / Upcoming."""
	today = getdate(nowdate())
	filters = {"status": "Open"}
	if reference_type and reference_name:
		filters.update({"reference_type": reference_type, "reference_name": reference_name})
		scope = "all"  # one person's follow-ups: whoever they are assigned to
	manager = bool({"TNC Manager", "TNC Super Admin", "System Manager"} & set(frappe.get_roles()))
	if not manager:
		scope, user = "mine", None  # counsellors see their own queue whatever the request says
	if scope == "mine" or (user and scope == "user"):
		filters["assigned_to"] = user or frappe.session.user
	if purpose:
		filters["purpose"] = purpose
	rows = frappe.get_all("Student Follow-Up", filters=filters, order_by="next_follow_up_date asc, modified desc",
		fields=["name", "reference_type", "reference_name", "student_name", "mobile", "purpose", "fee_kind", "notes", "followup_type", "next_follow_up_date",
			"sales_order", "payment_term", "instalment_due_date", "amount_pending", "assigned_to", "follow_up_date"], limit=500)
	out = {"overdue": [], "today": [], "upcoming": [], "no_date": []}
	for r in rows:
		if not r.next_follow_up_date:
			out["no_date"].append(r); continue
		d = getdate(r.next_follow_up_date)
		(out["overdue"] if d < today else out["today"] if d == today else out["upcoming"]).append(r)
	return out


@frappe.whitelist()
def log_outcome(name, notes, next_follow_up_date=None, followup_type="Call", close=1, lost=0, lost_reason=None):
	"""Close this follow-up with what was said; open the next one if a date is given."""
	f = frappe.get_doc("Student Follow-Up", name)
	f.check_permission("write")
	f.notes = (f.notes or "") + ("\n" if f.notes else "") + _("Outcome: {0}").format(notes)
	f.done_by = frappe.session.user
	if int(close):
		f.status = "Closed"
	f.save()
	nxt = None
	if next_follow_up_date:
		nxt = frappe.get_doc({"doctype": "Student Follow-Up", "reference_type": f.reference_type, "reference_name": f.reference_name, "purpose": f.purpose,
			"fee_kind": f.fee_kind, "sales_order": f.sales_order, "payment_term": f.payment_term, "instalment_due_date": f.instalment_due_date, "amount_pending": f.amount_pending,
			"follow_up_date": nowdate(), "next_follow_up_date": next_follow_up_date, "followup_type": followup_type, "notes": notes, "assigned_to": f.assigned_to, "status": "Open"}).insert()
	if int(lost) and f.reference_type == "Student Enquiry":
		from tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry import mark_lost
		mark_lost(f.reference_name, lost_reason or "No response", notes)
	return {"closed": f.name, "next": nxt.name if nxt else None}


@frappe.whitelist()
def get_calendar_events(start, end, filters=None):
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	conds = {"next_follow_up_date": ["between", [start, end]]}
	for f in filters or []:
		if isinstance(f, (list, tuple)) and len(f) >= 4 and f[3]:
			conds[f[1]] = f[3]
		elif isinstance(f, dict) and f.get("value"):
			conds[f["fieldname"]] = f["value"]
	rows = frappe.get_all("Student Follow-Up", filters=conds, fields=["name", "student_name", "purpose", "status", "next_follow_up_date", "amount_pending"])
	return [{"name": r.name, "title": f"{r.student_name} · {r.purpose}" + (f" ₹{flt(r.amount_pending):,.0f}" if r.purpose == "Fee" else "") + (" ✓" if r.status == "Closed" else ""),
		"start": r.next_follow_up_date, "end": r.next_follow_up_date, "allDay": 1, "color": "#16a34a" if r.status == "Closed" else ("#dc2626" if r.purpose == "Fee" else "#2563eb")} for r in rows]


@frappe.whitelist()
def count_overdue_followups():
	"""Custom Number Card: open follow-ups whose next date is before today."""
	n = frappe.db.count("Student Follow-Up", {"status": "Open", "next_follow_up_date": ["<", nowdate()]})
	return {"value": n, "fieldtype": "Int", "route": ["follow-ups"], "route_options": {}}


@frappe.whitelist()
def get_reference_followups(reference_type, reference_name):
	"""Follow-ups tab on Student / Enquiry: open first (by next date), then closed (latest first)."""
	from tnc_v2_360ithub.admissions.api import STYLE, _badge, _money
	from frappe.utils import formatdate
	from frappe.utils.html_utils import escape_html as e

	frappe.get_doc(reference_type, reference_name).check_permission("read")
	rows = frappe.get_all("Student Follow-Up", filters={"reference_type": reference_type, "reference_name": reference_name},
		fields=["name", "purpose", "fee_kind", "status", "follow_up_date", "next_follow_up_date", "followup_type", "notes", "assigned_to", "done_by", "payment_term", "amount_pending", "sales_order"],
		order_by="status desc, next_follow_up_date asc, follow_up_date desc", limit=200)
	today = getdate(nowdate())
	def state(r):
		if r.status == "Closed": return _badge(_("Closed"), "gray")
		if r.next_follow_up_date and getdate(r.next_follow_up_date) < today: return _badge(_("Overdue"), "red")
		if r.next_follow_up_date and getdate(r.next_follow_up_date) == today: return _badge(_("Today"), "orange")
		return _badge(_("Open"), "blue")
	kinds = {"Fee": "red", "Enquiry": "blue", "Demo": "orange", "General": "gray"}
	trs = ""
	for r in rows:
		fee = f"<div class='small text-muted'>{e(r.payment_term or '')} · {_money(r.amount_pending)}</div>" if r.purpose == "Fee" else ""
		trs += (f"<tr><td>{state(r)}</td><td>{_badge(r.purpose, kinds.get(r.purpose, 'gray'))}{fee}</td><td>{e(formatdate(r.follow_up_date))}</td>"
			f"<td>{e(r.followup_type or '')}</td><td style='max-width:420px;white-space:pre-wrap'>{e((r.notes or '')[-300:])}</td>"
			f"<td>{e(formatdate(r.next_follow_up_date)) if r.next_follow_up_date else ''}</td><td class='small'>{e(r.assigned_to or '')}</td>"
			f"<td><a class='btn btn-xs btn-default' href='/app/student-follow-up/{e(r.name)}'>{_('Open')}</a></td></tr>")
	open_n = sum(1 for r in rows if r.status == "Open")
	plan = ""
	if reference_type == "Student":
		nxt = frappe.db.sql("""select ps.payment_term, ps.due_date, (ps.payment_amount - ifnull(ps.paid_amount, 0)) pending
			from `tabPayment Schedule` ps join `tabSales Order` so on so.name = ps.parent
			where so.custom_student = %s and so.docstatus = 1 and (ps.payment_amount - ifnull(ps.paid_amount, 0)) > 0.5
			order by ps.due_date limit 1""", reference_name, as_dict=True)
		if nxt:
			n = nxt[0]
			due = getdate(n.due_date)
			create_on = add_days(due, -LEAD_DAYS)
			has_open = any(r.status == "Open" and r.purpose == "Fee" and r.payment_term == n.payment_term for r in rows)
			if has_open:
				when = _("reminder follow-up already created, see above")
			elif due < today:
				when = _("overdue since {0}").format(formatdate(due))
			elif create_on <= today:
				when = _("the system will create a reminder follow-up automatically at 7 AM tomorrow")
			else:
				when = _("the system will create a reminder follow-up automatically on {0} at 7 AM, {1} days before the due date").format(formatdate(create_on), LEAD_DAYS)
			plan = (f"<div class='tnc-sec' style='margin-top:8px;padding:10px 12px;border:1px solid #dbeafe;border-radius:8px;background:#f8fbff'>"
				f"<b>{_('Next fee reminder')}</b>: {e(n.payment_term or '')} · {_money(n.pending)} · {_('due')} {e(formatdate(due))} — {when}.</div>")
	html = STYLE + f"""<div class="tnc-ov">
	<div class="tnc-head"><div><div style="font-size:15px;font-weight:600">{_('Follow-ups')}</div><div class="text-muted">{open_n} {_('open')} · {len(rows) - open_n} {_('closed')}</div></div>
	  <div class="tnc-stats"><a class="btn btn-sm btn-primary" data-action="followups-page">{_('Open Follow-ups page')}</a></div></div>
	<div class="tnc-sec">{'<table class="tnc-table"><thead><tr><th>' + _('Status') + '</th><th>' + _('Purpose') + '</th><th>' + _('Date') + '</th><th>' + _('How') + '</th><th>' + _('Notes') + '</th><th>' + _('Next') + '</th><th>' + _('Assigned') + '</th><th></th></tr></thead><tbody>' + trs + '</tbody></table>' if rows else '<div class="tnc-empty">' + _('No follow-up yet.') + '</div>'}</div>{plan}</div>"""
	return {"html": html, "open": open_n}
