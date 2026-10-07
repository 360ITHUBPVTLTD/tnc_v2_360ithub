# Copyright (c) 2025, pankaj@360ithub.com and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, today, add_days, get_first_day, get_last_day


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("timespan", "This Month")

	columns = get_columns()
	data = get_data(filters)

	if not data:
		frappe.msgprint(_("No Records Found"), alert=True)

	return columns, data


def get_columns():
	return [
		{"label": _("Teacher"), "fieldname": "teacher", "fieldtype": "Link", "options": "Teacher", "width": 200},
		{"label": _("Opening Balance"), "fieldname": "opening_balance", "fieldtype": "Currency", "width": 140},
		{"label": _("Approved This Period"), "fieldname": "approved_payable", "fieldtype": "Currency", "width": 150},
		{"label": _("Penalties"), "fieldname": "penalties", "fieldtype": "Currency", "width": 110},
		{"label": _("Paid"), "fieldname": "payments", "fieldtype": "Currency", "width": 120},
		{"label": _("Closing Balance"), "fieldname": "closing_balance", "fieldtype": "Currency", "width": 140},
	]


def get_data(filters):
	"""Same arithmetic as the weekly Teacher Settlement, so the two never disagree:
	closing = opening + approved timesheets - penalties + waived + refunded - paid (cash incl. refunds)."""
	from tnc_v2_360ithub.tnc_v2.doctype.teacher_settlement.teacher_settlement import _lines_for, _opening
	start_date, end_date = get_date_range(filters.get("timespan"), filters.get("date_range"))
	if not (start_date and end_date):
		return []
	teacher_filters = {"name": filters.get("teacher_name")} if filters.get("teacher_name") else {}
	data = []
	for t in frappe.get_all("Teacher", filters=teacher_filters, fields=["name", "full_name", "supplier_id"], order_by="full_name asc"):
		_lines, ts, pen, pay, adj, ref = _lines_for(t.name, t.supplier_id, start_date, end_date)
		opening = _opening(t.name, t.supplier_id, start_date)
		closing = opening + ts - pen + adj + ref - pay
		if not any((opening, ts, pen, pay, adj, ref)):
			continue
		# penalties shown net: old waivers/refunds (before approval became final) still balance out
		data.append({"teacher": t.name, "teacher_name": t.full_name, "opening_balance": opening, "approved_payable": ts, "penalties": pen - adj - ref,
			"payments": pay, "closing_balance": closing})
	return data


def get_date_range(timespan, date_range=None):
	today_date = getdate(today())

	if timespan == "Today":
		return today_date, today_date
	elif timespan == "Tomorrow":
		return add_days(today_date, 1), add_days(today_date, 1)
	elif timespan == "This Week":
		start_date = add_days(today_date, -today_date.weekday())
		end_date = add_days(start_date, 6)
		return start_date, end_date
	elif timespan == "This Month":
		return get_first_day(today_date), get_last_day(today_date)
	elif timespan == "Custom":
		if isinstance(date_range, (list, tuple)) and len(date_range) == 2 and all(date_range):
			return getdate(date_range[0]), getdate(date_range[1])
		frappe.msgprint(_("Please select a valid Date Range"), alert=True)
		return None, None
	else:
		frappe.throw(_("Invalid Timespan Selection"))
