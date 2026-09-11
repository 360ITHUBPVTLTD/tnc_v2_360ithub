# -*- coding: utf-8 -*-
# Copyright (c) 2026, Administrator and contributors
# For license information, please see license.txt

import calendar
import datetime
from frappe.utils import getdate, format_date

WEEKDAYS = {
	"Monday": 0,
	"Tuesday": 1,
	"Wednesday": 2,
	"Thursday": 3,
	"Friday": 4,
	"Saturday": 5,
	"Sunday": 6,
}


def get_last_day_of_month(year, month):
	return calendar.monthrange(year, month)[1]


def get_next_run_date(doc, reference_date=None):
	"""
	Calculates the next run date for the recurring task.
	- If reference_date is None, uses last_run_date or start_date.
	- If reference_date is last_run_date, calculates the next run date strictly after last_run_date.
	- If reference_date is start_date (i.e. never run before), calculates the first run on or after start_date.
	"""
	start_date = getdate(doc.start_date)
	if not start_date:
		return None

	# Determine reference date
	is_first_run = False
	if not reference_date:
		if doc.last_run_date:
			reference_date = getdate(doc.last_run_date)
		else:
			reference_date = start_date
			is_first_run = True
	else:
		reference_date = getdate(reference_date)
		if reference_date == start_date and not doc.last_run_date:
			is_first_run = True

	frequency = doc.frequency

	if frequency == "Daily":
		if is_first_run:
			return start_date
		return reference_date + datetime.timedelta(days=1)

	elif frequency == "Weekly":
		target_weekday_name = doc.day_of_week or "Monday"
		target_weekday = WEEKDAYS.get(target_weekday_name, 0)
		
		# For first run, if start_date is matching weekday, use it. Otherwise, find first matching weekday after start_date.
		if is_first_run:
			days_ahead = target_weekday - start_date.weekday()
			if days_ahead < 0:
				days_ahead += 7
			return start_date + datetime.timedelta(days=days_ahead)
		else:
			# Find first matching weekday strictly after reference_date (last_run_date)
			start_search = reference_date + datetime.timedelta(days=1)
			days_ahead = target_weekday - start_search.weekday()
			if days_ahead < 0:
				days_ahead += 7
			return start_search + datetime.timedelta(days=days_ahead)

	elif frequency == "Monthly":
		repeat_by = doc.repeat_by or "Day of Month"

		if is_first_run:
			# Find the target day in start_date's month
			year = start_date.year
			month = start_date.month
			
			if repeat_by == "Day of Month":
				day_val = int(doc.day_of_month or 1)
				last_day = get_last_day_of_month(year, month)
				actual_day = min(day_val, last_day)
			else:
				# Last Day of Month
				actual_day = get_last_day_of_month(year, month)
				
			candidate = datetime.date(year, month, actual_day)
			if candidate >= start_date:
				return candidate
			
			# If candidate is in the past, move to next month
			return _get_next_monthly_date(year, month, repeat_by, doc.day_of_month)
		else:
			year = reference_date.year
			month = reference_date.month
			return _get_next_monthly_date(year, month, repeat_by, doc.day_of_month)

	elif frequency == "Custom":
		repeat_every = int(doc.repeat_every or 1)
		unit = doc.unit or "Days"

		if is_first_run:
			return start_date

		if unit == "Days":
			return reference_date + datetime.timedelta(days=repeat_every)
		elif unit == "Weeks":
			return reference_date + datetime.timedelta(weeks=repeat_every)
		elif unit == "Months":
			# Add repeat_every months
			next_month = reference_date.month + repeat_every
			next_year = reference_date.year + (next_month - 1) // 12
			next_month = (next_month - 1) % 12 + 1
			
			# Preserve start_date's day if possible, otherwise use last day of month
			target_day = start_date.day
			last_day = get_last_day_of_month(next_year, next_month)
			actual_day = min(target_day, last_day)
			return datetime.date(next_year, next_month, actual_day)
		elif unit == "Years":
			# Add repeat_every years
			next_year = reference_date.year + repeat_every
			next_month = start_date.month
			
			# Preserve start_date's day if possible
			target_day = start_date.day
			last_day = get_last_day_of_month(next_year, next_month)
			actual_day = min(target_day, last_day)
			return datetime.date(next_year, next_month, actual_day)

	return None


def _get_next_monthly_date(current_year, current_month, repeat_by, day_of_month_field):
	"""Helper to calculate monthly run date for the next month."""
	next_month = current_month + 1
	next_year = current_year
	if next_month > 12:
		next_month = 1
		next_year += 1

	if repeat_by == "Day of Month":
		day_val = int(day_of_month_field or 1)
		last_day = get_last_day_of_month(next_year, next_month)
		actual_day = min(day_val, last_day)
	else:
		actual_day = get_last_day_of_month(next_year, next_month)

	return datetime.date(next_year, next_month, actual_day)


def get_recurrence_summary(doc):
	"""Generates a human-readable summary of the recurrence schedule."""
	if not doc.start_date:
		return ""

	summary = ""
	f = doc.frequency

	if f == "Daily":
		summary = "Repeats every day."
	elif f == "Weekly":
		summary = f"Repeats every {doc.day_of_week or 'Monday'}."
	elif f == "Monthly":
		if doc.repeat_by == "Day of Month":
			day = doc.day_of_month or "1"
			# Ordinal suffix
			if day in ["1", "21", "31"]:
				suffix = "st"
			elif day in ["2", "22"]:
				suffix = "nd"
			elif day in ["3", "23"]:
				suffix = "rd"
			else:
				suffix = "th"
			summary = f"Repeats on the {day}{suffix} of every month."
		elif doc.repeat_by == "Last Day of Month":
			summary = "Repeats on the last day of every month."
		else:
			summary = "Repeats every month."
	elif f == "Custom":
		every = int(doc.repeat_every or 1)
		unit = (doc.unit or "Days")
		if every == 1:
			# Make singular
			if unit.endswith("s"):
				unit = unit[:-1]
		summary = f"Repeats every {every} {unit.lower()}."

	if summary:
		if doc.ends == "On Date" and doc.end_date:
			summary += f" until {format_date(doc.end_date)}."
		elif doc.ends == "After Occurrences" and doc.number_of_occurrences:
			summary += f" for {doc.number_of_occurrences} occurrences."

	return summary
