# -*- coding: utf-8 -*-
# Copyright (c) 2026, Administrator and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from tnc_v2_360ithub.tasks.recurring_task.date_calculator import (
	get_next_run_date,
	get_recurrence_summary,
)


class RecurringTask(Document):
	def validate(self):
		self.validate_edit_restrictions()
		self.validate_dates()
		self.validate_frequency_fields()

	def is_value_equal(self, val1, val2):
		if not val1 and not val2:
			return True
		return str(val1).strip() == str(val2).strip()

	def validate_edit_restrictions(self):
		before_save_doc = self.get_doc_before_save()
		if before_save_doc and before_save_doc.status not in ["Draft", "Paused"]:
			config_fields = [
				"frequency", "day_of_week", "repeat_by", "day_of_month", 
				"repeat_every", "unit", "start_date", "ends", "end_date", 
				"number_of_occurrences"
			]
			for field in config_fields:
				if not self.is_value_equal(self.get(field), before_save_doc.get(field)):
					frappe.throw(
						f"Cannot edit recurrence configuration field '{self.meta.get_label(field)}' "
						f"while the status is '{before_save_doc.status}'. Please pause the recurrence first."
					)

	def validate_dates(self):
		from frappe.utils import getdate
		if self.start_date:
			start = getdate(self.start_date)
			if self.ends == "On Date":
				if not self.end_date:
					frappe.throw("End Date is required when Ends is 'On Date'")
				end = getdate(self.end_date)
				if end < start:
					frappe.throw("End Date cannot be before Start Date")

	def validate_frequency_fields(self):
		if self.frequency == "Weekly":
			if not self.day_of_week:
				frappe.throw("Day of Week is required for Weekly frequency")
		elif self.frequency == "Monthly":
			if not self.repeat_by:
				frappe.throw("Repeat By is required for Monthly frequency")
			if self.repeat_by == "Day of Month" and not self.day_of_month:
				frappe.throw("Day of Month is required when Repeat By is 'Day of Month'")
		elif self.frequency == "Custom":
			if not self.repeat_every or int(self.repeat_every) <= 0:
				frappe.throw("Repeat Every must be a positive integer for Custom frequency")
			if not self.unit:
				frappe.throw("Unit is required for Custom frequency")

		if self.ends == "After Occurrences":
			if not self.number_of_occurrences or int(self.number_of_occurrences) <= 0:
				frappe.throw("Number of Occurrences must be a positive integer when Ends is 'After Occurrences'")

	def before_save(self):
		# Automatically generate recurrence summary
		self.recurrence_summary = get_recurrence_summary(self)

		# Check if any recurrence configuration fields changed
		config_fields = [
			"frequency", "day_of_week", "repeat_by", "day_of_month", 
			"repeat_every", "unit", "start_date", "ends", "end_date", 
			"number_of_occurrences", "enabled"
		]
		is_config_changed = False
		before_save_doc = self.get_doc_before_save()
		if before_save_doc:
			for field in config_fields:
				if not self.is_value_equal(self.get(field), before_save_doc.get(field)):
					is_config_changed = True
					break
		else:
			is_config_changed = True

		# State Transitions based on checkbox
		if self.enabled:
			if self.status in ["Draft", "Paused", "Completed"]:
				self.status = "Active"
		else:
			if self.status == "Active":
				self.status = "Paused"
			elif self.status not in ["Draft", "Completed", "Stopped"]:
				self.status = "Paused"

		# Recalculate next_run_date if config changed or if next_run_date is missing
		if is_config_changed or not self.next_run_date:
			if self.status == "Active":
				from frappe.utils import getdate
				# Determine reference date: Use last_run_date if start_date is not ahead of it
				ref_date = self.start_date
				if self.last_run_date and getdate(self.start_date) <= getdate(self.last_run_date):
					ref_date = self.last_run_date
				
				next_run = get_next_run_date(self, reference_date=ref_date)
				
				# Skip catchup if:
				# 1. We are resuming/restarting from Paused, Stopped, or Completed state.
				# 2. Or, config is changed on an existing active task.
				is_resuming = before_save_doc and before_save_doc.status in ["Paused", "Stopped", "Completed"]
				is_edit_config_change = before_save_doc and is_config_changed
				
				if is_resuming or is_edit_config_change:
					today = getdate()
					while next_run and next_run < today:
						next_run = get_next_run_date(self, reference_date=next_run)
				
				self.next_run_date = next_run

		# Validate and check if limits are exceeded
		is_completed = False
		if self.status == "Active" and self.next_run_date:
			from frappe.utils import getdate
			if self.ends == "On Date" and self.end_date:
				if getdate(self.next_run_date) > getdate(self.end_date):
					is_completed = True
			elif self.ends == "After Occurrences" and self.number_of_occurrences:
				if (self.generated_occurrence_count or 0) >= int(self.number_of_occurrences):
					is_completed = True

		if is_completed:
			self.status = "Completed"
			self.enabled = 0
			self.next_run_date = None

		# If Completed or Stopped, force enabled to 0
		if self.status in ["Completed", "Stopped"]:
			self.enabled = 0
			self.next_run_date = None

	@frappe.whitelist()
	def pause_recurrence(self):
		self.enabled = 0
		self.status = "Paused"
		self.save()
		return self.status

	@frappe.whitelist()
	def resume_recurrence(self):
		self.enabled = 1
		self.status = "Active"
		self.save()
		return self.status

	@frappe.whitelist()
	def stop_recurrence(self):
		self.enabled = 0
		self.status = "Stopped"
		self.save()
		return self.status
