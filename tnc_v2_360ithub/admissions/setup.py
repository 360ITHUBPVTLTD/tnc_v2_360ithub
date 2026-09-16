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


def ensure_defaults():
	# Everything below hangs off records the setup wizard creates: the root nodes of the
	# Customer Group and Item Group trees, and the company the modes of payment belong to.
	# On a site where the wizard has not been run, the first insert raises
	# LinkValidationError ("Could not find Parent Customer Group: All Customer Groups"),
	# and because after_migrate propagates, that takes the whole `bench migrate` down with
	# it. Skip until the site is set up; the next migrate applies these.
	if not frappe.db.get_single_value("System Settings", "setup_complete"):
		print("admissions defaults skipped: setup wizard not complete")
		return
	ensure_guest_uploads()
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
		("Enrol in Batch", "DocType", "Student Batch Enrollment", "Green"), ("Student Batch", "DocType", "Student Batch", "Grey"), ("Course", "DocType", "Course", "Grey"),
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
	for so in frappe.get_all("Sales Order", filters={"student_batch_enrollment": ["is", "set"]}, pluck="name"):
		rows = frappe.get_all("Payment Schedule", filters={"parent": so, "parenttype": "Sales Order"}, fields=["name", "idx", "payment_term"], order_by="idx")
		for r in rows:
			if not r.payment_term:
				frappe.db.set_value("Payment Schedule", r.name, "payment_term", payment_term_for(r.idx), update_modified=False); n += 1
	frappe.db.commit()
	print(f"stamped {n} schedule rows")


def fix_enrolment_orders_delivery_flag():
	"""Dev-site repair: enrolment Sales Orders made before skip_delivery_note was set.
	Sets the flag and recomputes the status (To Bill / Completed)."""
	for name in frappe.get_all("Sales Order", filters={"student_batch_enrollment": ["is", "set"], "docstatus": 1, "skip_delivery_note": 0}, pluck="name"):
		frappe.db.set_value("Sales Order", name, "skip_delivery_note", 1, update_modified=False)
		so = frappe.get_doc("Sales Order", name)
		so.set_status(update=True)
		print(name, "->", frappe.db.get_value("Sales Order", name, "status"))
	frappe.db.commit()
