# Copyright (c) 2026, 360ithub and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class StudentAttendance(Document):
	def validate(self):
		# Rows are built by the machine job; staff may only change the status, with a reason.
		before = self.get_doc_before_save()
		if self.flags.by_machine:
			return
		if before and before.status != self.status:
			if not (self.remarks or "").strip():
				frappe.throw(_("Please write in Remarks why the status is changed."))
			self.source = "Manual"
			self.marked_by = frappe.session.user
		if self.status == "Leave" and self.source != "Manual":
			self.source = "Manual"
			self.marked_by = frappe.session.user

	def validate_classes_for_leave(self):
		"""Leave covers the whole day: its classes read Leave and count for nothing. Any other
		status leaves the machine's class rows as they are."""
		if self.status == "Leave":
			for c in self.classes:
				c.status = "Leave"
			self.classes_present = 0
			self.classes_absent = 0

	def on_update(self):
		# A status change can start or clear a hold; keep the enrolment's count current.
		before = self.get_doc_before_save()
		if before and before.status != self.status:
			if self.status == "Leave" or before.status == "Leave":
				self.validate_classes_for_leave() if self.status == "Leave" else None
				if before.status == "Leave" and self.status != "Leave":
					# back from Leave: let the machine rule decide the classes again
					from tnc_v2_360ithub.attendance.daily import build_day
					build_day(self.date, batch=self.batch, student=self.student, notify=False)
				elif self.status == "Leave":
					for c in self.classes:
						frappe.db.set_value("Student Class Attendance", c.name, "status", "Leave", update_modified=False)
					self.db_set({"classes_present": 0, "classes_absent": 0}, update_modified=False)
			from tnc_v2_360ithub.attendance.daily import update_hold
			update_hold(self.enrollment, self.date)
