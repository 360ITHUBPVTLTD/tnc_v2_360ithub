# Copyright (c) 2026, 360ITHub and contributors
import frappe
from frappe import _
from frappe.utils import flt


def before_update_after_submit(doc, method=None):
	"""A submitted enrolment Sales Order keeps its fee line and schedule; the
	enrolment is the place to change them (cancel + amend). Status changes pass."""
	if not doc.get("student_batch_enrollment"):
		return
	before = doc.get_doc_before_save()
	if not before:
		return
	def sig(d):
		return [(r.item_code, flt(r.qty), flt(r.rate)) for r in d.items], flt(d.discount_amount), [(str(r.due_date), flt(r.payment_amount)) for r in d.payment_schedule]
	if sig(doc) != sig(before):
		frappe.throw(_("This order was created by enrolment {0}. Change the fee or instalments there, not with Update Items.").format(doc.student_batch_enrollment))
