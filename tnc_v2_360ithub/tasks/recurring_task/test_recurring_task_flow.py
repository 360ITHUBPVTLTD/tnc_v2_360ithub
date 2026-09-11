# -*- coding: utf-8 -*-
# Copyright (c) 2026, Administrator and contributors
# For license information, please see license.txt

import frappe
import datetime
from frappe.utils import getdate, add_days
from tnc_v2_360ithub.tasks.recurring_task.date_calculator import get_next_run_date
from tnc_v2_360ithub.tasks.recurring_task.scheduler import process_recurring_task


def run_tests():
	"""
	Main runner for the self-check verification tests.
	Can be executed via:
	bench --site tnc-v2.local execute tnc_v2_360ithub.tasks.recurring_task.test_recurring_task_flow.run_tests
	"""
	print("Starting Recurring Task Module Verification Tests...")

	# Ensure we run in a controlled test environment/transaction
	frappe.db.begin()
	try:
		test_daily_recurrence_and_idempotency()
		test_weekly_next_run_date()
		test_monthly_last_day_of_month()
		test_monthly_fewer_days_wrapping()
		test_custom_interval_recurrence()
		test_pause_resume_stop_transitions()
		test_allocated_days_expected_dates()
		test_multiple_task_owners_generation()
		test_paused_period_skipping()
		test_validation_rules()
		test_edit_restrictions_when_active()
		print("\nAll automated verification checks PASSED successfully!")
	except AssertionError as e:
		frappe.db.rollback()
		print(f"\nVerification check FAILED: {str(e)}")
		raise e
	except Exception as e:
		frappe.db.rollback()
		print(f"\nVerification check FAILED with unexpected exception: {str(e)}")
		raise e
	finally:
		# Rollback transaction so no garbage is committed to the site database
		frappe.db.rollback()
		print("Cleanup completed (transaction rolled back).")


def test_daily_recurrence_and_idempotency():
	print("  - Running test: Daily Recurrence and Idempotency...")
	
	today = getdate()
	
	# Create a Daily Recurring Task
	doc = frappe.get_doc({
		"doctype": "Recurring Task",
		"naming_series": "REC-TSK-.#####",
		"subject": "Daily Self-Check Task",
		"task_owner": [{"user": "Administrator"}],
		"frequency": "Daily",
		"start_date": today,
		"ends": "Never",
		"enabled": 1
	})
	doc.insert(ignore_permissions=True)
	
	assert doc.status == "Active", f"Expected Active status, got {doc.status}"
	assert doc.next_run_date == today, f"Expected Next Run Date to be {today}, got {doc.next_run_date}"
	
	# Process via Scheduler for today
	process_recurring_task(doc.name, today)
	
	# Reload and assert
	doc.reload()
	assert doc.generated_occurrence_count == 1, f"Expected 1 occurrence, got {doc.generated_occurrence_count}"
	assert doc.last_run_date == today, f"Expected Last Run Date to be {today}, got {doc.last_run_date}"
	assert doc.next_run_date == add_days(today, 1), f"Expected Next Run Date to be {add_days(today, 1)}, got {doc.next_run_date}"
	
	# Assert Task was generated
	tasks = frappe.get_all("Task", filters={"recurring_task": doc.name})
	assert len(tasks) == 1, f"Expected 1 generated Task, found {len(tasks)}"
	
	task_doc = frappe.get_doc("Task", tasks[0].name)
	assert task_doc.occurrence_number == 1
	assert task_doc.generated_automatically == 1
	assert task_doc.subject == "Daily Self-Check Task"
	
	# Run the scheduler again on the same day (verify Idempotency)
	process_recurring_task(doc.name, today)
	doc.reload()
	
	# Occurrence shouldn't change, and no duplicate task should be created
	assert doc.generated_occurrence_count == 1
	tasks_after = frappe.get_all("Task", filters={"recurring_task": doc.name})
	assert len(tasks_after) == 1, f"Duplicate task created! Found {len(tasks_after)} tasks"


def test_weekly_next_run_date():
	print("  - Running test: Weekly next run date calculations...")
	
	# Start date: 2026-07-23 (Thursday)
	start_date = getdate("2026-07-23")
	
	# Case 1: Weekly (Monday). Next Monday should be 2026-07-27
	doc1 = frappe.get_doc({
		"doctype": "Recurring Task",
		"naming_series": "REC-TSK-.#####",
		"subject": "Weekly Monday Task",
		"task_owner": [{"user": "Administrator"}],
		"frequency": "Weekly",
		"day_of_week": "Monday",
		"start_date": start_date,
		"ends": "Never",
		"enabled": 1
	})
	doc1.insert(ignore_permissions=True)
	assert doc1.next_run_date == getdate("2026-07-27"), f"Expected 2026-07-27, got {doc1.next_run_date}"

	# Case 2: Weekly (Thursday). Start date Thursday matches -> Next run should be 2026-07-23
	doc2 = frappe.get_doc({
		"doctype": "Recurring Task",
		"naming_series": "REC-TSK-.#####",
		"subject": "Weekly Thursday Task",
		"task_owner": [{"user": "Administrator"}],
		"frequency": "Weekly",
		"day_of_week": "Thursday",
		"start_date": start_date,
		"ends": "Never",
		"enabled": 1
	})
	doc2.insert(ignore_permissions=True)
	assert doc2.next_run_date == getdate("2026-07-23"), f"Expected 2026-07-23, got {doc2.next_run_date}"


def test_monthly_last_day_of_month():
	print("  - Running test: Monthly Last Day of Month calculation...")
	
	# Start date in a leap year: 2024-02-10
	start_date = getdate("2024-02-10")
	doc = frappe.get_doc({
		"doctype": "Recurring Task",
		"naming_series": "REC-TSK-.#####",
		"subject": "Monthly Last Day Task",
		"task_owner": [{"user": "Administrator"}],
		"frequency": "Monthly",
		"repeat_by": "Last Day of Month",
		"start_date": start_date,
		"ends": "Never",
		"enabled": 1
	})
	doc.insert(ignore_permissions=True)
	# Next run should be last day of Feb 2024, i.e. 29th (since 2024 is a leap year)
	assert doc.next_run_date == getdate("2024-02-29"), f"Expected 2024-02-29, got {doc.next_run_date}"
	
	# Simulate run
	doc.last_run_date = doc.next_run_date
	doc.generated_occurrence_count = 1
	doc.next_run_date = get_next_run_date(doc)
	# Next month is March. Last day should be 2024-03-31
	assert doc.next_run_date == getdate("2024-03-31"), f"Expected 2024-03-31, got {doc.next_run_date}"


def test_monthly_fewer_days_wrapping():
	print("  - Running test: Monthly 31st Wrapping in shorter months...")
	
	# Start date: 2026-04-10 (April).
	# Setup day of month = 31. April only has 30 days. Should wrap to April 30.
	start_date = getdate("2026-04-10")
	doc = frappe.get_doc({
		"doctype": "Recurring Task",
		"naming_series": "REC-TSK-.#####",
		"subject": "Monthly 31st Task",
		"task_owner": [{"user": "Administrator"}],
		"frequency": "Monthly",
		"repeat_by": "Day of Month",
		"day_of_month": "31",
		"start_date": start_date,
		"ends": "Never",
		"enabled": 1
	})
	doc.insert(ignore_permissions=True)
	# Target 31st in April 2026 does not exist -> should run on April 30th
	assert doc.next_run_date == getdate("2026-04-30"), f"Expected 2026-04-30, got {doc.next_run_date}"

	# Simulate run
	doc.last_run_date = doc.next_run_date
	doc.generated_occurrence_count = 1
	doc.next_run_date = get_next_run_date(doc)
	# Next month is May 2026 (has 31 days). Target 31st -> next run May 31
	assert doc.next_run_date == getdate("2026-05-31"), f"Expected 2026-05-31, got {doc.next_run_date}"


def test_custom_interval_recurrence():
	print("  - Running test: Custom Interval Recurrence...")
	
	start_date = getdate("2026-07-23")
	doc = frappe.get_doc({
		"doctype": "Recurring Task",
		"naming_series": "REC-TSK-.#####",
		"subject": "Custom Every 2 Weeks Task",
		"task_owner": [{"user": "Administrator"}],
		"frequency": "Custom",
		"repeat_every": 2,
		"unit": "Weeks",
		"start_date": start_date,
		"ends": "Never",
		"enabled": 1
	})
	doc.insert(ignore_permissions=True)
	
	# First run should be start_date
	assert doc.next_run_date == start_date, f"Expected {start_date}, got {doc.next_run_date}"
	
	# Simulate run
	doc.last_run_date = doc.next_run_date
	doc.generated_occurrence_count = 1
	doc.next_run_date = get_next_run_date(doc)
	
	# Next run should be start_date + 14 days = 2026-08-06
	expected_next = getdate("2026-08-06")
	assert doc.next_run_date == expected_next, f"Expected {expected_next}, got {doc.next_run_date}"


def test_pause_resume_stop_transitions():
	print("  - Running test: Pause, Resume, and Stop state transitions...")
	
	today = getdate()
	doc = frappe.get_doc({
		"doctype": "Recurring Task",
		"naming_series": "REC-TSK-.#####",
		"subject": "State Check Task",
		"task_owner": [{"user": "Administrator"}],
		"frequency": "Daily",
		"start_date": today,
		"ends": "Never",
		"enabled": 1
	})
	doc.insert(ignore_permissions=True)
	assert doc.status == "Active"
	
	# Pause
	doc.pause_recurrence()
	assert doc.status == "Paused"
	assert doc.enabled == 0
	
	# Resume
	doc.resume_recurrence()
	assert doc.status == "Active"
	assert doc.enabled == 1
	assert doc.next_run_date == today
	
	# Stop
	doc.stop_recurrence()
	assert doc.status == "Stopped"
	assert doc.enabled == 0


def test_allocated_days_expected_dates():
	print("  - Running test: Expected Start & End date generation based on Allocated Days...")
	
	today = getdate()
	doc = frappe.get_doc({
		"doctype": "Recurring Task",
		"naming_series": "REC-TSK-.#####",
		"subject": "Expected Date Check Task",
		"task_owner": [{"user": "Administrator"}],
		"frequency": "Daily",
		"start_date": today,
		"ends": "Never",
		"allocated_days": 5,
		"enabled": 1
	})
	doc.insert(ignore_permissions=True)
	
	# Run scheduler
	process_recurring_task(doc.name, today)
	
	# Find generated task
	tasks = frappe.get_all("Task", filters={"recurring_task": doc.name})
	assert len(tasks) == 1
	
	task_doc = frappe.get_doc("Task", tasks[0].name)
	assert task_doc.exp_start_date == today, f"Expected exp_start_date {today}, got {task_doc.exp_start_date}"
	expected_end = add_days(today, 5)
	assert task_doc.exp_end_date == expected_end, f"Expected exp_end_date {expected_end}, got {task_doc.exp_end_date}"


def test_multiple_task_owners_generation():
	print("  - Running test: Multiple task owners generating separate Tasks...")
	
	today = getdate()
	
	# Find or create a second user for testing
	users = frappe.get_all("User", filters={"enabled": 1}, limit=2)
	test_users = [u.name for u in users]
	if len(test_users) < 2:
		dummy_email = "dummy_owner@example.com"
		if not frappe.db.exists("User", dummy_email):
			dummy_user = frappe.get_doc({
				"doctype": "User",
				"email": dummy_email,
				"first_name": "Dummy Owner",
				"send_welcome_email": 0
			})
			dummy_user.insert(ignore_permissions=True)
		test_users = ["Administrator", dummy_email]
		
	# Create a Daily Recurring Task with 2 owners
	doc = frappe.get_doc({
		"doctype": "Recurring Task",
		"naming_series": "REC-TSK-.#####",
		"subject": "Multi-Owner Task",
		"task_owner": [{"user": test_users[0]}, {"user": test_users[1]}],
		"frequency": "Daily",
		"start_date": today,
		"ends": "Never",
		"enabled": 1
	})
	doc.insert(ignore_permissions=True)
	
	# Run scheduler
	process_recurring_task(doc.name, today)
	
	# Assert 2 separate Tasks were generated
	tasks = frappe.get_all("Task", filters={"recurring_task": doc.name})
	assert len(tasks) == 2, f"Expected 2 separate Tasks, found {len(tasks)}"
	
	task_owners = [frappe.db.get_value("Task", t.name, "task_owner") for t in tasks]
	assert test_users[0] in task_owners
	assert test_users[1] in task_owners


def test_paused_period_skipping():
	print("  - Running test: Paused period skipping (no tasks generated for pause time)...")
	
	# Start date: 6 days ago
	today = getdate()
	start_date = add_days(today, -6)
	
	doc = frappe.get_doc({
		"doctype": "Recurring Task",
		"naming_series": "REC-TSK-.#####",
		"subject": "Skip Pause Period Test Task",
		"task_owner": [{"user": "Administrator"}],
		"frequency": "Daily",
		"start_date": start_date,
		"ends": "Never",
		"enabled": 1
	})
	doc.insert(ignore_permissions=True)
	
	# Day 0: start_date. Run scheduler for start_date
	process_recurring_task(doc.name, start_date)
	doc.reload()
	assert doc.generated_occurrence_count == 1
	assert doc.next_run_date == add_days(start_date, 1)
	
	# Day 1: start_date + 1. Run scheduler
	process_recurring_task(doc.name, add_days(start_date, 1))
	doc.reload()
	assert doc.generated_occurrence_count == 2
	assert doc.next_run_date == add_days(start_date, 2)
	
	# Day 2: start_date + 2. Run scheduler
	process_recurring_task(doc.name, add_days(start_date, 2))
	doc.reload()
	assert doc.generated_occurrence_count == 3
	assert doc.next_run_date == add_days(start_date, 3)
	
	# Day 3: User pauses it
	doc.pause_recurrence()
	doc.reload()
	assert doc.status == "Paused"
	assert doc.enabled == 0
	
	# Today is Day 6 (today). We resume the task today
	doc.resume_recurrence()
	doc.reload()
	assert doc.status == "Active"
	assert doc.enabled == 1
	
	# Next run date MUST be today (Day 6) and NOT Day 3!
	assert doc.next_run_date == today, f"Expected Next Run Date to be today ({today}), got {doc.next_run_date}"
	
	# Run scheduler for today
	process_recurring_task(doc.name, today)
	doc.reload()
	assert doc.generated_occurrence_count == 4
	assert doc.next_run_date == add_days(today, 1)
	
	# Verify total generated tasks is exactly 4 (Day 0, 1, 2, 6). No tasks for Day 3, 4, 5.
	tasks = frappe.get_all("Task", filters={"recurring_task": doc.name})
	assert len(tasks) == 4, f"Expected exactly 4 Tasks, found {len(tasks)}"
	
	task_dates = sorted([getdate(frappe.db.get_value("Task", t.name, "exp_start_date")) for t in tasks])
	expected_dates = [start_date, add_days(start_date, 1), add_days(start_date, 2), today]
	assert task_dates == expected_dates, f"Expected task dates {expected_dates}, got {task_dates}"


def test_validation_rules():
	print("  - Running test: Validation rules and integrity checks...")
	
	today = getdate()
	
	# Case 1: end_date < start_date
	doc = frappe.get_doc({
		"doctype": "Recurring Task",
		"naming_series": "REC-TSK-.#####",
		"subject": "Invalid Dates Task",
		"task_owner": [{"user": "Administrator"}],
		"frequency": "Daily",
		"start_date": today,
		"ends": "On Date",
		"end_date": add_days(today, -1),
		"enabled": 1
	})
	try:
		doc.insert(ignore_permissions=True)
		assert False, "Should have thrown exception for end_date < start_date"
	except frappe.ValidationError as e:
		assert "End Date cannot be before Start Date" in str(e)
		
	# Case 2: Custom frequency with repeat_every <= 0
	doc2 = frappe.get_doc({
		"doctype": "Recurring Task",
		"naming_series": "REC-TSK-.#####",
		"subject": "Invalid Custom Interval Task",
		"task_owner": [{"user": "Administrator"}],
		"frequency": "Custom",
		"repeat_every": 0,
		"unit": "Days",
		"start_date": today,
		"ends": "Never",
		"enabled": 1
	})
	try:
		doc2.insert(ignore_permissions=True)
		assert False, "Should have thrown exception for repeat_every <= 0"
	except frappe.ValidationError as e:
		assert "Repeat Every must be a positive integer" in str(e)


def test_edit_restrictions_when_active():
	print("  - Running test: Restriction on editing config fields while Active...")
	
	today = getdate()
	doc = frappe.get_doc({
		"doctype": "Recurring Task",
		"naming_series": "REC-TSK-.#####",
		"subject": "Edit Restriction Task",
		"task_owner": [{"user": "Administrator"}],
		"frequency": "Daily",
		"start_date": today,
		"ends": "Never",
		"enabled": 1
	})
	doc.insert(ignore_permissions=True)
	assert doc.status == "Active"
	
	# Attempt to change frequency while Active
	doc.frequency = "Weekly"
	doc.day_of_week = "Monday"
	try:
		doc.save()
		assert False, "Should have thrown validation error when editing active config"
	except frappe.ValidationError as e:
		assert "Cannot edit recurrence configuration field" in str(e)
		
	# Pause the task, then changing frequency should succeed
	doc.reload()
	doc.pause_recurrence()
	assert doc.status == "Paused"
	
	doc.frequency = "Weekly"
	doc.day_of_week = "Monday"
	doc.save() # Should not throw error
	assert doc.frequency == "Weekly"

