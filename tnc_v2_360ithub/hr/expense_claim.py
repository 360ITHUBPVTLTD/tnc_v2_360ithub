# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Expense Claim server defaults (checklist row C8).

The desk form copies the approver from the Employee in the browser; the mobile
app posts the claim without one, so the field stayed empty and the claim could
not be submitted. Fill it server-side from Employee.expense_approver when missing.
"""
import frappe


def set_defaults(doc, method=None):
	if doc.employee and not doc.expense_approver:
		doc.expense_approver = frappe.db.get_value("Employee", doc.employee, "expense_approver")
