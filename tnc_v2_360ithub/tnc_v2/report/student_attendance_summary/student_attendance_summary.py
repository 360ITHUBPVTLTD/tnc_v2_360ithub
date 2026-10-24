# Copyright (c) 2026, 360ITHub and contributors
"""Student Attendance Summary: attendance counted over a period, three views.

Student view (default): one row per enrolment (student in a batch): class days, Present / Late /
Absent / Leave, attendance %, the current run of consecutive absences, and the hold (type, since).
Batch view: one row per batch: class days held, students, totals, average %, students on hold.
Month view: one row per student, batch and month.

Attendance % = (Present + Late) / (Present + Late + Partial + Absent). Leave days are not counted
against the student. Class days = attendance rows in the period (the daily build writes one
per enrolment per class day). "Only students on hold" keeps enrolments whose status is On Hold.
"""
import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, get_first_day, nowdate


def _period(f):
	"""The DateRange filter arrives as a list (or its JSON text); fall back to from_date / to_date,
	then to this month so far."""
	period = f.get("period")
	if isinstance(period, str) and period.strip().startswith("["):
		period = frappe.parse_json(period)
	if isinstance(period, (list, tuple)) and len(period) == 2 and period[0] and period[1]:
		return getdate(period[0]), getdate(period[1])
	if f.get("from_date") and f.get("to_date"):
		return getdate(f.from_date), getdate(f.to_date)
	today = getdate(nowdate())
	return get_first_day(today), today


def execute(filters=None):
	f = frappe._dict(filters or {})
	f.from_date, f.to_date = _period(f)
	view = f.view or "Student"
	if view == "Batch":
		return batch_columns(), batch_rows(f)
	if view == "Month":
		return month_columns(), month_rows(f)
	if view == "Subject":
		return subject_columns(), subject_rows(f)
	return student_columns(), student_rows(f)


def _where(f, extra=None):
	cond, vals = ["1=1"], {}
	if f.from_date:
		cond.append("a.date >= %(from_date)s"); vals["from_date"] = f.from_date
	if f.to_date:
		cond.append("a.date <= %(to_date)s"); vals["to_date"] = f.to_date
	if f.batch:
		cond.append("a.batch = %(batch)s"); vals["batch"] = f.batch
	if f.student:
		cond.append("a.student = %(student)s"); vals["student"] = f.student
	if cint(f.only_on_hold):
		cond.append("e.status = 'On Hold'")
	if extra:
		cond.extend(extra)
	return " and ".join(cond), vals


COUNTS = """
	count(*) as class_days,
	sum(a.status = 'Present') as present,
	sum(a.status = 'Late') as late,
	sum(a.status = 'Partial') as partial,
	sum(a.status = 'Absent') as absent,
	sum(a.status = 'Leave') as leave_days,
	max(case when a.status in ('Present', 'Late') then a.date end) as last_present"""


def _pct(r):
	for k in ("class_days", "students", "present", "late", "partial", "absent", "leave_days", "on_hold", "consecutive_absences"):
		if k in r:
			r[k] = cint(r[k])
	counted = cint(r.present) + cint(r.late) + cint(r.partial) + cint(r.absent)
	r.pct = round(flt(cint(r.present) + cint(r.late)) / counted * 100, 1) if counted else 0
	return r


def _count_cols():
	return [
		{"fieldname": "class_days", "label": _("Class Days"), "fieldtype": "Int", "width": 95},
		{"fieldname": "present", "label": _("Present"), "fieldtype": "Int", "width": 80},
		{"fieldname": "late", "label": _("Late"), "fieldtype": "Int", "width": 70},
		{"fieldname": "partial", "label": _("Partial"), "fieldtype": "Int", "width": 75},
		{"fieldname": "absent", "label": _("Absent"), "fieldtype": "Int", "width": 80},
		{"fieldname": "leave_days", "label": _("Leave"), "fieldtype": "Int", "width": 70},
		{"fieldname": "pct", "label": _("Attendance %"), "fieldtype": "Percent", "width": 140},
	]


# ---------- Student view ----------

def student_columns():
	return [
		{"fieldname": "student", "label": _("Student"), "fieldtype": "Link", "options": "Student", "width": 180},
		{"fieldname": "batch", "label": _("Batch"), "fieldtype": "Link", "options": "Student Batch", "width": 150},
		*_count_cols(),
		{"fieldname": "last_present", "label": _("Last Present"), "fieldtype": "Date", "width": 105},
		{"fieldname": "consecutive_absences", "label": _("Absent in a Row"), "fieldtype": "Int", "width": 110},
		{"fieldname": "enrol_status", "label": _("Enrolment"), "fieldtype": "Data", "width": 95},
		{"fieldname": "hold_type", "label": _("Hold"), "fieldtype": "Data", "width": 95},
		{"fieldname": "hold_on", "label": _("On Hold Since"), "fieldtype": "Date", "width": 105},
		{"fieldname": "enrollment", "label": _("Enrolment Record"), "fieldtype": "Link", "options": "Student Batch Enrollment", "width": 150},
	]


def student_rows(f):
	where, vals = _where(f)
	rows = frappe.db.sql(f"""
		select a.enrollment, a.student, a.student_name, a.batch, {COUNTS},
			e.consecutive_absences, e.status as enrol_status, e.hold_type, e.hold_on
		from `tabStudent Attendance` a
		left join `tabStudent Batch Enrollment` e on e.name = a.enrollment
		where {where}
		group by a.enrollment, a.student, a.student_name, a.batch, e.consecutive_absences, e.status, e.hold_type, e.hold_on
		order by a.batch, a.student_name""", vals, as_dict=True)
	for r in rows:
		_pct(r)
		if r.enrol_status != "On Hold":
			r.hold_type = r.hold_on = None
	# worst attendance first within a batch, so the students to call are at the top
	return sorted(rows, key=lambda r: (r.batch or "", r.pct, r.student_name or ""))


# ---------- Batch view ----------

def batch_columns():
	return [
		{"fieldname": "batch", "label": _("Batch"), "fieldtype": "Link", "options": "Student Batch", "width": 170},
		{"fieldname": "class_days", "label": _("Class Days"), "fieldtype": "Int", "width": 95},
		{"fieldname": "students", "label": _("Students"), "fieldtype": "Int", "width": 85},
		{"fieldname": "present", "label": _("Present"), "fieldtype": "Int", "width": 80},
		{"fieldname": "late", "label": _("Late"), "fieldtype": "Int", "width": 70},
		{"fieldname": "partial", "label": _("Partial"), "fieldtype": "Int", "width": 75},
		{"fieldname": "absent", "label": _("Absent"), "fieldtype": "Int", "width": 80},
		{"fieldname": "leave_days", "label": _("Leave"), "fieldtype": "Int", "width": 70},
		{"fieldname": "pct", "label": _("Attendance %"), "fieldtype": "Percent", "width": 140},
		{"fieldname": "on_hold", "label": _("On Hold"), "fieldtype": "Int", "width": 80},
		{"fieldname": "last_class", "label": _("Last Class Day"), "fieldtype": "Date", "width": 110},
	]


def batch_rows(f):
	where, vals = _where(f)
	rows = frappe.db.sql(f"""
		select a.batch, count(distinct a.date) as class_days, count(distinct a.enrollment) as students,
			sum(a.status = 'Present') as present, sum(a.status = 'Late') as late, sum(a.status = 'Partial') as partial,
			sum(a.status = 'Absent') as absent, sum(a.status = 'Leave') as leave_days,
			count(distinct case when e.status = 'On Hold' then a.enrollment end) as on_hold,
			max(a.date) as last_class
		from `tabStudent Attendance` a
		left join `tabStudent Batch Enrollment` e on e.name = a.enrollment
		where {where}
		group by a.batch
		order by a.batch""", vals, as_dict=True)
	return [_pct(r) for r in rows]


# ---------- Month view ----------

def month_columns():
	return [
		{"fieldname": "month", "label": _("Month"), "fieldtype": "Data", "width": 95},
		{"fieldname": "student", "label": _("Student"), "fieldtype": "Link", "options": "Student", "width": 180},
		{"fieldname": "batch", "label": _("Batch"), "fieldtype": "Link", "options": "Student Batch", "width": 150},
		*_count_cols(),
	]


def month_rows(f):
	where, vals = _where(f)
	rows = frappe.db.sql(f"""
		select date_format(a.date, '%%Y-%%m') as ym, date_format(a.date, '%%b %%Y') as month,
			a.student, a.student_name, a.batch, {COUNTS}
		from `tabStudent Attendance` a
		left join `tabStudent Batch Enrollment` e on e.name = a.enrollment
		where {where}
		group by ym, month, a.student, a.student_name, a.batch
		order by ym desc, a.batch, a.student_name""", vals, as_dict=True)
	return [_pct(r) for r in rows]


# ---------- Subject view (class rows) ----------

def subject_columns():
	return [
		{"fieldname": "student", "label": _("Student"), "fieldtype": "Link", "options": "Student", "width": 180},
		{"fieldname": "batch", "label": _("Batch"), "fieldtype": "Link", "options": "Student Batch", "width": 140},
		{"fieldname": "subject", "label": _("Subject"), "fieldtype": "Link", "options": "Subject", "width": 170},
		{"fieldname": "classes", "label": _("Classes"), "fieldtype": "Int", "width": 80},
		{"fieldname": "present", "label": _("Present"), "fieldtype": "Int", "width": 80},
		{"fieldname": "partial", "label": _("Partial"), "fieldtype": "Int", "width": 80},
		{"fieldname": "absent", "label": _("Absent"), "fieldtype": "Int", "width": 80},
		{"fieldname": "minutes", "label": _("Minutes Attended"), "fieldtype": "Int", "width": 120},
		{"fieldname": "pct", "label": _("Attendance %"), "fieldtype": "Percent", "width": 140},
	]


def subject_rows(f):
	where, vals = _where(f)
	if f.get("subject"):
		where += " and c.subject = %(subject)s"; vals["subject"] = f.subject
	rows = frappe.db.sql(f"""
		select a.student, a.student_name, a.batch, c.subject,
			sum(c.status != 'Leave') as classes, sum(c.status in ('Present', 'Late')) as present, sum(c.status = 'Partial') as partial, sum(c.status = 'Absent') as absent,
			sum(c.covered_minutes) as minutes
		from `tabStudent Class Attendance` c join `tabStudent Attendance` a on a.name = c.parent
		left join `tabStudent Batch Enrollment` e on e.name = a.enrollment
		where {where}
		group by a.student, a.student_name, a.batch, c.subject
		order by a.batch, a.student_name, c.subject""", vals, as_dict=True)
	for r in rows:
		for k in ("classes", "present", "partial", "absent", "minutes"):
			r[k] = cint(r[k])
		r.pct = round(flt(r.present) / r.classes * 100, 1) if r.classes else 0
	return rows
