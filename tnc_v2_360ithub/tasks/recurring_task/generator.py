# -*- coding: utf-8 -*-
# Copyright (c) 2026, Administrator and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, getdate


def generate_task_from_recurring_task(doc):
	"""
	Generates normal Task documents from the Recurring Task template.
	For each user in the task_owner child table, a separate Task is created.
	Returns a list of generated (or already existing) Task documents.
	"""
	next_occurrence = (doc.generated_occurrence_count or 0) + 1
	scheduled_date = getdate(doc.next_run_date)

	# 2. Compute expected start and end dates
	exp_start_date = scheduled_date
	if doc.allocated_days and int(doc.allocated_days) > 0:
		exp_end_date = add_days(exp_start_date, int(doc.allocated_days))
	else:
		exp_end_date = exp_start_date

	generated_tasks = []
	owners = [row.user for row in doc.task_owner if row.user] if doc.task_owner else [None]
	if not owners:
		owners = [None]

	for owner in owners:
		# 1. Duplicate prevention check per owner
		existing_task = frappe.db.exists("Task", {
			"recurring_task": doc.name,
			"occurrence_number": next_occurrence,
			"task_owner": owner
		})
		if existing_task:
			frappe.logger().warning(
				f"Task for Recurring Task {doc.name} occurrence #{next_occurrence} and owner {owner} already exists: {existing_task}. Skipping generation."
			)
			generated_tasks.append(frappe.get_doc("Task", existing_task))
			continue

		# 3. Create the Task doc
		task_data = {
			"doctype": "Task",
			"subject": doc.subject,
			"description": doc.description,
			"task_owner": owner,
			"priority": doc.priority or "Medium",
			"exp_start_date": exp_start_date,
			"exp_end_date": exp_end_date,
			# Custom tracking fields
			"recurring_task": doc.name,
			"generated_automatically": 1,
			"occurrence_number": next_occurrence,
		}

		new_task = frappe.get_doc(task_data)
		new_task.insert(ignore_permissions=True)

		# 4. Copy attachments from the Recurring Task to the generated Task
		copy_attachments(doc.doctype, doc.name, new_task.doctype, new_task.name)
		generated_tasks.append(new_task)

	return generated_tasks


def copy_attachments(from_doctype, from_name, to_doctype, to_name):
	"""Copies attachments from one document to another in Frappe."""
	files = frappe.get_all("File", filters={
		"attached_to_doctype": from_doctype,
		"attached_to_name": from_name
	})

	for f in files:
		file_doc = frappe.get_doc("File", f.name)
		# Clone the file document
		new_file = frappe.copy_doc(file_doc)
		new_file.attached_to_doctype = to_doctype
		new_file.attached_to_name = to_name
		# If the file path is a private or public path, keeping file_url is sufficient
		new_file.insert(ignore_permissions=True)
