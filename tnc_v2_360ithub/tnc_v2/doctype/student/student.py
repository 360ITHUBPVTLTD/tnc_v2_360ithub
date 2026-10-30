# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Student: the admitted person. Customer = Student, always (ADR-0006): a Customer
is created on insert and kept in step, so fees run on standard ERPNext documents."""
import frappe
from frappe import _
from frappe.model.document import Document

from tnc_v2_360ithub.admissions.setup import CUSTOMER_GROUP, ensure_customer_group


class Student(Document):
	def guard_hold_mirror(self):
		# Student.status mirrors the enrolments. A hold is released on the enrolment (with remarks),
		# never by editing the student; an edit here is put back and the user is told where to go.
		before = self.get_doc_before_save()
		if before and before.status == "Attendance Hold" and self.status != "Attendance Hold" and not self.flags.ignore_hold_mirror:
			held = frappe.get_all("Student Batch Enrollment", filters={"student": self.name, "docstatus": 1, "status": "On Hold", "hold_type": "Attendance"}, pluck="name")
			if held:
				self.status = "Attendance Hold"
				frappe.msgprint(_("The hold is on the enrolment, not on the student. Open {0}, set Status to Active and write the reason in Remarks; the student becomes Active by itself.").format(
					", ".join(frappe.utils.get_link_to_form("Student Batch Enrollment", h) for h in held)), title=_("Release the hold on the enrolment"), indicator="orange")

	def on_trash(self):
		# the enquiry points back at this student; unlink it so either record can be deleted first.
		# The enquiry goes back to New (its data is intact) and keeps a note of what happened.
		for enq in frappe.get_all("Student Enquiry", filters={"student": self.name}, pluck="name"):
			frappe.db.set_value("Student Enquiry", enq, {"student": None, "status": "New", "converted_on": None, "converted_by": None}, update_modified=False)
			frappe.get_doc({"doctype": "Comment", "comment_type": "Info", "reference_doctype": "Student Enquiry", "reference_name": enq,
				"content": _("Student {0} was deleted; enquiry reopened as New.").format(self.name)}).insert(ignore_permissions=True)

	def validate(self):
		self.guard_hold_mirror()
		if self.mobile:
			self.mobile = self.mobile.strip()
		# one Google account per student: the Meet email falls back to the plain email, both kept tidy
		# (Google compares addresses case-insensitively; our matching and guest list rely on lower-case)
		self.email = (self.email or "").strip().lower() or None
		self.meet_email = (self.meet_email or "").strip().lower() or self.email
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


@frappe.whitelist()
def holds(student):
	"""Enrolments of this student that are On Hold, for the Release Hold dialog."""
	return frappe.get_all("Student Batch Enrollment", filters={"student": student, "docstatus": 1, "status": "On Hold"},
		fields=["name", "batch", "hold_type", "hold_on", "hold_reason", "consecutive_absences"])


@frappe.whitelist()
def release_hold(student, enrollment, remarks):
	"""Release one enrolment's hold from the Student form. Same rule as on the enrolment: a
	reason is required and only Counsellor, Manager, Super Admin or System Manager may do it."""
	if not ({"TNC Counsellor", "TNC Manager", "TNC Super Admin", "System Manager"} & set(frappe.get_roles())):
		frappe.throw(_("Only a Counsellor, Manager or Super Admin can release a hold."), frappe.PermissionError)
	if not (remarks or "").strip():
		frappe.throw(_("Please write why the hold is released."))
	e = frappe.get_doc("Student Batch Enrollment", enrollment)
	if e.student != student or e.status != "On Hold":
		frappe.throw(_("{0} is not an enrolment of this student on hold.").format(enrollment))
	e.status = "Active"
	e.remarks = remarks.strip()
	e.flags.ignore_permissions = True
	e.save()
	return {"status": e.status, "student_status": frappe.db.get_value("Student", student, "status")}
