app_name = "tnc_v2_360ithub"
app_title = "TNC v2"
app_publisher = "360ITHub"
app_description = "TNC coaching institute ERP (v2 rebuild) on Frappe/ERPNext v15"
app_email = "pankaj@360ithub.com"
app_license = "mit"

# Apps
# ------------------

# This app builds on standard ERPNext Selling/Accounts, Frappe HR and India
# Compliance (GST). See the workspace spec: docs/specs/tnc-v2/ in the bench root.
# Entries must resolve to the installed Python module name (the part after "/"),
# so india_compliance is listed by module, not by its GitHub org/repo.
required_apps = ["frappe/erpnext", "frappe/hrms", "india_compliance"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "tnc_v2_360ithub",
# 		"logo": "/assets/tnc_v2_360ithub/logo.png",
# 		"title": "TNC v2",
# 		"route": "/tnc_v2_360ithub",
# 		"has_permission": "tnc_v2_360ithub.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/tnc_v2_360ithub/css/tnc_v2_360ithub.css"
# app_include_js = "/assets/tnc_v2_360ithub/js/tnc_v2_360ithub.js"
app_include_js = "/assets/tnc_v2_360ithub/js/tnc_admissions.js"

# include js, css files in header of web template
# web_include_css = "/assets/tnc_v2_360ithub/css/tnc_v2_360ithub.css"
# web_include_js = "/assets/tnc_v2_360ithub/js/tnc_v2_360ithub.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "tnc_v2_360ithub/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
doctype_js = {"Sales Order": "admissions/sales_order.js", "Expense Claim": "hr/expense_claim.js", "Payment Entry": "hr/payment_entry.js"}
doctype_list_js = {"Expense Claim": "hr/expense_claim_list.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "tnc_v2_360ithub/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "tnc_v2_360ithub.utils.jinja_methods",
# 	"filters": "tnc_v2_360ithub.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "tnc_v2_360ithub.install.before_install"
# after_install = "tnc_v2_360ithub.install.after_install"
# reconcile_custom_fields must stay LAST: it reads is_system_generated, and
# ensure_custom_fields above flips that flag to 0 for our "TNC v2" fields.
after_migrate = ["tnc_v2_360ithub.admissions.setup.ensure_defaults", "tnc_v2_360ithub.admissions.custom_fields.ensure_custom_fields", "tnc_v2_360ithub.customizations.reconcile_custom_fields"]

# Uninstallation
# ------------

# before_uninstall = "tnc_v2_360ithub.uninstall.before_uninstall"
# after_uninstall = "tnc_v2_360ithub.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "tnc_v2_360ithub.utils.before_app_install"
# after_app_install = "tnc_v2_360ithub.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "tnc_v2_360ithub.utils.before_app_uninstall"
# after_app_uninstall = "tnc_v2_360ithub.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "tnc_v2_360ithub.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["tnc_v2_360ithub.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"File": {"validate": "tnc_v2_360ithub.admissions.guest_files.validate"},
	# Task notifications and the creator-only completion rule, ported from v1.
	"Task": {
		"before_save": "tnc_v2_360ithub.tasks.task_hooks.before_save",
		"after_insert": "tnc_v2_360ithub.tasks.task_hooks.after_insert",
		"on_update": "tnc_v2_360ithub.tasks.task_hooks.on_update",
	},
	"Comment": {
		"after_insert": "tnc_v2_360ithub.tasks.task_hooks.on_comment",
	},
	# Teacher payables: keep Teachers Timesheet payment_status in step with
	# Purchase Invoice / Payment Entry, ported from institute_management_360ithub.
	"Purchase Invoice": {
		"on_submit": "tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher.on_purchase_invoice_submit",
		"on_cancel": "tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher.on_purchase_invoice_cancel",
	},
	"Payment Entry": {
		"validate": "tnc_v2_360ithub.hr.expense_claim.guard_payment_reference",
		"on_submit": "tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher.on_payment_entry_update",
		"on_cancel": "tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher.on_payment_entry_update",
	},
	"Activity": {
		"on_update": "tnc_v2_360ithub.tnc_v2.doctype.teachers_timesheet.teachers_timesheet.update_uom_in_related_docs",
	},
	# Mobile app posts Expense Claims without an approver; copy it from the Employee.
	"Expense Claim": {
		"validate": "tnc_v2_360ithub.hr.expense_claim.set_defaults",
	},
	"Journal Entry": {
		"validate": "tnc_v2_360ithub.hr.expense_claim.guard_payment_reference",
	},
	# enrolment Sales Orders: fee and schedule are changed through the enrolment only
	"Sales Order": {
		"before_update_after_submit": "tnc_v2_360ithub.admissions.sales_order_hooks.before_update_after_submit",
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		# Recurring Task engine, ported from v1 (ran 07:30 there too).
		"30 7 * * *": [
			"tnc_v2_360ithub.tasks.recurring_task.scheduler.run_scheduler",
		],
		# 08:00 WhatsApp task digest, gated by TNC Settings.task_reminders_enabled.
		"0 8 * * *": [
			"tnc_v2_360ithub.tasks.jobs.enqueue_task_reminders",
		],
		# Fee follow-ups: upcoming (3 days before due) and overdue instalments, 07:00 daily.
		"0 7 * * *": [
			"tnc_v2_360ithub.admissions.followups.create_fee_followups",
			"tnc_v2_360ithub.admissions.followups.create_form_followups",
		],
		# Monthly Teacher Task Summary emails, 07:00 on the 1st (as in v1).
		"0 7 1 * *": [
			"tnc_v2_360ithub.teachers.monthly_summary.send_monthly_teacher_task_summary_reports",
		],
	},
}

# scheduler_events = {
# 	"all": [
# 		"tnc_v2_360ithub.tasks.all"
# 	],
# 	"daily": [
# 		"tnc_v2_360ithub.tasks.daily"
# 	],
# 	"hourly": [
# 		"tnc_v2_360ithub.tasks.hourly"
# 	],
# 	"weekly": [
# 		"tnc_v2_360ithub.tasks.weekly"
# 	],
# 	"monthly": [
# 		"tnc_v2_360ithub.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "tnc_v2_360ithub.install.before_tests"

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	# Mobile app saves its push token with frappe.client.set_value on Employee; see hr/mobile.py.
	"frappe.client.set_value": "tnc_v2_360ithub.hr.mobile.set_value",
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "tnc_v2_360ithub.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["tnc_v2_360ithub.utils.before_request"]
# after_request = ["tnc_v2_360ithub.utils.after_request"]

# Job Events
# ----------
# before_job = ["tnc_v2_360ithub.utils.before_job"]
# after_job = ["tnc_v2_360ithub.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"tnc_v2_360ithub.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


# Fixtures
# --------
# Site-level configuration that v1 carried as bare database rows. Sourced from
# v1_schema_export/ and filtered to what this app owns (module = "Tasks").

fixtures = [
	{"dt": "Role", "filters": [["name", "in", ["TNC Employees", "TNC Manager", "TNC Super Admin", "TNC Teachers"]]]},
	{"dt": "Role Profile", "filters": [["name", "in", ["TNC Employees", "TNC Manager", "TNC Super Admin", "TNC Teacher"]]]},
	{"dt": "Custom DocPerm", "filters": [["parent", "in", ["Task", "Comment", "Employee", "User", "Payment Entry", "Purchase Invoice", "Supplier"]], ["role", "in", ["TNC Employees", "TNC Manager", "TNC Super Admin", "TNC Teachers"]]]},
	{"dt": "Number Card", "filters": [["module", "=", "TNC v2"]]},
	{"dt": "Report", "filters": [["module", "=", "TNC v2"], ["is_standard", "=", "No"]]},
	{"dt": "Workspace", "filters": [["module", "=", "TNC v2"]]},
]
