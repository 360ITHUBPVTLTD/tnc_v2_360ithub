# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt

"""Copy live data from the v1 site into this site over the REST API.

Read-only against v1. Idempotent on v2: a record that already exists (same
name) is skipped, so the script can be re-run after a fix or at cutover. Names,
creation/modified timestamps and owners are preserved so history reads the same
as on v1.

	export TNC_TOKEN="<api_key>:<api_secret>"          # v1 Administrator API key
	bench --site tnc-v2.local execute tnc_v2_360ithub.migration.from_v1.run --kwargs '{"steps": "all"}'
	bench --site tnc-v2.local execute tnc_v2_360ithub.migration.from_v1.run --kwargs '{"steps": "users,employees"}'
	bench --site tnc-v2.local execute tnc_v2_360ithub.migration.from_v1.compare

Steps, in dependency order: reference, files_branding, users, employees,
teachers, recurring_tasks, tasks, comments, attachments, timesheets, leave,
checkins. `frappe.flags.in_v1_migration` is set for the whole run so the Task
hooks do not send notifications for historical records.
"""

import json
import os
import urllib.parse
import urllib.request

import frappe
from frappe.utils import cint

V1_URL = os.environ.get("TNC_V1_URL", "https://tnc.360ithub.com")
COMPANY = "TNC Nursing"
SYSTEM_KEYS = {"docstatus", "idx", "_user_tags", "_comments", "_assign", "_liked_by", "__islocal", "__unsaved", "__onload", "amended_from"}
STAMP_KEYS = ("creation", "modified", "owner", "modified_by")

_stats = {}


# ---------------------------------------------------------------------------
# v1 access
# ---------------------------------------------------------------------------


TOKEN_FILE = os.path.join(frappe.utils.get_bench_path(), "sites", ".v1_token")


def _token():
	"""v1 Administrator API token, `api_key:api_secret`. Read from TNC_TOKEN, else
	from sites/.v1_token (untracked; never commit or print it)."""
	tok = os.environ.get("TNC_TOKEN")
	if not tok and os.path.exists(TOKEN_FILE):
		with open(TOKEN_FILE) as f:
			tok = f.read().strip()
	if not tok:
		frappe.throw("Set TNC_TOKEN (v1 api_key:api_secret) in the environment or in sites/.v1_token")
	return tok


def _get(path, **params):
	q = urllib.parse.urlencode({k: (json.dumps(v) if not isinstance(v, str) else v) for k, v in params.items()})
	req = urllib.request.Request(f"{V1_URL}{urllib.parse.quote(path)}?{q}", headers={"Authorization": f"token {_token()}"})
	with urllib.request.urlopen(req, timeout=180) as r:
		return json.load(r)


def v1_list(doctype, fields=("*",), filters=None, order_by="creation asc", parent=None, limit=0):
	"""All rows of a doctype (or a child doctype when `parent` is given), paged."""
	out, start, page = [], 0, 500
	while True:
		params = dict(doctype=doctype, fields=list(fields), limit_start=start, limit_page_length=page, order_by=order_by)
		if filters:
			params["filters"] = filters
		if parent:
			params["parent"] = parent
		rows = _get("/api/method/frappe.client.get_list", **params).get("message", [])
		out.extend(rows)
		if len(rows) < page or (limit and len(out) >= limit):
			break
		start += page
	return out


def v1_children(child_doctype, parenttype, parentfield=None):
	"""All child rows of one child doctype across every parent, grouped by parent."""
	filters = [["parenttype", "=", parenttype]]
	if parentfield:
		filters.append(["parentfield", "=", parentfield])
	rows = v1_list(child_doctype, filters=filters, order_by="parent asc, idx asc", parent=parenttype)
	by_parent = {}
	for r in rows:
		by_parent.setdefault(r["parent"], []).append(r)
	return by_parent


def v1_single(doctype):
	return _get(f"/api/resource/{doctype}/{doctype}")["data"]


def v1_download(file_url):
	req = urllib.request.Request(f"{V1_URL}{urllib.parse.quote(file_url)}", headers={"Authorization": f"token {_token()}"})
	with urllib.request.urlopen(req, timeout=180) as r:
		return r.read()


# ---------------------------------------------------------------------------
# v2 write helpers
# ---------------------------------------------------------------------------


def _clean(row, drop=()):
	return {k: v for k, v in row.items() if k not in SYSTEM_KEYS and k not in STAMP_KEYS and k not in drop and not k.startswith("__")}


def _child_rows(rows, drop=()):
	return [{k: v for k, v in _clean(r).items() if k not in ("name", "parent", "parenttype", "parentfield")} for r in rows or []]


def _stamp(doctype, name, src):
	"""Preserve v1 creation/modified/owner on the inserted v2 record."""
	values = {k: src.get(k) for k in STAMP_KEYS if src.get(k)}
	if values:
		frappe.db.set_value(doctype, name, values, update_modified=False)


def _count(step, key, n=1):
	_stats.setdefault(step, {}).setdefault(key, 0)
	_stats[step][key] += n


def insert_doc(step, doctype, src, data, docstatus=None, after=None, ignore_links=False):
	"""Insert `data` as `doctype` keeping v1's name. Returns the doc or None when skipped/failed."""
	name = src.get("name")
	if name and frappe.db.exists(doctype, name):
		_count(step, "skipped_exists")
		return None
	def _attempt(ignore_validate):
		d = frappe.get_doc({"doctype": doctype, **data})
		d.flags.ignore_permissions = True
		d.flags.ignore_mandatory = True
		d.flags.ignore_validate = ignore_validate
		d.flags.ignore_links = ignore_links
		d.insert(set_name=name, ignore_permissions=True, ignore_mandatory=True, ignore_links=ignore_links)
		return d

	frappe.db.savepoint("v1_row")
	try:
		doc = _attempt(False)
	except Exception as first_error:
		frappe.db.rollback(save_point="v1_row")
		# Historical rows can break today's validations (e.g. a due date before the
		# start date). Keep the data as v1 has it: retry once without validate().
		frappe.db.savepoint("v1_row")
		try:
			doc = _attempt(True)
			_count(step, "inserted_unvalidated")
			frappe.log_error(title=f"v1 migration: {doctype} {name} kept without validation", message=str(first_error)[:500])
		except Exception as e:
			frappe.db.rollback(save_point="v1_row")
			_count(step, "failed")
			frappe.log_error(title=f"v1 migration: {doctype} {name} failed", message=f"{e}\n\n{json.dumps(data, default=str)[:3000]}")
			return None
	if after:
		after(doc)
	if docstatus == 1 and doc.docstatus == 0:
		try:
			doc.submit()
		except Exception as e:
			_count(step, "submit_failed")
			frappe.log_error(title=f"v1 migration: submit {doctype} {name} failed", message=str(e))
	_stamp(doctype, doc.name, src)
	_count(step, "inserted")
	return doc


def copy_file(step, file_url, attached_to_doctype=None, attached_to_name=None, attached_to_field=None, is_private=None):
	"""Recreate one v1 file on v2. Returns the new file_url (or the old one when it already exists)."""
	if not file_url:
		return None
	existing = frappe.db.get_value("File", {"file_url": file_url}, "file_url")
	if not existing and attached_to_name is None:
		# v2 may have stored the same upload under a suffixed url; match the original name
		existing = frappe.db.get_value("File", {"file_name": os.path.basename(file_url), "attached_to_name": ["is", "not set"]}, "file_url")
	if existing:
		return existing
	try:
		content = v1_download(file_url)
	except Exception as e:
		_count(step, "file_failed")
		frappe.log_error(title="v1 migration: file download failed", message=f"{file_url}: {e}")
		return None
	private = is_private if is_private is not None else file_url.startswith("/private/")
	fname = os.path.basename(file_url)
	f = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": fname,
			"is_private": 1 if private else 0,
			"content": content,
			"attached_to_doctype": attached_to_doctype,
			"attached_to_name": attached_to_name,
			"attached_to_field": attached_to_field,
		}
	)
	f.flags.ignore_permissions = True
	f.insert(ignore_permissions=True)
	_count(step, "files")
	return f.file_url


# ---------------------------------------------------------------------------
# steps
# ---------------------------------------------------------------------------


def step_reference():
	s = "reference"
	if not frappe.db.exists("Module Profile", "No Module"):
		frappe.get_doc({"doctype": "Module Profile", "module_profile_name": "No Module"}).insert(ignore_permissions=True)
		_count(s, "inserted")
	# roles v1 users hold that v2 does not have yet (non-standard ones only)
	v2_roles = set(frappe.get_all("Role", pluck="name"))
	for r in v1_list("Role", fields=("name", "desk_access", "is_custom", "disabled")):
		if r["name"] not in v2_roles:
			insert_doc(s, "Role", r, {"role_name": r["name"], "desk_access": r.get("desk_access", 1), "is_custom": 1, "disabled": r.get("disabled", 0)})
	prof_roles = v1_children("Has Role", "Role Profile")
	for r in v1_list("Role Profile", fields=("name",)):
		if not frappe.db.exists("Role Profile", r["name"]):
			insert_doc(s, "Role Profile", r, {"role_profile": r["name"], "roles": [{"role": x["role"]} for x in prof_roles.get(r["name"], []) if frappe.db.exists("Role", x["role"])]})
	# roles users hold on v1 that were unknown to v2 when the user was copied
	for user, rows in v1_children("Has Role", "User").items():
		if not frappe.db.exists("User", user):
			continue
		have = set(frappe.get_roles(user))
		for x in rows:
			if x["role"] not in have and frappe.db.exists("Role", x["role"]):
				frappe.get_doc("User", user).add_roles(x["role"])
				_count(s, "role_added_to_user")
	for dt, fields in (
		("Department", ("*",)),
		("Designation", ("*",)),
		("Branch", ("*",)),
		("Employment Type", ("*",)),
		("Leave Type", ("*",)),
		("Expense Claim Type", ("*",)),
	):
		try:
			rows = v1_list(dt, fields=fields)
		except Exception as e:
			frappe.log_error(title=f"v1 migration: cannot list {dt}", message=str(e))
			continue
		for r in rows:
			data = _clean(r, drop=("parent_department", "lft", "rgt", "old_parent") if dt == "Department" else ())
			if dt == "Department":
				data["company"] = COMPANY
				data["parent_department"] = "All Departments" if r.get("name") != "All Departments" else None
				if r.get("name") == "All Departments":
					continue
			if dt == "Expense Claim Type" and data.get("accounts"):
				data.pop("accounts", None)  # account heads differ per company; leave for Finance
			insert_doc(s, dt, r, data)
	# holiday lists with their holidays
	hol = v1_children("Holiday", "Holiday List")
	for r in v1_list("Holiday List"):
		data = _clean(r)
		data["holidays"] = _child_rows(hol.get(r["name"]))
		insert_doc(s, "Holiday List", r, data)
	# shift types after holiday lists (they link to one)
	for r in v1_list("Shift Type"):
		data = _clean(r)
		if data.get("holiday_list") and not frappe.db.exists("Holiday List", data["holiday_list"]):
			data["holiday_list"] = None
		insert_doc(s, "Shift Type", r, data)
	# activities (teacher rate catalogue)
	for r in v1_list("Activity"):
		insert_doc(s, "Activity", r, _clean(r))


def step_files_branding():
	s = "files_branding"
	ws = v1_single("Website Settings")
	v2ws = frappe.get_single("Website Settings")
	for field in ("app_logo", "banner_image", "splash_image", "favicon", "footer_logo"):
		url = ws.get(field)
		if url:
			new = copy_file(s, url, "Website Settings", "Website Settings", field)
			if new:
				v2ws.set(field, new)
	for field in ("app_name", "brand_html", "title_prefix", "home_page", "disable_signup"):
		if ws.get(field) is not None:
			v2ws.set(field, ws.get(field))
	v2ws.flags.ignore_permissions = True
	v2ws.save(ignore_permissions=True)
	nav = v1_single("Navbar Settings")
	if nav.get("app_logo"):
		new = copy_file(s, nav["app_logo"], "Navbar Settings", "Navbar Settings", "app_logo")
		if new:
			frappe.db.set_single_value("Navbar Settings", "app_logo", new)
	for r in v1_list("Letter Head"):
		data = _clean(r)
		if data.get("image"):
			data["image"] = copy_file(s, data["image"], "Letter Head", r["name"], "image") or data["image"]
		insert_doc(s, "Letter Head", r, data)
	comp = _get(f"/api/resource/Company/{COMPANY}")["data"]
	updates = {k: comp.get(k) for k in ("email", "phone_no", "website", "tax_id", "company_description", "date_of_establishment") if comp.get(k)}
	if comp.get("company_logo"):
		new = copy_file(s, comp["company_logo"], "Company", COMPANY, "company_logo")
		if new:
			updates["company_logo"] = new
	if updates and frappe.db.exists("Company", COMPANY):
		frappe.db.set_value("Company", COMPANY, updates)
		_count(s, "company_fields", len(updates))


def step_users():
	s = "users"
	v2_roles = set(frappe.get_all("Role", pluck="name"))
	roles = v1_children("Has Role", "User")
	for r in v1_list("User", filters=[["name", "not in", ["Administrator", "Guest"]]]):
		data = _clean(r, drop=("roles", "user_emails", "social_logins", "block_modules", "defaults", "api_key", "api_secret", "last_login", "last_active", "last_ip", "login_after", "login_before", "reset_password_key", "last_password_reset_date", "last_known_versions", "unsubscribed", "logout_all_sessions"))
		data["send_welcome_email"] = 0
		data["new_password"] = None
		data["roles"] = [{"role": x["role"]} for x in roles.get(r["name"], []) if x["role"] in v2_roles]
		if data.get("role_profile_name") and not frappe.db.exists("Role Profile", data["role_profile_name"]):
			data["role_profile_name"] = None
		if data.get("module_profile") and not frappe.db.exists("Module Profile", data["module_profile"]):
			data["module_profile"] = None
		img = data.pop("user_image", None)

		def after(doc, img=img, r=r):
			if img:
				new = copy_file(s, img, "User", doc.name, "user_image")
				if new:
					frappe.db.set_value("User", doc.name, "user_image", new, update_modified=False)

		insert_doc(s, "User", r, data, after=after)


def step_employees():
	s = "employees"
	edu = v1_children("Employee Education", "Employee")
	ext = v1_children("Employee External Work History", "Employee")
	internal = v1_children("Employee Internal Work History", "Employee")
	rows = v1_list("Employee")
	v2_fields = {f.fieldname for f in frappe.get_meta("Employee").fields} | {"name"}
	deferred = {}
	for r in rows:
		data = {k: v for k, v in _clean(r, drop=("education", "external_work_history", "internal_work_history", "lft", "rgt")).items() if k in v2_fields}
		data["company"] = COMPANY
		deferred[r["name"]] = data.pop("reports_to", None)
		for link_field, dt in (("department", "Department"), ("designation", "Designation"), ("branch", "Branch"), ("holiday_list", "Holiday List"), ("default_shift", "Shift Type"), ("employment_type", "Employment Type"), ("payroll_cost_center", "Cost Center"), ("grade", "Employee Grade")):
			if data.get(link_field) and not frappe.db.exists(dt, data[link_field]):
				data[link_field] = None
		for uf in ("user_id", "leave_approver", "expense_approver", "shift_request_approver"):
			if data.get(uf) and not frappe.db.exists("User", data[uf]):
				data[uf] = None
		data["education"] = _child_rows(edu.get(r["name"]))
		data["external_work_history"] = _child_rows(ext.get(r["name"]))
		data["internal_work_history"] = _child_rows(internal.get(r["name"]))
		img = data.pop("image", None)

		def after(doc, img=img):
			if img:
				new = copy_file(s, img, "Employee", doc.name, "image")
				if new:
					frappe.db.set_value("Employee", doc.name, "image", new, update_modified=False)

		insert_doc(s, "Employee", r, data, after=after)
	for name, boss in deferred.items():
		if boss and frappe.db.exists("Employee", name) and frappe.db.exists("Employee", boss):
			frappe.db.set_value("Employee", name, "reports_to", boss, update_modified=False)



def step_masters():
	"""Item, Supplier, Customer, Contact, Address: every master v1 uses, with v1
	names kept so links in teachers, invoices and payments stay valid. Runs before
	teachers so Teacher.supplier_id resolves. Rows already on v2 are skipped."""
	s = "masters"
	# Items (activity items auto-created on v1 plus anything else). India Compliance
	# on v2 needs an HSN/SAC on every Item; keep v1's when set, else the coaching SAC.
	from tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher import TEACHER_SERVICE_SAC, ensure_teacher_service_sac
	ensure_teacher_service_sac()
	for r in v1_list("Item Group"):
		if r.get("name") in ("All Item Groups",):
			continue
		data = _clean(r, drop=("lft", "rgt", "old_parent"))
		data["parent_item_group"] = data.get("parent_item_group") or "All Item Groups"
		if not frappe.db.exists("Item Group", data["parent_item_group"]):
			data["parent_item_group"] = "All Item Groups"
		insert_doc(s, "Item Group", r, data)
	for r in v1_list("Item"):
		data = _clean(r, drop=("item_defaults", "taxes", "uoms", "barcodes", "reorder_levels", "supplier_items", "customer_items", "attributes", "variant_of"))
		if not frappe.db.exists("Item Group", data.get("item_group") or ""):
			data["item_group"] = "Services"
		if not frappe.db.exists("UOM", data.get("stock_uom") or ""):
			data["stock_uom"] = "Nos"
		if not data.get("gst_hsn_code") or not frappe.db.exists("GST HSN Code", data["gst_hsn_code"]):
			data["gst_hsn_code"] = TEACHER_SERVICE_SAC
		data["is_stock_item"] = 0
		insert_doc(s, "Item", r, data)
	# Suppliers (teachers and vendors) and Customers
	for dt, drop in (("Supplier", ("accounts", "companies", "portal_users")), ("Customer", ("accounts", "credit_limits", "companies", "sales_team", "portal_users"))):
		for r in v1_list(dt):
			data = _clean(r, drop=drop + ("lft", "rgt"))
			for f in ("supplier_group", "customer_group", "territory", "default_price_list", "payment_terms"):
				if data.get(f) and not frappe.db.exists(frappe.get_meta(dt).get_field(f).options, data[f]):
					data[f] = None
			insert_doc(s, dt, r, data)
	# Contacts and Addresses with their Dynamic Links (only links whose target exists on v2)
	links = v1_children("Dynamic Link", "Contact")
	emails = v1_children("Contact Email", "Contact")
	phones = v1_children("Contact Phone", "Contact")
	for r in v1_list("Contact"):
		data = _clean(r, drop=("links", "email_ids", "phone_nos"))
		data["links"] = [l for l in _child_rows(links.get(r["name"])) if frappe.db.exists(l.get("link_doctype") or "", l.get("link_name") or "")]
		data["email_ids"] = _child_rows(emails.get(r["name"]))
		data["phone_nos"] = _child_rows(phones.get(r["name"]))
		insert_doc(s, "Contact", r, data)
	alinks = v1_children("Dynamic Link", "Address")
	for r in v1_list("Address"):
		data = _clean(r, drop=("links",))
		data["links"] = [l for l in _child_rows(alinks.get(r["name"])) if frappe.db.exists(l.get("link_doctype") or "", l.get("link_name") or "")]
		insert_doc(s, "Address", r, data)


def step_teachers():
	s = "teachers"
	rates = v1_children("Teachers Activity Type", "Teacher")
	for r in v1_list("Teacher"):
		data = _clean(r, drop=("teachers_activity_type", "timesheet_portal", "teacher_payment_details"))
		data["teachers_activity_type"] = _child_rows(rates.get(r["name"]))
		# after_insert creates Supplier + User + role; keep v1's supplier link when it exists here
		if data.get("supplier_id") and not frappe.db.exists("Supplier", data["supplier_id"]):
			data.pop("supplier_id")
		insert_doc(s, "Teacher", r, data)


def step_students():
	"""v1 Student -> v2 Student, keeping the TNC-ADM-xxxxx names. v1 holds little beyond
	name, gender, mobile and the customer link; the academic child rows become the
	college / passout fields plus a note. Status: Enrolled -> Active, else Enrolment Pending."""
	s = "students"
	acad = v1_children("Previous Academic Record", "Student", "academics")
	gender = {"Male": "Male", "Female": "Female", "others": "Other", "Others": "Other"}
	for r in v1_list("Student"):
		rows = sorted(acad.get(r["name"]) or [], key=lambda a: a.get("passing_year") or "")
		latest = rows[-1] if rows else {}
		notes = "; ".join(
			" ".join(str(x) for x in (a.get("academic_level"), a.get("college_name"), (a.get("passing_year") or "")[:4], f"{a['percentage']}%" if a.get("percentage") else None) if x)
			for a in rows
		)
		customer = r.get("customer_id") if r.get("customer_id") and frappe.db.exists("Customer", r["customer_id"]) else None
		data = {
			"naming_series": "TNC-ADM-.#####",
			"student_name": (r.get("student_name") or "").strip() or r["name"],
			"gender": gender.get(r.get("gender") or ""),
			"date_of_birth": r.get("date_of_birth"),
			"category": r.get("category") or None,
			"email": r.get("email"),
			"mobile": r.get("mobile_number"),
			"aadhar_number": r.get("aadhar_number"),
			"state": r.get("state"), "district": r.get("district"),
			"nationality": r.get("nationality"), "religion": r.get("religion"),
			"address": r.get("residential_address"), "permanent_address": r.get("permanent_address"),
			"college": latest.get("college_name"),
			"passout_year": (latest.get("passing_year") or r.get("passout_year") or "")[:4] or None,
			"fathers_name": r.get("fathers_name"), "father_occupation": r.get("father_occupation"), "father_mobile_no": r.get("father_mobile_no"),
			"mothers_name": r.get("mothers_name"), "mother_occupation": r.get("mother_occupation"), "mother_mobile_no": r.get("mother_mobile_no"),
			"guardian_name": r.get("guardian_name"),
			"customer": customer,
			"status": "Active" if r.get("batch_enrollment_details") == "Enrolled" else "Enrolment Pending",
			"notes": (f"Academics (v1): {notes}" if notes else None),
		}
		data = {k: v for k, v in data.items() if v not in (None, "")}

		def files(doc, r=r):
			for field, dtype in (("student_photo", "Photo"), ("aadhar", "Aadhaar"), ("final_year_result", "Marksheet")):
				url = copy_file(s, r.get(field), "Student", doc.name, "student_photo" if field == "student_photo" else None)
				if url:
					if field == "student_photo":
						frappe.db.set_value("Student", doc.name, "student_photo", url, update_modified=False)
					doc.append("documents", {"document_type": dtype, "file": url})
			if doc.get("documents"):
				doc.flags.ignore_validate = True
				doc.save(ignore_permissions=True)

		insert_doc(s, "Student", r, data, after=files)
	# keep the running number above the highest migrated name
	mx = frappe.db.sql("select max(cast(substring_index(name, '-', -1) as unsigned)) from tabStudent where name like 'TNC-ADM-%%'")[0][0] or 0
	frappe.db.sql("insert into tabSeries (name, current) values ('TNC-ADM-', %s) on duplicate key update current = greatest(current, %s)", (mx, mx))


def step_recurring_tasks(pause=False):
	s = "recurring_tasks"
	owners = v1_children("Recurring Task Owner", "Recurring Task")
	for r in v1_list("Recurring Task"):
		data = _clean(r, drop=("task_owner", "recurrence_summary"))
		data["task_owner"] = _child_rows(owners.get(r["name"]))
		for o in data["task_owner"]:
			if not frappe.db.exists("User", o.get("user")):
				o["user"] = None
		data["task_owner"] = [o for o in data["task_owner"] if o.get("user")]
		# insert as a fresh template, then restore the live counters exactly
		live = {k: r.get(k) for k in ("status", "next_run_date", "last_run_date", "generated_occurrence_count", "enabled")}
		data.update({"status": "Active", "enabled": 1})

		def after(doc, live=live):
			vals = {k: v for k, v in live.items() if v is not None}
			if pause:
				vals["status"] = "Paused"
				vals["enabled"] = 0
			frappe.db.set_value("Recurring Task", doc.name, vals, update_modified=False)

		insert_doc(s, "Recurring Task", r, data, after=after)


def step_tasks():
	s = "tasks"
	child_dt = frappe.get_meta("Task").get_field("other_assignees").options
	others = v1_children("User Multiselect Clarity", "Task", "other_assignees")
	v2_fields = {f.fieldname for f in frappe.get_meta("Task").fields}
	for r in v1_list("Task"):
		data = {k: v for k, v in _clean(r, drop=("depends_on", "other_assignees", "lft", "rgt")).items() if k in v2_fields}
		for uf in ("task_owner", "task_reporter", "completed_by"):
			if data.get(uf) and not frappe.db.exists("User", data[uf]):
				data[uf] = None
		if data.get("recurring_task") and not frappe.db.exists("Recurring Task", data["recurring_task"]):
			data["recurring_task"] = None
		for lf in ("project", "issue", "parent_task", "type", "department", "company"):
			if lf in data and data[lf] and lf != "company" and not frappe.db.exists(frappe.get_meta("Task").get_field(lf).options, data[lf]):
				data[lf] = None
		data["company"] = COMPANY
		data["other_assignees"] = [{"doctype": child_dt, "user": x["user"]} for x in others.get(r["name"], []) if x.get("user") and frappe.db.exists("User", x["user"])]
		if not data.get("task_reporter"):
			data["task_reporter"] = r.get("owner") if frappe.db.exists("User", r.get("owner") or "") else None
		status = data.get("status")

		def after(doc, status=status):
			if status and doc.status != status:
				frappe.db.set_value("Task", doc.name, "status", status, update_modified=False)

		insert_doc(s, "Task", r, data, after=after)


def step_comments():
	s = "comments"
	rows = v1_list("Comment", filters=[["reference_doctype", "=", "Task"]])  # every type: v1 shows the full trail
	v1names = set()
	for r in rows:
		v1names.add(r["name"])
		data = _clean(r)
		# comments whose task v1 later deleted are kept as they are (v1 shows them in the trail)
		insert_doc(s, "Comment", r, data, ignore_links=not frappe.db.exists("Task", r.get("reference_name") or ""))
	# File inserts on v2 auto-create "Attachment" comments v1 already has under other names: drop the duplicates
	for name in frappe.get_all("Comment", filters={"reference_doctype": "Task", "name": ["not in", list(v1names)]}, pluck="name"):
		frappe.delete_doc("Comment", name, force=True, ignore_permissions=True)
		_count(s, "removed_v2_generated")


def step_attachments():
	s = "attachments"
	frappe.conf["max_file_size"] = 200 * 1024 * 1024  # v1 holds files above the 25 MB default; copy them as they are
	ffields = ("name", "file_url", "file_name", "is_private", "is_folder", "attached_to_doctype", "attached_to_name", "attached_to_field", "creation", "modified", "owner", "modified_by")
	rows = v1_list("File", filters=[["is_folder", "=", 0], ["attached_to_doctype", "in", ["Task", "Teachers Timesheet", "Recurring Task", "Employee", "User", "Expense Claim", "Website Settings", "Navbar Settings", "Public Website Settings", "Letter Head"]]], fields=ffields)
	# files not attached to any document (uploads used in descriptions, logos)
	rows += [r for r in v1_list("File", filters=[["is_folder", "=", 0], ["attached_to_doctype", "is", "not set"]], fields=ffields) if r.get("file_url")]
	for r in rows:
		if not r.get("attached_to_doctype"):
			if frappe.db.exists("File", {"file_url": r["file_url"]}):
				_count(s, "skipped_exists")
				continue
			try:
				new = copy_file(s, r["file_url"], None, None, None, cint(r.get("is_private")))
			except Exception as e:
				_count(s, "failed"); frappe.log_error(title=f"v1 migration: File {r['name']} failed", message=str(e)[:500]); continue
			if new:
				fname = frappe.db.get_value("File", {"file_url": new}, "name")
				if fname:
					_stamp("File", fname, r)
			continue
		parent_ok = frappe.db.exists("DocType", r["attached_to_doctype"]) and frappe.db.exists(r["attached_to_doctype"], r["attached_to_name"])
		if not parent_ok:
			# v1 points at a document that does not exist (report PDFs "attached" to a user, doctypes v2 lacks): keep the file itself
			if frappe.db.exists("File", {"file_url": r["file_url"]}):
				_count(s, "skipped_exists")
				continue
			try:
				new = copy_file(s, r["file_url"], None, None, None, cint(r.get("is_private")))
				_count(s, "kept_unattached")
			except Exception as e:
				_count(s, "failed"); frappe.log_error(title=f"v1 migration: File {r['name']} failed", message=str(e)[:500])
			continue
		if frappe.db.exists("File", {"file_url": r["file_url"], "attached_to_name": r["attached_to_name"]}):
			_count(s, "skipped_exists")
			continue
		existing = frappe.db.get_value("File", {"file_url": r["file_url"]}, ["file_url", "file_name", "is_private"], as_dict=True)
		if existing:
			# same file already copied for another parent: add a File row pointing at it
			f = frappe.get_doc({"doctype": "File", "file_url": existing.file_url, "file_name": existing.file_name or r.get("file_name"),
				"is_private": existing.is_private, "attached_to_doctype": r["attached_to_doctype"], "attached_to_name": r["attached_to_name"],
				"attached_to_field": r.get("attached_to_field")})
			f.flags.ignore_permissions = True
			f.insert(ignore_permissions=True)
			_stamp("File", f.name, r)
			_count(s, "linked_existing")
			continue
		try:
			new = copy_file(s, r["file_url"], r["attached_to_doctype"], r["attached_to_name"], r.get("attached_to_field"), cint(r.get("is_private")))
		except Exception as e:
			_count(s, "failed"); frappe.log_error(title=f"v1 migration: File {r['name']} failed", message=str(e)[:500]); continue
		if new:
			fname = frappe.db.get_value("File", {"file_url": new, "attached_to_name": r["attached_to_name"]}, "name")
			if fname:
				_stamp("File", fname, r)


def step_timesheets():
	s = "timesheets"
	acts = v1_children("Activities", "Teachers Timesheet")
	frappe.flags.in_v1_migration = True
	for r in v1_list("Teachers Timesheet"):
		if not frappe.db.exists("Teacher", r.get("teacher_id") or ""):
			_count(s, "skipped_no_teacher")
			continue
		data = _clean(r, drop=("activity_type",))
		child = _child_rows(acts.get(r["name"]))
		data["activity_type"] = child
		for uf in ("approved_by", "rejected_by", "created_by"):
			if data.get(uf) and not frappe.db.exists("User", data[uf]):
				data[uf] = None
		if data.get("purchase_order_id") and not frappe.db.exists("Purchase Order", data["purchase_order_id"]):
			data["purchase_order_id"] = None
		stored = {"grand_total": r.get("grand_total"), "status": r.get("status"), "payment_status": r.get("payment_status")}
		stored_rows = [(c.get("activity_fee"), c.get("amount"), c.get("purchase_invoice_id")) for c in child]

		def after(doc, stored=stored, stored_rows=stored_rows):
			# validate() recomputed fees from today's rates; restore the historical values
			frappe.db.set_value("Teachers Timesheet", doc.name, {k: v for k, v in stored.items() if v is not None}, update_modified=False)
			for row, (fee, amount, pi) in zip(doc.activity_type, stored_rows):
				vals = {}
				if fee is not None:
					vals["activity_fee"] = fee
				if amount is not None:
					vals["amount"] = amount
				if pi:
					vals["purchase_invoice_id"] = pi
				if vals:
					frappe.db.set_value("Activities", row.name, vals, update_modified=False)

		insert_doc(s, "Teachers Timesheet", r, data, after=after)


def step_leave():
	s = "leave"
	for r in v1_list("Leave Allocation", filters=[["docstatus", "<", 2]]):
		if not frappe.db.exists("Employee", r.get("employee") or ""):
			_count(s, "skipped_no_employee")
			continue
		data = _clean(r, drop=("total_leaves_encashed", "leave_policy_assignment"))
		data["company"] = COMPANY
		insert_doc(s, "Leave Allocation", r, data, docstatus=cint(r.get("docstatus")))
	for r in v1_list("Leave Application", filters=[["docstatus", "<", 2]]):
		if not frappe.db.exists("Employee", r.get("employee") or ""):
			continue
		data = _clean(r)
		data["company"] = COMPANY
		if data.get("leave_approver") and not frappe.db.exists("User", data["leave_approver"]):
			data["leave_approver"] = None
		insert_doc(s, "Leave Application", r, data, docstatus=cint(r.get("docstatus")))


def step_checkins():
	s = "checkins"
	for r in v1_list("Employee Checkin"):
		if not frappe.db.exists("Employee", r.get("employee") or ""):
			_count(s, "skipped_no_employee")
			continue
		data = _clean(r, drop=("attendance", "shift", "shift_start", "shift_end", "shift_actual_start", "shift_actual_end", "skip_auto_attendance"))
		insert_doc(s, "Employee Checkin", r, data)


def step_settings():
	"""v1 'Institute Management Admin Settings' -> TNC Settings.teacher_timesheet_approval."""
	s = "settings"
	src = v1_single("Institute Management Admin Settings")
	settings = frappe.get_single("TNC Settings")
	have = {r.user for r in settings.get("teacher_timesheet_approval") or []}
	for row in src.get("teacher_timesheet_approval") or []:
		u = row.get("user")
		if u and u not in have and frappe.db.exists("User", u):
			settings.append("teacher_timesheet_approval", {"user": u})
			_count(s, "approvers_added")
	settings.flags.ignore_permissions = True
	settings.save(ignore_permissions=True)


def step_naming_rules():
	"""v1 names records through Document Naming Rules (e.g. Teachers Timesheet ->
	TEAC-TMS-000001), overriding the doctype autoname. Copy the rules for the
	doctypes that exist here, with live counters, so new records continue the
	same sequences."""
	s = "naming_rules"
	# v1's admission doctypes share names with v2's redesigned ones but number differently (STU-ENQ- vs ENQ-);
	# v2's own naming series rule these, so v1's rules must not be copied for them
	V2_OWN = {"Student", "Student Enquiry", "Student Follow-Up", "Course", "Student Batch", "Demo Class", "Admission Form", "Student Batch Enrollment", "WhatsApp Message Log"}
	for r in v1_list("Document Naming Rule", fields=("name", "document_type", "prefix", "prefix_digits", "counter", "disabled", "priority", "creation", "modified", "owner", "modified_by")):
		if not frappe.db.exists("DocType", r["document_type"]) or r["document_type"] in V2_OWN:
			# v2's WhatsApp Message Log is a new autoincrement doctype, not v1's WA-Log- table
			_count(s, "skipped_no_doctype")
			continue
		existing = frappe.db.get_value("Document Naming Rule", {"document_type": r["document_type"], "prefix": r["prefix"]}, "name")
		if existing:
			if cint(frappe.db.get_value("Document Naming Rule", existing, "counter")) < cint(r["counter"]):
				frappe.db.set_value("Document Naming Rule", existing, "counter", cint(r["counter"]), update_modified=False)
				_count(s, "counter_advanced")
			else:
				_count(s, "skipped_exists")
			continue
		insert_doc(s, "Document Naming Rule", r, {"document_type": r["document_type"], "prefix": r["prefix"], "prefix_digits": r["prefix_digits"], "counter": r["counter"], "disabled": r["disabled"], "priority": r["priority"]})


def step_integrations():
	"""Provider configuration: FCM Settings (Firebase service account JSON) and the
	Webtoolex WhatsApp Instance record(s). Values are copied, never printed.
	Providers stay switched off in TNC Settings until cutover."""
	s = "integrations"
	if frappe.db.exists("DocType", "FCM Settings"):
		try:
			src = v1_single("FCM Settings")
			if src.get("firebase_config"):
				frappe.db.set_single_value("FCM Settings", "firebase_config", src["firebase_config"])
				_count(s, "fcm_config_copied")
		except Exception as e:
			frappe.log_error(title="v1 migration: FCM Settings", message=str(e))
	if frappe.db.exists("DocType", "WhatsApp Instance"):
		for r in v1_list("WhatsApp Instance"):
			data = _clean(r)
			insert_doc(s, "WhatsApp Instance", r, data)
	settings = frappe.get_single("TNC Settings")
	settings.whatsapp_provider = "Disabled"
	settings.fcm_enabled = 0
	settings.task_reminders_enabled = 0
	settings.flags.ignore_permissions = True
	settings.save(ignore_permissions=True)
	_count(s, "providers_kept_off", 1)


def step_accounts():
	"""Chart of Accounts: create v1's accounts that v2 lacks, under the same parent,
	in tree order. Where v2 has ERPNext's default spelling of an account v1 renamed
	(Capital Equipments vs Capital Equipment, ...), rename v2's to v1's name."""
	s = "accounts"
	v2 = set(frappe.get_all("Account", pluck="name"))
	rows = sorted(v1_list("Account", fields=("name", "account_name", "parent_account", "account_type", "root_type", "is_group", "company", "account_number", "tax_rate", "lft")), key=lambda x: x.get("lft") or 0)
	v1names = {r["name"] for r in rows}
	renames = {"Capital Equipments - IND": "Capital Equipment - IND", "Electronic Equipments - IND": "Electronic Equipment - IND",
		"Furnitures and Fixtures - IND": "Furniture and Fixtures - IND", "Office Equipments - IND": "Office Equipment - IND",
		"Print and Stationery - IND": "Print and Stationary - IND"}
	for old, new in renames.items():
		if old in v2 and new in v1names and new not in v2:
			frappe.rename_doc("Account", old, new, force=True)
			frappe.db.set_value("Account", new, "account_name", new.rsplit(" - ", 1)[0])
			_count(s, "renamed")
			v2.discard(old); v2.add(new)
	for r in rows:
		if r["name"] in v2:
			continue
		parent = r.get("parent_account")
		if parent and not frappe.db.exists("Account", parent):
			_count(s, "skipped_no_parent")
			frappe.log_error(title=f"v1 migration: Account {r['name']} parent missing", message=parent)
			continue
		data = {"account_name": r.get("account_name") or r["name"].rsplit(" - ", 1)[0], "parent_account": parent, "company": COMPANY,
			"account_type": r.get("account_type") or None, "root_type": r.get("root_type"), "is_group": cint(r.get("is_group")),
			"account_number": r.get("account_number") or None, "tax_rate": r.get("tax_rate") or 0}
		insert_doc(s, "Account", r, data)
		v2.add(r["name"])
	# Modes of Payment with their default accounts (v1 adds bank-wise modes such as "KOTAK BANK@TNC Edutech")
	mop_accounts = v1_children("Mode of Payment Account", "Mode of Payment", "accounts")
	for r in v1_list("Mode of Payment"):
		rows = [{"company": COMPANY, "default_account": x.get("default_account")} for x in mop_accounts.get(r["name"], []) if frappe.db.exists("Account", x.get("default_account") or "")]
		data = {"mode_of_payment": r.get("mode_of_payment") or r["name"], "type": r.get("type"), "enabled": cint(r.get("enabled")), "accounts": rows}
		if frappe.db.exists("Mode of Payment", r["name"]):
			doc = frappe.get_doc("Mode of Payment", r["name"])
			have = [(x.company, x.default_account) for x in doc.accounts]
			if doc.type != data["type"] or cint(doc.enabled) != data["enabled"] or have != [(x["company"], x["default_account"]) for x in rows]:
				doc.update({"type": data["type"], "enabled": data["enabled"]}); doc.set("accounts", rows)
				doc.flags.ignore_permissions = True; doc.save(ignore_permissions=True); _stamp("Mode of Payment", doc.name, r); _count(s, "mop_refreshed")
			else:
				_count(s, "skipped_exists")
			continue
		insert_doc(s, "Mode of Payment", r, data)
	# Bank and Bank Account masters (bank-wise accounts TNC added in Sep 2026)
	for r in v1_list("Bank"):
		if not frappe.db.exists("Bank", r["name"]):
			insert_doc(s, "Bank", r, {"bank_name": r.get("bank_name") or r["name"], "swift_number": r.get("swift_number")})
	for r in v1_list("Bank Account"):
		if not frappe.db.exists("Bank Account", r["name"]):
			data = _clean(r)
			data["company"] = COMPANY if r.get("company") else None
			if data.get("account") and not frappe.db.exists("Account", data["account"]):
				data["account"] = None
			insert_doc(s, "Bank Account", r, data)


# records v1 edited after they were first copied: refresh them field by field, keeping v1's modified stamp
REFRESH_DOCTYPES = {
	# doctype: (child tables to replace, fields never overwritten)
	"Task": ({"other_assignees": "User Multiselect Clarity"}, ()),
	"Recurring Task": ({}, ()),
	"Teachers Timesheet": ({}, ()),
	"Teacher": ({"teachers_activity_type": "Teachers Activity Type"}, ()),
	"Employee": ({}, ()),
	"User": ({}, ("api_key", "api_secret", "password", "last_login", "last_active", "login_after", "login_before", "user_image", "roles", "form_navigation_buttons")),
	"Customer": ({}, ()),
	"Supplier": ({}, ()),
	"Contact": ({"email_ids": "Contact Email", "phone_nos": "Contact Phone", "links": "Dynamic Link"}, ()),
	"Comment": ({}, ()),
	"Expense Claim": ({}, ()),
	"Purchase Invoice": ({}, ()),
	"Journal Entry": ({}, ("ineligibility_reason",)),
	"Payment Entry": ({}, ("paid_from_account_type", "paid_to_account_type")),
	"Leave Type": ({}, ()),
	"Shift Type": ({}, ()),
	"Holiday List": ({}, ()),
	"Letter Head": ({}, ()),
	"Company": ({}, ()),
	"Item": ({}, ()),
	"Department": ({}, ("lft", "rgt", "old_parent")),
	"Designation": ({}, ()),
	"Account": ({}, ("lft", "rgt", "old_parent")),
	"Cost Center": ({}, ("lft", "rgt", "old_parent")),
	"Holiday List": ({"holidays": "Holiday"}, ()),
	"Leave Allocation": ({}, ()),
	"Employment Type": ({}, ()),
	"Role Profile": ({"roles": "Has Role"}, ()),
}

# v1 Student fields -> v2 Student fields (the schema changed; everything else is not on v1)
STUDENT_MAP = {"student_name": "student_name", "mobile_number": "mobile", "email": "email", "gender": "gender", "date_of_birth": "date_of_birth",
	"category": "category", "aadhar_number": "aadhar_number", "state": "state", "district": "district", "nationality": "nationality", "religion": "religion",
	"residential_address": "address", "permanent_address": "permanent_address", "fathers_name": "fathers_name", "father_occupation": "father_occupation",
	"father_mobile_no": "father_mobile_no", "mothers_name": "mothers_name", "mother_occupation": "mother_occupation", "mother_mobile_no": "mother_mobile_no",
	"guardian_name": "guardian_name", "customer_id": "customer"}


def refresh_students():
	"""v1 Student edits since the copy (name, mobile, parents, ...) applied to v2's Student."""
	s = "refresh"
	gender = {"Male": "Male", "Female": "Female", "others": "Other", "Others": "Other"}
	for r in v1_list("Student"):
		if not frappe.db.exists("Student", r["name"]):
			continue
		cur = frappe.db.get_value("Student", r["name"], list(set(STUDENT_MAP.values())), as_dict=True)
		values = {}
		for v1f, v2f in STUDENT_MAP.items():
			x = r.get(v1f)
			if v1f == "gender":
				x = gender.get(x or "", x)
			if v1f == "customer_id" and x and not frappe.db.exists("Customer", x):
				continue
			if x in (None, "") or str(x) == str(cur.get(v2f) or ""):
				continue
			values[v2f] = x
		if values:
			frappe.db.set_value("Student", r["name"], values, update_modified=False)
			_count(s, "Student_refreshed")



def step_refresh_changed():
	refresh_students()
	_refresh_main()


def _refresh_main():
	"""Every v1 row of REFRESH_DOCTYPES is compared field by field with v2's copy and overwritten
	where anything differs (status, names, dates, subject, ...). "Exists" never means "same":
	a v2-made record that took the same number as a later v1 record is replaced by v1's."""
	s = "refresh"
	for dt, (children, skip) in REFRESH_DOCTYPES.items():
		meta = frappe.get_meta(dt)
		valid = [df.fieldname for df in meta.fields if df.fieldtype not in ("Table", "Table MultiSelect", "Section Break", "Column Break", "Tab Break", "HTML", "Button")
			and df.fieldname not in skip and frappe.db.has_column(dt, df.fieldname)]
		v2rows = {r["name"]: r for r in frappe.db.get_all(dt, fields=["name", "modified", "modified_by", "owner", "creation"] + valid, limit=0, as_list=False)}
		if not v2rows:
			continue
		child_rows = {cf: v1_children(cdt, dt, cf) for cf, cdt in children.items()}
		for r in v1_list(dt):
			cur = v2rows.get(r["name"])
			if not cur:
				continue
			values = {}
			for f in valid:
				x, y = r.get(f), cur.get(f)
				if x in (None, "") and y in (None, "", 0) and f != "docstatus":
					continue
				if x is None:
					continue  # v1 has nothing here; never write NULL into v2
				if str(x)[:19] != str(y if y is not None else "")[:19]:
					values[f] = x
			stamp_differs = str(r.get("modified") or "")[:19] != str(cur.get("modified") or "")[:19]
			kids_differ = False
			for cf, cdt in children.items():
				theirs = sorted(child_rows[cf].get(r["name"]) or [], key=lambda x: x.get("idx") or 0)
				mine = frappe.db.get_all(cdt, filters={"parent": r["name"], "parentfield": cf}, fields=["*"], order_by="idx asc", limit=0)
				if len(theirs) != len(mine):
					kids_differ = True; break
				for a, b in zip(theirs, mine):
					for k, x in _clean(a).items():
						if k in ("name", "parent", "parenttype", "parentfield", "idx") or x in (None, ""):
							continue
						if str(x)[:19] != str(b.get(k) if b.get(k) is not None else "")[:19]:
							kids_differ = True; break
					if kids_differ:
						break
				if kids_differ:
					break
			if not values and not stamp_differs and not kids_differ:
				continue
			try:
				if values:
					frappe.db.set_value(dt, r["name"], values, update_modified=False)
				for cf, cdt in children.items():
					frappe.db.delete(cdt, {"parent": r["name"], "parentfield": cf})
					for idx, row in enumerate(_child_rows(child_rows[cf].get(r["name"])), 1):
						frappe.get_doc({"doctype": cdt, "parent": r["name"], "parenttype": dt, "parentfield": cf, "idx": idx, **row}).db_insert()
				_stamp(dt, r["name"], r)
				_count(s, f"{dt}_refreshed")
			except Exception as e:
				_count(s, f"{dt}_failed")
				frappe.log_error(title=f"v1 refresh: {dt} {r['name']} failed", message=str(e)[:800])


def step_sales_orders():
	"""v1's Sales Orders (history: one cancelled order). Inserted with v1's items and dates,
	then given v1's docstatus, so the list looks the same on v2. Items unknown to v2 are created
	as plain service items."""
	s = "sales_orders"
	items = v1_children("Sales Order Item", "Sales Order", "items")
	taxes = v1_children("Sales Taxes and Charges", "Sales Order", "taxes")
	for r in v1_list("Sales Order"):
		if frappe.db.exists("Sales Order", r["name"]):
			_count(s, "skipped_exists"); continue
		if not frappe.db.exists("Customer", r.get("customer")):
			_count(s, "skipped_no_customer"); continue
		rows = _child_rows(items.get(r["name"]), drop=("sales_order_item", "prevdoc_docname", "quotation_item"))
		for it in rows:
			if it.get("item_code") and not frappe.db.exists("Item", it["item_code"]):
				from tnc_v2_360ithub.admissions.setup import ITEM_GROUP, ensure_item_group
				ensure_item_group()
				frappe.get_doc({"doctype": "Item", "item_code": it["item_code"], "item_name": it.get("item_name") or it["item_code"], "item_group": ITEM_GROUP, "stock_uom": "Nos", "is_stock_item": 0}).insert(ignore_permissions=True)
				_count(s, "item_created")
		data = _clean(r, drop=("items", "taxes", "payment_schedule", "sales_team", "packed_items", "pricing_rules", "amended_from", "fee_schedule", "custom_batch_enrollment_id", "custom_tax_type", "custom_sndfbvlnkwef"))
		data["items"] = rows
		data["taxes"] = _child_rows(taxes.get(r["name"]))
		data["skip_delivery_note"] = 1
		target = cint(r.get("docstatus"))
		doc = insert_doc(s, "Sales Order", r, data, docstatus=1 if target else None, ignore_links=True)
		if doc and target == 2:
			try:
				doc.reload(); doc.flags.ignore_permissions = True; doc.cancel()
			except Exception:
				frappe.db.set_value("Sales Order", doc.name, {"docstatus": 2, "status": "Cancelled"}, update_modified=False)
			_count(s, "cancelled_like_v1")


def step_fix_teacher_suppliers():
	"""Point every Teacher at the Supplier v1 links it to (after step_masters has
	created them), and drop the differently named Suppliers v2's Teacher hook made
	while v1's were missing, when nothing references them."""
	s = "fix_teacher_suppliers"
	for r in v1_list("Teacher", fields=("name", "supplier_id")):
		if not frappe.db.exists("Teacher", r["name"]):
			continue
		want = r.get("supplier_id") or None
		have = frappe.db.get_value("Teacher", r["name"], "supplier_id") or None
		if want == have:
			continue
		if want and not frappe.db.exists("Supplier", want):
			_count(s, "skipped_no_supplier")
			continue
		frappe.db.set_value("Teacher", r["name"], "supplier_id", want, update_modified=False)
		_count(s, "relinked")
		if have and not frappe.db.exists("Teacher", {"supplier_id": have}) and not frappe.db.exists("Purchase Invoice", {"supplier": have}) and not frappe.db.exists("Payment Entry", {"party": have}):
			frappe.delete_doc("Supplier", have, force=True, ignore_permissions=True)
			_count(s, "removed_v2_only_supplier")


def step_user_permissions(prune=False):
	"""Copy v1's User Permission rows (Company, Employee, Teacher) where user and
	target exist on v2. Replaces the heuristic back-fill in setup_helpers."""
	s = "user_permissions"
	for r in v1_list("User Permission", fields=("name", "user", "allow", "for_value", "is_default", "apply_to_all_doctypes", "applicable_for", "hide_descendants", "creation", "modified", "owner", "modified_by")):
		if not frappe.db.exists("User", r["user"]) or not frappe.db.exists(r["allow"], r["for_value"]):
			_count(s, "skipped_missing_target")
			continue
		if frappe.db.exists("User Permission", {"user": r["user"], "allow": r["allow"], "for_value": r["for_value"]}):
			_count(s, "skipped_exists")
			continue
		data = _clean(r)
		insert_doc(s, "User Permission", r, data)
	# rows v2 grew that v1 never had (heuristic back-fill, hooks); keep rows of users unknown to v1 (local test users)
	v1keys = {(r["user"], r["allow"], r["for_value"]) for r in v1_list("User Permission", fields=("name", "user", "allow", "for_value"))}
	v1users = {r["name"] for r in v1_list("User", fields=("name",))}
	if prune:
		for row in frappe.get_all("User Permission", fields=["name", "user", "allow", "for_value"]):
			if row.user in v1users and (row.user, row.allow, row.for_value) not in v1keys:
				frappe.delete_doc("User Permission", row.name, force=True, ignore_permissions=True)
				_count(s, "removed_v2_only")


def step_fix_contacts():
	"""Drop Contacts v2's hooks created (Supplier/Employee/User inserts) that v1 does
	not have, unless they belong to a party unknown to v1 (local test data)."""
	s = "fix_contacts"
	v1names = {r["name"] for r in v1_list("Contact", fields=("name",))}
	v1parties = set()
	for dt in ("Supplier", "Customer", "Employee", "User"):
		v1parties |= {(dt, r["name"]) for r in v1_list(dt, fields=("name",))}
	for row in frappe.get_all("Contact", pluck="name"):
		if row in v1names:
			continue
		links = frappe.get_all("Dynamic Link", filters={"parenttype": "Contact", "parent": row}, fields=["link_doctype", "link_name"])
		if links and any((l.link_doctype, l.link_name) not in v1parties and frappe.db.exists(l.link_doctype, l.link_name) for l in links):
			_count(s, "kept_local_party")
			continue
		frappe.delete_doc("Contact", row, force=True, ignore_permissions=True)
		_count(s, "removed_v2_only")


def step_notification_logs():
	"""Bell-notification history (the app's notification screen)."""
	s = "notification_logs"
	have = set(frappe.get_all("Notification Log", pluck="name"))
	for r in v1_list("Notification Log"):
		if r["name"] in have:
			_count(s, "skipped_exists")
			continue
		data = _clean(r)
		if not frappe.db.exists("User", r.get("for_user") or ""):
			_count(s, "user_missing_kept")  # user later deleted on v1; the log row is history and stays
		insert_doc(s, "Notification Log", r, data, ignore_links=True)


def step_expense_types(prune=False):
	"""v1 has five Expense Claim Types; drop ERPNext's unused defaults on v2 so the
	master matches. Types referenced by a claim are kept."""
	s = "expense_types"
	v1 = {r["name"] for r in v1_list("Expense Claim Type", fields=("name",))}
	if prune:
		for name in frappe.get_all("Expense Claim Type", pluck="name"):
			if name in v1:
				continue
			if frappe.db.exists("Expense Claim Detail", {"expense_type": name}):
				_count(s, "kept_in_use")
				continue
			frappe.delete_doc("Expense Claim Type", name, force=True, ignore_permissions=True)
			_count(s, "removed_default")


def step_accounting():
	"""Purchase Invoices, Payment Entries and Journal Entries as accounting history,
	submitted with v1's posting dates. Needs step_accounts and step_masters first."""
	s = "accounting"
	for r in v1_list("Fiscal Year", fields=("name", "year_start_date", "year_end_date")):
		if not frappe.db.exists("Fiscal Year", r["name"]):
			insert_doc(s, "Fiscal Year", r, {"year": r["name"], "year_start_date": r["year_start_date"], "year_end_date": r["year_end_date"], "companies": [{"company": COMPANY}]})
	child = {
		"Expense Claim": [("expenses", "Expense Claim Detail"), ("taxes", "Expense Taxes and Charges"), ("advances", "Expense Claim Advance")],
		"Purchase Invoice": [("items", "Purchase Invoice Item"), ("taxes", "Purchase Taxes and Charges")],
		"Payment Entry": [("references", "Payment Entry Reference"), ("deductions", "Payment Entry Deduction")],
		"Journal Entry": [("accounts", "Journal Entry Account")],
	}
	for dt in ("Expense Claim", "Purchase Invoice", "Payment Entry", "Journal Entry"):
		kids = {f: v1_children(cdt, dt, f) for f, cdt in child[dt]}
		for r in v1_list(dt):
			data = _clean(r, drop=tuple(f for f, _ in child[dt]) + ("payment_schedule", "advances", "pricing_rules", "supplied_items"))
			if data.get("amended_from") and not frappe.db.exists(dt, data["amended_from"]):
				data["amended_from"] = None
			for f, _ in child[dt]:
				data[f] = _child_rows(kids[f].get(r["name"]))
			data["company"] = COMPANY
			if dt == "Payment Entry":
				data["references"] = [x for x in data["references"] if frappe.db.exists(x.get("reference_doctype") or "", x.get("reference_name") or "")]
			ds = cint(r.get("docstatus"))
			if frappe.db.exists(dt, r["name"]) and ds == 0 and cint(frappe.db.get_value(dt, r["name"], "docstatus")) == 1:
				# submitted locally while testing; v1 never submitted it: drop and re-copy as draft
				_drop_submitted(dt, r["name"]); _count(s, "resubmitted_locally_reverted")
			doc = insert_doc(s, dt, r, data, docstatus=1 if ds else 0)
			if doc and ds == 2 and doc.docstatus == 1:
				try:
					doc = frappe.get_doc(dt, doc.name)  # reload: _stamp changed modified after insert
					doc.flags.ignore_permissions = True
					doc.cancel()
					_stamp(dt, doc.name, r)
					_count(s, "cancelled_as_v1")
				except Exception as e:
					_count(s, "cancel_failed"); frappe.log_error(title=f"v1 migration: cancel {dt} {r['name']} failed", message=str(e)[:500])


def dedupe_unattached_files(commit=True):
	"""Remove duplicate unattached File rows (same file_url) left by repeated
	attachment runs; keeps the oldest row, never touches the file on disk."""
	rows = frappe.db.sql("""select file_url, group_concat(name order by creation) names, count(*) c from tabFile
		where is_folder = 0 and ifnull(attached_to_name, '') = '' group by file_url having c > 1""", as_dict=True)
	removed = 0
	for r in rows:
		for name in r.names.split(",")[1:]:
			frappe.db.delete("File", {"name": name})  # plain row delete: the file itself stays for the kept row
			removed += 1
	if commit:
		frappe.db.commit()
	print(f"removed {removed} duplicate unattached File row(s)")


def fix_cancelled_accounting(commit=True):
	"""Cancel on v2 the accounting documents v1 holds as cancelled (repair for a run
	whose cancel step failed). Payment Entries first, then invoices and journals."""
	for dt in ("Payment Entry", "Purchase Invoice", "Journal Entry"):
		v1 = {r["name"]: r for r in v1_list(dt, fields=("name", "docstatus", "modified", "modified_by"), filters=[["docstatus", "=", 2]])}
		for name in v1:
			if frappe.db.get_value(dt, name, "docstatus") != 1:
				continue
			doc = frappe.get_doc(dt, name)
			doc.flags.ignore_permissions = True
			try:
				doc.cancel()
				_stamp(dt, name, v1[name])
				print(f"cancelled {dt} {name}")
			except Exception as e:
				print(f"FAILED {dt} {name}: {str(e)[:200]}")
	if commit:
		frappe.db.commit()


def cleanup_test_data(commit=True):
	"""Remove documents created while testing on tnc-v2.local (not from v1):
	Payment Entries, Expense Claims and Employee Checkins that v1 does not have.
	The test user Anurag Dubey (User, Employee, Teacher, Supplier) is left in place."""
	removed = 0
	for dt in ("Payment Entry", "Expense Claim", "Employee Checkin", "Purchase Invoice"):
		v1rows = {r["name"]: str(r.get("creation") or "")[:16] for r in v1_list(dt, fields=("name", "creation"))}
		for row in frappe.get_all(dt, fields=["name", "creation"]):
			name = row.name
			# same name AND same creation minute means it is v1's row; anything else is local test data
			if name in v1rows and v1rows[name] == str(row.creation)[:16]:
				continue
			doc = frappe.get_doc(dt, name)
			if doc.docstatus == 1:
				doc.flags.ignore_permissions = True
				doc.cancel()
			frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
			removed += 1
			print(f"removed test {dt} {name}")
	if commit:
		frappe.db.commit()
	print(f"removed {removed} test document(s)")


# doctypes where v2 must hold exactly v1's records: whatever v1 no longer has is removed here too.
# Names v2 needs for its own modules are kept (fee items and accounts the admission module created).
MIRROR_DOCTYPES = ["Sales Invoice", "Sales Order", "WhatsApp Instance", "User Permission", "Employee Checkin", "Leave Allocation", "Expense Claim", "Payment Entry", "Purchase Invoice", "Journal Entry",
	"Employee", "Teacher", "Supplier", "Customer", "Contact", "Mode of Payment", "Account", "Item", "User",
	"Task", "Comment", "Notification Log", "Bank", "Bank Account"]  # Task: the local scheduler used to generate tasks under v1 numbers
MIRROR_KEEP = {
	"User": {"Administrator", "Guest"},
	"Mode of Payment": {"Cash", "UPI", "Card", "Bank Transfer", "Cheque"},  # fee collection modes the admission module sets up
	"Account": {"Demo Fee Income - IND"},
	"Item": {"Demo Fee"},
}


def _mirror_delete(dt, name, s):
	"""Cancel + delete one v2 record, clearing what blocks the delete the way an admin would."""
	try:
		doc = frappe.get_doc(dt, name)
	except frappe.DoesNotExistError:
		return
	try:
		if getattr(doc, "docstatus", 0) == 1:
			doc.flags.ignore_permissions = True
			doc.flags.ignore_links = True
			doc.cancel()
	except Exception:
		frappe.db.set_value(dt, name, "docstatus", 2, update_modified=False)
		for ledger in ("GL Entry", "Payment Ledger Entry"):
			frappe.db.sql(f"delete from `tab{ledger}` where voucher_type=%s and voucher_no=%s", (dt, name))
	frappe.flags.ignore_links = True
	try:
		frappe.delete_doc(dt, name, force=True, ignore_permissions=True, ignore_missing=True, ignore_on_trash=True, delete_permanently=True)
		_count(s, "removed")
	except frappe.LinkExistsError as e:
		_count(s, "kept_linked")
		frappe.log_error(title=f"mirror v1: {dt} {name} still linked", message=str(e)[:500])
	finally:
		frappe.flags.ignore_links = False


def mirror_v1(doctypes=None, commit=True):
	"""Remove v2 records that v1 does not have (v1 is the source of truth until cutover).
	Fee items / accounts the admission module created are kept; test data goes."""
	s = "mirror_v1"
	for dt in doctypes or MIRROR_DOCTYPES:
		if dt == "User Permission":  # random names on both sides: compare by content
			v1keys = {(r["user"], r["allow"], r["for_value"]) for r in v1_list(dt, fields=("user", "allow", "for_value"))}
			for r in frappe.get_all(dt, fields=["name", "user", "allow", "for_value"]):
				if (r.user, r.allow, r.for_value) not in v1keys:
					_mirror_delete(dt, r.name, s); print(f"removed {dt} {r.user} {r.allow} {r.for_value}")
			continue
		v1names = {r["name"] for r in v1_list(dt, fields=("name",))}
		keep = MIRROR_KEEP.get(dt, set())
		extra = [n for n in frappe.get_all(dt, pluck="name") if n not in v1names and n not in keep]
		if dt == "Account":  # only leaf accounts without entries can go; groups and ledgers with entries stay
			extra = [n for n in extra if not frappe.db.get_value("Account", n, "is_group") and not frappe.db.exists("GL Entry", {"account": n})]
		if dt == "Item":
			extra = [n for n in extra if not n.startswith("Fee - ")]
		for n in extra:
			_mirror_delete(dt, n, s)
			print(f"removed {dt} {n}")
	if commit:
		frappe.db.commit()
	print(json.dumps(_stats.get(s, {}), indent=1))


def step_user_roles():
	"""Last: make every user's roles exactly v1's. Saving a User re-applies its Role Profile and drops
	roles added by hand (TNC Teachers on teacher logins, approver roles on accounts), so this runs after refresh."""
	s = "user_roles"
	v1 = {(r["parent"], r["role"]) for r in v1_list("Has Role", fields=("parent", "role"), filters=[["parenttype", "=", "User"]], parent="User")}
	v2 = {tuple(r) for r in frappe.db.sql("select parent, role from `tabHas Role` where parenttype='User'")}
	for user, role in v1 - v2:
		if frappe.db.exists("User", user) and frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Has Role", "parent": user, "parenttype": "User", "parentfield": "roles", "role": role}).db_insert()
			_count(s, "role_added")
	for user, role in v2 - v1:
		if user not in ("Administrator", "Guest") and frappe.db.exists("User", {"name": user}) and user in {u for u, _ in v1}:
			frappe.db.delete("Has Role", {"parent": user, "parenttype": "User", "role": role})
			_count(s, "role_removed")
	frappe.clear_cache()


def _drop_submitted(dt, name):
	"""Remove a locally submitted copy (and its ledger rows) so v1's version can be copied afresh."""
	frappe.db.delete("GL Entry", {"voucher_no": name}); frappe.db.delete("Payment Ledger Entry", {"voucher_no": name})
	frappe.db.set_value(dt, name, "docstatus", 2, update_modified=False)
	frappe.delete_doc(dt, name, force=True, ignore_permissions=True, delete_permanently=True)


LEDGERS = ("GL Entry", "Payment Ledger Entry")


def step_ledgers():
	"""General Ledger and Payment Ledger exactly as v1: every row v1 has, none it does not.
	v2 re-posts documents when copying them, which leaves duplicate or orphan ledger rows behind
	(deleted test documents, re-submitted copies), so the ledger tables are rebuilt from v1's rows."""
	s = "ledgers"
	for dt in LEDGERS:
		cols = set(frappe.db.get_table_columns(dt))
		rows = v1_list(dt)
		frappe.db.delete(dt)
		for r in rows:
			data = {k: v for k, v in r.items() if k in cols}
			if data.get("company"):
				data["company"] = COMPANY
			doc = frappe.get_doc(dict(data, doctype=dt))
			doc.db_insert()
			_count(s, f"{dt}_rows")
	frappe.db.commit()


def step_purge_side_effects():
	"""Task hooks fire while tasks are copied and log Skipped WhatsApp attempts; v1's own WhatsApp log
	table is not carried over, so before cutover v2's log must be empty."""
	n = frappe.db.count("WhatsApp Message Log")
	frappe.db.delete("WhatsApp Message Log")
	_count("purge_side_effects", "whatsapp_log_rows_removed", n)


STEPS = [
	("reference", step_reference),
	("naming_rules", step_naming_rules),
	("files_branding", step_files_branding),
	("users", step_users),
	("settings", step_settings),
	("integrations", step_integrations),
	("employees", step_employees),
	("masters", step_masters),
	("accounts", step_accounts),
	("expense_types", step_expense_types),
	("teachers", step_teachers),
	("fix_teacher_suppliers", step_fix_teacher_suppliers),
	("user_permissions", step_user_permissions),
	("fix_contacts", step_fix_contacts),
	("students", step_students),
	("recurring_tasks", step_recurring_tasks),
	("tasks", step_tasks),
	("comments", step_comments),
	("attachments", step_attachments),
	("timesheets", step_timesheets),
	("leave", step_leave),
	("checkins", step_checkins),
	("notification_logs", step_notification_logs),
	("accounting", step_accounting),
	("sales_orders", step_sales_orders),
	("refresh", step_refresh_changed),
	("user_roles", step_user_roles),
	("ledgers", step_ledgers),
	("purge_side_effects", step_purge_side_effects),
]


def run(steps="all", commit=True):
	"""Run the listed steps (comma-separated) or all, in dependency order."""
	wanted = None if steps == "all" else {x.strip() for x in steps.split(",")}
	frappe.flags.in_v1_migration = True
	frappe.flags.mute_emails = True
	frappe.flags.mute_messages = True
	_stats.clear()
	try:
		for name, fn in STEPS:
			if wanted and name not in wanted:
				continue
			print(f"== {name}")
			fn()
			print("   ", json.dumps(_stats.get(name, {})))
			if commit:
				frappe.db.commit()
	finally:
		frappe.flags.in_v1_migration = False
	print("\nSUMMARY", json.dumps(_stats, indent=1))
	return _stats


COMPARE = ["User", "Employee", "Department", "Designation", "Holiday List", "Leave Type", "Activity", "Teacher", "Teachers Timesheet", "Recurring Task", "Task", "Comment", "File", "Leave Allocation", "Leave Application", "Employee Checkin", "Letter Head"]


def compare():
	"""Row counts v1 vs v2 for the migrated doctypes."""
	print(f"{'doctype':22} {'v1':>7} {'v2':>7}")
	for dt in COMPARE:
		try:
			filters = [["reference_doctype", "=", "Task"]] if dt == "Comment" else None
			v1 = _get("/api/method/frappe.client.get_count", doctype=dt, **({"filters": filters} if filters else {})).get("message")
		except Exception as e:
			v1 = f"err:{str(e)[:20]}"
		v2 = frappe.db.count(dt, {"reference_doctype": "Task"} if dt == "Comment" else None)
		print(f"{dt:22} {str(v1):>7} {v2:>7}")


COMPARE_ALL = [
	# masters
	"User", "Role", "Role Profile", "User Permission", "Employee", "Department", "Designation", "Branch",
	"Employment Type", "Holiday List", "Leave Type", "Leave Allocation", "Shift Type", "Expense Claim Type",
	"Teacher", "Activity", "Supplier", "Customer", "Contact", "Address", "Item", "Item Group", "Account",
	"Cost Center", "Company", "Letter Head",
	# transactions
	"Task", "Recurring Task", "Comment", "File", "Teachers Timesheet", "Purchase Invoice", "Payment Entry",
	"Purchase Order", "Journal Entry", "Expense Claim", "Leave Application", "Attendance", "Attendance Request",
	"Employee Checkin", "Notification Log", "Event", "Lead", "Student", "Sales Order", "Sales Invoice",
	"GL Entry", "Payment Ledger Entry", "Bank", "Bank Account", "Mode of Payment",
]


def compare_all(doctypes=None, only_mismatch=False):
	"""Row counts v1 vs v2 for COMPARE_ALL (or the given list). Prints a diff column
	so the parity gaps are visible at a glance; run before and after a migration."""
	rows = []
	for dt in doctypes or COMPARE_ALL:
		try:
			filters = [["reference_doctype", "=", "Task"]] if dt == "Comment" else None
			v1 = _get("/api/method/frappe.client.get_count", doctype=dt, **({"filters": filters} if filters else {})).get("message")
		except Exception as e:
			v1 = None if "DoesNotExist" in str(e) or "404" in str(e) else f"err:{str(e)[:18]}"
		try:
			v2 = frappe.db.count(dt, {"reference_doctype": "Task"} if dt == "Comment" else None)
		except Exception:
			v2 = None
		diff = (v2 - v1) if isinstance(v1, int) and isinstance(v2, int) else ""
		if only_mismatch and diff == 0:
			continue
		rows.append((dt, v1, v2, diff))
	print(f"{'doctype':22} {'v1':>7} {'v2':>7} {'v2-v1':>7}")
	for dt, v1, v2, diff in rows:
		print(f"{dt:22} {str(v1 if v1 is not None else '-'):>7} {str(v2 if v2 is not None else '-'):>7} {str(diff):>7}")
	return rows


def show_failures(limit=40):
	"""Group the migration's Error Log entries by doctype and first error line."""
	import collections

	rows = frappe.get_all("Error Log", filters={"method": ["like", "v1 migration:%"]}, fields=["method", "error"], order_by="creation desc", limit=5000)
	groups = collections.Counter()
	sample = {}
	for r in rows:
		dt = r.method.split(":")[1].strip().split(" ")[0] if ":" in r.method else r.method
		first = (r.error or "").strip().split("\n")[0][:160]
		key = (dt, first)
		groups[key] += 1
		sample.setdefault(key, r.method)
	for (dt, first), n in groups.most_common(limit):
		print(f"{n:5}  {dt:20} {first}    e.g. {sample[(dt, first)][-60:]}")


def fix_task_start_dates(commit=True):
	"""Tasks with no exp_start_date on v1 received the form default (today) on
	insert. Restore NULL so the data reads exactly as v1."""
	rows = v1_list("Task", fields=("name", "exp_start_date", "exp_end_date"))
	fixed = 0
	for r in rows:
		if r.get("exp_start_date") is None and frappe.db.exists("Task", r["name"]):
			cur = frappe.db.get_value("Task", r["name"], "exp_start_date")
			if cur is not None:
				frappe.db.set_value("Task", r["name"], "exp_start_date", None, update_modified=False)
				fixed += 1
	if commit:
		frappe.db.commit()
	print(f"start dates restored to NULL: {fixed} of {len(rows)} tasks")
	return fixed


def align_to_v1(commit=True):
	"""Make status-like fields read exactly as live v1:
	- Users: same enabled flag; users that do not exist on v1 (created here by
	  Teacher.after_insert) are removed
	- Recurring Tasks: same status/enabled as v1 (run the scheduler only on one site!)
	- Departments: drop ERPNext's default departments that v1 never had
	"""
	report = {}
	v1_users = {u["name"]: u for u in v1_list("User", fields=("name", "enabled", "user_type"))}
	removed, re_enabled = [], 0
	for u in frappe.get_all("User", fields=["name", "enabled"], filters={"name": ["not in", ["Administrator", "Guest"]]}):
		src = v1_users.get(u.name)
		if not src:
			frappe.delete_doc("User", u.name, force=True, ignore_permissions=True)
			removed.append(u.name)
		elif cint(src["enabled"]) != cint(u.enabled):
			frappe.db.set_value("User", u.name, "enabled", cint(src["enabled"]), update_modified=False)
			re_enabled += 1
	report["users_removed"] = removed
	report["users_enabled_fixed"] = re_enabled

	fixed = 0
	for r in v1_list("Recurring Task", fields=("name", "status", "enabled", "next_run_date", "last_run_date", "generated_occurrence_count")):
		if frappe.db.exists("Recurring Task", r["name"]):
			frappe.db.set_value("Recurring Task", r["name"], {k: r[k] for k in ("status", "enabled", "next_run_date", "last_run_date", "generated_occurrence_count") if r.get(k) is not None}, update_modified=False)
			fixed += 1
	report["recurring_restored"] = fixed

	v1_depts = {d["name"] for d in v1_list("Department", fields=("name",))}
	dropped = []
	for d in frappe.get_all("Department", pluck="name"):
		if d not in v1_depts and d != "All Departments" and not frappe.db.exists("Employee", {"department": d}):
			try:
				frappe.delete_doc("Department", d, force=True, ignore_permissions=True)
				dropped.append(d)
			except Exception as e:
				report.setdefault("dept_errors", []).append(f"{d}: {e}")
	report["departments_dropped"] = dropped
	if commit:
		frappe.db.commit()
	print(json.dumps(report, indent=1))
	return report


def fix_naming_series(commit=True):
	"""Advance every naming-series counter past the highest migrated name so new
	records do not collide with v1 names (e.g. TASK-2026-01426 exists, counter
	still at 16). Covers the series-based doctypes this migration copies."""
	import re

	report = {}
	specs = [
		("Task", r"^(TASK-\d{4}-)(\d+)$"),
		("Teachers Timesheet", r"^(TIMESHEET-)(\d+)$"),
		("Teacher", r"^(TCH-\d{4}-)(\d+)$"),
		("Teacher", r"^(TEACHER-)(\d+)$"),
		("Recurring Task", r"^(REC-TSK-)(\d+)$"),
		("Employee", r"^(EMP-)(\d+)$"),
		("Leave Allocation", r"^(HR-LAL-\d{4}-)(\d+)$"),
		("Employee Checkin", r"^(EMP-CKIN-\d{2}-\d{4}-)(\d+)$"),
		("Purchase Invoice", r"^(ACC-PINV-\d{4}-)(\d+)$"),
		("Payment Entry", r"^(ACC-PAY-\d{4}-)(\d+)$"),
		("Journal Entry", r"^(ACC-JV-\d{4}-)(\d+)$"),
		("Expense Claim", r"^(HR-EXP-\d{4}-)(\d+)$"),
		("Leave Application", r"^(HR-LAP-\d{4}-)(\d+)$"),
		("Customer", r"^(CUST-)(\d+)$"),
	]
	for dt, pattern in specs:
		rx = re.compile(pattern)
		maxes = {}
		for name in frappe.get_all(dt, pluck="name"):
			m = rx.match(name)
			if m:
				prefix, num = m.group(1), int(m.group(2))
				maxes[prefix] = max(maxes.get(prefix, 0), num)
		for prefix, mx in maxes.items():
			current = frappe.db.get_value("Series", prefix, "current", order_by=None)
			if current is None:
				frappe.db.sql("insert into `tabSeries` (name, current) values (%s, %s)", (prefix, mx))
				report[f"{dt}:{prefix}"] = f"created at {mx}"
			elif cint(current) < mx:
				frappe.db.sql("update `tabSeries` set current = %s where name = %s", (mx, prefix))
				report[f"{dt}:{prefix}"] = f"{current} -> {mx}"
	if commit:
		frappe.db.commit()
	print(json.dumps(report, indent=1))
	return report


def compare_fields(doctypes=None, sample=3):
	"""For each doctype: rows whose fields differ between v1 and v2 (system columns ignored).
	Prints the count per doctype and a few examples. Returns {doctype: n_differing_rows}."""
	ignore = set(SYSTEM_KEYS) | {"modified", "modified_by", "creation", "owner", "idx", "_user_tags", "_comments", "_assign", "_liked_by", "docstatus",
		"lft", "rgt", "old_parent", "is_custom", "form_navigation_buttons", "posting_time", "ineligibility_reason", "paid_from_account_type", "paid_to_account_type",
		"skip_delivery_note", "api_key", "api_secret", "last_known_versions", "last_login", "last_active", "last_ip", "login_after", "login_before", "user_image", "gst_hsn_code", "parent_item_group"}
	out = {}
	for dt in doctypes or [d for d in COMPARE_ALL if d not in ("File", "Notification Log", "Student")]:
		if not frappe.db.exists("DocType", dt):
			continue
		meta = frappe.get_meta(dt)
		valid = [df.fieldname for df in meta.fields if df.fieldtype not in ("Table", "Table MultiSelect", "Section Break", "Column Break", "Tab Break", "HTML", "Button")
			and df.fieldname not in ignore and frappe.db.has_column(dt, df.fieldname)]
		v2rows = {r["name"]: r for r in frappe.db.get_all(dt, fields=["name", "docstatus"] + valid, limit=0)}
		bad = []
		for r in v1_list(dt):
			cur = v2rows.get(r["name"])
			if not cur:
				continue
			if cint(r.get("docstatus")) != cint(cur.get("docstatus")):
				bad.append((r["name"], "docstatus", r.get("docstatus"), cur.get("docstatus"))); continue
			for f in valid:
				x, y = r.get(f), cur.get(f)
				if x in (None, "", 0) and y in (None, "", 0):
					continue
				if x is None:
					continue  # v1 empty, v2 filled by a default: not a data difference
				if str(x)[:19] != str(y if y is not None else "")[:19]:
					bad.append((r["name"], f, str(x)[:30], str(y)[:30]))
					break
		# child rows: same parent, same position, same values
		for cf, cdt in (REFRESH_DOCTYPES.get(dt, ({}, ()))[0] or {}).items():
			cmeta = frappe.get_meta(cdt)
			cvalid = [df.fieldname for df in cmeta.fields if df.fieldtype not in ("Table", "Section Break", "Column Break", "HTML") and frappe.db.has_column(cdt, df.fieldname)]
			v1kids = v1_children(cdt, dt, cf)
			for parent, rows in v1kids.items():
				if parent not in v2rows:
					continue
				mine = frappe.db.get_all(cdt, filters={"parent": parent, "parentfield": cf}, fields=cvalid, order_by="idx asc", limit=0)
				theirs = sorted(rows, key=lambda x: x.get("idx") or 0)
				if len(mine) != len(theirs):
					bad.append((parent, f"{cf} rows", len(theirs), len(mine))); continue
				for a, b in zip(theirs, mine):
					for f in cvalid:
						if f in ignore or f in ("name", "parent", "parenttype", "parentfield"): continue
						x, y = a.get(f), b.get(f)
						if x in (None, "", 0) and y in (None, "", 0): continue
						if x is not None and str(x)[:19] != str(y if y is not None else "")[:19]:
							bad.append((parent, f"{cf}.{f}", str(x)[:30], str(y)[:30])); break
		out[dt] = len(bad)
		print(f"{dt:24} rows differing: {len(bad)}" + (f"   e.g. {bad[:sample]}" if bad else ""))
	return out
