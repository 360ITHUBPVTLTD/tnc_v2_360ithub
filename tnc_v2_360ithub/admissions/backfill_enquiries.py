"""Enquiries for students who were admitted directly (imported), so Enquiry Overview's Converted
matches the batch's Enrolled.

Every Active / On Hold enrolment whose student has no enquiry linked to them gets one enquiry,
already Converted, linked to the student, under the counsellor named on the command. Nothing is
sent to the student and no follow-up is made. Existing enquiries and their counsellors are never
edited unless `existing="convert"` is asked for.

	preview (changes nothing):
	bench --site <site> execute tnc_v2_360ithub.admissions.backfill_enquiries.run --kwargs "{'counsellor': '<user>'}"
	do it:
	bench --site <site> execute tnc_v2_360ithub.admissions.backfill_enquiries.run --kwargs "{'counsellor': '<user>', 'commit': 1}"
	take it back (only the enquiries this tool created):
	bench --site <site> execute tnc_v2_360ithub.admissions.backfill_enquiries.undo --kwargs "{'commit': 1}"

Safe to run again: a student who already has a linked enquiry is skipped.
"""

import frappe
from frappe.utils import cint, getdate

from tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry import _normalize_mobile

MARK = "Admitted directly, without an enquiry. Enquiry added afterwards so the counts match."


def _todo(batch=None):
	"""Enrolments whose student has no linked enquiry, and the open enquiry (if any) on the same mobile."""
	cond, args = "", {}
	if batch:
		cond = "and e.batch = %(batch)s"; args["batch"] = batch
	rows = frappe.db.sql(f"""
		select e.name as enrollment, e.student, e.batch, e.enrollment_date, b.batch_name, b.course, b.mode,
			s.student_name, s.mobile, s.email, s.gender, s.city
		from `tabStudent Batch Enrollment` e
		join `tabStudent` s on s.name = e.student
		left join `tabStudent Batch` b on b.name = e.batch
		where e.docstatus = 1 and e.status in ('Active', 'On Hold') {cond}
			and not exists (select 1 from `tabStudent Enquiry` x where x.student = e.student)
		order by e.batch, e.enrollment_date, e.name""", args, as_dict=True)
	open_by_mobile = {}
	for x in frappe.db.sql("""select name, mobile, status, counsellor, batch_interested, student from `tabStudent Enquiry`
			where status not in ('Converted', 'Lost')""", as_dict=True):
		open_by_mobile.setdefault(_normalize_mobile(x.mobile), []).append(x)
	for r in rows:
		r.key = _normalize_mobile(r.mobile)
		r.open = open_by_mobile.get(r.key, []) if r.key else []
	return rows


def run(counsellor, batch=None, existing="skip", source=None, commit=0):
	"""`existing`: what to do when the student's mobile already has an open enquiry under some
	counsellor. "skip" leaves that enquiry and its counsellor's numbers alone (the student stays
	unmatched and is listed). "convert" marks that enquiry Converted and links it to the student,
	which moves one from Remaining to Converted for that counsellor. "reassign" does the same and
	also moves that enquiry to the counsellor named on the command, so every directly admitted
	student sits under one counsellor (the earlier counsellor is kept in a comment).
	`source`: an Enquiry Source to put on the enquiries this tool creates, so they do not show as
	"(no source)". Also filled on enquiries an earlier run created without one."""
	commit = cint(commit)
	if existing not in ("skip", "convert", "reassign"):
		frappe.throw("existing must be 'skip', 'convert' or 'reassign'")
	if not frappe.db.get_value("User", counsellor, "enabled"):
		frappe.throw(f"User {counsellor} not found or disabled")
	if source and not frappe.db.exists("Enquiry Source", source):
		frappe.throw(f"Enquiry Source {source} not found. Create it first, or use one of: " + ", ".join(frappe.get_all("Enquiry Source", pluck="name")))
	out = frappe._dict(counsellor=counsellor, committed=bool(commit), existing=existing, by_batch={}, created=0, converted_existing=0,
		left_existing=[], no_mobile=[], failed=[], source_filled=0)
	if source:
		earlier = frappe.get_all("Student Enquiry", filters={"notes": MARK, "source": ["is", "not set"]}, pluck="name")
		for n in earlier:
			frappe.db.set_value("Student Enquiry", n, "source", source, update_modified=False)
		out.source_filled = len(earlier)
	seen = set()  # one student twice in the list (two enrolments): one enquiry per batch, never two for the same batch
	frappe.flags.mute_messages = True
	try:
		for r in _todo(batch):
			b = out.by_batch.setdefault(r.batch_name or r.batch, {"create": 0, "existing_enquiry": 0, "no_mobile": 0})
			if (r.student, r.batch) in seen:
				continue
			seen.add((r.student, r.batch))
			if not r.key:
				b["no_mobile"] += 1; out.no_mobile.append(r.student); continue
			if r.open:
				b["existing_enquiry"] += 1
				x = r.open[0]
				if existing in ("convert", "reassign"):
					# the batch they actually joined, so the batch's Converted equals its Enrolled even when they first asked about another batch
					frappe.db.set_value("Student Enquiry", x.name, {"student": r.student, "status": "Converted", "converted_on": getdate(r.enrollment_date),
						"batch_interested": r.batch, "course_interested": r.course or x.get("course_interested")})
					note = f"Linked to Student {r.student}, who was admitted directly on {r.enrollment_date}."
					if existing == "reassign" and x.counsellor != counsellor:
						frappe.db.set_value("Student Enquiry", x.name, "counsellor", counsellor)
						note += f" Counsellor changed from {x.counsellor or 'none'} to {counsellor}."
					frappe.get_doc("Student Enquiry", x.name).add_comment("Info", note)
					r.open.remove(x)
					out.converted_existing += 1
				else:
					out.left_existing.append({"student": r.student, "name": r.student_name, "mobile": r.mobile, "batch": r.batch_name, "enquiry": x.name, "status": x.status, "counsellor": x.counsellor})
				continue
			b["create"] += 1
			try:
				enq = frappe.get_doc({
					"doctype": "Student Enquiry", "mobile": r.mobile, "student_name": r.student_name, "email": r.email, "gender": r.gender, "city": r.city,
					"batch_interested": r.batch, "course_interested": r.course, "preferred_mode": r.mode if r.mode in ("Offline", "Online") else None,
					"enquiry_date": getdate(r.enrollment_date), "counsellor": counsellor, "notes": MARK, "source": source,
				})
				enq.flags.no_form_link = True  # no enquiry-form WhatsApp to a student who is already admitted
				enq.insert(ignore_permissions=True)
				# the Student is left as it is: no counsellor, no enquiry link on it, so the admission-form
				# chase (which follows Student.enquiry) never starts for these students
				enq.db_set({"student": r.student, "status": "Converted", "converted_on": getdate(r.enrollment_date), "converted_by": counsellor}, update_modified=False)
				out.created += 1
			except Exception as e:
				b["create"] -= 1
				out.failed.append({"student": r.student, "mobile": r.mobile, "error": str(e)[:200]})
	finally:
		frappe.flags.mute_messages = False
	if commit:
		frappe.db.commit()
	else:
		frappe.db.rollback()
	out.left_existing_count = len(out.left_existing)
	return out


def undo(commit=0):
	"""Delete the enquiries this tool created (recognised by their note and by still being exactly as created)."""
	names = frappe.get_all("Student Enquiry", filters={"notes": MARK, "status": "Converted"}, pluck="name")
	for n in names:
		frappe.db.set_value("Student Enquiry", n, "student", None, update_modified=False)  # on_trash must not touch the Student
		frappe.delete_doc("Student Enquiry", n, ignore_permissions=True, force=True)
	if cint(commit):
		frappe.db.commit()
	else:
		frappe.db.rollback()
	return {"deleted": len(names), "committed": bool(cint(commit))}
