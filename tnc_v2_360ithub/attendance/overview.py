"""Attendance overview page: one student's attendance (days, subjects, holds) or a whole batch,
over a period. Reads Student Attendance and its class rows; nothing is computed here that the
nightly build has not already written."""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate, get_first_day, get_last_day


def _pct(p, a):
	return round(flt(p) / (p + a) * 100, 1) if (p + a) else 0


@frappe.whitelist()
def get_overview(batch=None, student=None, from_date=None, to_date=None):
	from_date = getdate(from_date or get_first_day(nowdate()))
	to_date = getdate(to_date or get_last_day(nowdate()))
	if student:
		return student_overview(student, batch, from_date, to_date)
	if batch:
		return batch_overview(batch, from_date, to_date)
	return {"batches": frappe.get_all("Student Batch", filters={"status": ["!=", "Completed"]}, fields=["name", "batch_name", "mode"], order_by="batch_name")}


def _days(filters, from_date, to_date):
	return frappe.get_all("Student Attendance", filters=dict(filters, date=["between", [from_date, to_date]]),
		fields=["name", "student", "student_name", "enrollment", "batch", "date", "status", "in_time", "out_time", "duration", "note", "source", "remarks", "classes_held", "classes_present", "classes_absent"],
		order_by="date asc")


def _classes(day_names):
	if not day_names:
		return []
	rows = frappe.get_all("Student Class Attendance", filters={"parent": ["in", day_names]},
		fields=["parent", "subject", "chapter", "teacher_name", "from_time", "to_time", "status", "covered_minutes", "class_minutes", "cover_pct"], order_by="from_time asc")
	dates = dict(frappe.get_all("Student Attendance", filters={"name": ["in", day_names]}, fields=["name", "date"], as_list=True))
	for r in rows:
		r.parent_date = str(dates.get(r.parent))
	return rows


def _subject_table(classes):
	subj = {}
	for c in classes:
		s = subj.setdefault(c.subject or _("(no subject)"), {"subject": c.subject or _("(no subject)"), "held": 0, "present": 0, "partial": 0, "absent": 0, "leave": 0, "minutes": 0, "sessions": set()})
		s["held"] += 1
		s["sessions"].add((c.parent_date, str(c.from_time)))
		s[{"Present": "present", "Late": "present", "Partial": "partial", "Leave": "leave"}.get(c.status, "absent")] += 1
		s["minutes"] += cint(c.covered_minutes)
	for s in subj.values():
		s["pct"] = _pct(s["present"], s["partial"] + s["absent"])
		s["classes"] = len(s.pop("sessions"))  # distinct class sessions (date + start time)
	return sorted(subj.values(), key=lambda s: s["pct"])


def student_overview(student, batch, from_date, to_date):
	filters = {"student": student}
	if batch:
		filters["batch"] = batch
	days = _days(filters, from_date, to_date)
	classes = _classes([d.name for d in days])
	by_day = {}
	for c in classes:
		by_day.setdefault(c.parent, []).append(c)
	for d in days:
		d.classes = by_day.get(d.name, [])
	st = frappe.db.get_value("Student", student, ["student_name", "status", "mobile", "biometric_id"], as_dict=True) or {}
	enrols = frappe.get_all("Student Batch Enrollment", filters={"student": student, "docstatus": 1}, fields=["name", "batch", "status", "hold_type", "hold_on", "hold_reason", "consecutive_absences"])
	counts = {k: sum(1 for d in days if d.status == k) for k in ("Present", "Late", "Absent", "Leave")}
	present_days = counts["Present"] + counts["Late"]
	cls_present = sum(1 for c in classes if c.status in ("Present", "Late"))
	cls_counted = sum(1 for c in classes if c.status != "Leave")
	daily = [{"date": str(d.date), "status": d.status, "pct": (round(cint(d.classes_present) / cint(d.classes_held) * 100) if cint(d.classes_held) else (100 if d.status in ("Present", "Late") else 0))} for d in days]
	return {
		"student": dict(st, name=student), "enrolments": enrols, "from_date": from_date, "to_date": to_date, "daily": daily,
		"days": days, "subjects": _subject_table(classes),
		"totals": {"class_days": len(days), "present": present_days, "late": counts["Late"], "absent": counts["Absent"], "leave": counts["Leave"],
			"day_pct": _pct(present_days, counts["Absent"]), "classes_held": len(classes), "classes_present": cls_present, "class_pct": _pct(cls_present, cls_counted - cls_present)},
	}


def batch_overview(batch, from_date, to_date):
	days = _days({"batch": batch}, from_date, to_date)
	classes = _classes([d.name for d in days])
	by_student = {}
	for d in days:
		s = by_student.setdefault(d.student, {"student": d.student, "student_name": d.student_name, "enrollment": d.enrollment, "days": 0, "present": 0, "late": 0, "absent": 0, "leave": 0, "classes": 0, "classes_present": 0})
		s["days"] += 1
		s[d.status.lower()] += 1
		s["classes"] += cint(d.classes_held)
		s["classes_present"] += cint(d.classes_present)
	for s in by_student.values():
		s["day_pct"] = _pct(s["present"] + s["late"], s["absent"])
		s["class_pct"] = _pct(s["classes_present"], s["classes"] - s["classes_present"])
		e = frappe.db.get_value("Student Batch Enrollment", s["enrollment"], ["status", "hold_type", "hold_on", "hold_reason", "consecutive_absences"], as_dict=True) or {}
		s.update({"enrol_status": e.get("status"), "hold_type": e.get("hold_type"), "hold_on": e.get("hold_on"), "hold_reason": e.get("hold_reason"), "consecutive_absences": cint(e.get("consecutive_absences"))})
	class_dates = sorted({str(d.date) for d in days})
	date_of = {d.name: str(d.date) for d in days}
	b = frappe.db.get_value("Student Batch", batch, ["batch_name", "mode"], as_dict=True) or {}
	enrolled = frappe.db.count("Student Batch Enrollment", {"batch": batch, "docstatus": 1, "status": ["in", ["Active", "On Hold"]]})
	on_hold = frappe.db.count("Student Batch Enrollment", {"batch": batch, "docstatus": 1, "status": "On Hold"})
	rows = sorted(by_student.values(), key=lambda s: (s["class_pct"] if s["classes"] else s["day_pct"], s["student_name"]))
	# per class day: share of students present (day level)
	per_day = {}
	for d in days:
		x = per_day.setdefault(str(d.date), {"present": 0, "total": 0})
		x["total"] += 1
		x["present"] += 1 if d.status in ("Present", "Late") else 0
	daily = [{"date": k, "pct": round(v["present"] / v["total"] * 100) if v["total"] else 0, "present": v["present"], "total": v["total"]} for k, v in sorted(per_day.items())]
	status_counts = {k: sum(1 for d in days if d.status == k) for k in ("Present", "Late", "Absent", "Leave")}
	# per class day: which classes ran (one entry per subject + time), and how many came
	day_detail = {}
	for c in classes:
		dd = day_detail.setdefault(date_of.get(c.parent), {"date": date_of.get(c.parent), "classes": {}})
		key = (c.subject, str(c.from_time), str(c.to_time))
		cl = dd["classes"].setdefault(key, {"subject": c.subject, "chapter": c.chapter, "teacher_name": c.teacher_name, "from_time": c.from_time, "to_time": c.to_time, "present": 0, "partial": 0, "absent": 0})
		cl[{"Present": "present", "Late": "present", "Partial": "partial"}.get(c.status, "absent")] += 1
	for k, v in per_day.items():
		day_detail.setdefault(k, {"date": k, "classes": {}})
		day_detail[k].update({"present": v["present"], "total": v["total"]})
	class_days_detail = [dict(v, classes=sorted(v["classes"].values(), key=lambda x: str(x["from_time"]))) for k, v in sorted(day_detail.items())]
	return {
		"batch": dict(b, name=batch), "from_date": from_date, "to_date": to_date, "enrolled": enrolled, "on_hold": on_hold,
		"class_days": len(class_dates), "classes_held": len({(date_of.get(c.parent), c.subject, str(c.from_time)) for c in classes}),
		"students": rows, "subjects": _subject_table(classes), "daily": daily, "status_counts": status_counts, "class_days_detail": class_days_detail,
		"avg_pct": round(sum(s["day_pct"] for s in rows) / len(rows), 1) if rows else 0,
	}
