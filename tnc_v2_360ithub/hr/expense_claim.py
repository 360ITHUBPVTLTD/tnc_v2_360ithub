# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Expense Claim server defaults (checklist row C8).

The desk form copies the approver from the Employee in the browser; the mobile
app posts the claim without one, so the field stayed empty and the claim could
not be submitted. Fill it server-side from Employee.expense_approver when missing.
"""
import frappe
from frappe import _


def set_defaults(doc, method=None):
	if doc.employee and not doc.expense_approver:
		doc.expense_approver = frappe.db.get_value("Employee", doc.employee, "expense_approver")
	require_decision_comment(doc)


def require_decision_comment(doc):
	"""Client meeting 17 Sep: approving or rejecting a claim needs a comment, on the web and in the app."""
	if doc.approval_status not in ("Approved", "Rejected"):
		return
	before = doc.get_doc_before_save() if not doc.is_new() else None
	changed = not before or before.approval_status != doc.approval_status
	if changed and not (doc.get("custom_approval_comment") or "").strip():
		frappe.throw(_("Please add a comment for the {0} of this expense claim.").format(_("approval") if doc.approval_status == "Approved" else _("rejection")))


def guard_payment_reference(doc, method=None):
	"""Payment Entry / Journal Entry validate: no payment against a rejected or unsubmitted
	Expense Claim, even when the entry is typed by hand instead of from the Create button."""
	rows = doc.get("references") if doc.doctype == "Payment Entry" else doc.get("accounts")
	for r in rows or []:
		if r.get("reference_doctype") != "Expense Claim" or not r.get("reference_name"):
			continue
		status, docstatus = frappe.db.get_value("Expense Claim", r.reference_name, ["approval_status", "docstatus"]) or (None, None)
		if status == "Rejected":
			frappe.throw(frappe._("Expense Claim {0} is rejected. Payment cannot be made against it.").format(r.reference_name))
		if docstatus != 1:
			frappe.throw(frappe._("Expense Claim {0} is not submitted. Payment cannot be made against it.").format(r.reference_name))
