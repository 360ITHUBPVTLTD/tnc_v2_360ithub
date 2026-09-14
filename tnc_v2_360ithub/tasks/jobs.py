# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt

"""Scheduled jobs for the Tasks module.

08:00 WhatsApp digest of today's, overdue and upcoming tasks per user, ported
from v1 tnc_frappe_custom_app.custom_employee.send_due_and_overdue_task_reminders.

Differences from v1 (module design, parity layer):
- gated by TNC Settings.task_reminders_enabled instead of a hard-coded
  production site name
- sends through tnc_v2_360ithub.notifications, so every message is logged
- the summary is returned and logged once; per-user chatter is in the log rows
"""

from datetime import date

import frappe
from frappe.utils import getdate

from tnc_v2_360ithub import notifications

ACTIVE_STATUSES = ["Working", "Open", "Pending Review", "Overdue"]


def enqueue_task_reminders():
	"""Cron entry point (08:00). Cheap check, then hand off to a long worker."""
	if not notifications.settings().task_reminders_enabled:
		return "Skipped: task reminders disabled in TNC Settings"
	frappe.enqueue(
		"tnc_v2_360ithub.tasks.jobs.send_due_and_overdue_task_reminders",
		queue="long",
		job_name="Send Due and Overdue Task Reminders",
	)
	return "Enqueued"


def _is_working_day(today):
	if today.weekday() == 6:
		return False, "Sunday"
	if frappe.db.exists("Holiday", {"holiday_date": today}):
		return False, "holiday"
	return True, ""


def collect_reminders(today=None):
	"""Return {user: {"today": [...], "overdue": [...], "upcoming": [...]}} for active tasks."""
	today = getdate(today) if today else date.today()
	tasks = frappe.get_all(
		"Task",
		filters={"status": ["in", ACTIVE_STATUSES], "is_template": 0},
		or_filters=[["Task", "exp_start_date", "<=", today], ["Task", "exp_start_date", "is", "not set"]],
		fields=["name", "subject", "exp_end_date", "task_owner"],
	)
	names = [t.name for t in tasks]
	others = {}
	if names:
		child = frappe.get_meta("Task").get_field("other_assignees")
		if child and child.options:
			for row in frappe.get_all(child.options, filters={"parenttype": "Task", "parentfield": "other_assignees", "parent": ["in", names]}, fields=["parent", "user"]):
				if row.user:
					others.setdefault(row.parent, []).append(row.user)

	per_user = {}
	skipped_no_due, skipped_no_assignee = [], []
	for t in tasks:
		if not t.exp_end_date:
			skipped_no_due.append(t.name)
			continue
		recipients = set(others.get(t.name) or [])
		if t.task_owner:
			recipients.add(t.task_owner)
		if not recipients:
			skipped_no_assignee.append(t.name)
			continue
		due = getdate(t.exp_end_date)
		bucket = "today" if due == today else ("overdue" if due < today else "upcoming")
		for u in recipients:
			per_user.setdefault(u, {"today": [], "overdue": [], "upcoming": []})[bucket].append({"title": t.subject, "due_date": due})
	return per_user, {"tasks": len(tasks), "no_due_date": skipped_no_due, "no_assignee": skipped_no_assignee}


def build_message(user, buckets):
	name = frappe.db.get_value("User", user, "full_name") or user
	manager = ""
	emp = frappe.get_all("Employee", filters={"user_id": user, "status": "Active"}, fields=["reports_to"], limit=1)
	if emp and emp[0].reports_to:
		manager = frappe.get_value("Employee", emp[0].reports_to, "first_name") or ""
	parts = [f"Reminder: Task Summary\n\nHi {name},\n\nHere are your tasks:\n"]
	if buckets["today"]:
		parts.append("⭐ Today's Tasks (%d):\n%s\n" % (len(buckets["today"]), "\n".join(f"• {t['title']}" for t in buckets["today"])))
	if buckets["overdue"]:
		parts.append("⭐ Overdue Tasks (%d):\n%s\n" % (len(buckets["overdue"]), "\n".join(f"• {t['title']} - {t['due_date'].strftime('%d-%b-%Y')}" for t in buckets["overdue"])))
	if buckets["upcoming"]:
		parts.append("⭐ Upcoming Tasks (%d):\n%s\n" % (len(buckets["upcoming"]), "\n".join(f"• {t['title']} - {t['due_date'].strftime('%d-%b-%Y')}" for t in buckets["upcoming"])))
	parts.append(f"Please prioritize and complete them. If you need help, contact your manager {manager}.\n\nTNC Admin Team")
	return "\n".join(p.strip() for p in parts if p.strip())


def send_due_and_overdue_task_reminders(today=None):
	today = getdate(today) if today else date.today()
	ok, why = _is_working_day(today)
	if not ok:
		return f"Skipped: {today} is a {why}"

	available, reason = notifications.whatsapp_available()
	if not available:
		frappe.log_error(title="WA REMINDER ABORTED", message=reason)
		return f"Aborted: {reason}"

	per_user, stats = collect_reminders(today)
	if stats["no_due_date"] or stats["no_assignee"]:
		frappe.log_error(
			title="WA REMINDER SKIPPED TASKS",
			message=f"No assignee ({len(stats['no_assignee'])}): {stats['no_assignee']}\nNo exp_end_date ({len(stats['no_due_date'])}): {stats['no_due_date']}",
		)

	counts = {"Sent": 0, "Failed": 0, "Skipped": 0}
	for user, buckets in per_user.items():
		if not any(buckets.values()):
			continue
		result = notifications.send_whatsapp(user, build_message(user, buckets), "Task", None)
		counts[result] = counts.get(result, 0) + 1

	summary = f"Tasks considered: {stats['tasks']} | Recipients: {len(per_user)} | Sent: {counts['Sent']} | Failed: {counts['Failed']} | Skipped: {counts['Skipped']}"
	frappe.log_error(title="WA REMINDER SUMMARY", message=summary)
	return summary
