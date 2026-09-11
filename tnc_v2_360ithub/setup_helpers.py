# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt

"""One-off, idempotent site setup steps used while bringing v1 across.

Run with `bench --site <site> execute tnc_v2_360ithub.setup_helpers.<fn> --args '[...]'`.
Each function prints what it did and commits only when told to.
"""

import traceback

import frappe


def align_company(old_name, new_name, new_abbr, commit=True):
	"""Rename the site's Company and its abbreviation so migrated documents
	(Purchase Invoices, Payment Entries) can reference the same company as v1.
	Safe only while the company has no transactions."""
	try:
		if frappe.db.exists("Company", old_name) and old_name != new_name:
			frappe.rename_doc("Company", old_name, new_name, force=True)
			print(f"renamed Company {old_name!r} -> {new_name!r}")
		company = frappe.get_doc("Company", new_name)
		old_abbr = company.abbr
		if old_abbr != new_abbr:
			# ERPNext v15 has no helper for this; rename every " - <abbr>" suffixed
			# master ourselves. Safe only on a company with no transactions.
			for dt in ("Account", "Cost Center", "Warehouse"):
				for name in frappe.get_all(dt, filters={"company": new_name}, pluck="name"):
					if name.endswith(f" - {old_abbr}"):
						frappe.rename_doc(dt, name, name[: -len(f" - {old_abbr}")] + f" - {new_abbr}", force=True)
			frappe.db.set_value("Company", new_name, "abbr", new_abbr)
			frappe.clear_cache()
			print(f"abbr {old_abbr!r} -> {new_abbr!r}")
		frappe.db.set_single_value("Global Defaults", "default_company", new_name)
		if commit:
			frappe.db.commit()
		row = frappe.db.get_value("Company", new_name, ["name", "abbr"], as_dict=True)
		print("company now:", dict(row), "| accounts:", frappe.db.count("Account", {"company": new_name}))
		return dict(row)
	except Exception:
		traceback.print_exc()
		frappe.db.rollback()
		raise


def fix_abbr_suffixes(company, abbr, commit=True):
	"""Repair master names that ended up with a doubled suffix (e.g. 'Main - IND - 3')
	after align_company: ERPNext re-appends the company abbr on rename, so rename to
	the bare base name and let it add ' - <abbr>' once."""
	fixed = 0
	for dt in ("Account", "Cost Center", "Warehouse"):
		for name in frappe.get_all(dt, filters={"company": company}, pluck="name"):
			parts = name.split(" - ")
			# strip every trailing token that is an abbreviation (current or stale)
			while len(parts) > 1 and (parts[-1] == abbr or len(parts[-1]) <= 3):
				parts.pop()
			base = " - ".join(parts)
			expected = f"{base} - {abbr}"
			if name != expected:
				new = frappe.rename_doc(dt, name, base, force=True)
				fixed += 1
				if new != expected:
					print(f"  WARN {dt} {name!r} -> {new!r} (expected {expected!r})")
	if commit:
		frappe.db.commit()
	bad = [n for dt in ("Account", "Cost Center", "Warehouse") for n in frappe.get_all(dt, filters={"company": company}, pluck="name") if not n.endswith(f" - {abbr}") or n.endswith(f" - {abbr} - {abbr}")]
	print(f"renamed {fixed}; still odd: {bad[:10]}")
	return fixed


# Role permissions v1 granted through Custom DocPerm on standard doctypes, taken
# from v1_schema_export/custom_docperm/all.json (live tnc.360ithub.com, 2026-09-11).
# Rows on the TNC app's own doctypes live in their doctype JSON instead, and
# v1's "Institute Management Admin Settings" rows are carried by TNC Settings.
# Deliberately not carried: ('User', 'Academics User') - the Education app is
# not installed on v2.
V1_ROLE_PERMISSIONS = [
	# (parent, role, permlevel, {flag: 1})
	("Employee", "TNC Employees", 0, {"read": 1}),
	("Employee", "TNC Super Admin", 0, {"read": 1, "write": 1, "create": 1, "report": 1, "select": 1}),
	("Payment Entry", "TNC Employees", 0, {"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1, "amend": 1, "select": 1}),
	("Payment Entry", "TNC Manager", 0, {"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1, "export": 1, "select": 1}),
	("Payment Entry", "TNC Super Admin", 0, {"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1, "amend": 1, "print": 1, "select": 1}),
	("Purchase Invoice", "TNC Manager", 0, {"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1, "export": 1, "print": 1, "select": 1}),
	("Supplier", "TNC Manager", 0, {"read": 1, "write": 1, "create": 1, "report": 1, "export": 1, "select": 1}),
	("Supplier", "TNC Super Admin", 0, {"read": 1, "write": 1, "create": 1, "report": 1, "export": 1, "email": 1, "select": 1}),
	("Supplier", "TNC Teachers", 0, {"read": 1, "write": 1, "create": 1, "report": 1, "export": 1, "import": 1, "print": 1, "email": 1, "share": 1, "select": 1}),
	("User", "TNC Employees", 1, {"read": 1, "write": 1, "export": 1}),
	("User", "TNC Manager", 0, {"read": 1, "write": 1, "create": 1, "export": 1, "select": 1}),
	("User", "TNC Super Admin", 0, {"read": 1, "write": 1, "create": 1, "report": 1, "print": 1, "select": 1}),
]

PERM_FLAGS = ("read", "write", "create", "delete", "submit", "cancel", "amend", "report",
	"export", "import", "print", "email", "share", "select", "if_owner")


def apply_v1_role_permissions(commit=True):
	"""Grant the TNC roles the same access to standard doctypes as on v1.
	Idempotent: existing rows are updated flag by flag, missing rows are added.
	Uses frappe.permissions so standard DocPerm rows are copied to Custom DocPerm
	first and nothing already granted is lost."""
	from frappe.permissions import add_permission, update_permission_property

	changed = 0
	for parent, role, permlevel, flags in V1_ROLE_PERMISSIONS:
		if not frappe.db.exists("Role", role):
			print(f"skip {parent}/{role}: role missing")
			continue
		name = frappe.db.get_value("Custom DocPerm", {"parent": parent, "role": role, "permlevel": permlevel})
		if not name:
			add_permission(parent, role, permlevel)
			name = frappe.db.get_value("Custom DocPerm", {"parent": parent, "role": role, "permlevel": permlevel})
			changed += 1
			print(f"added {parent} / {role} / level {permlevel}")
		current = frappe.db.get_value("Custom DocPerm", name, PERM_FLAGS, as_dict=True)
		for flag in PERM_FLAGS:
			want = int(flags.get(flag, 0))
			if int(current.get(flag) or 0) != want:
				update_permission_property(parent, role, permlevel, flag, want, validate=False)
				changed += 1
				print(f"  {parent} / {role}: {flag} -> {want}")
	if commit:
		frappe.db.commit()
	print(f"done, {changed} change(s)")
	return changed


def ensure_recurring_task_report(commit=True):
	"""Create v1's 'Recurring task report' (Report Builder on Recurring Task,
	checklist row A20) if it is missing. Definition copied from
	v1_schema_export/report. Shipped onward as a Report fixture (module Tasks)."""
	name = "Recurring task report"
	if frappe.db.exists("Report", name):
		print(f"{name!r} already exists")
		return
	frappe.get_doc({
		"doctype": "Report",
		"report_name": name,
		"ref_doctype": "Recurring Task",
		"report_type": "Report Builder",
		"is_standard": "No",
		"module": "Tasks",
		"json": frappe.as_json({
			"filters": [],
			"fields": [["name", "Recurring Task"], ["subject", "Recurring Task"],
				["priority", "Recurring Task"], ["frequency", "Recurring Task"]],
			"order_by": "`tabRecurring Task`.`creation` desc",
			"add_totals_row": 0,
			"page_length": 20,
			"column_widths": {"name": 120, "subject": 286, "priority": 294, "frequency": 388},
			"group_by": None,
		}),
		"roles": [{"role": "System Manager"}, {"role": "TNC Super Admin"}],
	}).insert(ignore_permissions=True)
	if commit:
		frappe.db.commit()
	print(f"created {name!r}")


# Accounts the ported teacher payables code names literally (as v1 did):
# credit_to / paid_to, the PI expense account, and the bank the payments leave.
# Parents are the standard India chart groups; v1's exact placement should be
# confirmed against tnc.360ithub.com's Chart of Accounts at cutover.
TEACHER_PAYABLE_ACCOUNTS = [
	("TNC Teachers Salary Paid A/c", "Accounts Payable", "Payable"),
	("Services Rendered", "Indirect Expenses", ""),
	("BOI TNC A/c - Bank of india", "Bank Accounts", "Bank"),
]


def ensure_teacher_payable_accounts(company="TNC Nursing", commit=True):
	"""Create the accounts teacher.py hard-codes if the company lacks them.
	Idempotent; names get the company abbreviation appended by ERPNext."""
	abbr = frappe.db.get_value("Company", company, "abbr")
	for account_name, parent, account_type in TEACHER_PAYABLE_ACCOUNTS:
		full = f"{account_name} - {abbr}"
		if frappe.db.exists("Account", full):
			print(f"exists  {full}")
			continue
		frappe.get_doc({
			"doctype": "Account",
			"account_name": account_name,
			"parent_account": f"{parent} - {abbr}",
			"company": company,
			"account_type": account_type or None,
			"is_group": 0,
		}).insert(ignore_permissions=True)
		print(f"created {full} under {parent}")
	if commit:
		frappe.db.commit()


# Custom Fields v1 carried on standard doctypes that no v2 app provides
# (definitions from v1_schema_export/custom_field/all.json). Employee.custom_fcm_token
# is where the mobile app stores its push token and where notifications.send_fcm
# reads it; the others belong to the teacher payables flow.
V1_CUSTOM_FIELDS = {
	"Employee": [
		{"fieldname": "custom_fcm_token", "label": "FCM Token", "fieldtype": "Small Text",
			"insert_after": "create_user_permission", "translatable": 1, "module": "TNC v2"},
		{"fieldname": "custom_teacher", "label": "Teacher", "fieldtype": "Link", "options": "Teacher",
			"insert_after": "status", "module": "Teachers"},
	],
	"Payment Entry": [
		{"fieldname": "custom_description", "label": "Description", "fieldtype": "JSON",
			"insert_after": "mode_of_payment", "read_only": 1, "module": "Teachers"},
	],
	"Purchase Invoice": [
		{"fieldname": "custom_timesheet_ids", "label": "Timesheet Ids", "fieldtype": "Small Text",
			"insert_after": "due_date", "translatable": 1, "module": "Teachers"},
	],
}


def ensure_v1_custom_fields(commit=True):
	"""Create V1_CUSTOM_FIELDS where missing (idempotent), then they are exported
	as Custom Field fixtures by module."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(V1_CUSTOM_FIELDS, ignore_validate=True, update=True)
	for dt, fields in V1_CUSTOM_FIELDS.items():
		for f in fields:
			print(("ok      " if frappe.db.exists("Custom Field", f"{dt}-{f['fieldname']}") else "MISSING ") + f"{dt}.{f['fieldname']}")
	if commit:
		frappe.db.commit()


def ensure_expense_claim_accounts(company="TNC Nursing", account_name="TNC Other -EXP", commit=True):
	"""Expense claims from the mobile app need a default account on the Expense
	Claim Type (ERPNext validation). v1 had 'TNC Other -EXP - IND' on the
	'Travel & Accommodation' type only; v2 sets it on every type so any claim can
	be saved (checklist row C8; noted as deliberate difference G9)."""
	abbr = frappe.db.get_value("Company", company, "abbr")
	full = f"{account_name} - {abbr}"
	if not frappe.db.exists("Account", full):
		frappe.get_doc({"doctype": "Account", "account_name": account_name, "company": company,
			"parent_account": f"Indirect Expenses - {abbr}", "is_group": 0}).insert(ignore_permissions=True)
		print(f"created {full}")
	for name in frappe.get_all("Expense Claim Type", pluck="name"):
		doc = frappe.get_doc("Expense Claim Type", name)
		row = next((a for a in doc.accounts if a.company == company), None)
		if row and row.default_account:
			continue
		if row:
			row.default_account = full
		else:
			doc.append("accounts", {"company": company, "default_account": full})
		doc.save(ignore_permissions=True)
		print(f"default account set on {name!r}")
	if commit:
		frappe.db.commit()


def link_employees_to_teachers(commit=True):
	"""Fill Employee.custom_teacher for migrated teachers. The field did not exist
	on v2 during the first trial migration, so v1's values were dropped; a
	cutover re-run carries them. Until then, match Teacher.email to the
	Employee's user_id or personal_email (create_teacher_from_employee sets both
	to the same address). The mobile app shows its Timesheet tile only when this
	link is set."""
	linked = skipped = 0
	for t in frappe.get_all("Teacher", fields=["name", "email"], filters={"email": ["!=", ""]}):
		emp = frappe.db.get_value("Employee", {"user_id": t.email}, ["name", "custom_teacher"], as_dict=True) \
			or frappe.db.get_value("Employee", {"personal_email": t.email}, ["name", "custom_teacher"], as_dict=True)
		if not emp:
			skipped += 1
			print(f"no employee for {t.name} ({t.email})")
			continue
		if emp.custom_teacher == t.name:
			continue
		frappe.db.set_value("Employee", emp.name, "custom_teacher", t.name, update_modified=False)
		linked += 1
	if commit:
		frappe.db.commit()
	print(f"linked {linked}, no employee for {skipped}, teachers total {frappe.db.count('Teacher')}")


# Grants v1's export does not contain but the mobile app needs to behave as users
# remember it (deliberate v2 differences, listed in checklist section G).
# Comment: the app lists, posts and deletes task comments through frappe.client
# as the logged-in user; stock Frappe lets only System Manager read Comment.
V2_ROLE_PERMISSIONS = [
	("Comment", "TNC Employees", 0, {"read": 1, "write": 1, "create": 1, "delete": 1, "if_owner": 1, "select": 1}),
	("Comment", "TNC Manager", 0, {"read": 1, "write": 1, "create": 1, "delete": 1, "select": 1}),
	("Comment", "TNC Super Admin", 0, {"read": 1, "write": 1, "create": 1, "delete": 1, "select": 1}),
]


def apply_v2_role_permissions(commit=True):
	"""Apply V2_ROLE_PERMISSIONS the same idempotent way as apply_v1_role_permissions."""
	from frappe.permissions import add_permission, update_permission_property

	changed = 0
	for parent, role, permlevel, flags in V2_ROLE_PERMISSIONS:
		name = frappe.db.get_value("Custom DocPerm", {"parent": parent, "role": role, "permlevel": permlevel})
		if not name:
			add_permission(parent, role, permlevel)
			name = frappe.db.get_value("Custom DocPerm", {"parent": parent, "role": role, "permlevel": permlevel})
			changed += 1
			print(f"added {parent} / {role} / level {permlevel}")
		current = frappe.db.get_value("Custom DocPerm", name, PERM_FLAGS, as_dict=True)
		for flag in PERM_FLAGS:
			want = int(flags.get(flag, 0))
			if int(current.get(flag) or 0) != want:
				update_permission_property(parent, role, permlevel, flag, want, validate=False)
				changed += 1
	if commit:
		frappe.db.commit()
	print(f"done, {changed} change(s)")


def ensure_teacher_user_permissions(commit=True):
	"""Restrict teachers to their own Teacher record, as v1 did.

	v1 never used role permissions for this: create_teacher_from_employee adds a
	User Permission (Allow = Teacher, For Value = the teacher) and Frappe then
	filters every doctype linking Teacher, Teachers Timesheet included. The trial
	migration copied no User Permissions, so on v2 every teacher saw every
	timesheet. Creates the missing rows for users whose Employee is linked to a
	Teacher, except TNC Super Admins and users on the TNC Manager profile, who
	are meant to see all."""
	created = skipped = 0
	rows = frappe.db.sql("""
		select e.user_id, e.custom_teacher, u.role_profile_name
		from tabEmployee e join tabUser u on u.name = e.user_id
		where ifnull(e.custom_teacher, '') != '' and u.enabled = 1""", as_dict=True)
	for r in rows:
		roles = set(frappe.get_roles(r.user_id))
		if "TNC Super Admin" in roles or r.role_profile_name == "TNC Manager":
			skipped += 1
			continue
		if frappe.db.exists("User Permission", {"user": r.user_id, "allow": "Teacher", "for_value": r.custom_teacher}):
			continue
		frappe.get_doc({"doctype": "User Permission", "user": r.user_id, "allow": "Teacher",
			"for_value": r.custom_teacher, "is_default": 1}).insert(ignore_permissions=True)
		created += 1
	if commit:
		frappe.db.commit()
	print(f"created {created} Teacher user permissions; {skipped} manager/super-admin teachers left unrestricted; {len(rows)} linked teacher users")
