"""Admit: one action from the enquiry that does convert + enrol + first payment.

The pieces already exist and are tested on their own (convert_to_student, Student Batch
Enrollment.on_submit -> Sales Order, fees.receive_payment, send_admission_link). This only
calls them in order inside one transaction and returns the links for the result card.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from tnc_v2_360ithub.admissions.fees import BANK_MODES


@frappe.whitelist()
def preview(enquiry, batch=None):
	"""Numbers the dialog shows before anything is created."""
	enq = frappe.get_doc("Student Enquiry", enquiry)
	enq.check_permission("read")
	batch = batch or enq.batch_interested
	out = {"batch": batch, "student_name": enq.student_name, "mobile": enq.mobile, "counsellor": enq.counsellor}
	if batch:
		b = frappe.db.get_value("Student Batch", batch, ["standard_fee", "starting_date", "actual_ending_date", "course", "course_name", "mode"], as_dict=True)
		out.update({"standard_fee": flt(b.standard_fee), "batch_start": b.starting_date, "batch_end": b.actual_ending_date, "course_name": b.course_name, "mode": b.mode})
	from tnc_v2_360ithub.admissions.demo_fee import settings, summary_for_enquiry
	_amt, adjust = settings()
	out["demo_fee_paid"] = summary_for_enquiry(enquiry)["paid"] if adjust else 0
	out["form_received"] = bool(frappe.db.exists("Admission Form", {"enquiry": enquiry, "status": ["!=", "Rejected"]}))
	out["existing_student"] = enq.student
	from tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry import find_matches
	m = find_matches(enq.mobile)
	out["duplicate_students"] = [s for s in m["students"] if s.name != enq.student]
	return out


def _draft_enrolment(enquiry, batch, number_of_installments, installment_gap_days, first_due_date, discount_type, discount_value, discount_reason, gst_applicable, installments=None):
	"""An unsaved Student Batch Enrollment with the same rules the real one uses, so the page
	previews exactly what will be created (demo fee deduction, GST, schedule, batch window)."""
	enq = frappe.get_doc("Student Enquiry", enquiry)
	en = frappe.get_doc({"doctype": "Student Batch Enrollment", "student": enq.student or None, "batch": batch, "enrollment_date": nowdate(),
		"discount_type": discount_type or None, "discount_value": flt(discount_value), "discount_reason": discount_reason,
		"gst_applicable": cint(gst_applicable), "number_of_installments": max(cint(number_of_installments), 1),
		"installment_gap_days": cint(installment_gap_days) or 30, "first_due_date": first_due_date or nowdate()})
	if isinstance(installments, str):
		installments = frappe.parse_json(installments) if installments.strip() and installments.strip().lower() not in ("null", "none") else None
	if installments:
		for r in installments:
			en.append("installments", {"due_date": r.get("due_date"), "amount": flt(r.get("amount")), "description": r.get("description")})
	else:
		en.flags.regenerate = True
	return en, enq


@frappe.whitelist()
def plan(enquiry, batch, number_of_installments=1, installment_gap_days=30, first_due_date=None, discount_type=None, discount_value=0,
	discount_reason=None, gst_applicable=0, installments=None, paid_today=0):
	"""Live preview for the Admit page: amounts, schedule rows, GST, warnings. Creates nothing."""
	from tnc_v2_360ithub.admissions.demo_fee import settings, summary_for_enquiry
	from tnc_v2_360ithub.tnc_v2.doctype.student_batch_enrollment.student_batch_enrollment import DEFAULT_GST_TEMPLATE
	en, enq = _draft_enrolment(enquiry, batch, number_of_installments, installment_gap_days, first_due_date, discount_type, discount_value, discount_reason, gst_applicable, installments)
	en.set_batch_window()
	fee = flt(frappe.db.get_value("Student Batch", batch, "standard_fee"))
	en.standard_fee = fee
	# demo fee: the enquiry's paid demos (student may not exist yet)
	_amt, adjust = settings()
	demo = summary_for_enquiry(enquiry)["paid"] if adjust else 0
	disc = flt(fee * flt(discount_value) / 100, 2) if discount_type == "Percentage" else (flt(discount_value, 2) if discount_type == "Amount" else 0)
	warnings = []
	if disc + demo > fee:
		warnings.append({"kind": "error", "text": _("Discount plus demo fee adjustment exceeds the fee.")})
	net = flt(fee - disc - demo, 2)
	en.discount_amount = disc; en.demo_fee_adjusted = demo; en.net_payable = net
	if not en.installments or en.flags.regenerate:
		en.generate_installments()
	rows = []
	total = 0
	batch_end = getdate(en.batch_end) if en.batch_end else None
	for i, r in enumerate(en.installments, 1):
		beyond = bool(batch_end and r.due_date and getdate(r.due_date) > batch_end)
		rows.append({"installment_no": i, "due_date": str(r.due_date), "amount": flt(r.amount, 2), "description": r.description or _("Instalment {0}").format(i), "beyond_batch": beyond})
		total += flt(r.amount)
	if abs(flt(total, 2) - net) > 0.5:
		warnings.append({"kind": "error", "text": _("Instalments total {0} but net payable is {1}. Fix the amounts or regenerate.").format(frappe.format_value(total, {"fieldtype": "Currency"}), frappe.format_value(net, {"fieldtype": "Currency"}))})
	beyond_rows = [r for r in rows if r["beyond_batch"]]
	if beyond_rows:
		warnings.append({"kind": "warn", "text": _("{0} instalment(s) fall after the batch ends on {1}. Collect the fee within the batch unless this was agreed.").format(len(beyond_rows), frappe.format_value(batch_end, {"fieldtype": "Date"}))})
	gst = 0
	if cint(gst_applicable) and frappe.db.exists("Sales Taxes and Charges Template", DEFAULT_GST_TEMPLATE):
		rate = sum(flt(t.rate) for t in frappe.get_doc("Sales Taxes and Charges Template", DEFAULT_GST_TEMPLATE).taxes)
		gst = flt(net * rate / 100, 2)
	grand = flt(net + gst, 2)
	paid_today = flt(paid_today)
	if paid_today > grand + 0.5:
		warnings.append({"kind": "error", "text": _("Amount paid today is more than the total payable.")})
	return {"fee": fee, "discount": disc, "demo_fee": demo, "net": net, "gst": gst, "grand_total": grand, "rows": rows, "warnings": warnings,
		"batch_start": str(en.batch_start) if en.batch_start else None, "batch_end": str(en.batch_end) if en.batch_end else None,
		"paid_today": paid_today, "pending_after": flt(grand - paid_today, 2), "can_admit": not any(w["kind"] == "error" for w in warnings)}


@frappe.whitelist()
def admit(enquiry, batch, number_of_installments=1, installment_gap_days=30, first_due_date=None, discount_type=None, discount_value=0,
	discount_reason=None, gst_applicable=0, paid_today=0, mode_of_payment="Cash", reference_no=None, link_student=None, extra=None, send_form=1, confirm_beyond_batch=0, installments=None):
	"""Student + submitted enrolment + Sales Order + today's receipt + admission form link, in one go."""
	from tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry import convert_to_student, send_admission_link
	from tnc_v2_360ithub.admissions.fees import receive_payment
	enq = frappe.get_doc("Student Enquiry", enquiry)
	enq.check_permission("write")
	if enq.status == "Lost":
		frappe.throw(_("This enquiry is marked Lost. Reopen it first."))
	if not batch:
		frappe.throw(_("Please choose the batch."))
	paid_today = flt(paid_today, 2)
	if paid_today < 0:
		frappe.throw(_("Amount paid today cannot be negative."))
	if paid_today and mode_of_payment in BANK_MODES and not reference_no:
		frappe.throw(_("Reference number is required for {0}").format(mode_of_payment))
	if isinstance(extra, str):
		extra = frappe.parse_json(extra)

	# 1. the Student (reuses an existing one when the counsellor said so)
	student = convert_to_student(enquiry, extra=extra, link_student=link_student)

	# 2. the enrolment, generated instalments, submitted -> Sales Order
	en, _enq = _draft_enrolment(enquiry, batch, number_of_installments, installment_gap_days, first_due_date, discount_type, discount_value, discount_reason, gst_applicable, installments)
	en.student = student
	en.insert()
	beyond = [r for r in en.installments if en.batch_end and getdate(r.due_date) > getdate(en.batch_end)]
	if beyond and not cint(confirm_beyond_batch):
		frappe.throw(_("{0} instalment(s) fall after the batch ends on {1}. Tick 'I know, continue' to admit anyway.").format(len(beyond), frappe.format_value(en.batch_end, {"fieldtype": "Date"})), title=_("Instalments beyond batch end"))
	en.submit()
	en.reload()

	# 3. today's payment -> Payment Entry + receipt invoice
	receipt = None
	if paid_today > 0:
		receipt = receive_payment(en.sales_order, paid_today, mode_of_payment, reference_no)

	# 4. consent: send the admission form link if no form has come in yet
	form_sent = None
	if cint(send_form) and not frappe.db.exists("Admission Form", {"enquiry": enquiry, "status": ["!=", "Rejected"]}):
		try:
			form_sent = send_admission_link(enquiry)
		except Exception as e:
			form_sent = {"status": "Skipped", "reason": str(e)[:200]}

	so = frappe.db.get_value("Sales Order", en.sales_order, ["grand_total", "advance_paid"], as_dict=True)
	from tnc_v2_360ithub.admissions.fees import pending_on_order
	pending, paid = pending_on_order(frappe.get_doc("Sales Order", en.sales_order))
	next_due = next(((r.due_date, flt(r.amount)) for r in sorted(en.installments, key=lambda x: getdate(x.due_date)) if True), (None, 0))
	return {"student": student, "enrollment": en.name, "sales_order": en.sales_order, "receipt": receipt, "form_sent": form_sent,
		"net_payable": flt(en.net_payable), "demo_fee_adjusted": flt(en.demo_fee_adjusted), "paid": paid, "pending": pending, "grand_total": flt(so.grand_total)}
