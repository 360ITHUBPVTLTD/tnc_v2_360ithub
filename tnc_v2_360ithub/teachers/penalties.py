# Copyright (c) 2026, 360ITHub and contributors
"""One-time setup for teacher penalties: the starting Penalty Types.

The starting types and amounts are the ones written in the TNC SOW (Teacher Penalty
Management). They are created only when missing, so whatever the office changes on the
Penalty Type list afterwards stays as they set it.
"""
import frappe

# (type, default amount, when it applies) as listed in the SOW; the last amount was left open there
SOW_PENALTY_TYPES = (
	("Meeting Late", 5000, "Teacher joined a scheduled staff meeting late."),
	("Meeting Absent", 5000, "Teacher did not attend a scheduled staff meeting."),
	("Error in Question", 2000, "A mistake in a question or answer key prepared by the teacher. Amount varies by case."),
	("Weekly New Question Late Submission", 0, "Weekly new questions were not submitted on time. Amount to be set by TNC."),
)


def ensure_penalty_types():
	"""after_migrate: seed the SOW types once; never overwrite what the office edited."""
	if not frappe.db.exists("DocType", "Penalty Type"):
		return
	for name, amount, desc in SOW_PENALTY_TYPES:
		if not frappe.db.exists("Penalty Type", name):
			frappe.get_doc({"doctype": "Penalty Type", "penalty_type_name": name, "default_amount": amount, "description": desc}).insert(ignore_permissions=True)
	frappe.db.commit()
