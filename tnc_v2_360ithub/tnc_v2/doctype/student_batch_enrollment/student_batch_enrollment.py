# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Student Batch Enrollment: this Student in this Batch. Submitting it IS the
admission: exactly one standard Sales Order is created for the Student's Customer,
one line (the course fee item) at the batch fee, the discount applied at order
level, GST if ticked, and the instalments as the order's Payment Schedule.
The Sales Order is the commitment record; paid / pending live there (ADR-0006)."""
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, flt, getdate, nowdate

from tnc_v2_360ithub.admissions.setup import ensure_fee_item, payment_term_for

DEFAULT_GST_TEMPLATE = "Output GST In-state - 3"


class StudentBatchEnrollment(Document):
	# ---- amounts -------------------------------------------------------------
	def validate(self):
		self.set_batch_window()
		self.compute_amounts()
		if not self.installments or self.flags.regenerate:
			self.generate_installments()
		self.validate_installments()
		if self.gst_applicable and not self.taxes_and_charges:
			self.taxes_and_charges = DEFAULT_GST_TEMPLATE if frappe.db.exists("Sales Taxes and Charges Template", DEFAULT_GST_TEMPLATE) else None
		self.suggest_admission_type()
		if self.enrollment_type == "New Admission":
			self.previous_enrollment = None
		if self.status != "On Hold":
			self.hold_reason = None
		if not self.is_new() or self.docstatus == 0:
			self.block_duplicate_ongoing()

	def set_batch_window(self):
		if not self.batch:
			return
		b = frappe.db.get_value("Student Batch", self.batch, ["starting_date", "actual_ending_date"], as_dict=True)
		self.batch_start = b.starting_date
		self.batch_end = b.actual_ending_date

	def compute_amounts(self):
		fee = flt(self.standard_fee)
		if self.discount_type == "Percentage":
			if not 0 <= flt(self.discount_value) <= 100:
				frappe.throw(_("Discount percentage must be between 0 and 100"))
			self.discount_amount = flt(fee * flt(self.discount_value) / 100, 2)
		elif self.discount_type == "Amount":
			self.discount_amount = flt(self.discount_value, 2)
		else:
			self.discount_value = 0
			self.discount_amount = 0
		if self.discount_amount > fee:
			frappe.throw(_("Discount cannot exceed the fee"))
		if self.discount_type and flt(self.discount_amount) > 0 and not (self.discount_reason or "").strip():
			frappe.throw(_("Please give the reason for the discount"))
		if not self.discount_type:
			self.discount_reason = None
		self.net_payable = flt(fee - flt(self.discount_amount), 2)

	def generate_installments(self):
		"""Equal split of Net Payable, `installment_gap_days` apart from `first_due_date`;
		the last row absorbs rounding. Counsellor edits rows afterwards."""
		n = max(int(self.number_of_installments or 1), 1)
		start = getdate(self.first_due_date or nowdate())
		gap = int(self.installment_gap_days or 30)
		base = flt(self.net_payable / n, 2) if n else 0
		self.set("installments", [])
		running = 0
		for i in range(n):
			amount = flt(self.net_payable - running, 2) if i == n - 1 else base
			running += amount
			self.append("installments", {"installment_no": i + 1, "due_date": add_days(start, gap * i), "amount": amount,
				"description": _("Instalment {0} of {1}").format(i + 1, n)})
		self.number_of_installments = n

	def validate_installments(self):
		total = flt(sum(flt(r.amount) for r in self.installments), 2)
		if abs(total - flt(self.net_payable)) > 0.5:
			frappe.throw(_("Instalments total {0} but Net Payable is {1}. Adjust the rows or press Generate Instalments.").format(
				frappe.format_value(total, {"fieldtype": "Currency"}), frappe.format_value(self.net_payable, {"fieldtype": "Currency"})))
		batch_end = getdate(self.batch_end) if self.batch_end else None
		beyond = [r for r in self.installments if batch_end and r.due_date and getdate(r.due_date) > batch_end]
		if beyond:
			frappe.msgprint(_("{0} instalment(s) fall after the batch ends on {1} (latest due {2}). Collect the fee within the batch unless this was agreed.").format(
				len(beyond), frappe.format_value(batch_end, {"fieldtype": "Date"}), frappe.format_value(max(getdate(r.due_date) for r in beyond), {"fieldtype": "Date"})),
				title=_("Instalments beyond batch end"), indicator="orange")
		last = None
		for i, r in enumerate(self.installments, 1):
			r.installment_no = i
			if not r.due_date:
				frappe.throw(_("Row #{0}: due date is required").format(i))
			if last and getdate(r.due_date) < last:
				frappe.throw(_("Row #{0}: due dates must be in order").format(i))
			last = getdate(r.due_date)
		self.number_of_installments = len(self.installments)

	def suggest_admission_type(self):
		"""Rejoining when the student completed the same course before; Batch Change when
		another enrolment in the same course is still active (linked as previous)."""
		if not (self.student and self.course) or self.flags.type_confirmed:
			return
		same_course = frappe.get_all("Student Batch Enrollment", filters={"student": self.student, "course": self.course, "docstatus": 1, "name": ["!=", self.name or ""]},
			fields=["name", "status", "batch"], order_by="enrollment_date desc")
		active = [e for e in same_course if e.status in ("Active", "On Hold")]
		done = [e for e in same_course if e.status in ("Completed", "Left")]
		if active and self.enrollment_type != "Batch Change":
			self.enrollment_type = "Batch Change"
			self.previous_enrollment = self.previous_enrollment or active[0].name
		elif done and not active and self.enrollment_type == "New Admission":
			self.enrollment_type = "Rejoining"
			self.previous_enrollment = self.previous_enrollment or done[0].name

	def block_duplicate_ongoing(self):
		dup = frappe.db.exists("Student Batch Enrollment", {"student": self.student, "batch": self.batch, "docstatus": 1,
			"status": ["in", ["Active", "On Hold"]], "name": ["!=", self.name]})
		if dup:
			frappe.throw(_("{0} is already enrolled in {1} ({2})").format(self.student_name, self.batch, dup))

	# ---- submit: the Sales Order ---------------------------------------------
	def on_submit(self):
		if not self.sales_order:
			so = self.make_sales_order()
			self.db_set("sales_order", so.name)
		# first paid-for enrolment ends the trial
		if frappe.db.get_value("Student", self.student, "status") == "Trial":
			frappe.db.set_value("Student", self.student, "status", "Active", update_modified=False)

	def on_cancel(self):
		if self.sales_order:
			so = frappe.get_doc("Sales Order", self.sales_order)
			if so.docstatus == 1:
				if flt(so.advance_paid) or frappe.db.exists("Sales Invoice Item", {"sales_order": so.name, "docstatus": 1}):
					frappe.throw(_("Sales Order {0} already has payments or invoices. Cancel those first.").format(so.name))
				so.flags.ignore_permissions = True
				so.cancel()

	def make_sales_order(self):
		student = frappe.get_doc("Student", self.student)
		customer = student.customer or student.ensure_customer()
		course = frappe.get_doc("Course", self.course)
		item = course.fee_item or ensure_fee_item(course)
		batch = frappe.get_doc("Student Batch", self.batch)
		so = frappe.get_doc({
			"doctype": "Sales Order",
			"customer": customer,
			"order_type": "Sales",
			"transaction_date": self.enrollment_date or nowdate(),
			"delivery_date": batch.actual_ending_date or batch.starting_date or self.enrollment_date or nowdate(),
			"company": frappe.defaults.get_global_default("company") or frappe.db.get_single_value("Global Defaults", "default_company"),
			"skip_delivery_note": 1,  # a fee is not delivered; order goes To Bill -> Completed as receipts come in
			"student": self.student,
			"student_batch_enrollment": self.name,
			"student_batch": self.batch,
			"items": [{"item_code": item, "item_name": f"{course.course_name} - {batch.batch_name}", "description": f"Course fee: {course.course_name}, batch {batch.batch_name}",
				"qty": 1, "rate": flt(self.standard_fee), "uom": "Nos", "delivery_date": batch.actual_ending_date or batch.starting_date or self.enrollment_date or nowdate()}],
		})
		if flt(self.discount_amount):
			so.apply_discount_on = "Net Total"
			so.discount_amount = flt(self.discount_amount)
			so.terms = _("Discount {0}: {1}").format(frappe.format_value(self.discount_amount, {"fieldtype": "Currency"}), self.discount_reason or "")
		if self.gst_applicable and self.taxes_and_charges:
			so.taxes_and_charges = self.taxes_and_charges
		so.flags.ignore_permissions = True
		so.set_missing_values()
		if so.taxes_and_charges and not so.taxes:
			from erpnext.controllers.accounts_controller import get_taxes_and_charges
			for t in get_taxes_and_charges("Sales Taxes and Charges Template", so.taxes_and_charges) or []:
				so.append("taxes", t)
		so.run_method("calculate_taxes_and_totals")
		# instalments -> Payment Schedule, scaled to the grand total (GST spreads evenly)
		grand = flt(so.grand_total) or flt(self.net_payable)
		so.set("payment_schedule", [])
		running = 0
		for i, r in enumerate(self.installments):
			portion = flt(r.amount) / flt(self.net_payable) * 100 if self.net_payable else 100 / len(self.installments)
			amount = flt(grand - running, 2) if i == len(self.installments) - 1 else flt(grand * portion / 100, 2)
			running += amount
			so.append("payment_schedule", {"payment_term": payment_term_for(i + 1), "due_date": r.due_date, "invoice_portion": flt(portion, 6), "payment_amount": amount,
				"description": r.description or _("Instalment {0}").format(i + 1)})
		so.insert()
		so.submit()
		return so


@frappe.whitelist()
def active_enrolments(student, batch):
	"""For the form when a batch is picked: what is this student already active in?
	Returns same_batch (duplicate), same_course (batch change) and other (parallel course)."""
	course = frappe.db.get_value("Student Batch", batch, "course")
	rows = frappe.get_all("Student Batch Enrollment", filters={"student": student, "docstatus": 1, "status": ["in", ["Active", "On Hold"]]},
		fields=["name", "batch", "course", "course_name", "status"])
	return {
		"same_batch": next((r for r in rows if r.batch == batch), None),
		"same_course": next((r for r in rows if r.course == course and r.batch != batch), None),
		"other": [r for r in rows if r.course != course],
	}
