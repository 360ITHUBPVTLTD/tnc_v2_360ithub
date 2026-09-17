# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Remove the `custom_kkkkk` test field from Expense Claim.

Removing a field from `custom/<doctype>.json` does not remove it from a site.
`bench migrate` calls `sync_customizations_for_doctype`, whose Custom Field branch
iterates the JSON and inserts what is missing or updates what is already there -
it never looks for fields that exist in the database but are absent from the file.
(Custom DocPerm in the same function *is* deleted and reinserted, so the asymmetry
is deliberate, not an oversight.)

So a removal needs an explicit patch. Adding and editing fields still work through
the JSON alone.
"""

import frappe

FIELD = "Expense Claim-custom_kkkkk"


def execute():
	# Custom Field.on_trash drops the column, clears the doctype cache and removes
	# any Property Setter rows for the field, so delete_doc is all that is needed.
	frappe.delete_doc("Custom Field", FIELD, ignore_missing=True, force=True)
