# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document


class StudentFollowUp(Document):
	def validate(self):
		if self.reference_type and self.reference_name:
			self.student_name, self.mobile = frappe.db.get_value(self.reference_type, self.reference_name, ["student_name", "mobile"])
			if not self.assigned_to:
				self.assigned_to = frappe.db.get_value(self.reference_type, self.reference_name, "counsellor") or frappe.session.user
		if self.purpose != "Fee":
			self.sales_order = self.payment_term = self.instalment_due_date = self.fee_kind = None
			self.amount_pending = 0
		if self.purpose == "Enquiry" and self.reference_type != "Student Enquiry":
			self.purpose = "General"  # an admitted student is not a lead
		if self.purpose == "Fee" and self.reference_type != "Student":
			self.purpose = "General"  # fees exist only once admitted
		if self.next_follow_up_date and self.follow_up_date and self.next_follow_up_date < self.follow_up_date:
			frappe.throw("Next follow-up cannot be before this follow-up")

	def after_insert(self):
		# only the latest follow-up on a lead stays open (fee follow-ups are per instalment, handled by the job)
		if self.purpose != "Fee" and self.status == "Open":
			for name in frappe.get_all("Student Follow-Up", filters={"reference_type": self.reference_type, "reference_name": self.reference_name,
					"purpose": ["!=", "Fee"], "status": "Open", "name": ["!=", self.name]}, pluck="name"):
				frappe.db.set_value("Student Follow-Up", name, "status", "Closed", update_modified=False)

	def on_update(self):
		self.push_next_date()

	def after_delete(self):
		self.push_next_date()

	def push_next_date(self):
		if self.reference_type != "Student Enquiry":
			return
		nxt = frappe.db.sql("""select min(next_follow_up_date) from `tabStudent Follow-Up`
			where reference_type='Student Enquiry' and reference_name=%s and status='Open' and next_follow_up_date is not null""", self.reference_name)[0][0]
		frappe.db.set_value("Student Enquiry", self.reference_name, "next_follow_up", nxt, update_modified=False)
