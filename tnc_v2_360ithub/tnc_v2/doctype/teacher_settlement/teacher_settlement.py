# Copyright (c) 2026, 360ITHub and contributors
"""Weekly Teacher Settlement (SOW): week = Saturday to Friday, generated on Saturday.

closing = opening + approved timesheets − penalties approved + waived + refunded − paid (cash, incl. refunds).
A refund therefore nets to zero on the balance but both sides of it are visible.
Everything is read from the records that already exist (timesheets, penalties, payment entries),
so a week can be regenerated any time and always shows the current truth.
"""
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, flt, getdate, now_datetime, today


class TeacherSettlement(Document):
	pass


def week_bounds(on=None):
	"""(saturday, friday) of the week that contains `on` (default: the week that ended most recently)."""
	d = getdate(on or today())
	# weekday(): Mon=0 ... Sat=5, Sun=6 -> days since last Saturday
	back = (d.weekday() - 5) % 7
	start = add_days(d, -back)
	return start, add_days(start, 6)


def _lines_for(teacher, supplier, start, end):
	since = frappe.db.get_single_value("TNC Settings", "settlement_start_date")
	if since and getdate(since) > getdate(start):
		start = getdate(since)
	lines, ts_total, pen_total, pay_total, adj_total, ref_total = [], 0, 0, 0, 0, 0
	if getdate(start) > getdate(end):
		return lines, 0, 0, 0, 0, 0
	for r in frappe.get_all("Teachers Timesheet", filters={"teacher_id": teacher, "status": "Approved", "date": ["between", [start, end]]},
			fields=["name", "date", "grand_total"], order_by="date asc"):
		lines.append({"line_date": r.date, "line_type": "Timesheet", "reference_doctype": "Teachers Timesheet", "reference_name": r.name, "description": _("Approved timesheet"), "amount": flt(r.grand_total)})
		ts_total += flt(r.grand_total)
	for r in frappe.get_all("Teacher Penalty", filters={"teacher": teacher, "docstatus": 1, "status": ["in", ["Approved", "Recovered", "Waived", "Refunded"]], "decided_on": ["between", [f"{start} 00:00:00", f"{end} 23:59:59"]]},
			fields=["name", "decided_on", "penalty_type", "amount"], order_by="decided_on asc"):
		lines.append({"line_date": getdate(r.decided_on), "line_type": "Penalty", "reference_doctype": "Teacher Penalty", "reference_name": r.name, "description": r.penalty_type, "amount": -flt(r.amount)})
		pen_total += flt(r.amount)
	if supplier:
		for r in frappe.get_all("Payment Entry", filters={"party_type": "Supplier", "party": supplier, "payment_type": "Pay", "docstatus": 1, "posting_date": ["between", [start, end]]},
				fields=["name", "posting_date", "paid_amount", "custom_penalty_deduction"], order_by="posting_date asc"):
			desc = _("Payment") + (_(" (after ₹{0} penalty deducted)").format(flt(r.custom_penalty_deduction)) if flt(r.custom_penalty_deduction) else "")
			lines.append({"line_date": r.posting_date, "line_type": "Payment", "reference_doctype": "Payment Entry", "reference_name": r.name, "description": desc, "amount": -flt(r.paid_amount)})
			pay_total += flt(r.paid_amount)
	for r in frappe.db.sql("""select rec.entry_date, rec.entry_type, rec.amount, rec.parent, rec.reference_doctype, rec.reference_name, rec.remarks
			from `tabTeacher Penalty Recovery` rec join `tabTeacher Penalty` p on p.name = rec.parent
			where p.teacher = %s and rec.entry_type in ('Waiver', 'Refund') and rec.entry_date between %s and %s order by rec.entry_date""", (teacher, start, end), as_dict=True):
		if r.entry_type == "Waiver":
			lines.append({"line_date": r.entry_date, "line_type": "Waiver", "reference_doctype": "Teacher Penalty", "reference_name": r.parent, "description": _("Waived: {0}").format(r.remarks or ""), "amount": flt(r.amount)})
			adj_total += flt(r.amount)
		else:  # refund: the penalty is undone (+) and the cash goes out (-), shown as two lines
			lines.append({"line_date": r.entry_date, "line_type": "Refund", "reference_doctype": "Teacher Penalty", "reference_name": r.parent, "description": _("Penalty refunded: {0}").format(r.remarks or ""), "amount": flt(r.amount)})
			lines.append({"line_date": r.entry_date, "line_type": "Payment", "reference_doctype": r.reference_doctype or "Teacher Penalty", "reference_name": r.reference_name or r.parent, "description": _("Refund paid"), "amount": -flt(r.amount)})
			ref_total += flt(r.amount); pay_total += flt(r.amount)
	lines.sort(key=lambda x: (str(x["line_date"]), x["line_type"]))
	return lines, ts_total, pen_total, pay_total, adj_total, ref_total


def _opening(teacher, supplier, start):
	"""Closing of the previous week's settlement when it exists; else computed from all history before `start`."""
	prev = frappe.db.get_value("Teacher Settlement", {"teacher": teacher, "week_end": add_days(start, -1)}, "closing_balance")
	if prev is not None:
		return flt(prev)
	since = frappe.db.get_single_value("TNC Settings", "settlement_start_date") or "1900-01-01"
	if getdate(since) >= getdate(start):
		return 0
	_l, ts, pen, pay, adj, ref = _lines_for(teacher, supplier, since, add_days(start, -1))
	return ts - pen + adj + ref - pay


def generate(teacher, on=None):
	"""Create or refresh the settlement of the week containing `on` for one teacher. Returns the doc."""
	start, end = week_bounds(on)
	supplier = frappe.db.get_value("Teacher", teacher, "supplier_id")
	lines, ts, pen, pay, adj, ref = _lines_for(teacher, supplier, start, end)
	opening = _opening(teacher, supplier, start)
	name = frappe.db.get_value("Teacher Settlement", {"teacher": teacher, "week_start": start}, "name")
	doc = frappe.get_doc("Teacher Settlement", name) if name else frappe.new_doc("Teacher Settlement")
	doc.update({"teacher": teacher, "week_start": start, "week_end": end, "opening_balance": opening, "approved_payable": ts, "penalties": pen,
		"payments": pay, "adjustments": adj, "refunds": ref, "closing_balance": opening + ts - pen + adj + ref - pay})
	doc.set("lines", [])
	for l in lines:
		doc.append("lines", l)
	doc.flags.ignore_permissions = True
	doc.save()
	return doc


def generate_all(on=None):
	"""Saturday job: every active teacher who had anything this week or still has a balance."""
	made = []
	for t in frappe.get_all("Teacher", filters={"status": "Active"}, pluck="name"):
		doc = generate(t, on)
		if doc.lines or flt(doc.opening_balance) or flt(doc.closing_balance):
			made.append(doc.name)
		else:
			frappe.delete_doc("Teacher Settlement", doc.name, force=1, ignore_permissions=True)
	frappe.db.commit()
	return made


def report_card_text(doc):
	"""Short plus/minus list a teacher can read in ten seconds (penalties shown net)."""
	from tnc_v2_360ithub.teachers.teacher_documents import statement_text
	return statement_text(doc)


def send_report_cards(on=None):
	"""Saturday job, second half: WhatsApp each generated settlement to the teacher's mobile."""
	if not frappe.db.get_single_value("TNC Settings", "send_weekly_report_card"):
		return []
	from tnc_v2_360ithub import notifications
	start, _e = week_bounds(on)
	sent = []
	for name in frappe.get_all("Teacher Settlement", filters={"week_start": start}, pluck="name"):
		doc = frappe.get_doc("Teacher Settlement", name)
		mobile = frappe.db.get_value("Teacher", doc.teacher, "mobile_no")
		if not mobile:
			doc.db_set({"sent_status": "No mobile on Teacher"}); continue
		r = _send(doc, mobile)
		ok = bool(r.get("status")) if isinstance(r, dict) else bool(r)
		doc.db_set({"sent_on": now_datetime(), "sent_status": "Sent" if ok else f"Failed: {(r.get('msg') or r.get('error') or '') if isinstance(r, dict) else ''}", "status": "Sent" if ok else doc.status})
		sent.append(doc.name)
	frappe.db.commit()
	return sent


def _send(doc, mobile):
	"""The statement PDF with the short summary as its caption."""
	from tnc_v2_360ithub.teachers.teacher_documents import STATEMENT_FORMAT, send_document
	return send_document(mobile, report_card_text(doc), "Teacher Settlement", doc.name, STATEMENT_FORMAT)


def weekly_job():
	"""Every Saturday morning: settle last week (Sat..Fri that just ended) and send the cards."""
	on = add_days(today(), -1)  # yesterday = Friday, the week that just closed
	generate_all(on)
	send_report_cards(on)


@frappe.whitelist()
def generate_now(on=None, teacher=None):
	"""Desk button: (re)generate this week, for one teacher or everyone."""
	if not ({"System Manager", "TNC Super Admin", "TNC Manager"} & set(frappe.get_roles())):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if teacher:
		return [generate(teacher, on).name]
	return generate_all(on)


@frappe.whitelist()
def send_now(name):
	if not ({"System Manager", "TNC Super Admin", "TNC Manager"} & set(frappe.get_roles())):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	from tnc_v2_360ithub import notifications
	doc = frappe.get_doc("Teacher Settlement", name)
	mobile = frappe.db.get_value("Teacher", doc.teacher, "mobile_no")
	if not mobile:
		frappe.throw(_("No mobile number on the Teacher record."))
	r = _send(doc, mobile)
	ok = bool(r.get("status")) if isinstance(r, dict) else bool(r)
	doc.db_set({"sent_on": now_datetime(), "sent_status": "Sent" if ok else "Failed", "status": "Sent" if ok else doc.status})
	return {"status": "Sent" if ok else "Failed", "message": report_card_text(doc)}
