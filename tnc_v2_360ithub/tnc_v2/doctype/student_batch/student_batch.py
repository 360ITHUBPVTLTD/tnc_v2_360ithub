# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document


class StudentBatch(Document):
	def validate(self):
		if self.starting_date and self.actual_ending_date and self.actual_ending_date < self.starting_date:
			frappe.throw("End Date cannot be before Start Date")
		if not self.standard_fee:
			self.standard_fee = frappe.db.get_value("Course", self.course, "default_fee")
