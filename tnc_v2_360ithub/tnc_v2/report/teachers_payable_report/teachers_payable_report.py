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
		{"label": _("Teacher Name"), "fieldname": "teacher_name", "fieldtype": "Data", "width": 200},
		{"label": _("Outstanding Balance"), "fieldname": "outstanding_balance", "fieldtype": "Currency", "width": 160},
		{"label": _("Total Payable (Selected Month)"), "fieldname": "total_payable", "fieldtype": "Currency", "width": 190},
		# {"label": _("Total Advance Paid"), "fieldname": "total_advance_paid", "fieldtype": "Currency", "width": 150},
		# {"label": _("Total Penalty"), "fieldname": "total_penalty", "fieldtype": "Currency", "width": 130},
		{"label": _("Total Amount Paid"), "fieldname": "total_amount_paid", "fieldtype": "Currency", "width": 150},
		{"label": _("Balance Amount"), "fieldname": "balance_amount", "fieldtype": "Currency", "width": 150},
	]


def get_data(filters):
	start_date, end_date = get_date_range(filters.get("timespan"), filters.get("date_range"))
	if not (start_date and end_date):
		return []

	teacher_filters = {}
	if filters.get("teacher_name"):
		teacher_filters["name"] = filters.get("teacher_name")

	teachers = frappe.get_all(
		"Teacher",
		filters=teacher_filters,
		fields=["name", "full_name", "supplier_id"],
		order_by="full_name asc",
	)

	data = []
	for teacher in teachers:
		total_payable = get_total_payable(teacher.name, start_date, end_date)
		outstanding_balance = get_outstanding_balance(teacher.name, start_date)
		total_amount_paid = get_total_amount_paid(teacher.supplier_id, start_date, end_date)

		# Advance and Penalty tracking are not implemented yet - placeholders until sourcing is confirmed.
		total_advance_paid = 0
		total_penalty = 0

		balance_amount = (outstanding_balance + total_payable) - (total_advance_paid + total_penalty + total_amount_paid)

		data.append({
			"teacher_name": teacher.full_name or teacher.name,
			"outstanding_balance": outstanding_balance,
			"total_payable": total_payable,
			"total_advance_paid": total_advance_paid,
			"total_penalty": total_penalty,
			"total_amount_paid": total_amount_paid,
			"balance_amount": balance_amount,
		})

	return data


def get_total_payable(teacher_id, start_date, end_date):
	"""Sum of Approved timesheet dues for the teacher within the selected period."""
	total = frappe.db.sql("""
		SELECT SUM(grand_total)
		FROM `tabTeachers Timesheet`
		WHERE teacher_id = %(teacher_id)s
		AND status = 'Approved'
		AND date BETWEEN %(start_date)s AND %(end_date)s
	""", {"teacher_id": teacher_id, "start_date": start_date, "end_date": end_date})[0][0]

	return flt(total)


def get_outstanding_balance(teacher_id, start_date):
	"""Dues carried forward from before the selected period, based on when the work
	happened (timesheet date) rather than when it was invoiced. Uninvoiced Approved
	timesheets count in full; invoiced ones count their proportional unpaid share of
	that invoice (an invoice can bundle several timesheets and be partially paid)."""
	rows = frappe.get_all(
		"Teachers Timesheet",
		filters={"teacher_id": teacher_id, "status": "Approved", "date": ["<", start_date]},
		fields=["name", "grand_total", "purchase_invoice_id"],
	)

	total_outstanding = 0
	pi_cache = {}

	for row in rows:
		if not row.purchase_invoice_id:
			total_outstanding += flt(row.grand_total)
			continue

		if row.purchase_invoice_id not in pi_cache:
			pi_cache[row.purchase_invoice_id] = frappe.db.get_value(
				"Purchase Invoice", row.purchase_invoice_id, ["outstanding_amount", "grand_total"], as_dict=True
			)

		inv = pi_cache[row.purchase_invoice_id]
		if inv and flt(inv.grand_total) > 0:
			ratio = flt(row.grand_total) / flt(inv.grand_total)
			total_outstanding += flt(inv.outstanding_amount) * ratio

	return total_outstanding


def get_total_amount_paid(supplier_id, start_date, end_date):
	"""Payments made to the teacher's supplier account within the selected period."""
	if not supplier_id:
		return 0

	total = frappe.db.sql("""
		SELECT SUM(base_paid_amount)
		FROM `tabPayment Entry`
		WHERE party_type = 'Supplier'
		AND party = %(supplier_id)s
		AND payment_type = 'Pay'
		AND docstatus = 1
		AND posting_date BETWEEN %(start_date)s AND %(end_date)s
	""", {"supplier_id": supplier_id, "start_date": start_date, "end_date": end_date})[0][0]

	return flt(total)


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
