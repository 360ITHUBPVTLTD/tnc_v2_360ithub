"""Student attendance for a day, built from the machine punches and the teachers' timesheets.

Class days. A batch has a class on a date when a teacher's timesheet (any status but the row
deleted) names that batch for that date; this is the default ("Class Days From" in settings).
The older way, Mon-Sun ticks and a start time on the batch, stays as the alternative. A class row
with From and To time is a class window; rows without times make the day a class day only.

Day row (Student Attendance). Any punch that day = Present; with a minimum stay set, the student
must have stayed that long (IN to OUT). First punch after the first class start + grace = Late.
No punch = Absent. Staff may change a day to Leave (or anything) with remarks; such rows are never
overwritten by a rebuild.

Class rows (Student Class Attendance under the day). The student's IN..OUT period is matched to
each class window: covered share >= "Class Counts as Present From" = Present, some but less =
Partial (counts as absent), none = Absent. IN only is taken as present until the end of the day;
OUT only as present from the start of the day.

Hold. Consecutive absences are counted per class when the day has class windows, otherwise per
day; at the threshold the enrolment goes On Hold (type Attendance). Never released automatically.

When it runs. Nightly at 23:30 for today and the last N days (look-back setting), so timesheets
filed late are picked up; a timesheet also rebuilds its own date when saved or deleted; a punch
refreshes the student's row for today; "Rebuild a day" on the list does any past date.
"""

import frappe
from datetime import timedelta
from frappe import _
from frappe.utils import add_days, cint, flt, get_datetime, getdate, now_datetime, nowdate, time_diff_in_seconds

DAY_FIELDS = ["day_mon", "day_tue", "day_wed", "day_thu", "day_fri", "day_sat", "day_sun"]
ENROLMENT_FILTERS = {"docstatus": 1, "status": ["in", ["Active", "On Hold"]]}


def _settings():
	s = frappe.get_cached_doc("TNC Settings")
	return frappe._dict(
		hold_after=cint(s.get("attendance_hold_after")) or 4,
		count_by=s.get("attendance_hold_count_by") or "Days",
		grace=cint(s.get("attendance_late_grace")),
		parent_whatsapp=cint(s.get("attendance_parent_whatsapp")),
		parent_daily=cint(s.get("attendance_parent_daily")),
		parent_number=s.get("attendance_parent_number") or "Father",
		source=s.get("attendance_class_source") or "Teacher timesheets",
		# an unset number shows as 0 on a settings record that existed before the field: 0 means "default"
		lookback=cint(s.get("attendance_lookback_days")) or 7,
		min_stay=cint(s.get("attendance_min_stay")),
		cover_pct=cint(s.get("attendance_class_cover_pct")) or 75,
		single_punch=s.get("attendance_single_punch") or "Partial",
		meet_connected=bool(s.get("meet_account")),
		meet_presence_pct=cint(s.get("meet_presence_pct")) or 75,
	)


def is_holiday(date):
	hl = frappe.get_cached_value("Company", frappe.defaults.get_global_default("company"), "default_holiday_list")
	return bool(hl and frappe.db.exists("Holiday", {"parent": hl, "holiday_date": getdate(date)}))


# ---------- class days and class windows ----------

def class_windows(batch, date):
	"""Class rows a teacher logged for this batch on this date: [{subject, teacher, teacher_name,
	from_time, to_time, timesheet, timesheet_row}], earliest first. Rows without times come
	back with from_time None; batches_with_class drops them, so they never make a class day."""
	rows = frappe.db.sql("""
		select a.subject, a.chapter, a.from_time, a.to_time, ts.teacher_id as teacher, ts.teacher_name, ts.name as timesheet, a.name as timesheet_row
		from `tabActivities` a join `tabTeachers Timesheet` ts on ts.name = a.parent
		where a.batch = %(batch)s and ts.date = %(date)s and ts.docstatus < 2
		order by a.from_time is null, a.from_time, a.idx""", {"batch": batch, "date": getdate(date)}, as_dict=True)
	from tnc_v2_360ithub.tnc_v2.doctype.teachers_timesheet.teachers_timesheet import _clean_time
	for r in rows:
		r.from_time, r.to_time = _clean_time(r.from_time), _clean_time(r.to_time)
		if r.from_time is not None and r.to_time is not None and r.to_time <= r.from_time:
			r.from_time = r.to_time = None
	return rows


def batches_with_class(date):
	"""Batches that had a class on the date, each with its class windows (may be empty when the
	batch-days setting is used or the timesheet rows carry no times)."""
	date = getdate(date)
	out = []
	if _settings().source == "Batch class days":
		if is_holiday(date):
			return []
		for b in frappe.get_all("Student Batch", filters={"status": ["!=", "Completed"]}, fields=["name", "start_time", "late_after_minutes", "mode", "meet_link"] + DAY_FIELDS):
			if b.get(DAY_FIELDS[date.weekday()]):
				b.windows = class_windows(b.name, date)
				out.append(b)
		return out
	# Timesheet source: only rows with a class time (From and To) make a class day, so old
	# timesheets filed before times existed never mark anyone absent.
	names = frappe.db.sql_list("""
		select distinct a.batch from `tabActivities` a join `tabTeachers Timesheet` ts on ts.name = a.parent
		where ts.date = %s and ts.docstatus < 2 and ifnull(a.batch, '') != ''
		and a.from_time is not null and a.to_time is not null""", getdate(date))
	for n in names:
		b = frappe.db.get_value("Student Batch", n, ["name", "start_time", "late_after_minutes", "mode", "meet_link"], as_dict=True)
		if b:
			b.windows = [w for w in class_windows(n, date) if w.from_time is not None]
			if b.windows:
				out.append(b)
	return out


# ---------- one student-day ----------

def is_online(batch):
	"""An online batch is marked from Google Meet only: never from the biometric machines."""
	return batch.get("mode") == "Online" or bool(batch.get("meet_link"))


def meet_ready(batch, date):
	"""True when Google Meet data for this batch-day has been pulled (a Synced Meet Class Sync exists).
	Until then an online class day is not built at all, so nobody is marked absent for a class the
	server has not seen: before the account is connected, or before the 15-minute sync has run."""
	return bool(frappe.db.exists("Meet Class Sync", {"batch": batch.name, "date": getdate(date), "status": "Synced"}))


def _punches(student, date, online=False):
	"""The day's punches that count for this batch: Meet punches (device MEET:…) for an online
	batch, machine punches for an offline one, never mixed."""
	return frappe.db.sql(f"""select punch_time, direction from `tabStudent Punch Log`
		where student = %(student)s and punch_time between %(start)s and %(end)s
		and ifnull(device_id, '') {"like" if online else "not like"} 'MEET:%%'
		order by punch_time asc""", {"student": student, "start": f"{date} 00:00:00", "end": f"{date} 23:59:59"}, as_dict=True)


def _in_out(punches, date):
	"""(in_dt, out_dt, note). First IN / last OUT; one direction only leaves the other blank;
	punches with no direction fall back to first / last."""
	ins = [p.punch_time for p in punches if p.direction == "IN"]
	outs = [p.punch_time for p in punches if p.direction == "OUT"]
	first, last = punches[0].punch_time, punches[-1].punch_time
	note = "Out only" if (not ins and outs) else "In only" if (ins and not outs) else ""
	in_dt = ins[0] if ins else (None if outs else first)
	out_dt = outs[-1] if outs else (None if ins else last)
	return (get_datetime(in_dt) if in_dt else None), (get_datetime(out_dt) if out_dt else None), note


def _presence(in_dt, out_dt, date, punches=None):
	"""The periods the student is taken to be in, as a list of (start, end).
	One IN and one OUT: IN..OUT. IN only runs to end of day; OUT only from start of day.
	Several IN/OUT pairs (a student who stepped out and came back, or joined a Google Meet more
	than once): one period per pair, so the class cover counts only the time actually inside."""
	if not in_dt and not out_dt:
		return None
	day0 = get_datetime(f"{date} 00:00:00")
	day1 = day0 + timedelta(days=1)
	directed = [p for p in (punches or []) if p.direction in ("IN", "OUT")]
	if len(directed) >= 3:
		# union of sessions: a student on a laptop and a phone at once is inside while any session
		# is open (count INs and OUTs; OUT comes before IN at a tie so a re-join at the same second closes nothing)
		periods, depth, open_at = [], 0, None
		for p in sorted(directed, key=lambda p: (get_datetime(p.punch_time), 0 if p.direction == "OUT" else 1)):
			t = get_datetime(p.punch_time)
			if p.direction == "IN":
				if depth == 0:
					open_at = t
				depth += 1
			else:
				if depth == 0:
					if not periods:
						periods.append((day0, t))  # OUT before any IN: inside since the start of the day
					continue
				depth -= 1
				if depth == 0 and open_at is not None and t > open_at:
					periods.append((open_at, t))
		if depth > 0 and open_at is not None:
			periods.append((open_at, day1))
		if periods:
			return periods
	return [(in_dt or day0, out_dt or day1)]


def _overlap_minutes(periods, start, end):
	total = 0
	for a, b in periods or []:
		lo, hi = max(start, a), min(end, b)
		total += max(0, int((hi - lo).total_seconds() // 60))
	return total


def class_rows(windows, presence, date, cover_pct, grace=0):
	"""Per-class status for the day from the presence periods. Late: the student arrived after the
	class start plus grace but still covered enough of it (counts as attended)."""
	rows = []
	first_in = min((a for a, b in presence), default=None) if presence else None
	for w in windows:
		if w.from_time is None or w.to_time is None:
			continue
		start, end = get_datetime(f"{date} {w.from_time}"), get_datetime(f"{date} {w.to_time}")
		total = max(1, int((end - start).total_seconds() // 60))
		covered = _overlap_minutes(presence, start, end) if presence else 0
		pct = round(covered / total * 100, 1)
		status = "Present" if covered and pct >= cover_pct else "Partial" if covered else "Absent"
		if status == "Present" and presence:
			# first time inside during this class, after the start plus grace = Late
			arrived = min((a for a, b in presence if b > start), default=first_in)
			if arrived and arrived > start + timedelta(minutes=grace):
				status = "Late"
		rows.append({"subject": w.subject, "chapter": w.chapter, "teacher": w.teacher, "teacher_name": w.teacher_name, "from_time": w.from_time, "to_time": w.to_time,
			"status": status, "covered_minutes": covered, "class_minutes": total, "cover_pct": pct, "timesheet": w.timesheet, "timesheet_row": w.timesheet_row})
	return rows


def day_status(punches, batch, date):
	"""(status, in_dt, out_dt, duration_seconds, note, class_rows) for one student-day."""
	s = _settings()
	windows = batch.get("windows") or []
	grace = cint(batch.get("late_after_minutes")) or s.grace
	if not punches:
		return "Absent", None, None, 0, "", class_rows(windows, None, date, s.cover_pct)
	in_dt, out_dt, note = _in_out(punches, date)
	duration = max(0, time_diff_in_seconds(str(out_dt), str(in_dt))) if (in_dt and out_dt and out_dt > in_dt) else 0
	status = "Present"
	if s.min_stay and in_dt and out_dt and duration < s.min_stay * 60:
		status = "Absent"
		note = (note + "; " if note else "") + _("Stayed {0} min").format(duration // 60)
	# Late: first punch after the first class start (timesheet) or the batch start time, plus grace
	first = get_datetime(punches[0].punch_time)
	starts = [w.from_time for w in windows if w.from_time is not None]
	start = min(starts) if starts else batch.get("start_time")
	if status == "Present" and start and in_dt:  # an OUT-only day says nothing about when the student came
		grace = cint(batch.get("late_after_minutes")) or s.grace
		if first > get_datetime(f"{date} {start}") + timedelta(minutes=grace):
			status = "Late"
	# online batches: time in the meeting against the Meet threshold; offline: the class cover setting
	cover = cint(s.meet_presence_pct) if (batch.get("mode") == "Online" and s.meet_connected) else s.cover_pct
	classes = class_rows(windows, _presence(in_dt, out_dt, date, punches), date, cover, grace)
	# the day follows its classes: punches prove the student came, the class cover says whether they
	# sat the classes. No class attended = Partial (some cover) or Absent (none), even with punches.
	if classes and status in ("Present", "Late") and not any(c["status"] in ("Present", "Late") for c in classes):
		status = "Partial" if any(c["status"] == "Partial" for c in classes) else "Absent"
		if status == "Absent":
			note = (note + "; " if note else "") + _("punched, but no class covered")
	# one punch only (IN without OUT, or OUT without IN): the setting decides how much credit it earns
	if note in ("In only", "Out only") and s.single_punch != "Present" and status in ("Present", "Late"):
		if status == "Late":
			note += "; " + _("late")
		status = s.single_punch
		for c in classes:
			if c["status"] in ("Present", "Late", "Partial"):
				c["status"] = "Partial" if s.single_punch == "Partial" else "Absent"
	return status, in_dt, out_dt, duration, note, classes


MANUAL_CLASS_STATUS = {"Present": "Present", "Late": "Present", "Partial": "Partial", "Absent": "Absent", "Leave": "Leave"}


def apply_manual_status(classes, status):
	"""A day marked by staff overrides what the punches say: every class of the day takes the
	matching class status (Late day = classes attended). Works on dicts or child docs."""
	cs = MANUAL_CLASS_STATUS.get(status)
	if not cs:
		return
	for c in classes:
		if isinstance(c, dict):
			c["status"] = cs
		else:
			c.status = cs


def write_row(enrolment, batch, date, punches):
	"""Create or refresh the Student Attendance row for one enrolment-day. Manual rows keep their
	status but still get the day's class rows. Returns the status written, or None when unchanged."""
	status, in_dt, out_dt, duration, note, classes = day_status(punches, batch, date)
	name = frappe.db.get_value("Student Attendance", {"enrollment": enrolment.name, "date": getdate(date)}, "name")
	values = {"status": status, "in_time": in_dt.time() if in_dt else None, "out_time": out_dt.time() if out_dt else None,
		"duration": duration, "punches": len(punches), "note": note,
		"classes_held": len(classes), "classes_present": sum(1 for c in classes if c["status"] in ("Present", "Late")), "classes_absent": sum(1 for c in classes if c["status"] not in ("Present", "Late"))}
	if name:
		doc = frappe.get_doc("Student Attendance", name)
		manual = doc.source == "Manual"
		if manual:
			values = {k: v for k, v in values.items() if k not in ("status", "note")}
			apply_manual_status(classes, doc.status)
			values["classes_present"] = sum(1 for c in classes if c["status"] in ("Present", "Late"))
			values["classes_absent"] = sum(1 for c in classes if c["status"] not in ("Present", "Late", "Leave"))
		old_classes = [(c.timesheet_row, c.status, c.covered_minutes, c.chapter) for c in doc.classes]
		new_classes = [(c["timesheet_row"], c["status"], c["covered_minutes"], c.get("chapter")) for c in classes]
		changed = old_classes != new_classes or any(str(doc.get(k) or "") != str(v or "") for k, v in values.items())
		if not changed:
			return None if manual else doc.status
		doc.update(values)
		doc.set("classes", classes)
		doc.flags.ignore_permissions = True
		doc.flags.by_machine = True
		doc.save()
		status = doc.status
	else:
		doc = frappe.get_doc({"doctype": "Student Attendance", "student": enrolment.student, "enrollment": enrolment.name, "batch": batch.name,
			"date": getdate(date), "source": "Machine", "classes": classes, **values})
		doc.flags.by_machine = True
		doc.insert(ignore_permissions=True)
	blank = {k: None for k in ("in_time", "out_time") if not values.get(k)}
	if blank:
		# an empty Time field is turned into "now" on save; store a real blank
		doc.db_set(blank, update_modified=False)
	return status


def _remove_stale(date, batch_names, batch=None, student=None):
	"""Machine rows for a date whose batch no longer had a class that day (timesheet row deleted)."""
	filters = {"date": getdate(date), "source": "Machine"}
	if batch:
		filters["batch"] = batch
	if student:
		filters["student"] = student
	removed = 0
	for r in frappe.get_all("Student Attendance", filters=filters, fields=["name", "batch", "enrollment"]):
		if r.batch in batch_names:
			continue
		frappe.delete_doc("Student Attendance", r.name, ignore_permissions=True, force=True)
		update_hold(r.enrollment, date, notify=False)
		removed += 1
	return removed


def build_day(date=None, batch=None, student=None, notify=True):
	"""Build (or refresh) attendance of one date for every enrolment with a class that day.
	`batch` / `student` narrow it. Returns counts."""
	date = getdate(date or nowdate())
	counts = frappe._dict(present=0, late=0, partial=0, absent=0, skipped=0, removed=0)
	batches = [b for b in batches_with_class(date) if (not batch or b.name == batch) and (not is_online(b) or meet_ready(b, date))]
	for b in batches:
		filters = dict(ENROLMENT_FILTERS, batch=b.name)
		if student:
			filters["student"] = student
		for e in frappe.get_all("Student Batch Enrollment", filters=filters, fields=["name", "student", "student_name", "status"]):
			status = write_row(e, b, date, _punches(e.student, date, is_online(b)))
			if status is None:
				counts.skipped += 1
				continue
			counts[status.lower() if status.lower() in counts else "present"] += 1
			update_hold(e.name, date, notify=notify)
			if status == "Absent" and notify:
				notify_parent_absent(e, b, date)
	counts.removed = _remove_stale(date, {b.name for b in batches}, batch=batch, student=student)
	frappe.db.commit()
	return counts


def nightly():
	"""Scheduled late evening: close today, and refresh the last N days so late timesheets land."""
	today = getdate(nowdate())
	out = {str(today): build_day(today)}
	for i in range(1, _settings().lookback + 1):
		d = add_days(today, -i)
		out[str(d)] = build_day(d, notify=False)
	return out


@frappe.whitelist()
def rebuild_day(date):
	if not ({"System Manager", "TNC Super Admin", "TNC Manager", "TNC Counsellor"} & set(frappe.get_roles())):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if getdate(date) > getdate(nowdate()):
		frappe.throw(_("That day has not happened yet."))
	# a rebuild of a past day should not re-message parents
	return build_day(date, notify=False)


def on_punch(doc, method=None):
	"""Student Punch Log after_insert: refresh today's row for that student, so the list shows
	Present / In time while the day is running. Absences are only written by the nightly run."""
	date = getdate(doc.punch_time)
	for b in batches_with_class(date):
		if is_online(b) and not meet_ready(b, date):
			continue
		for e in frappe.get_all("Student Batch Enrollment", filters=dict(ENROLMENT_FILTERS, batch=b.name, student=doc.student), fields=["name", "student", "student_name", "status"]):
			write_row(e, b, date, _punches(e.student, date, is_online(b)))
			update_hold(e.name, date, notify=False)


def on_timesheet_change(doc, method=None):
	"""Teachers Timesheet on_update / on_trash: the batches it names get that date rebuilt at once,
	whatever the date, so a timesheet filed late still produces the day's attendance.
	Also the date it used to carry, when the date was changed."""
	if _settings().source != "Teacher timesheets" or getdate(doc.date) > getdate(nowdate()):
		return
	dates = {getdate(doc.date)}
	before = doc.get_doc_before_save() if method != "on_trash" else None
	if before and before.date and getdate(before.date) != getdate(doc.date):
		dates.add(getdate(before.date))
	batches = {r.batch for r in doc.activity_type if r.batch}
	if before:
		batches |= {r.batch for r in before.activity_type if r.batch}
	if method == "on_trash":
		# the rows are still in the table at on_trash; rebuild after the delete has gone through
		frappe.db.after_commit.add(lambda: _rebuild_batches(dates, batches))
	else:
		_rebuild_batches(dates, batches)


def _rebuild_batches(dates, batches):
	for d in dates:
		for b in batches:
			build_day(d, batch=b, notify=False)
		if not batches:
			build_day(d, notify=False)


# ---------- hold ----------

def consecutive_absences(enrolment, upto=None):
	"""Absences in a row counted from the newest attendance row backwards. By default one absent
	day is one absence (setting "Count Absences By"); with Classes, each missed class of a day
	with class windows counts. Stops at the first Present / Late / Leave day (or Present class).
	`upto` is accepted for callers but the count always starts at the newest row, so a late
	timesheet or a deleted one re-counts correctly."""
	n = 0
	by_classes = _settings().count_by == "Classes"
	for r in frappe.get_all("Student Attendance", filters={"enrollment": enrolment},
			fields=["name", "status", "classes_held"], order_by="date desc", limit=200):
		if r.status in ("Leave", "Partial"):
			break  # a Partial day (one punch only) is not an absence and never feeds the hold
		if by_classes and cint(r.classes_held):
			stop = False
			for c in frappe.get_all("Student Class Attendance", filters={"parent": r.name}, fields=["status"], order_by="from_time desc"):
				if c.status in ("Present", "Late"):
					stop = True
					break
				n += 1
			if stop:
				break
			continue
		if r.status != "Absent":
			break
		n += 1
	return n


def update_hold(enrolment, upto, notify=True):
	"""Recount, and put the enrolment On Hold (Attendance) at the threshold. Never releases a hold:
	that is a person's decision (Counsellor/Manager, with remarks)."""
	if not frappe.db.exists("Student Batch Enrollment", enrolment):
		return 0
	e = frappe.get_doc("Student Batch Enrollment", enrolment)
	n = consecutive_absences(enrolment, upto)
	if n != cint(e.consecutive_absences):
		e.db_set("consecutive_absences", n, update_modified=False)
	threshold = _settings().hold_after
	if n >= threshold and e.status == "Active":
		e.db_set({"status": "On Hold", "hold_type": "Attendance", "hold_on": getdate(upto),
			"hold_reason": (_("Absent for {0} consecutive {1}, last on {2}.")).format(n, (_("day") if n == 1 else _("days")) if _settings().count_by == "Days" else (_("class") if n == 1 else _("classes")), frappe.format_value(getdate(upto), {"fieldtype": "Date"}))})
		sync_student_status(e.student)
		frappe.get_doc({"doctype": "Comment", "comment_type": "Info", "reference_doctype": "Student Batch Enrollment", "reference_name": e.name,
			"content": _("Put on Attendance Hold automatically: {0} consecutive absences.").format(n)}).insert(ignore_permissions=True)
		if notify:
			notify_parent_hold(e, n)
	return n


def sync_student_status(student):
	"""Student.status mirrors the enrolments: Attendance Hold while any enrolment is held for attendance, else Active."""
	cur = frappe.db.get_value("Student", student, "status")
	if cur in ("Completed", "Discontinued"):
		return
	held = frappe.db.exists("Student Batch Enrollment", dict(ENROLMENT_FILTERS, student=student, status="On Hold", hold_type="Attendance"))
	want = "Attendance Hold" if held else "Active"
	if cur != want and frappe.db.exists("Student Batch Enrollment", dict(ENROLMENT_FILTERS, student=student)):
		frappe.db.set_value("Student", student, "status", want, update_modified=False)


# ---------- parent messages ----------

def parent_mobile(student):
	s = frappe.db.get_value("Student", student, ["father_mobile_no", "mother_mobile_no", "guardian_mobile", "mobile"], as_dict=True) or {}
	order = {"Father": ["father_mobile_no", "mother_mobile_no", "guardian_mobile"], "Mother": ["mother_mobile_no", "father_mobile_no", "guardian_mobile"],
		"Guardian": ["guardian_mobile", "father_mobile_no", "mother_mobile_no"]}[_settings().parent_number]
	for k in order + ["mobile"]:
		if (s.get(k) or "").strip():
			return s[k].strip()
	return None


def _send(student, text, ref):
	from tnc_v2_360ithub import notifications
	mobile = parent_mobile(student)
	if not mobile:
		return
	notifications.send_whatsapp_to_mobile(mobile, text, ref_doctype="Student Batch Enrollment", ref_name=ref)


def _parent_salutation(student=None):
	return _("Dear Parent,")


def notify_parent_absent(enrolment, batch, date):
	# the client wants parents told when a hold starts, not every absent day (16 Oct); daily is a separate switch
	if not (_settings().parent_whatsapp and _settings().parent_daily):
		return
	text = "\n".join([
		_parent_salutation(),
		"",
		_("{0} was absent from {1} on {2}.").format(enrolment.student_name, batch.name, frappe.format_value(getdate(date), {"fieldtype": "Date"})),
		"",
		_("Regards,"), _institute(),
	])
	_send(enrolment.student, text, enrolment.name)


def notify_parent_hold(e, n):
	if not _settings().parent_whatsapp:
		return
	unit = _("days") if _settings().count_by == "Days" else _("classes")
	text = "\n".join([
		_parent_salutation(),
		"",
		_("{0} has been absent from {1} for {2} consecutive {3} and is on Attendance Hold. Please contact the office.").format(e.student_name, e.batch, n, unit),
		"",
		_("Regards,"), _institute(),
	])
	_send(e.student, text, e.name)


def _institute():
	return frappe.db.get_single_value("TNC Settings", "document_institute_name") or frappe.defaults.get_global_default("company") or ""
