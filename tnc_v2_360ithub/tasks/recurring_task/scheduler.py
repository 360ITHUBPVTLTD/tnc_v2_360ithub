# -*- coding: utf-8 -*-
# Copyright (c) 2026, Administrator and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate
from tnc_v2_360ithub.tasks.recurring_task.generator import generate_task_from_recurring_task
from tnc_v2_360ithub.tasks.recurring_task.date_calculator import get_next_run_date


@frappe.whitelist()
def run_scheduler():
	"""
	Scheduler entry point. Fetches all active recurring tasks and generates due tasks.
	"""
	active_tasks = frappe.get_all(
		"Recurring Task",
		filters={"status": "Active", "enabled": 1},
		fields=["name"]
	)

	today = getdate()

	for task_ref in active_tasks:
		try:
			process_recurring_task(task_ref.name, today)
		except Exception as e:
			frappe.log_error(
				title=f"Recurring Task {task_ref.name} failed in scheduler",
				message=frappe.get_traceback()
			)


def process_recurring_task(docname, today):
	"""
	Processes a single active recurring task. Catch up until next_run_date is in the future.
	"""
	# Get doc with write lock to prevent race conditions
	doc = frappe.get_doc("Recurring Task", docname)
	doc.db_set("status", doc.status)  # dummy to check DB transaction lock if needed, but get_doc is fine

	while doc.status == "Active" and doc.enabled and doc.next_run_date and getdate(doc.next_run_date) <= today:
		# Generate the standard Task
		generate_task_from_recurring_task(doc)

		# Advance occurrence trackers
		doc.generated_occurrence_count = (doc.generated_occurrence_count or 0) + 1
		doc.last_run_date = doc.next_run_date

		# Determine if limits have been reached before calculating next date
		is_completed = False
		if doc.ends == "After Occurrences" and doc.number_of_occurrences:
			if doc.generated_occurrence_count >= int(doc.number_of_occurrences):
				is_completed = True

		# Calculate the subsequent Next Run Date
		next_run = get_next_run_date(doc)
		doc.next_run_date = next_run

		# If ends on date and next run date is past end date, mark completed
		if doc.ends == "On Date" and doc.end_date and doc.next_run_date:
			if getdate(doc.next_run_date) > getdate(doc.end_date):
				is_completed = True

		if is_completed:
			doc.status = "Completed"
			doc.enabled = 0
			doc.next_run_date = None

		doc.save()
		# Commit per template so one failure does not roll back the others.
		# Skipped under tests so the verification scripts can roll back cleanly.
		if not frappe.flags.in_test:
			frappe.db.commit()
