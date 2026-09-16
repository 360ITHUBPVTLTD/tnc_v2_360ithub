# Copyright (c) 2026, 360ITHub and contributors
"""Core-doctype customizations (Sales Order / Sales Invoice / Payment Entry student links, Expense
Claim custom_expense_for, Task and Payment Schedule setters, ...) live as files in
tnc_v2/custom/<doctype>.json, made with Customize Form -> Export Customizations and synced on
every migrate. Admins may edit them on the site through Customize Form / Custom Field.

This module only tidies up: it removes renamed legacy fields and keeps our custom fields
editable (Customize Form refuses edits on fields flagged "system generated").
"""
import frappe

LEGACY_CUSTOM_FIELDS = ["Expense Claim-expense_for", "Expense Claim-payment_type"]  # renamed to custom_*


def ensure_custom_fields():
	for name in LEGACY_CUSTOM_FIELDS:
		if frappe.db.exists("Custom Field", name):
			frappe.delete_doc("Custom Field", name, force=1, ignore_permissions=True)
	frappe.db.sql("update `tabCustom Field` set is_system_generated = 0 where module = 'TNC v2' and is_system_generated = 1")
	frappe.db.commit()
