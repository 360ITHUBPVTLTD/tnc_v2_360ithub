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
		self.message_on_schedule()

	def message_on_schedule(self):
		"""The student gets a WhatsApp when the demo is scheduled, and again when its date, time
		or batch changes while still Scheduled. Never blocks the save; the outcome is kept on the
		demo (headline) so a failed send can be resent from More."""
		if self.result != "Scheduled" or self.flags.no_schedule_message:
			return
		before = self.get_doc_before_save()
		changed = before is None or any((before.get(k) or None) != (self.get(k) or None) for k in ("demo_date", "from_time", "to_time", "batch"))
		if not changed:
			return
		if before and before.demo_date != self.demo_date and self.reminder_sent_on:
			self.db_set("reminder_sent_on", None, update_modified=False)  # a new day gets its own reminder
		try:
			send_schedule_message(self, rescheduled=bool(before and before.schedule_sent_on))
		except Exception:
			frappe.log_error(title="Demo schedule message not sent", message=frappe.get_traceback())

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


# ---------- demo schedule message ----------

def _institute():
	return frappe.db.get_single_value("TNC Settings", "document_institute_name") or frappe.defaults.get_global_default("company") or _("our institute")


def schedule_message(doc, rescheduled=False):
	"""Message text for the scheduled demo: date, time, batch, and the Meet link for an online batch."""
	from frappe.utils import get_datetime
	hhmm = lambda t: get_datetime(f"2000-01-01 {t}").strftime("%I:%M %p").lstrip("0")  # 10:00 AM
	when = frappe.format_value(doc.demo_date, {"fieldtype": "Date"}) if doc.demo_date else _("the agreed date")
	if doc.from_time:
		when += " " + _("at") + " " + hhmm(doc.from_time)
		if doc.to_time:
			when += " - " + hhmm(doc.to_time)
	batch = frappe.db.get_value("Student Batch", doc.batch, ["batch_name", "mode", "meet_link"], as_dict=True) if doc.batch else None
	lines = [(_("Namaste {0}, your demo class at {1} has been rescheduled to {2}.") if rescheduled else _("Namaste {0}, your demo class at {1} is scheduled on {2}.")).format(
		(doc.student_name or "").strip() or _("student"), _institute(), when)]
	if batch:
		lines.append(_("Batch: {0} ({1})").format(batch.batch_name or doc.batch, batch.mode or _("Offline")))
		if batch.mode == "Online" and batch.meet_link:
			lines.append(_("Join link: {0}").format(batch.meet_link))
		elif batch.mode != "Online":
			lines.append(_("Please reach the centre 10 minutes early."))
	lines.append(_("For any help, reply to this message or call the office."))
	return "\n".join(lines)


def send_schedule_message(doc, mobile=None, rescheduled=False):
	from tnc_v2_360ithub import notifications
	from frappe.utils import now_datetime
	digits = "".join(ch for ch in (mobile or doc.mobile or "") if ch.isdigit())
	if len(digits) < 10:
		doc.db_set("schedule_sent_status", _("Not sent: no valid 10-digit mobile number"), update_modified=False)
		return {"status": "Failed", "reason": _("Please enter a valid 10-digit mobile number."), "mobile": digits}
	to = digits[-10:]
	msg = schedule_message(doc, rescheduled)
	result = notifications.send_whatsapp_to_mobile(to, msg, ref_doctype="Demo Class", ref_name=doc.name)
	if isinstance(result, dict):
		ok, reason = bool(result.get("status")), (result.get("msg") or result.get("message") or result.get("error"))
	else:
		ok, reason = bool(result), None
	if ok:
		doc.db_set({"schedule_sent_on": now_datetime(), "schedule_sent_status": "Sent"}, update_modified=False)
		doc.add_comment("Info", _("Demo schedule sent on WhatsApp to {0}").format(to))
	else:
		doc.db_set("schedule_sent_status", f"Failed: {reason or ''}".strip(": ")[:140], update_modified=False)
	return {"status": "Sent" if ok else "Failed", "reason": reason, "message": msg, "mobile": to}


@frappe.whitelist()
def resend_schedule_message(demo, mobile=None):
	doc = frappe.get_doc("Demo Class", demo)
	doc.check_permission("write")
	if doc.result != "Scheduled":
		frappe.throw(_("The schedule message can be sent only while the demo is Scheduled."))
	return send_schedule_message(doc, mobile, rescheduled=bool(doc.schedule_sent_on))


def reminder_message(doc):
	when = _("today")
	if doc.from_time:
		from frappe.utils import get_datetime
		when += " " + _("at") + " " + get_datetime(f"2000-01-01 {doc.from_time}").strftime("%I:%M %p").lstrip("0")
	batch = frappe.db.get_value("Student Batch", doc.batch, ["batch_name", "mode", "meet_link"], as_dict=True) if doc.batch else None
	lines = [_("Namaste {0}, a reminder: your demo class at {1} is {2}.").format((doc.student_name or "").strip() or _("student"), _institute(), when)]
	if batch and batch.mode == "Online" and batch.meet_link:
		lines.append(_("Join link: {0}").format(batch.meet_link))
	elif batch:
		lines.append(_("Please reach the centre 10 minutes early."))
	lines.append(_("For any help, reply to this message or call the office."))
	return "\n".join(lines)


def send_demo_reminders(date=None):
	"""Scheduled 08:00: one reminder to each student whose demo is Scheduled for today and
	has not been reminded yet. Returns the count sent."""
	from tnc_v2_360ithub import notifications
	from frappe.utils import now_datetime, nowdate
	date = date or nowdate()
	sent = 0
	for d in frappe.get_all("Demo Class", filters={"result": "Scheduled", "demo_date": date, "reminder_sent_on": ["is", "not set"]}, pluck="name"):
		doc = frappe.get_doc("Demo Class", d)
		digits = "".join(ch for ch in (doc.mobile or "") if ch.isdigit())
		if len(digits) < 10:
			continue
		result = notifications.send_whatsapp_to_mobile(digits[-10:], reminder_message(doc), ref_doctype="Demo Class", ref_name=doc.name)
		if isinstance(result, dict) and result.get("status"):
			doc.db_set("reminder_sent_on", now_datetime(), update_modified=False)
			doc.add_comment("Info", _("Demo reminder sent on WhatsApp to {0}").format(digits[-10:]))
			sent += 1
	frappe.db.commit()
	return sent
