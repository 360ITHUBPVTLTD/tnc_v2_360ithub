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

	def apply_status_to_classes(self):
		"""A status set by staff covers the whole day: every class row takes the matching status
		(Leave counts for nothing; Present / Late count as attended; Partial and Absent as missed)."""
		from tnc_v2_360ithub.attendance.daily import apply_manual_status
		apply_manual_status(self.classes, self.status)
		self.classes_present = sum(1 for c in self.classes if c.status in ("Present", "Late"))
		self.classes_absent = sum(1 for c in self.classes if c.status not in ("Present", "Late", "Leave"))

	def on_update(self):
		# A status change by staff carries down to the class rows and can start or clear a hold.
		before = self.get_doc_before_save()
		if before and before.status != self.status and self.source == "Manual":
			self.apply_status_to_classes()
			for c in self.classes:
				frappe.db.set_value("Student Class Attendance", c.name, "status", c.status, update_modified=False)
			self.db_set({"classes_present": self.classes_present, "classes_absent": self.classes_absent}, update_modified=False)
			from tnc_v2_360ithub.attendance.daily import update_hold
			update_hold(self.enrollment, self.date)
