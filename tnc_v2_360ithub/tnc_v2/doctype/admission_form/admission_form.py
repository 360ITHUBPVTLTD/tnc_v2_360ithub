# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Admission Form: the paper admission form filled online (public web form /admission
or on a tablet at the counter). Not a Student by itself: staff review it and press
"Apply to Student", which fills or creates the Student and records the consent."""
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from tnc_v2_360ithub.admissions.terms import TERMS_VERSION

COPY_FIELDS = ("student_name", "date_of_birth", "aadhar_number", "place_of_birth", "state", "nationality", "religion", "gender", "category",
	"mobile", "email", "fathers_name", "father_occupation", "father_mobile_no", "mothers_name", "mother_occupation", "mother_mobile_no",
	"permanent_address", "passing_year", "emergency_contact", "blood_group", "student_photo")


class AdmissionForm(Document):
	def validate(self):
		if not self.terms_accepted:
			frappe.throw(_("The rules and consent must be accepted before the form can be submitted."))
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
			frappe.get_doc("Student Enquiry", self.enquiry).add_comment("Info", _("Admission form {0} received, consent accepted.").format(self.name))


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
		doc.status = "Trial"
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
				"course_interested": form.course_interested, "source": "Website", "notes": _("Created from admission form {0}").format(form.name)})
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
