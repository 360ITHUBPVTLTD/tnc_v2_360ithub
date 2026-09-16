# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class StudentEnquiry(Document):
	def warn_duplicate_mobile(self):
		if self.status in ("Converted", "Lost") or not self.mobile:
			return
		m = find_matches(self.mobile, exclude_enquiry=self.name)
		if m["students"]:
			st = m["students"][0]
			frappe.msgprint(_("A student with this mobile already exists: {0} ({1}, {2}). If this is the same person, use Convert to Student and link them instead of creating a new student.").format(
				frappe.utils.get_link_to_form("Student", st.name), st.student_name, st.status), title=_("Existing student"), indicator="orange")
		if m["enquiries"]:
			en = m["enquiries"][0]
			frappe.msgprint(_("An open enquiry with this mobile already exists: {0} ({1}, {2}, counsellor {3}).").format(
				frappe.utils.get_link_to_form("Student Enquiry", en.name), en.student_name, en.status, en.counsellor or ""), title=_("Duplicate enquiry"), indicator="orange")

	def validate(self):
		# status is owned by the actions (demo results, Convert, Mark Lost, Reopen); a manual edit is reverted
		if not self.is_new() and not self.flags.status_by_action:
			before = self.get_doc_before_save()
			if before and before.status != self.status:
				frappe.msgprint(_("Status is set automatically. Use Schedule Demo, Convert to Student or Mark Lost."), indicator="orange")
				self.status = before.status
		elif self.is_new():
			self.status = "New"
			from tnc_v2_360ithub.admissions.invites import guard
			guard(self)
		if self.status == "Converted" and not self.student:
			frappe.throw(_("Use the Convert to Student action instead of setting the status by hand."))
		if self.status == "Lost" and not self.lost_reason:
			frappe.throw(_("Please choose a reason for marking this enquiry Lost"))
		if self.status != "Lost":
			self.lost_on = None
		elif not self.lost_on:
			self.lost_on = today()
		if self.counsellor == "Guest":
			self.counsellor = None  # a website enquiry gets the counsellor who sent the link (invites.guard), else waits for a manager
		if not self.counsellor and frappe.session.user != "Guest" and self.is_new():
			self.counsellor = frappe.session.user
		if not (self.referrer_name or "").strip() and (self.referrer_teacher_name or "").strip():
			self.referrer_name = self.referrer_teacher_name.strip()  # web form: teacher name typed by the student
		if not (self.student_name or "").strip():
			self.student_name = self.mobile  # name is optional at enquiry time; the number identifies the lead
		if not self.is_new() and self.status == "Converted":
			before = self.get_doc_before_save()
			if before and before.counsellor and before.counsellor != self.counsellor:
				frappe.throw(_("The counsellor cannot be changed after the enquiry is converted (used for incentives)."))
		self.warn_duplicate_mobile()
		asks = frappe.db.get_value("Enquiry Source", self.source, "asks_referrer") if self.source else None
		if asks != "Teacher":
			self.referred_by_teacher = None
		if asks != "Student":
			self.referred_by_student = None


def _normalize_mobile(m):
	digits = "".join(ch for ch in (m or "") if ch.isdigit())
	return digits[-10:] if len(digits) >= 10 else digits


def find_matches(mobile, exclude_enquiry=None):
	"""Students and open Enquiries whose mobile ends with the same 10 digits."""
	key = _normalize_mobile(mobile)
	if not key:
		return {"students": [], "enquiries": []}
	students = frappe.db.sql("""select name, student_name, mobile, status from tabStudent
		where right(regexp_replace(ifnull(mobile,''), '[^0-9]', ''), 10) = %s or right(regexp_replace(ifnull(alt_mobile,''), '[^0-9]', ''), 10) = %s
		order by modified desc limit 5""", (key, key), as_dict=True)
	enquiries = frappe.db.sql("""select name, student_name, mobile, status, counsellor from `tabStudent Enquiry`
		where right(regexp_replace(ifnull(mobile,''), '[^0-9]', ''), 10) = %s and status not in ('Converted', 'Lost') and name != %s
		order by modified desc limit 5""", (key, exclude_enquiry or ""), as_dict=True)
	return {"students": students, "enquiries": enquiries}


@frappe.whitelist()
def check_duplicates(mobile, exclude_enquiry=None):
	return find_matches(mobile, exclude_enquiry)


@frappe.whitelist()
def convert_to_student(enquiry, extra=None, link_student=None):
	"""One action: create the Student from what the Enquiry already holds, link both,
	mark the Enquiry Converted. `extra` may carry fields typed in the dialog
	(date_of_birth, gender, aadhar_number, ...)."""
	enq = frappe.get_doc("Student Enquiry", enquiry)
	if enq.student and frappe.db.exists("Student", enq.student):
		return enq.student
	if not enq.counsellor:
		frappe.throw(_("Please set the Counsellor (sales person) on the enquiry before converting. It is needed for incentive calculation."))
	if link_student:
		# same person already admitted: link, do not create a second Student
		if not frappe.db.exists("Student", link_student):
			frappe.throw(_("Student {0} not found").format(link_student))
		enq.db_set({"student": link_student, "status": "Converted", "converted_on": today()})
		if enq.course_interested and not frappe.db.get_value("Student", link_student, "course_interested"):
			frappe.db.set_value("Student", link_student, "course_interested", enq.course_interested, update_modified=False)
		if not frappe.db.get_value("Student", link_student, "enquiry"):
			frappe.db.set_value("Student", link_student, "enquiry", enq.name, update_modified=False)
		enq.add_comment("Info", _("Linked to existing Student {0}").format(link_student))
		return link_student
	if isinstance(extra, str):
		extra = frappe.parse_json(extra)
	from tnc_v2_360ithub.tnc_v2.doctype.admission_form.admission_form import apply_to_student, latest_form_for
	form = latest_form_for(enq.name, enq.mobile)
	if form:
		# the student filled the admission form: it carries every detail and the consent
		student = apply_to_student(form.name)
		enq.reload()
		return student
	data = {
		"doctype": "Student",
		"student_name": enq.student_name,
		"mobile": enq.mobile,
		"email": enq.email,
		"gender": enq.gender,
		"city": enq.city,
		"course_interested": enq.course_interested,
		"batch_interested": enq.batch_interested,
		"counsellor": enq.counsellor,
		"enquiry": enq.name,
		"status": "Enrolment Pending",
	}
	for k, v in (extra or {}).items():
		if v not in (None, "") and frappe.get_meta("Student").has_field(k):
			data[k] = v
	student = frappe.get_doc(data)
	student.insert()
	enq.db_set({"student": student.name, "status": "Converted", "converted_on": today(), "converted_by": frappe.session.user})
	enq.add_comment("Info", _("Converted to Student {0}").format(student.name))
	return student.name


@frappe.whitelist()
def schedule_demo(enquiry, batch, demo_date=None, from_time=None, to_time=None):
	demo = frappe.get_doc({"doctype": "Demo Class", "enquiry": enquiry, "batch": batch, "demo_date": demo_date or today(),
		"from_time": from_time, "to_time": to_time, "result": "Scheduled"})
	demo.insert()
	return demo.name


@frappe.whitelist()
def mark_lost(enquiry, reason, note=None):
	"""Close the enquiry: status Lost with a reason, open follow-ups closed,
	scheduled demos cancelled. Reversible with reopen()."""
	enq = frappe.get_doc("Student Enquiry", enquiry)
	enq.check_permission("write")
	if enq.status == "Converted":
		frappe.throw(_("A converted enquiry cannot be marked Lost"))
	if not reason:
		frappe.throw(_("Reason is required"))
	enq.status = "Lost"
	enq.lost_reason = reason
	enq.lost_note = note
	enq.lost_on = today()
	enq.lost_count = (enq.lost_count or 0) + 1
	enq.flags.status_by_action = True
	enq.save()
	closed = 0
	for f in frappe.get_all("Student Follow-Up", filters={"reference_type": "Student Enquiry", "reference_name": enquiry, "status": "Open"}, pluck="name"):
		frappe.db.set_value("Student Follow-Up", f, "status", "Closed")
		closed += 1
	cancelled = 0
	for dm in frappe.get_all("Demo Class", filters={"enquiry": enquiry, "result": "Scheduled"}, pluck="name"):
		frappe.db.set_value("Demo Class", dm, "result", "Cancelled")
		cancelled += 1
	frappe.db.set_value("Student Enquiry", enquiry, "next_follow_up", None, update_modified=False)
	enq.add_comment("Info", _("Marked Lost: {0}{1}").format(reason, f" — {note}" if note else ""))
	return {"closed_follow_ups": closed, "cancelled_demos": cancelled}


@frappe.whitelist()
def reopen(enquiry):
	enq = frappe.get_doc("Student Enquiry", enquiry)
	enq.check_permission("write")
	if enq.status != "Lost":
		frappe.throw(_("Only a Lost enquiry can be reopened"))
	# keep the last Lost record for reference before clearing the live fields
	enq.last_lost_on = enq.lost_on
	enq.last_lost_reason = enq.lost_reason
	enq.last_lost_note = enq.lost_note
	enq.reopened_on = today()
	enq.status = "New"
	enq.lost_reason = None
	enq.lost_note = None
	enq.lost_on = None
	enq.flags.status_by_action = True
	enq.save()
	enq.add_comment("Info", _("Reopened (was Lost on {0}: {1})").format(frappe.format_value(enq.last_lost_on, {"fieldtype": "Date"}), enq.last_lost_reason))
	return enq.status


@frappe.whitelist()
def admission_form_status(enquiry):
	"""For the enquiry form: is there an admission form waiting, and the link to send."""
	from tnc_v2_360ithub.tnc_v2.doctype.admission_form.admission_form import latest_form_for
	enq = frappe.get_doc("Student Enquiry", enquiry)
	form = latest_form_for(enq.name, enq.mobile)
	applied = frappe.get_all("Admission Form", filters={"enquiry": enq.name, "status": "Applied"}, pluck="name", limit=1)
	link = admission_link(enq)
	return {"pending": form, "applied": applied[0] if applied else None, "link": link}


LINK_HOURS = 48  # a personal admission link works for this long after it is sent


def admission_link_expired(enq):
	from frappe.utils import now_datetime, get_datetime
	return not enq.form_token_sent_on or (now_datetime() - get_datetime(enq.form_token_sent_on)).total_seconds() > LINK_HOURS * 3600


def admission_link(enq):
	"""Personal admission link: enquiry id plus a token. A new token is issued when the
	previous one has expired, so an old forwarded link stops working after LINK_HOURS."""
	from frappe.utils import now_datetime
	if not enq.form_token or admission_link_expired(enq):
		enq.db_set({"form_token": frappe.generate_hash(length=24), "form_token_sent_on": now_datetime()}, update_modified=False)
	return f"{frappe.utils.get_url()}/admission/new?enquiry={enq.name}&t={enq.form_token}"


@frappe.whitelist(allow_guest=True)
def admission_prefill(enquiry, t):
	"""Public form: the enquiry's details for prefilling, only with the matching token."""
	row = frappe.db.get_value("Student Enquiry", enquiry, ["form_token", "form_token_sent_on", "student_name", "mobile", "email", "gender", "city", "course_interested", "batch_interested", "status"], as_dict=True)
	if not row or not t or row.form_token != t:
		return {}
	if admission_link_expired(row):
		return {"closed": _("This link has expired. Please ask the institute for a new link.")}
	if row.status == "Converted":
		return {"closed": _("This enquiry is already admitted. Please contact the institute.")}
	if frappe.db.exists("Admission Form", {"enquiry": enquiry, "status": ["!=", "Rejected"]}):
		return {"closed": _("An admission form has already been submitted with this link. Please contact the institute if you need to correct it.")}
	return {"student_name": row.student_name, "mobile": row.mobile, "email": row.email, "gender": row.gender, "city": row.city, "course_interested": row.course_interested}


def _admission_message(enq, link=None):
	"""Message body without the link; the link is appended at send time."""
	return _("Namaste {0}, welcome to Team Nursing Classes! Please fill your admission form using the link below. Read the rules on the form and tick to accept. Our counsellor will help if you have any question.").format(enq.student_name)


def whatsapp_instance_state():
	"""State of the WhatsApp instance that will send: provider, connection, credits, number."""
	from tnc_v2_360ithub import notifications
	from frappe.utils import cint
	s = notifications.settings()
	inst = {"provider": s.whatsapp_provider, "ok": False, "msg": None, "name": None, "connected": 0, "active": 0, "credits": 0, "number": None}
	if s.whatsapp_provider != "Webtoolex":
		inst["msg"] = _("WhatsApp provider is Disabled in TNC Settings")
	elif not notifications.app_installed("webtoolex_whatsapp"):
		inst["msg"] = _("webtoolex_whatsapp app is not installed")
	else:
		name = s.whatsapp_instance or frappe.db.get_value("WhatsApp Instance", {"default": 1}, "name")
		inst["name"] = name
		if name:
			try:
				check = frappe.get_attr(notifications.WEBTOOLEX_VALIDATE)(name)  # syncs credits and connection from the provider
				inst["ok"] = bool(check.get("status")); inst["msg"] = check.get("msg")
			except Exception as e:
				inst["msg"] = str(e)[:200]
			d = frappe.db.get_value("WhatsApp Instance", name, ["instance_name", "connection_status", "active", "remaining_credits", "connected_number", "assigned_mobile_number"], as_dict=True)
			if d:
				inst.update({"label": d.instance_name or name, "connected": cint(d.connection_status), "active": cint(d.active), "credits": cint(d.remaining_credits), "number": d.connected_number or d.assigned_mobile_number})
		else:
			inst["msg"] = _("No WhatsApp Instance configured")
	return inst


@frappe.whitelist()
def admission_link_preview(enquiry):
	"""Everything the Send WhatsApp dialog shows before the user confirms: the
	instance that will send (state, credits, number), the recipient and the message."""
	from tnc_v2_360ithub import notifications
	from frappe.utils import cint
	enq = frappe.get_doc("Student Enquiry", enquiry)
	enq.check_permission("read")
	link = admission_link(enq)
	inst = whatsapp_instance_state()
	digits = "".join(ch for ch in (enq.mobile or "") if ch.isdigit())[-10:]
	return {"instance": inst, "mobile": digits, "link": link, "message": _admission_message(enq), "student_name": enq.student_name}


@frappe.whitelist()
def send_admission_link(enquiry, mobile=None, message=None):
	"""Confirm and Send: WhatsApp the admission form link (tied to this enquiry) from
	the institute's number through the notification service. Logged in WhatsApp
	Message Log. Returns Sent / Failed / Skipped with the provider's reason."""
	from tnc_v2_360ithub import notifications
	enq = frappe.get_doc("Student Enquiry", enquiry)
	enq.check_permission("write")
	link = admission_link(enq)
	digits = "".join(ch for ch in (mobile or enq.mobile or "") if ch.isdigit())
	if len(digits) < 10:
		frappe.throw(_("Please enter a valid 10-digit mobile number."))
	to = digits[-10:]
	msg = (message or "").strip() or _admission_message(enq)
	if link not in msg:
		msg = msg + "\n\n" + link  # the form link always goes at the end
	result = notifications.send_whatsapp_to_mobile(to, msg, ref_doctype="Student Enquiry", ref_name=enq.name)
	if isinstance(result, dict):
		status = "Sent" if result.get("status") else "Failed"
		reason = result.get("msg") or result.get("message") or result.get("error")
	else:
		status, reason = (result or "Skipped"), None
	if status == "Sent":
		enq.add_comment("Info", _("Admission form link sent on WhatsApp to {0}").format(to))
	if status != "Sent" and not reason:
		reason = frappe.db.get_value("WhatsApp Message Log", {"reference_doctype": "Student Enquiry", "reference_name": enq.name}, "error", order_by="creation desc")
	return {"status": status, "reason": reason, "link": link, "message": msg, "mobile": to}


@frappe.whitelist(allow_guest=True)
def open_batches():
	"""Public enquiry form: batches a student can pick, with course and mode for the label."""
	rows = frappe.get_all("Student Batch", filters={"status": ["in", ["Upcoming", "Ongoing"]]}, fields=["name", "batch_name", "course_name", "mode", "starting_date"], order_by="starting_date asc")
	return [{"value": r.name, "label": f"{r.batch_name}" + (f" · {r.mode}" if r.mode else "") + (f" · from {frappe.format_value(r.starting_date, {'fieldtype': 'Date'})}" if r.starting_date else "")} for r in rows]
