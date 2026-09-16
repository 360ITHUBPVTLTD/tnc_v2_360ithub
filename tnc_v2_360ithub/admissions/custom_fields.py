# Copyright (c) 2026, 360ITHub and contributors
"""Back-links from standard ERPNext documents to the admission records, so the
Sales Order shows which student and batch it belongs to and reports can join."""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FIELDS = {
	# Client meeting 14 Sep: every claim is tagged to the online or the offline classes side.
	"Expense Claim": [
		{"fieldname": "custom_expense_for", "fieldtype": "Select", "label": "Expense For", "options": "\nOnline\nOffline", "insert_after": "expense_approver", "in_list_view": 1, "in_standard_filter": 1, "allow_on_submit": 0, "module": "TNC v2"},
	],
	"Sales Order": [
		{"fieldname": "admissions_section", "fieldtype": "Section Break", "label": "Admission", "insert_after": "customer_name", "collapsible": 0, "module": "TNC v2"},
		{"fieldname": "student", "fieldtype": "Link", "label": "Student", "options": "Student", "insert_after": "admissions_section", "read_only": 1, "in_standard_filter": 1, "module": "TNC v2"},
		{"fieldname": "student_batch", "fieldtype": "Link", "label": "Student Batch", "options": "Student Batch", "insert_after": "student", "read_only": 1, "in_standard_filter": 1, "module": "TNC v2"},
		{"fieldname": "admissions_cb", "fieldtype": "Column Break", "insert_after": "student_batch", "module": "TNC v2"},
		{"fieldname": "student_batch_enrollment", "fieldtype": "Link", "label": "Enrolment", "options": "Student Batch Enrollment", "insert_after": "admissions_cb", "read_only": 1, "module": "TNC v2"},
	],
	"Sales Invoice": [
		{"fieldname": "student", "fieldtype": "Link", "label": "Student", "options": "Student", "insert_after": "customer_name", "read_only": 1, "in_standard_filter": 1, "module": "TNC v2"},
	],
	"Payment Entry": [
		{"fieldname": "student", "fieldtype": "Link", "label": "Student", "options": "Student", "insert_after": "party_name", "read_only": 1, "in_standard_filter": 1, "module": "TNC v2"},
	],
}


PROPERTY_SETTERS = [
	# (doctype, fieldname, property, value, property_type)
	("Sales Order", "payment_schedule_section", "label", "Payment Terms", "Data"),
	# instalment grid: show what was paid and what is left; hide the accountant-only portion column
	("Payment Schedule", "paid_amount", "in_list_view", "1", "Check"),
	("Payment Schedule", "paid_amount", "columns", "2", "Int"),
	("Payment Schedule", "outstanding", "in_list_view", "1", "Check"),
	("Payment Schedule", "outstanding", "columns", "2", "Int"),
	("Payment Schedule", "invoice_portion", "in_list_view", "0", "Check"),
	("Payment Schedule", "payment_amount", "columns", "2", "Int"),
	("Payment Schedule", "due_date", "columns", "2", "Int"),
	("Payment Schedule", "description", "columns", "2", "Int"),
	("Payment Schedule", "payment_term", "in_list_view", "0", "Check"),
]


def ensure_custom_fields():
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	create_custom_fields(FIELDS, ignore_validate=True, update=True)
	for dt, fieldname, prop, value, ptype in PROPERTY_SETTERS:
		make_property_setter(dt, fieldname, prop, value, ptype, validate_fields_for_doctype=False)
		frappe.db.set_value("Property Setter", {"doc_type": dt, "field_name": fieldname, "property": prop}, "module", "TNC v2", update_modified=False)
	# every Sales Invoice here is a fee receipt: print it as one by default
	make_property_setter("Sales Invoice", None, "default_print_format", "Fee Receipt", "Data", for_doctype=True, validate_fields_for_doctype=False)
	frappe.db.set_value("Property Setter", {"doc_type": "Sales Invoice", "property": "default_print_format"}, "module", "TNC v2", update_modified=False)
	frappe.db.commit()
