# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Mobile-app compatibility for calls the Flutter app hard-codes.

The app registers its push token with frappe.client.set_value on
Employee.custom_fcm_token. Only HR roles may write Employee, so for every
ordinary user that call failed with "does not have doctype access via role
permission" (checklist row C11). Instead of granting TNC roles write access to
Employee, this override lets a user set that single field on the Employee that
is linked to them, and hands every other call to the stock implementation.
Wired through override_whitelisted_methods in hooks.py.
"""
import frappe
from frappe.client import set_value as _frappe_set_value

OWN_EMPLOYEE_FIELDS = {"custom_fcm_token"}


@frappe.whitelist(methods=["POST", "PUT"])
def set_value(doctype, name, fieldname, value=None):
	if (
		doctype == "Employee"
		and isinstance(fieldname, str)
		and fieldname in OWN_EMPLOYEE_FIELDS
		and frappe.session.user not in ("Guest", "Administrator")
		and frappe.db.get_value("Employee", name, "user_id") == frappe.session.user
	):
		frappe.db.set_value("Employee", name, fieldname, value, update_modified=False)
		return frappe.db.get_value("Employee", name, ["name", fieldname], as_dict=True)
	return _frappe_set_value(doctype, name, fieldname, value)
