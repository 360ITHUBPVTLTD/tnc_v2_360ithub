# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Admission Form: the paper admission form filled online (public web form /admission
or on a tablet at the counter). Not a Student by itself: staff review it and press
"Apply to Student", which fills or creates the Student and records the consent."""
import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from tnc_v2_360ithub.admissions.terms import TERMS_VERSION

COPY_FIELDS = ("student_name", "date_of_birth", "aadhar_number", "place_of_birth", "state", "nationality", "religion", "gender", "category",
	"mobile", "email", "fathers_name", "father_occupation", "father_mobile_no", "mothers_name", "mother_occupation", "mother_mobile_no",
	"permanent_address", "passing_year", "emergency_contact", "blood_group", "student_photo")


class AdmissionForm(Document):
	def onload(self):
		if self.enquiry:
			self.set_onload("enquiry_name", frappe.db.get_value("Student Enquiry", self.enquiry, "student_name"))

	def validate(self):
		if not self.terms_accepted or not self.guardian_consent:
			frappe.throw(_("Both the rules consent and the guardian consent must be ticked before the form can be submitted."))
		if self.student_name:
			self.student_name = self.student_name.strip().upper()
		if self.is_new():
			self.terms_version = TERMS_VERSION
			self.accepted_on = now_datetime()
			self.ip_address = getattr(frappe.local, "request_ip", None)
			self.status = "Pending Review"
		digits = "".join(ch for ch in (self.mobile or "") if ch.isdigit())
		if len(digits) < 10:
			frappe.throw(_("Please enter a valid 10-digit mobile number."))
		if self.is_new():
			self.attach_to_enquiry()
			self.guard_enquiry_link()

	def guard_enquiry_link(self):
		"""A personal link is for one student, once. The mobile on the form must be the
		enquiry's mobile, and an enquiry that already has a live form takes no second one."""
		if not self.enquiry:
			if frappe.session.user == "Guest":
				frappe.throw(_("Please use the personal admission link sent to you by the institute."), frappe.PermissionError)
			return
		enq = frappe.db.get_value("Student Enquiry", self.enquiry, ["mobile", "status", "student_name", "form_token", "form_token_sent_on"], as_dict=True)
		enq_mobile, enq_status = enq.mobile, enq.status
		d10 = lambda m: "".join(ch for ch in (m or "") if ch.isdigit())[-10:]
		if frappe.session.user == "Guest":
			from tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry import admission_link_expired
			if admission_link_expired(enq):
				frappe.throw(_("This link has expired. Please ask the institute for a new link."), frappe.PermissionError)
		norm = lambda n: re.sub(r"[^a-z]", "", (n or "").lower())
		self.name_mismatch = 1 if enq.student_name and norm(enq.student_name) != norm(self.student_name) else 0
		if enq_mobile and d10(enq_mobile) != d10(self.mobile):
			frappe.throw(_("This admission link was sent to a different mobile number. Please fill the form with the number your enquiry was made from, or ask the institute for your own link."), frappe.PermissionError)
		if frappe.db.exists("Admission Form", {"enquiry": self.enquiry, "status": ["!=", "Rejected"]}):
			frappe.throw(_("An admission form has already been submitted for this enquiry. Please contact the institute if you need to correct it."), frappe.DuplicateEntryError)
		if enq_status == "Converted":
			frappe.throw(_("This enquiry is already admitted. Please contact the institute."), frappe.PermissionError)

	def attach_to_enquiry(self):
		"""Link the open enquiry this form belongs to: the one named in the link the
		counsellor sent, else the open enquiry with the same mobile."""
		if self.enquiry and not frappe.db.exists("Student Enquiry", self.enquiry):
			self.enquiry = None
		if not self.enquiry:
			from tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry import find_matches
			open_enq = find_matches(self.mobile)["enquiries"]
			if open_enq:
				self.enquiry = open_enq[0].name
		if self.enquiry and not self.course_interested:
			self.course_interested = frappe.db.get_value("Student Enquiry", self.enquiry, "course_interested")

	def after_insert(self):
		if self.enquiry:
			enq = frappe.get_doc("Student Enquiry", self.enquiry)
			enq.add_comment("Info", _("Admission form {0} received, consent accepted.").format(self.name))
			if self.name_mismatch:
				enq.add_comment("Info", _("⚠ Name on admission form {0} is <b>{1}</b>, enquiry name is <b>{2}</b>. Please check before applying.").format(self.name, self.student_name, enq.student_name))


@frappe.whitelist()
def apply_to_student(name, student=None):
	"""Fill the Student from this form (create one if none matches) and record consent."""
	form = frappe.get_doc("Admission Form", name)
	form.check_permission("write")
	if form.status == "Applied" and form.student:
		return form.student
	if not student:
		from tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry import find_matches
		m = find_matches(form.mobile)["students"]
		student = m[0].name if m else None
	if student:
		doc = frappe.get_doc("Student", student)
	else:
		doc = frappe.new_doc("Student")
		doc.status = "Enrolment Pending"
	for f in COPY_FIELDS:
		if form.get(f) not in (None, "") and frappe.get_meta("Student").has_field(f):
			doc.set(f, form.get(f))
	doc.address = doc.address or form.residential_address
	doc.course_interested = form.course_interested or doc.course_interested or (frappe.db.get_value("Student Enquiry", form.enquiry, "course_interested") if form.enquiry else None)
	doc.college = form.college_name or doc.college
	doc.passout_year = form.passing_year or doc.passout_year
	doc.terms_accepted = 1
	doc.terms_accepted_on = form.accepted_on
	doc.terms_version = form.terms_version
	doc.admission_form = form.name
	doc.flags.ignore_permissions = True
	created = doc.is_new()
	doc.save() if not created else doc.insert()
	# keep the funnel complete: link the open enquiry with this mobile, or create a converted one
	from tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry import convert_to_student, find_matches
	if not doc.enquiry:
		linked = form.enquiry if form.enquiry and frappe.db.get_value("Student Enquiry", form.enquiry, "status") not in ("Converted",) else None
		open_enq = find_matches(form.mobile)["enquiries"]
		if linked or open_enq:
			convert_to_student(linked or open_enq[0].name, link_student=doc.name)
		else:
			enq = frappe.get_doc({"doctype": "Student Enquiry", "student_name": doc.student_name, "mobile": doc.mobile, "email": doc.email, "gender": doc.gender,
				"course_interested": form.course_interested, "source": "Other", "notes": _("Created from admission form {0}").format(form.name)})
			enq.flags.ignore_permissions = True
			enq.insert()
			convert_to_student(enq.name, link_student=doc.name)
		doc.reload()
	form.db_set({"status": "Applied", "student": doc.name, "reviewed_by": frappe.session.user})
	form.add_comment("Info", _("Applied to Student {0}").format(doc.name))
	return doc.name


@frappe.whitelist()
def reject(name, reason):
	"""Office action: mark the form Rejected with a reason. Status is never edited by hand."""
	form = frappe.get_doc("Admission Form", name)
	form.check_permission("write")
	if form.status == "Applied":
		frappe.throw(_("This form is already applied to a student."))
	form.db_set({"status": "Rejected", "office_remarks": reason, "reviewed_by": frappe.session.user})
	form.add_comment("Info", _("Rejected: {0}").format(reason))
	return form.status


def latest_form_for(enquiry, mobile=None):
	"""The newest unapplied admission form for this enquiry (or this mobile)."""
	rows = frappe.get_all("Admission Form", filters={"enquiry": enquiry, "status": "Pending Review"}, fields=["name", "accepted_on", "terms_version", "student_photo"], order_by="creation desc", limit=1)
	if not rows and mobile:
		digits = "".join(ch for ch in mobile if ch.isdigit())[-10:]
		rows = frappe.db.sql("""select name, accepted_on, terms_version, student_photo from `tabAdmission Form`
			where status = 'Pending Review' and right(regexp_replace(ifnull(mobile,''), '[^0-9]', ''), 10) = %s order by creation desc limit 1""", digits, as_dict=True)
	return rows[0] if rows else None
