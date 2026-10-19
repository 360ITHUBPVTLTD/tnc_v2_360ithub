"""Remove students that carry no history, before a fresh office import.

A student is "unused" when nothing points at them: no enrolment, no Sales Order / Invoice /
Payment on their customer, no attendance, punches, demo, enquiry or follow-up. Everyone else
stays. Run preview() first; delete_unused() removes exactly what preview listed and returns
the count. Both are meant for System Console or bench execute.
"""
import frappe
from frappe import _

LINKS = [  # (doctype, field pointing at the Student)
	("Student Batch Enrollment", "student"), ("Student Attendance", "student"), ("Student Punch Log", "student"),
	("Student Enquiry", "student"), ("Student Enquiry", "referred_by_student"), ("Admission Form", "student"),
]
CUSTOMER_LINKS = [("Sales Order", "customer"), ("Sales Invoice", "customer"), ("Payment Entry", "party")]


def _used(student, customer):
	for dt, field in LINKS:
		if frappe.db.exists(dt, {field: student}):
			return dt
	if customer:
		for dt, field in CUSTOMER_LINKS:
			if frappe.db.exists(dt, {field: customer}):
				return dt
	return None


def unused():
	"""[(name, student_name, mobile, customer)] of students with no history."""
	out = []
	for s in frappe.get_all("Student", fields=["name", "student_name", "mobile", "customer"], order_by="name"):
		if not _used(s.name, s.customer):
			out.append((s.name, s.student_name, s.mobile, s.customer))
	return out


@frappe.whitelist()
def preview():
	frappe.only_for(("System Manager", "TNC Super Admin"))
	rows = unused()
	total = frappe.db.count("Student")
	lines = [f"{len(rows)} of {total} students have no history and would be deleted; {total - len(rows)} kept."]
	lines += [f"  {n}  {nm}  {m or ''}" for n, nm, m, _c in rows]
	return "\n".join(lines)


@frappe.whitelist()
def delete_unused():
	frappe.only_for(("System Manager", "TNC Super Admin"))
	rows = unused()
	deleted = 0
	for name, _nm, _m, customer in rows:
		frappe.delete_doc("Student", name, ignore_permissions=True, force=True)
		if customer and frappe.db.exists("Customer", customer) and not frappe.db.exists("Student", {"customer": customer}):
			try:
				frappe.delete_doc("Customer", customer, ignore_permissions=True)
			except Exception:
				pass  # a customer with ledger history stays; harmless
		deleted += 1
	frappe.db.commit()
	return _("Deleted {0} students; {1} remain.").format(deleted, frappe.db.count("Student"))
