"""Demo fee (client meeting 14 Sep 2026): a per-demo charge, default Rs 500 from TNC Settings.

Collected at the demo: a Sales Invoice on the 'Demo Fee' item plus a Payment Entry, so the money is
income at once and a receipt can be printed. On enrolment the paid demo fees of that enquiry are
deducted from the payable (Student Batch Enrollment.demo_fee_adjusted); the demos turn Adjusted.
If the student does not join, nothing more happens: the fee stays income. Refund makes a credit
note and a payment out.
"""

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from tnc_v2_360ithub.admissions.fees import BANK_MODES
from tnc_v2_360ithub.admissions.setup import CUSTOMER_GROUP, DEMO_FEE_ITEM, ensure_customer_group, ensure_demo_fee_item


def settings():
	s = frappe.get_cached_doc("TNC Settings")
	return flt(s.get("demo_fee_amount")), bool(s.get("demo_fee_adjust"))


def ensure_enquiry_customer(enq):
	"""The enquiry's Customer, created on first payment; Convert to Student reuses it."""
	if enq.customer and frappe.db.exists("Customer", enq.customer):
		return enq.customer
	if enq.student:
		c = frappe.db.get_value("Student", enq.student, "customer")
		if c:
			enq.db_set("customer", c, update_modified=False)
			return c
	ensure_customer_group()
	customer = frappe.get_doc({"doctype": "Customer", "customer_name": enq.student_name or enq.mobile, "customer_type": "Individual", "customer_group": CUSTOMER_GROUP,
		"territory": "India" if frappe.db.exists("Territory", "India") else "All Territories", "mobile_no": enq.mobile, "email_id": enq.email})
	customer.flags.ignore_permissions = True
	customer.insert()
	enq.db_set("customer", customer.name, update_modified=False)
	return customer.name


@frappe.whitelist()
def collect(demo, amount=None, mode_of_payment="Cash", reference_no=None, posting_date=None):
	"""Take the demo fee: receipt invoice + payment, stamped on the Demo Class."""
	doc = frappe.get_doc("Demo Class", demo)
	doc.check_permission("write")
	if doc.demo_fee_status and doc.demo_fee_status != "Not Collected":
		frappe.throw(_("Demo fee for {0} is already {1}.").format(demo, doc.demo_fee_status))
	default_amount, _adj = settings()
	amount = flt(amount if amount not in (None, "") else default_amount, 2)
	if amount <= 0:
		frappe.throw(_("Demo fee amount must be more than zero. Set it in TNC Settings."))
	if mode_of_payment in BANK_MODES and not reference_no:
		frappe.throw(_("Reference number is required for {0}").format(mode_of_payment))
	enq = frappe.get_doc("Student Enquiry", doc.enquiry)
	customer = ensure_enquiry_customer(enq)
	company = frappe.defaults.get_global_default("company") or frappe.db.get_single_value("Global Defaults", "default_company")
	item = ensure_demo_fee_item(company)
	posting_date = posting_date or nowdate()
	si = frappe.get_doc({"doctype": "Sales Invoice", "customer": customer, "company": company, "posting_date": posting_date, "set_posting_time": 1, "due_date": posting_date,
		"custom_student": enq.student, "remarks": _("Demo fee for demo class {0} on {1}").format(doc.name, frappe.format_value(doc.demo_date, {"fieldtype": "Date"})),
		"items": [{"item_code": item, "item_name": _("Demo Fee"), "description": _("Demo class fee — {0}, {1}").format(doc.batch or "", frappe.format_value(doc.demo_date, {"fieldtype": "Date"})), "qty": 1, "rate": amount, "uom": "Nos"}]})
	si.flags.ignore_permissions = True
	si.run_method("set_missing_values"); si.run_method("calculate_taxes_and_totals")
	si.insert(); si.submit()
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
	pe = get_payment_entry("Sales Invoice", si.name, party_amount=si.grand_total)
	pe.mode_of_payment = mode_of_payment
	account = frappe.db.get_value("Mode of Payment Account", {"parent": mode_of_payment, "company": company}, "default_account")
	if not account:
		frappe.throw(_("Mode of Payment {0} has no account for {1}. Set it in Mode of Payment.").format(mode_of_payment, company))
	pe.paid_to = account; pe.posting_date = posting_date
	pe.reference_no = reference_no or f"{mode_of_payment} {posting_date}"; pe.reference_date = posting_date
	pe.remarks = _("Demo fee for {0}").format(doc.name)
	pe.flags.ignore_permissions = True
	pe.setup_party_account_field(); pe.set_missing_values()
	pe.insert(); pe.submit()
	doc.db_set({"demo_fee_status": "Paid", "demo_fee_amount": amount, "demo_fee_paid_on": posting_date, "demo_fee_mode": mode_of_payment, "demo_fee_invoice": si.name, "demo_fee_payment": pe.name})
	doc.add_comment("Info", _("Demo fee {0} received by {1}, receipt {2}").format(frappe.format_value(amount, {"fieldtype": "Currency"}), mode_of_payment, si.name))
	enq.add_comment("Info", _("Demo fee {0} received for {1}").format(frappe.format_value(amount, {"fieldtype": "Currency"}), doc.name))
	return {"invoice": si.name, "payment_entry": pe.name, "amount": amount}


def paid_for_student(student):
	"""Demo fees still 'Paid' (not yet adjusted) for the enquiry behind this student."""
	enq = frappe.db.get_value("Student", student, "enquiry")
	if not enq:
		return []
	return frappe.get_all("Demo Class", filters={"enquiry": enq, "demo_fee_status": "Paid"}, fields=["name", "demo_fee_amount"])


def adjustable_for_student(student):
	_amt, adjust = settings()
	if not adjust:
		return 0, []
	rows = paid_for_student(student)
	return flt(sum(flt(r.demo_fee_amount) for r in rows), 2), rows


def mark_adjusted(enrollment):
	for r in paid_for_student(enrollment.student):
		frappe.db.set_value("Demo Class", r.name, {"demo_fee_status": "Adjusted", "demo_fee_adjusted_in": enrollment.name}, update_modified=False)


def unmark_adjusted(enrollment):
	for name in frappe.get_all("Demo Class", filters={"demo_fee_adjusted_in": enrollment.name}, pluck="name"):
		frappe.db.set_value("Demo Class", name, {"demo_fee_status": "Paid", "demo_fee_adjusted_in": None}, update_modified=False)


@frappe.whitelist()
def refund(demo, mode_of_payment="Cash", reference_no=None, mark_lost=0, lost_reason=None, lost_note=None):
	"""Give the demo fee back: credit note against the receipt and a payment out."""
	doc = frappe.get_doc("Demo Class", demo)
	doc.check_permission("write")
	if doc.demo_fee_status != "Paid":
		frappe.throw(_("Only a Paid demo fee can be refunded (this one is {0}).").format(doc.demo_fee_status))
	from erpnext.controllers.sales_and_purchase_return import make_return_doc
	cn = make_return_doc("Sales Invoice", doc.demo_fee_invoice)
	cn.flags.ignore_permissions = True
	cn.insert(); cn.submit()
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
	pe = get_payment_entry("Sales Invoice", cn.name)
	pe.mode_of_payment = mode_of_payment
	company = cn.company
	account = frappe.db.get_value("Mode of Payment Account", {"parent": mode_of_payment, "company": company}, "default_account")
	pe.paid_from = account
	pe.reference_no = reference_no or f"Refund {nowdate()}"; pe.reference_date = nowdate()
	pe.remarks = _("Demo fee refund for {0}").format(doc.name)
	pe.flags.ignore_permissions = True
	pe.setup_party_account_field(); pe.set_missing_values()
	pe.insert(); pe.submit()
	doc.db_set({"demo_fee_status": "Refunded", "demo_fee_credit_note": cn.name, "demo_fee_refund_payment": pe.name, "demo_fee_refunded_on": nowdate()})
	doc.add_comment("Info", _("Demo fee refunded by {0}: credit note {1}, payment {2}").format(mode_of_payment, cn.name, pe.name))
	lost = None
	if frappe.utils.cint(mark_lost) and doc.enquiry and frappe.db.get_value("Student Enquiry", doc.enquiry, "status") not in ("Converted", "Lost"):
		from tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry import mark_lost as _mark_lost
		_mark_lost(doc.enquiry, lost_reason or _("Not interested now"), lost_note or _("Demo fee refunded"))
		lost = doc.enquiry
	return {"credit_note": cn.name, "payment_entry": pe.name, "enquiry_lost": lost}


@frappe.whitelist()
def summary_for_enquiry(enquiry):
	rows = frappe.get_all("Demo Class", filters={"enquiry": enquiry, "demo_fee_status": ["in", ["Paid", "Adjusted", "Refunded"]]}, fields=["name", "demo_fee_status", "demo_fee_amount", "demo_fee_paid_on"])
	return {"paid": flt(sum(r.demo_fee_amount for r in rows if r.demo_fee_status == "Paid"), 2), "rows": rows}
