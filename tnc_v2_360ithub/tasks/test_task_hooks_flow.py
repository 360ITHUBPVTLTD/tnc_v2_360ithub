# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt

"""Verification script for the Task hooks and the reminder job (parity checklist
rows A3, A5, A7, A8, A16 to A18). Same style as the recurrence engine's
test_recurring_task_flow: runs inside one transaction and rolls back.

	bench --site tnc-v2.local execute tnc_v2_360ithub.tasks.test_task_hooks_flow.run_tests

No WhatsApp or FCM provider is needed: with none installed every send must be
recorded as Skipped in WhatsApp Message Log, never raise.
"""

import traceback

import frappe
from frappe.utils import add_days, today

from tnc_v2_360ithub.tasks import jobs

OWNER = "tnc-test-owner@example.com"
HELPER = "tnc-test-helper@example.com"
REPORTER = "tnc-test-reporter@example.com"


def _user(email, phone=None, roles=("TNC Employees",)):
	if not frappe.db.exists("User", email):
		u = frappe.get_doc({"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0, "phone": phone})
		u.insert(ignore_permissions=True)
	u = frappe.get_doc("User", email)
	for r in roles:
		if not any(x.role == r for x in u.roles):
			u.append("roles", {"role": r})
	u.enabled = 1
	u.phone = phone
	u.save(ignore_permissions=True)
	return u


def _logs(ref, channel=None):
	f = {"reference_doctype": "Task", "reference_name": ref}
	if channel:
		f["channel"] = channel
	return frappe.get_all("WhatsApp Message Log", filters=f, fields=["channel", "status", "recipient_user", "error"])


def _bell(user, task):
	return frappe.db.count("Notification Log", {"for_user": user, "document_type": "Task", "document_name": task})


def run_tests():
	frappe.db.begin()
	frappe.flags.in_test = True
	try:
		print("Starting Task hooks verification...")
		# providers off for the duration of this transaction (rolled back below), whatever the site has set
		frappe.db.set_single_value("TNC Settings", {"whatsapp_provider": "Disabled", "fcm_enabled": 0, "in_app_notifications_enabled": 1})
		frappe.clear_document_cache("TNC Settings", "TNC Settings")
		_user(OWNER, phone="9999900001")
		_user(HELPER, phone=None)
		_user(REPORTER)

		# --- A3/A4: insert notifies owner + assignee; WhatsApp attempts are logged ---
		print("  - insert: bell + FCM + WhatsApp log rows")
		frappe.set_user(REPORTER)
		child = frappe.get_meta("Task").get_field("other_assignees").options
		task = frappe.get_doc(
			{
				"doctype": "Task",
				"subject": "Hooks test task",
				"task_owner": OWNER,
				"exp_end_date": add_days(today(), 2),
				"priority": "High",
				"other_assignees": [{"doctype": child, "user": HELPER}],
			}
		).insert()
		frappe.set_user("Administrator")
		assert task.task_reporter == REPORTER, f"reporter should default to creator, got {task.task_reporter}"
		assert _bell(OWNER, task.name) == 1, "owner did not get a bell notification"
		assert _bell(HELPER, task.name) == 1, "helper did not get a bell notification"
		fcm = _logs(task.name, "FCM")
		assert len(fcm) == 2 and all(r.status == "Skipped" for r in fcm), f"FCM should be logged Skipped for both: {fcm}"
		# WhatsApp is enqueued after commit; call the worker directly to check the logging path.
		from tnc_v2_360ithub import notifications
		assert notifications.send_whatsapp(OWNER, "hello", "Task", task.name) == "Skipped"
		assert notifications.send_whatsapp(HELPER, "hello", "Task", task.name) == "Skipped"
		wa = _logs(task.name, "WhatsApp")
		assert len(wa) == 2, f"expected 2 WhatsApp log rows, got {wa}"
		assert any("No phone" in (r.error or "") for r in wa if r.recipient_user == HELPER), "helper without number must be logged as no-phone"
		assert any("Disabled" in (r.error or "") for r in wa if r.recipient_user == OWNER), "owner must be logged as provider disabled"

		# --- A7: non-reporter cannot complete ---
		print("  - completion rule: helper blocked, reporter allowed, admin allowed")
		frappe.set_user(HELPER)
		t = frappe.get_doc("Task", task.name)
		t.status = "Completed"
		blocked = False
		try:
			t.save()
		except frappe.ValidationError:
			blocked = True
		frappe.set_user("Administrator")
		assert blocked, "non-reporter was able to complete the task"

		# --- A8: reporter can complete; status change notifies owner + helper ---
		frappe.set_user(REPORTER)
		t = frappe.get_doc("Task", task.name)
		t.status = "Completed"
		t.save()
		frappe.set_user("Administrator")
		assert frappe.db.get_value("Task", task.name, "status") == "Completed"
		assert _bell(OWNER, task.name) == 2, "owner should be told about the status change"

		# --- A5: comment notifies owner, helper and reporter, not the commenter ---
		print("  - comment notification")
		frappe.set_user(HELPER)
		frappe.get_doc({"doctype": "Comment", "comment_type": "Comment", "reference_doctype": "Task", "reference_name": task.name, "content": "on it"}).insert(ignore_permissions=True)
		frappe.set_user("Administrator")
		assert _bell(OWNER, task.name) == 3, "owner should be told about the comment"
		assert _bell(REPORTER, task.name) == 1, "reporter should be told about the comment"
		assert _bell(HELPER, task.name) == 2, "the commenter must not be notified of their own comment"

		# --- A16-A18: reminder job is safe with no provider and respects the switch ---
		print("  - reminder job: disabled switch, then graceful abort without provider")
		s = frappe.get_single("TNC Settings")
		s.task_reminders_enabled = 0
		s.save(ignore_permissions=True)
		assert jobs.enqueue_task_reminders().startswith("Skipped")
		# a Monday that is not a holiday
		monday = "2026-09-14"
		frappe.db.delete("Holiday", {"holiday_date": monday})
		result = jobs.send_due_and_overdue_task_reminders(monday)
		assert result.startswith("Aborted"), f"without a provider the digest must abort cleanly: {result}"
		per_user, stats = jobs.collect_reminders(monday)
		assert OWNER not in per_user or not per_user[OWNER]["overdue"], "completed task must not appear in reminders"
		open_task = frappe.get_doc({"doctype": "Task", "subject": "Digest test", "task_owner": OWNER, "exp_start_date": "2026-09-01", "exp_end_date": "2026-09-10"}).insert(ignore_permissions=True)
		per_user, _ = jobs.collect_reminders(monday)
		assert per_user[OWNER]["overdue"], "open overdue task must appear in the owner's overdue bucket"
		msg = jobs.build_message(OWNER, per_user[OWNER])
		assert "Overdue Tasks (1)" in msg and "Digest test" in msg, msg
		assert jobs.send_due_and_overdue_task_reminders("2026-09-13").startswith("Skipped"), "Sunday must be skipped"

		print("\nAll Task hook verification checks PASSED successfully!")
	except Exception:
		traceback.print_exc()
		raise
	finally:
		frappe.set_user("Administrator")
		frappe.db.rollback()
		print("Cleanup completed (transaction rolled back).")
