# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Student: the admitted person. Customer = Student, always (ADR-0006): a Customer
is created on insert and kept in step, so fees run on standard ERPNext documents."""
import frappe
from frappe.model.document import Document

from tnc_v2_360ithub.admissions.setup import CUSTOMER_GROUP, ensure_customer_group


class Student(Document):
	def validate(self):
		if self.mobile:
			self.mobile = self.mobile.strip()
		if self.status == "Discontinued" and self.merged_into == self.name:
			frappe.throw("A student cannot be merged into itself")
		if self.status not in ("Attendance Hold", "Discontinued"):
			self.status_reason = None

	def after_insert(self):
		self.ensure_customer()

	def on_update(self):
		if self.customer and frappe.db.exists("Customer", self.customer):
			frappe.db.set_value("Customer", self.customer, {"customer_name": self.student_name, "mobile_no": self.mobile, "email_id": self.email,
				"disabled": 1 if self.status == "Discontinued" else 0}, update_modified=False)

	def ensure_customer(self):
		if self.customer and frappe.db.exists("Customer", self.customer):
			return self.customer
		ensure_customer_group()
		customer = frappe.get_doc({
			"doctype": "Customer",
			"customer_name": self.student_name,
			"customer_type": "Individual",
			"customer_group": CUSTOMER_GROUP,
			"territory": "India" if frappe.db.exists("Territory", "India") else "All Territories",
			"mobile_no": self.mobile,
			"email_id": self.email,
		})
		customer.flags.ignore_permissions = True
		customer.insert()
		self.db_set("customer", customer.name, update_modified=False)
		return customer.name
