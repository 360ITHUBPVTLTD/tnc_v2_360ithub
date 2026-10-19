# Copyright (c) 2026, 360ithub and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StudentPunchLog(Document):
	def validate(self):
		# A punch is a record of what happened; it is never edited. A wrong manual one is deleted.
		if not self.is_new():
			frappe.throw(frappe._("A punch cannot be edited. Delete it and add it again if it was wrong."))
		# A punch is identified by number + time + machine; the machine re-sends, so keep one.
		dup = frappe.db.get_value("Student Punch Log", {"biometric_id": self.biometric_id, "punch_time": self.punch_time,
			"device_id": self.device_id or "", "name": ["!=", self.name]}, "name")
		if dup:
			frappe.throw(frappe._("This punch is already recorded as {0}.").format(dup), frappe.DuplicateEntryError)
		if not self.student:
			frappe.throw(frappe._("No student has Biometric ID {0}.").format(self.biometric_id))
