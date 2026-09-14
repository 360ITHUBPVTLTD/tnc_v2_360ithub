# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document


def _seconds(t):
	parts = [int(float(x)) for x in str(t).split(":")[:3]]
	while len(parts) < 3:
		parts.append(0)
	return parts[0] * 3600 + parts[1] * 60 + parts[2]


class DemoClass(Document):
	def validate(self):
		if self.result == "Attended" and not self.demo_date:
			frappe.throw("Demo Date is required")
		if self.from_time and self.to_time and self.to_time <= self.from_time:
			frappe.throw("To Time must be after From Time")
		self.duration = _seconds(self.to_time) - _seconds(self.from_time) if self.from_time and self.to_time else 0

	def on_update(self):
		self.sync_enquiry_status()

	def after_delete(self):
		self.sync_enquiry_status()

	def sync_enquiry_status(self):
		"""Enquiry status follows the LATEST demo (by date, time, creation):
		Scheduled -> Demo Scheduled; Attended -> Demo Attended; Not Attended or
		Cancelled -> Demo Attended if an earlier demo was attended, else New.
		Converted and Lost are never touched."""
		status = frappe.db.get_value("Student Enquiry", self.enquiry, "status")
		if status in ("Converted", "Lost"):
			return
		demos = frappe.get_all("Demo Class", filters={"enquiry": self.enquiry}, fields=["result", "demo_date", "from_time", "creation"],
			order_by="demo_date desc, from_time desc, creation desc")
		if not demos:
			new = "New"
		elif demos[0].result == "Scheduled":
			new = "Demo Scheduled"
		elif demos[0].result == "Attended":
			new = "Demo Attended"
		else:
			new = "Demo Attended" if any(d.result == "Attended" for d in demos) else "New"
		if new != status:
			frappe.db.set_value("Student Enquiry", self.enquiry, "status", new, update_modified=False)
