# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Expense Claim server defaults (checklist row C8).

The desk form copies the approver from the Employee in the browser; the mobile
app posts the claim without one, so the field stayed empty and the claim could
not be submitted. Fill it server-side from Employee.expense_approver when missing.
"""
import frappe
from frappe import _
from frappe.utils import cint, escape_html


def set_defaults(doc, method=None):
	if doc.employee and not doc.expense_approver:
		doc.expense_approver = frappe.db.get_value("Employee", doc.employee, "expense_approver")
	require_decision_comment(doc)
	keep_employee(doc)


def keep_employee(doc):
	"""A claim stays with the employee who made it. Older app builds sent the logged-in user's
	employee on every update, so an approver editing a claim silently took it over."""
	if doc.is_new():
		return
	before = doc.get_doc_before_save()
	if before and before.employee and doc.employee != before.employee and "System Manager" not in frappe.get_roles():
		frappe.throw(_("The employee on an expense claim cannot be changed. This claim belongs to {0}.").format(before.employee_name or before.employee))


def require_decision_comment(doc):
	"""Client meeting 17 Sep: approving or rejecting a claim needs a comment, on the web and in the app."""
	if doc.approval_status not in ("Approved", "Rejected"):
		return
	before = doc.get_doc_before_save() if not doc.is_new() else None
	changed = not before or before.approval_status != doc.approval_status
	if changed and not (doc.get("custom_approval_comment") or "").strip():
		frappe.throw(_("Please add a comment for the {0} of this expense claim.").format(_("approval") if doc.approval_status == "Approved" else _("rejection")))


# ---- Review step (optional): the approver asks, the employee answers, then approve or reject.
# Rejecting directly stays possible; review is for when the approver wants an answer first.

def _can_review(doc):
	user = frappe.session.user
	roles = frappe.get_roles(user)
	return user == "Administrator" or user == doc.expense_approver or "Expense Approver" in roles or "System Manager" in roles


def _employee_user(doc):
	return frappe.db.get_value("Employee", doc.employee, "user_id") if doc.employee else None


@frappe.whitelist()
def request_review(name, comment):
	"""Approver sends a draft claim back to the employee with a comment. Used by the desk and the app."""
	from tnc_v2_360ithub import notifications
	doc = frappe.get_doc("Expense Claim", name)
	if not _can_review(doc):
		frappe.throw(_("Only the expense approver can send a claim for review."), frappe.PermissionError)
	if doc.docstatus != 0 or doc.approval_status != "Draft":
		frappe.throw(_("Only a draft claim can be sent for review."))
	comment = (comment or "").strip()
	if not comment:
		frappe.throw(_("Please write what the employee should check or change."))
	doc.db_set({"custom_review_status": "Review Requested", "custom_review_comment": comment, "custom_review_reply": "",
		"custom_review_count": cint(doc.custom_review_count) + 1})
	doc.add_comment("Comment", _("Review requested: {0}").format(escape_html(comment)))
	emp_user = _employee_user(doc)
	if emp_user:
		notifications.notify_users([emp_user], doc, _("Your expense claim {0} needs a review: {1}").format(doc.name, comment), title=_("Expense claim: review requested"))
	return {"review_status": "Review Requested", "review_count": cint(doc.custom_review_count) + 1}


@frappe.whitelist()
def reply_review(name, comment):
	"""The claim's employee answers the review. The claim stays draft; the approver decides next."""
	from tnc_v2_360ithub import notifications
	doc = frappe.get_doc("Expense Claim", name)
	user = frappe.session.user
	if user not in ("Administrator", doc.owner, _employee_user(doc)):
		frappe.throw(_("Only the employee who made this claim can reply to the review."), frappe.PermissionError)
	if doc.docstatus != 0 or doc.custom_review_status != "Review Requested":
		frappe.throw(_("No review is pending on this claim."))
	comment = (comment or "").strip()
	if not comment:
		frappe.throw(_("Please write your reply."))
	doc.db_set({"custom_review_status": "Reviewed", "custom_review_reply": comment})
	doc.add_comment("Comment", _("Review reply: {0}").format(escape_html(comment)))
	if doc.expense_approver:
		notifications.notify_users([doc.expense_approver], doc, _("{0} replied on expense claim {1}: {2}").format(doc.employee_name or doc.employee, doc.name, comment), title=_("Expense claim: reviewed"))
	return {"review_status": "Reviewed"}


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
