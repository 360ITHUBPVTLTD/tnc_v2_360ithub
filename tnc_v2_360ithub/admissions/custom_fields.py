# Copyright (c) 2026, 360ITHub and contributors
"""Core-doctype customizations (Sales Order / Sales Invoice / Payment Entry student links, Expense
Claim custom_expense_for, Task and Payment Schedule setters, ...) live as files in
tnc_v2/custom/<doctype>.json, made with Customize Form -> Export Customizations and synced on
every migrate. Admins may edit them on the site through Customize Form / Custom Field.

This module only tidies up: it removes renamed legacy fields and keeps our custom fields
editable (Customize Form refuses edits on fields flagged "system generated").
"""
import frappe

# (doctype, old fieldname, new fieldname): fields renamed to the custom_ prefix. On migrate the new
# field arrives from tnc_v2/custom/*.json first; then data is copied across and the old field removed.
RENAMED_CUSTOM_FIELDS = [
	("Expense Claim", "expense_for", "custom_expense_for"),
	("Expense Claim", "payment_type", None),
	("Sales Order", "student", "custom_student"),
	("Sales Order", "student_batch", "custom_student_batch"),
	("Sales Order", "student_batch_enrollment", "custom_student_batch_enrollment"),
	("Sales Order", "admissions_section", None),
	("Sales Order", "admissions_cb", None),
	("Sales Invoice", "student", "custom_student"),
	("Payment Entry", "student", "custom_student"),
]


def ensure_custom_fields():
	for dt, old, new in RENAMED_CUSTOM_FIELDS:
		cols = frappe.db.get_table_columns(dt)
		if new and old in cols and new in cols:
			frappe.db.sql(f"update `tab{dt}` set `{new}` = `{old}` where ifnull(`{new}`, '') = '' and ifnull(`{old}`, '') != ''")
		if frappe.db.exists("Custom Field", f"{dt}-{old}"):
			frappe.delete_doc("Custom Field", f"{dt}-{old}", force=1, ignore_permissions=True)
	frappe.db.sql("update `tabCustom Field` set is_system_generated = 0 where module = 'TNC v2' and is_system_generated = 1")
	frappe.db.commit()
	frappe.clear_cache()
