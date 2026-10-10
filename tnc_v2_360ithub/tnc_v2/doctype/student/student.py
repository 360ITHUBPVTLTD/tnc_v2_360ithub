# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Student: the admitted person. Customer = Student, always (ADR-0006): a Customer
is created on insert and kept in step, so fees run on standard ERPNext documents."""
import frappe
from frappe import _
from frappe.model.document import Document

from tnc_v2_360ithub.admissions.setup import CUSTOMER_GROUP, ensure_customer_group


class Student(Document):
	def on_trash(self):
		# the enquiry points back at this student; unlink it so either record can be deleted first.
		# The enquiry goes back to New (its data is intact) and keeps a note of what happened.
		for enq in frappe.get_all("Student Enquiry", filters={"student": self.name}, pluck="name"):
			frappe.db.set_value("Student Enquiry", enq, {"student": None, "status": "New", "converted_on": None, "converted_by": None}, update_modified=False)
			frappe.get_doc({"doctype": "Comment", "comment_type": "Info", "reference_doctype": "Student Enquiry", "reference_name": enq,
				"content": _("Student {0} was deleted; enquiry reopened as New.").format(self.name)}).insert(ignore_permissions=True)

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
		if self.enquiry:
			c = frappe.db.get_value("Student Enquiry", self.enquiry, "customer")
			if c and frappe.db.exists("Customer", c):
				self.db_set("customer", c, update_modified=False)
				return c
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
