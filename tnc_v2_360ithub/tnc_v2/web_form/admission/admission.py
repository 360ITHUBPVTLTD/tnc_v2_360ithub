# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
import frappe


def get_context(context):
	context.no_cache = 1
	context.show_sidebar = False
	context.title = context.get("title") or frappe.db.get_value("Web Form", frappe.form_dict.get("web_form") or "", "title")
