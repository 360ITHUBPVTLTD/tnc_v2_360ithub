"""Enrol existing students into a batch without a fee order: for the students migrated from v1
(and anyone whose fees are settled outside the system). Each gets a submitted Student Batch
Enrollment with "Fees settled outside the system" ticked, so attendance can run for them."""

import frappe
from frappe import _
from frappe.utils import nowdate


@frappe.whitelist()
def candidates(batch, txt=None):
	"""Students not yet enrolled in this batch (any status but Completed / Discontinued)."""
	frappe.only_for(("TNC Manager", "TNC Super Admin", "TNC Counsellor", "System Manager"))
	enrolled = frappe.get_all("Student Batch Enrollment", filters={"batch": batch, "docstatus": 1, "status": ["in", ["Active", "On Hold"]]}, pluck="student")
	filters = {"status": ["not in", ["Completed", "Discontinued"]]}
	if enrolled:
		filters["name"] = ["not in", enrolled]
	if txt:
		filters["student_name"] = ["like", f"%{txt}%"]
	return frappe.get_all("Student", filters=filters, fields=["name", "student_name", "mobile", "status", "biometric_id", "course_interested", "batch_interested"], order_by="student_name", limit=500)


@frappe.whitelist()
def enrol(batch, students, enrollment_date=None):
	"""Create and submit one fees-outside-system enrolment per student. Returns what was made and skipped."""
	frappe.only_for(("TNC Manager", "TNC Super Admin", "TNC Counsellor", "System Manager"))
	students = frappe.parse_json(students) if isinstance(students, str) else (students or [])
	b = frappe.get_doc("Student Batch", batch)
	made, skipped = [], []
	for st in students:
		if frappe.db.exists("Student Batch Enrollment", {"batch": batch, "student": st, "docstatus": 1, "status": ["in", ["Active", "On Hold"]]}):
			skipped.append((st, _("already enrolled")))
			continue
		try:
			e = frappe.get_doc({"doctype": "Student Batch Enrollment", "student": st, "batch": batch, "course": b.course, "enrollment_date": enrollment_date or nowdate(),
				"enrollment_type": "New Admission", "fees_outside_system": 1, "status": "Active", "remarks": _("Enrolled by the office; fees settled outside the system.")})
			e.flags.ignore_permissions = True
			e.insert()
			e.submit()
			made.append(e.name)
		except Exception as ex:
			skipped.append((st, str(ex)[:120]))
	frappe.db.commit()
	return {"made": made, "skipped": skipped}
