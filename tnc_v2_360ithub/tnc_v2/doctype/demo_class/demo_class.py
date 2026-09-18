# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
import frappe
from frappe import _
from frappe.model.document import Document


def _seconds(t):
	parts = [int(float(x)) for x in str(t).split(":")[:3]]
	while len(parts) < 3:
		parts.append(0)
	return parts[0] * 3600 + parts[1] * 60 + parts[2]


class DemoClass(Document):
	def validate(self):
		self.block_duplicate()
		if self.result == "Attended" and not self.demo_date:
			frappe.throw("Demo Date is required")
		if self.from_time and self.to_time:
			a, b = _seconds(self.from_time), _seconds(self.to_time)
			if a == b:
				# Frappe stamps empty Time fields with the current clock at save; equal times mean "no slot given"
				self.from_time = self.to_time = None
			elif b < a:
				frappe.throw(_("To Time must be after From Time"))
		self.duration = _seconds(self.to_time) - _seconds(self.from_time) if self.from_time and self.to_time else 0

	def block_duplicate(self):
		"""One open demo per enquiry, and never the same slot twice (a double-click must not book twice)."""
		if not self.enquiry or self.result == "Cancelled":
			return
		if self.result == "Scheduled":
			other = frappe.db.get_value("Demo Class", {"enquiry": self.enquiry, "result": "Scheduled", "name": ["!=", self.name or ""]}, ["name", "demo_date"], as_dict=True)
			if other:
				frappe.throw(_("A demo is already scheduled for this enquiry on {0} ({1}). Mark it Attended, Not Attended or Cancelled before scheduling another.").format(
					frappe.format_value(other.demo_date, {"fieldtype": "Date"}), other.name), frappe.DuplicateEntryError)
		same = frappe.db.get_value("Demo Class", {"enquiry": self.enquiry, "demo_date": self.demo_date, "from_time": self.from_time or None, "result": ["!=", "Cancelled"], "name": ["!=", self.name or ""]}, "name")
		if same:
			frappe.throw(_("This demo slot is already booked for this enquiry ({0}).").format(same), frappe.DuplicateEntryError)

	def on_update(self):
		self.sync_enquiry_status()
		self.followup_after_result()

	def followup_after_result(self):
		"""Once the demo result is known, the counsellor gets a next-day Enquiry follow-up so the
		student is called while the demo is fresh. One per demo; nothing if the enquiry already
		has an open enquiry follow-up or is Converted / Lost."""
		if self.result not in ("Attended", "Not Attended") or not self.enquiry:
			return
		before = self.get_doc_before_save()
		if before and before.result == self.result:
			return
		enq = frappe.db.get_value("Student Enquiry", self.enquiry, ["status", "counsellor", "student_name", "mobile"], as_dict=True)
		if not enq or enq.status in ("Converted", "Lost"):
			return
		if frappe.db.exists("Student Follow-Up", {"reference_type": "Student Enquiry", "reference_name": self.enquiry, "purpose": "Demo", "status": "Open", "notes": ["like", f"%{self.name}%"]}):
			return
		from frappe.utils import add_days, today
		note = (_("Demo attended on {0} ({1}). Call to ask how it went and offer admission.") if self.result == "Attended"
			else _("Did not attend the demo on {0} ({1}). Call to reschedule or ask why.")).format(frappe.format_value(self.demo_date, {"fieldtype": "Date"}), self.name)
		frappe.get_doc({"doctype": "Student Follow-Up", "reference_type": "Student Enquiry", "reference_name": self.enquiry, "purpose": "Demo",
			"student_name": enq.student_name, "mobile": enq.mobile, "follow_up_date": today(), "next_follow_up_date": add_days(today(), 1),
			"followup_type": "Call", "status": "Open", "assigned_to": enq.counsellor, "notes": note}).insert(ignore_permissions=True)

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
