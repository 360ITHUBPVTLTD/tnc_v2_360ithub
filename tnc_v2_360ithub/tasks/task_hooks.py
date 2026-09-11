# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt

"""Task document hooks, ported from v1 tnc_frappe_custom_app.custom_task.

Parity behaviour (acceptance checklist rows A3 to A8):
- on insert: owner + other assignees get bell + FCM, owner also gets WhatsApp
- on update: a new owner or newly added assignee is notified the same way;
  a status change notifies owner + assignees (bell + FCM)
- on comment: owner + assignees are told who commented
- only the Reporter or an admin may set Completed

Differences from v1, both agreed in the module design:
- the completion rule checks task_reporter (defaulted to the creator on
  insert) instead of doc.owner, so generated tasks behave correctly
- every outbound message goes through tnc_v2_360ithub.notifications
"""

import re

import frappe
from frappe.utils import formatdate, get_fullname, strip_html

from tnc_v2_360ithub import notifications

ADMIN_ROLES = {"Administrator", "System Manager", "TNC Super Admin"}


def _assignees(doc):
	users = set()
	if doc.get("task_owner"):
		users.add(doc.task_owner)
	for row in doc.get("other_assignees") or []:
		if row.get("user"):
			users.add(row.user)
	return users


# ---------------------------------------------------------------------------
# before_save: reporter default + completion rule
# ---------------------------------------------------------------------------


def before_save(doc, method=None):
	if doc.is_new() and not doc.get("task_reporter"):
		doc.task_reporter = frappe.session.user if frappe.session.user != "Guest" else None

	old = doc.get_doc_before_save()
	being_completed = doc.status == "Completed" and old and old.status != "Completed"
	if not being_completed:
		return

	user = frappe.session.user
	is_reporter = user in {doc.get("task_reporter"), doc.owner}
	is_admin = bool(ADMIN_ROLES & set(frappe.get_roles(user)))
	if not (is_reporter or is_admin):
		frappe.throw("You need to be creator of the task to mark it as completed.")


# ---------------------------------------------------------------------------
# after_insert / on_update
# ---------------------------------------------------------------------------


def after_insert(doc, method=None):
	recipients = _assignees(doc)
	if not recipients:
		return
	for user in recipients:
		notifications.queue_whatsapp(user, assignment_message(doc, user), "Task", doc.name)
	notifications.notify_users(recipients, doc, f"You have been assigned a new task: {doc.subject}", title=f"Task: {doc.subject}")


def on_update(doc, method=None):
	old = doc.get_doc_before_save()
	if not old:
		return

	newly_assigned = set()
	if old.get("task_owner") != doc.get("task_owner") and doc.get("task_owner"):
		newly_assigned.add(doc.task_owner)
	old_users = {r.user for r in old.get("other_assignees") or [] if r.get("user")}
	new_users = {r.user for r in doc.get("other_assignees") or [] if r.get("user")}
	newly_assigned |= new_users - old_users

	if newly_assigned:
		for user in newly_assigned:
			notifications.queue_whatsapp(user, assignment_message(doc, user), "Task", doc.name)
		notifications.notify_users(newly_assigned, doc, f"You have been assigned to task: {doc.subject}", title=f"Task: {doc.subject}")

	if old.status != doc.status:
		recipients = _assignees(doc)
		recipients.discard(frappe.session.user)
		if recipients:
			notifications.notify_users(recipients, doc, f"Task status changed to {doc.status}: {doc.subject}", title=f"Task: {doc.subject}")


# ---------------------------------------------------------------------------
# Comment.after_insert
# ---------------------------------------------------------------------------


def on_comment(doc, method=None):
	if doc.reference_doctype != "Task" or not doc.reference_name or doc.comment_type != "Comment":
		return
	task = frappe.get_doc("Task", doc.reference_name)
	recipients = _assignees(task)
	if task.get("task_reporter"):
		recipients.add(task.task_reporter)
	recipients.discard(frappe.session.user)
	if recipients:
		who = get_fullname(frappe.session.user)
		notifications.notify_users(recipients, task, f"{who} commented on task: {task.subject}", title=f"Task: {task.subject}")


# ---------------------------------------------------------------------------
# message text (kept identical to v1 so users see no change)
# ---------------------------------------------------------------------------


def clean_html_for_whatsapp(html_text):
	if not html_text:
		return ""
	html_text = html_text.replace("</li>", "\n").replace("<li", "\n• <li")
	for tag in ("</p>", "</div>", "<br>", "<br/>"):
		html_text = html_text.replace(tag, "\n")
	text = strip_html(html_text)
	text = "\n".join(line.strip() for line in text.split("\n"))
	return re.sub(r"\n\s*\n", "\n\n", text).strip()


def assignment_message(doc, user):
	recipient_name = frappe.db.get_value("User", user, "full_name") or user
	description = clean_html_for_whatsapp(doc.get("description") or "No description provided")
	due = formatdate(doc.exp_end_date) if doc.get("exp_end_date") else "Not Set"
	assigned_by = frappe.db.get_value("Employee", {"user_id": doc.modified_by}, "employee_name") or doc.modified_by
	return (
		f"Dear {recipient_name},\n"
		f"You have been assigned a new task:\n"
		f"📌 *{doc.subject}*({due})\n"
		f"🔥 *Priority*: {doc.priority}\n"
		f"📝*Description*:\n{description}\n"
		f"👤 *Assigned By*: {assigned_by}\n"
		f"Regards\nTNC Admin\n"
	)
