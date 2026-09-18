# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Defaults the Admissions module relies on. Idempotent; runs after migrate."""
import frappe

CUSTOMER_GROUP = "Student"
ITEM_GROUP = "Fee Component"
SAC_EDUCATION = "999293"  # commercial training and coaching services


def ensure_guest_uploads():
	"""Public Admission Form: guests may upload the photo. Frappe's web form sends the first
	upload without a doctype, so the core allow-list cannot be used; admissions.guest_files
	guards what a guest may upload instead."""
	ss = frappe.get_single("System Settings")
	if not ss.allow_guests_to_upload_files or ss.allowed_doctypes_for_guest_uploads:
		frappe.db.set_single_value("System Settings", {"allow_guests_to_upload_files": 1, "allowed_doctypes_for_guest_uploads": ""})


def ensure_expense_claim_account():
	"""Expense Claim asks for a Payable Account unless the company has a default. v1 staff
	picked Creditors on every claim by hand; make it the default."""
	for company in frappe.get_all("Company", pluck="name"):
		if not frappe.db.get_value("Company", company, "default_expense_claim_payable_account"):
			acc = frappe.db.get_value("Company", company, "default_payable_account") or frappe.db.get_value("Account", {"account_type": "Payable", "is_group": 0, "company": company, "account_name": "Creditors"}, "name")
			if acc:
				frappe.db.set_value("Company", company, "default_expense_claim_payable_account", acc, update_modified=False)


EXPENSE_CLAIM_TYPES = {
	# type name -> expense account name (without the company suffix). Standard ERPNext accounts:
	# v1 removed its TNC-specific expense accounts on 16 Sep 2026 and maps its types to these.
	"Travel (Ola / Auto / Bus / Train)": "Travel Expenses",
	"Ola / Cab": "Travel Expenses",
	"Porter / Courier": "Postal Expenses",
	"Food & Refreshment": "Food Expenses",
	"Water": "Utility Expenses",
	"Stationery & Printing": "Print and Stationary",
	"Internet & Mobile Recharge": "Telephone Expenses",
	"Electricity": "Utility Expenses",
	"Medical": "Medical Expenses",
	"Marketing & Events": "Marketing Expenses",
	"Repairs & Maintenance": "Office Maintenance Expenses",
	"Other": "TNC Other -EXP",
	# v1's own five types, mapped exactly as v1 maps them today
	"Travel & Accommodation": "Travel Expenses",
	"Marketing & Program Expenses": "Marketing Expenses",
	"Office & Administration Expenses": "Office Maintenance Expenses",
	"Staff Welfare Expenses": "Staff Welfare Expenses",
}


def ensure_expense_claim_types():
	"""Expense Claim Types the mobile app offers, each posting to its own expense account."""
	for company in frappe.get_all("Company", pluck="name"):
		for type_name, account_name in EXPENSE_CLAIM_TYPES.items():
			acc = frappe.db.get_value("Account", {"account_name": account_name, "company": company, "is_group": 0}, "name")
			if not acc:
				continue
			if frappe.db.exists("Expense Claim Type", type_name):
				doc = frappe.get_doc("Expense Claim Type", type_name)
			else:
				doc = frappe.get_doc({"doctype": "Expense Claim Type", "expense_type": type_name})
			row = next((r for r in doc.accounts if r.company == company), None)
			if row:
				row.default_account = acc
			else:
				doc.append("accounts", {"company": company, "default_account": acc})
			doc.flags.ignore_permissions = True
			doc.save() if not doc.is_new() else doc.insert()


ENQUIRY_SOURCES = {
	# name -> (asks_referrer, show_on_web_form); order = order on the form and in the desk list
	"Friend / Existing Student": ("Student", 1),
	"Teacher": ("Teacher", 1),
	"Instagram / Facebook": (None, 1),
	"YouTube": (None, 1),
	"Google Search": (None, 1),
	"Institute Visit": (None, 1),
	"Other": (None, 1),
	# office-only channels
	"Walk-in": (None, 0), "Call": (None, 0), "College Data": (None, 0),
}
# old names folded into the list above
SOURCE_MERGES = {"Existing Student": "Friend / Existing Student", "Social Media": "Instagram / Facebook", "Website": "Other",
	"WhatsApp Forward": "Other", "Poster / Flyer / Newspaper": "Other", "College Visit": "Institute Visit", "College Visit / Seminar": "Institute Visit"}


def ensure_enquiry_sources():
	for old, new in SOURCE_MERGES.items():
		if frappe.db.exists("Enquiry Source", old):
			if not frappe.db.exists("Enquiry Source", new):
				frappe.get_doc({"doctype": "Enquiry Source", "source_name": new}).insert(ignore_permissions=True)
			frappe.db.sql("update `tabStudent Enquiry` set source=%s where source=%s", (new, old))
			frappe.delete_doc("Enquiry Source", old, force=1, ignore_permissions=True)
	for idx, (name, (asks, on_form)) in enumerate(ENQUIRY_SOURCES.items(), start=1):
		if frappe.db.exists("Enquiry Source", name):
			frappe.db.set_value("Enquiry Source", name, {"asks_referrer": asks, "show_on_web_form": on_form, "idx": idx}, update_modified=False)
		else:
			frappe.get_doc({"doctype": "Enquiry Source", "source_name": name, "asks_referrer": asks, "show_on_web_form": on_form, "idx": idx}).insert(ignore_permissions=True)


def ensure_defaults():
	ensure_guest_uploads()
	if frappe.db.get_single_value("TNC Settings", "demo_fee_amount") is None:
		frappe.db.set_single_value("TNC Settings", {"demo_fee_amount": 500, "demo_fee_adjust": 1})
	ensure_demo_fee_item()
	ensure_enquiry_sources()
	ensure_expense_claim_types()
	ensure_expense_claim_account()
	ensure_customer_group()
	ensure_item_group()
	ensure_sac()
	ensure_modes_of_payment()
	ensure_payment_terms()
	frappe.db.commit()


def ensure_customer_group():
	if not frappe.db.exists("Customer Group", CUSTOMER_GROUP):
		frappe.get_doc({"doctype": "Customer Group", "customer_group_name": CUSTOMER_GROUP, "parent_customer_group": "All Customer Groups", "is_group": 0}).insert(ignore_permissions=True)


def ensure_item_group():
	if not frappe.db.exists("Item Group", ITEM_GROUP):
		frappe.get_doc({"doctype": "Item Group", "item_group_name": ITEM_GROUP, "parent_item_group": "All Item Groups", "is_group": 0}).insert(ignore_permissions=True)


def ensure_sac():
	if not frappe.db.exists("GST HSN Code", SAC_EDUCATION):
		frappe.get_doc({"doctype": "GST HSN Code", "hsn_code": SAC_EDUCATION, "description": "Commercial training and coaching services"}).insert(ignore_permissions=True)


def ensure_fee_item(course):
	"""One non-stock service Item per Course, named 'Fee - <course>'. Returns item_code."""
	code = f"Fee - {course.course_name}"
	if frappe.db.exists("Item", code):
		frappe.db.set_value("Item", code, "standard_rate", course.default_fee, update_modified=False)
		return code
	ensure_item_group(); ensure_sac()
	frappe.get_doc({"doctype": "Item", "item_code": code, "item_name": code, "item_group": ITEM_GROUP, "stock_uom": "Nos",
		"is_stock_item": 0, "is_sales_item": 1, "is_purchase_item": 0, "include_item_in_manufacturing": 0,
		"gst_hsn_code": SAC_EDUCATION, "standard_rate": course.default_fee, "description": f"Course fee for {course.course_name}"}).insert(ignore_permissions=True)
	return code


WORKSPACE = "TNC Admissions"
NUMBER_CARDS = [
	("Enquiries this month", "Student Enquiry", [["enquiry_date", "Timespan", "this month"]], "Blue"),
	("Demos this week", "Demo Class", [["demo_date", "Timespan", "this week"], ["result", "=", "Scheduled"]], "Orange"),
	("Admissions this month", "Student", [["creation", "Timespan", "this month"]], "Green"),
	("Enrolments active", "Student Batch Enrollment", [["docstatus", "=", 1], ["status", "=", "Active"]], "Green"),
	("Follow-ups overdue", None, "tnc_v2_360ithub.admissions.followups.count_overdue_followups", "Red"),
	("Follow-ups due today", "Student Follow-Up", [["status", "=", "Open"], ["next_follow_up_date", "Timespan", "today"]], "Orange"),
	("Fee follow-ups open", "Student Follow-Up", [["status", "=", "Open"], ["purpose", "=", "Fee"]], "Red"),
	("Form not submitted by student", "Student", [["status", "=", "Active"], ["terms_accepted", "=", 0]], "Orange"),
]


def ensure_workspace():
	"""'Admissions' workspace: five number cards and shortcuts, same style as TNC Task.
	Idempotent; exported as fixtures (module Admissions)."""
	for label, dt, filters, color in NUMBER_CARDS:
		if dt is None:  # custom card backed by a whitelisted method
			if not frappe.db.exists("Number Card", label):
				frappe.get_doc({"doctype": "Number Card", "name": label, "label": label, "type": "Custom", "method": filters, "is_public": 1,
					"show_percentage_stats": 0, "color": color, "module": "TNC v2"}).insert(ignore_permissions=True)
			else:
				frappe.db.set_value("Number Card", label, {"type": "Custom", "method": filters, "filters_json": None, "document_type": None, "show_percentage_stats": 0}, update_modified=False)
			continue
		if frappe.db.exists("Number Card", label):
			frappe.db.set_value("Number Card", label, "filters_json", frappe.as_json([[dt, f[0], f[1], f[2], False] for f in filters]), update_modified=False)
			continue
		frappe.get_doc({"doctype": "Number Card", "name": label, "label": label, "type": "Document Type", "document_type": dt, "function": "Count",
			"filters_json": frappe.as_json([[dt, f[0], f[1], f[2], False] for f in filters]), "is_public": 1, "show_percentage_stats": 1, "stats_time_interval": "Monthly", "color": color, "module": "TNC v2"}).insert(ignore_permissions=True)
	shortcuts = [("Follow-ups", "Page", "follow-ups", "Red"), ("Share Forms", "Page", "share-forms", "Grey"), ("Student Enquiry", "DocType", "Student Enquiry", "Blue"), ("Demo Class", "DocType", "Demo Class", "Orange"), ("Student", "DocType", "Student", "Green"),
		("Enrol in Batch", "DocType", "Student Batch Enrollment", "Green"), ("Batches", "DocType", "Student Batch", "Grey"),
		("Sales Orders", "DocType", "Sales Order", "Grey"), ("Enquiry Funnel", "Report", "Enquiry Funnel", "Blue")]
	content = [{"id": "hdr", "type": "header", "data": {"text": "<span class=\"h4\"><b>Admissions</b></span>", "col": 12}}]
	content += [{"id": f"nc{i}", "type": "number_card", "data": {"number_card_name": label, "col": 3 if i else 3}} for i, (label, *_r) in enumerate(NUMBER_CARDS)]
	content += [{"id": "sh", "type": "header", "data": {"text": "<span class=\"h4\"><b>Quick actions</b></span>", "col": 12}}]
	content += [{"id": f"sc{i}", "type": "shortcut", "data": {"shortcut_name": s[0], "col": 3}} for i, s in enumerate(shortcuts)]
	is_new = not frappe.db.exists("Workspace", WORKSPACE)
	if is_new:
		ws = frappe.get_doc({"doctype": "Workspace", "name": WORKSPACE, "label": WORKSPACE, "title": WORKSPACE, "module": "TNC v2", "public": 1, "icon": "education", "sequence_id": 2.0})
	else:
		ws = frappe.get_doc("Workspace", WORKSPACE)
		ws.set("shortcuts", []); ws.set("number_cards", [])
	for label, *_r in NUMBER_CARDS:
		ws.append("number_cards", {"label": label, "number_card_name": label})
	for s in shortcuts:
		ws.append("shortcuts", {"label": s[0], "type": s[1], "link_to": s[2], "color": s[3]})
	ws.content = frappe.as_json(content)
	ws.roles = []
	for r in ("TNC Employees", "TNC Manager", "TNC Super Admin"):
		ws.append("roles", {"role": r})
	ws.flags.ignore_permissions = True
	ws.insert(ignore_permissions=True) if is_new else ws.save(ignore_permissions=True)
	frappe.db.commit()
	print(f"workspace {WORKSPACE!r}: {len(NUMBER_CARDS)} cards, {len(shortcuts)} shortcuts")


MODES_OF_PAYMENT = [
	# (name, type, account name without company suffix)
	("Cash", "Cash", "Cash"),
	("UPI", "Bank", "BOI TNC A/c - Bank of india"),
	("Bank Transfer", "Bank", "BOI TNC A/c - Bank of india"),
	("Card", "Bank", "BOI TNC A/c - Bank of india"),
	("Cheque", "Bank", "BOI TNC A/c - Bank of india"),
]


DEMO_FEE_ITEM = "Demo Fee"
DEMO_FEE_ACCOUNT = "Demo Fee Income"


def ensure_demo_fee_item(company=None):
	"""Service item 'Demo Fee' posting to its own income account, so kept demo fees are visible."""
	company = company or frappe.defaults.get_global_default("company") or frappe.db.get_single_value("Global Defaults", "default_company")
	ensure_item_group(); ensure_sac()
	acc = frappe.db.get_value("Account", {"account_name": DEMO_FEE_ACCOUNT, "company": company}, "name")
	if not acc:
		parent = frappe.db.get_value("Account", {"account_name": "Direct Income", "company": company, "is_group": 1}, "name") or frappe.db.get_value("Account", {"root_type": "Income", "company": company, "is_group": 1, "parent_account": ["is", "not set"]}, "name")
		acc = frappe.get_doc({"doctype": "Account", "account_name": DEMO_FEE_ACCOUNT, "parent_account": parent, "company": company, "root_type": "Income", "report_type": "Profit and Loss", "account_type": "Income Account"}).insert(ignore_permissions=True).name
	if not frappe.db.exists("Item", DEMO_FEE_ITEM):
		frappe.get_doc({"doctype": "Item", "item_code": DEMO_FEE_ITEM, "item_name": DEMO_FEE_ITEM, "item_group": ITEM_GROUP, "stock_uom": "Nos",
			"is_stock_item": 0, "is_sales_item": 1, "is_purchase_item": 0, "include_item_in_manufacturing": 0, "gst_hsn_code": SAC_EDUCATION,
			"description": "Demo class fee", "item_defaults": [{"company": company, "income_account": acc}]}).insert(ignore_permissions=True)
	elif not frappe.db.exists("Item Default", {"parent": DEMO_FEE_ITEM, "company": company}):
		it = frappe.get_doc("Item", DEMO_FEE_ITEM); it.append("item_defaults", {"company": company, "income_account": acc}); it.save(ignore_permissions=True)
	return DEMO_FEE_ITEM


def ensure_modes_of_payment(company="TNC Nursing"):
	"""Modes the Receive Payment dialog offers, each with its account for the company."""
	abbr = frappe.db.get_value("Company", company, "abbr")
	for name, mtype, account in MODES_OF_PAYMENT:
		acc = f"{account} - {abbr}"
		if not frappe.db.exists("Account", acc):
			print(f"skip {name}: account {acc} missing"); continue
		if frappe.db.exists("Mode of Payment", name):
			doc = frappe.get_doc("Mode of Payment", name)
		else:
			doc = frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": name, "type": mtype, "enabled": 1})
		row = next((a for a in doc.accounts if a.company == company), None)
		if row:
			row.default_account = acc
		else:
			doc.append("accounts", {"company": company, "default_account": acc})
		doc.enabled = 1
		doc.flags.ignore_permissions = True
		doc.save() if not doc.is_new() else doc.insert()
	frappe.db.commit()
	print("modes of payment ready:", [m[0] for m in MODES_OF_PAYMENT])


def ensure_payment_terms(upto=12):
	"""Generic Payment Terms 'Instalment 1..N'. ERPNext allocates a Payment Entry to
	the order's Payment Schedule only when each row carries a Payment Term, so every
	enrolment schedule row is stamped with one of these."""
	for i in range(1, upto + 1):
		name = f"Instalment {i}"
		if not frappe.db.exists("Payment Term", name):
			frappe.get_doc({"doctype": "Payment Term", "payment_term_name": name, "invoice_portion": 0, "due_date_based_on": "Day(s) after invoice date", "credit_days": 0, "description": f"Fee instalment {i}"}).insert(ignore_permissions=True)
	return upto


def payment_term_for(i):
	name = f"Instalment {i}"
	if not frappe.db.exists("Payment Term", name):
		ensure_payment_terms(max(i, 12))
	return name


def stamp_payment_terms_on_orders():
	"""Backfill payment_term on schedule rows of enrolment Sales Orders made before
	the terms existed (dev site only; new orders get them at creation)."""
	ensure_payment_terms()
	n = 0
	for so in frappe.get_all("Sales Order", filters={"custom_student_batch_enrollment": ["is", "set"]}, pluck="name"):
		rows = frappe.get_all("Payment Schedule", filters={"parent": so, "parenttype": "Sales Order"}, fields=["name", "idx", "payment_term"], order_by="idx")
		for r in rows:
			if not r.payment_term:
				frappe.db.set_value("Payment Schedule", r.name, "payment_term", payment_term_for(r.idx), update_modified=False); n += 1
	frappe.db.commit()
	print(f"stamped {n} schedule rows")


def fix_enrolment_orders_delivery_flag():
	"""Dev-site repair: enrolment Sales Orders made before skip_delivery_note was set.
	Sets the flag and recomputes the status (To Bill / Completed)."""
	for name in frappe.get_all("Sales Order", filters={"custom_student_batch_enrollment": ["is", "set"], "docstatus": 1, "skip_delivery_note": 0}, pluck="name"):
		frappe.db.set_value("Sales Order", name, "skip_delivery_note", 1, update_modified=False)
		so = frappe.get_doc("Sales Order", name)
		so.set_status(update=True)
		print(name, "->", frappe.db.get_value("Sales Order", name, "status"))
	frappe.db.commit()
