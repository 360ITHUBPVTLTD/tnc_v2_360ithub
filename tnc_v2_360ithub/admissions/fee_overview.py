"""Fee Overview: every student's fee position in one place, the daily WhatsApp reminders and the
automatic Fee Hold.

Where the money sits. Admission creates one Sales Order per enrolment with a Payment Schedule
(the instalments). Receive Payment allocates to the earliest-due instalment first, so each row
carries its own paid / outstanding. Nothing here stores a second copy of any amount: the page,
the reminders and the hold all read the schedule.

Reminders (TNC Settings > Fees, 07:00 daily). Per unpaid instalment: "due soon" N days before
the due date, "due today" on it, "overdue" every M days after it. One message per instalment
per day at most, recorded on the schedule row (custom_fee_reminded_on / _kind) so a rerun never
sends twice. Texts are editable in TNC Settings with placeholders.

Fee Hold. An instalment unpaid for more than the grace days (default 3) ticks "On Fee Hold" on
the enrolment (fee_hold / fee_hold_on / fee_hold_reason), in the morning job or the moment a
payment or cancellation changes the picture. It is its own flag, independent of the Enrolment
Status: status On Hold + Hold Type is the Attendance (or manual) hold, released by a person with
remarks; a student can carry both at once and each is released on its own. The hold lifts by itself when nothing is overdue any more (a part payment that clears the
overdue instalment is enough). While on Fee Hold the machine still logs the punch, but the day
stays Absent with the note "Fee hold" and the front desk gets a WhatsApp the first time the
student punches that day. Attendance Holds are untouched: a Fee Hold never counts towards the
consecutive-absence rule, and releasing the Attendance Hold never touches the Fee Hold.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, fmt_money, getdate, nowdate

from tnc_v2_360ithub.admissions.enquiry_overview import is_manager
from tnc_v2_360ithub.branding import institute_logo

ENROL_STATUSES = ("Active", "On Hold")
FEE_NOTE = "Fee hold"  # Student Attendance.note prefix on days a held student's punches were ignored
HOLD_ROLES = {"TNC Counsellor", "TNC Manager", "TNC Super Admin", "System Manager"}


def _s():
	s = frappe.get_cached_doc("TNC Settings")
	return frappe._dict(
		grace=cint(s.get("fee_hold_grace_days")),
		blocks_punch=cint(s.get("fee_hold_blocks_punch")),
		desk=(s.get("fee_desk_mobile") or "").strip(),
		before=cint(s.get("fee_remind_before_days")),
		every=cint(s.get("fee_remind_every_days")),
		guardian=cint(s.get("fee_remind_guardian")),
		msg={k: (s.get(f"fee_msg_{k}") or "").strip() for k in ("upcoming", "due_today", "overdue", "hold", "desk")},
		institute=s.get("document_institute_name") or frappe.defaults.get_global_default("company") or "",
	)


def _money(v):
	return fmt_money(flt(v), precision=0)


def _date(d):
	return frappe.format_value(getdate(d), {"fieldtype": "Date"}) if d else ""


# ---------------------------------------------------------------------------
# the fee position of every enrolment
# ---------------------------------------------------------------------------


def settled_by_order(orders):
	"""{sales_order: money really held against it}. Two parts: receipts (Sales Invoices billed
	against the order) to the extent they are settled (grand_total - outstanding_amount, so a
	receipt whose Payment Entry was cancelled counts for nothing), credit notes deducted; plus any
	Payment Entry still allocated to the order itself (an advance not yet turned into a receipt).
	This is independent of the Payment Schedule's paid_amount, which ERPNext does not reverse when
	a payment is cancelled after its receipt was made."""
	orders = list(orders)
	out = {o: 0.0 for o in orders}
	if not orders:
		return out
	for so, amt in frappe.db.sql("""select x.sales_order, sum(x.amt) from (
			select distinct si.name, i.sales_order,
				(case when si.is_return = 1 then -abs(si.grand_total) else si.grand_total - si.outstanding_amount end) as amt
			from `tabSales Invoice` si join `tabSales Invoice Item` i on i.parent = si.name
			where si.docstatus = 1 and i.sales_order in %(so)s) x group by x.sales_order""", {"so": orders}):
		out[so] = flt(out.get(so, 0) + flt(amt), 2)
	for so, amt in frappe.db.sql("""select r.reference_name, sum(r.allocated_amount) from `tabPayment Entry Reference` r
			join `tabPayment Entry` pe on pe.name = r.parent
			where pe.docstatus = 1 and pe.payment_type = 'Receive' and r.reference_doctype = 'Sales Order' and r.reference_name in %(so)s
			group by r.reference_name""", {"so": orders}):
		out[so] = flt(out.get(so, 0) + flt(amt), 2)
	return out


def resync_schedule(sales_order):
	"""Bring the order's instalments back in line with the money really held (settled_by_order),
	earliest due first, the same order Receive Payment allocates in. Needed after a Payment Entry
	is cancelled: ERPNext leaves paid_amount on the instalment. Writes only when something differs
	and records it as a comment on the order. Returns the corrected amount, or 0."""
	settled = settled_by_order([sales_order]).get(sales_order, 0)
	# the order's own "advance paid" is ERPNext's figure; let ERPNext recompute it from its ledger rather than leave a stale one
	try:
		frappe.get_doc("Sales Order", sales_order).set_total_advance_paid()
	except Exception:
		frappe.log_error(title="Fee: advance paid not recomputed", message=frappe.get_traceback())
	rows = frappe.get_all("Payment Schedule", filters={"parent": sales_order, "parenttype": "Sales Order"},
		fields=["name", "payment_amount", "paid_amount", "outstanding", "due_date", "idx"], order_by="due_date asc, idx asc")
	was = flt(sum(flt(r.paid_amount) for r in rows), 2)
	if not rows or abs(was - settled) <= 0.01:
		return 0
	remaining = max(0, settled)
	for r in rows:
		paid = flt(min(flt(r.payment_amount), remaining), 2)
		remaining = flt(remaining - paid, 2)
		out = flt(flt(r.payment_amount) - paid, 2)
		if abs(flt(r.paid_amount) - paid) > 0.005 or abs(flt(r.outstanding) - out) > 0.005:
			frappe.db.set_value("Payment Schedule", r.name, {"paid_amount": paid, "outstanding": out, "base_paid_amount": paid, "base_outstanding": out}, update_modified=False)
	frappe.get_doc({"doctype": "Comment", "comment_type": "Info", "reference_doctype": "Sales Order", "reference_name": sales_order,
		"content": _("Instalments re-synced with the payments: received was shown as {0}, the payments and receipts on record add up to {1}.").format(_money(was), _money(settled))}).insert(ignore_permissions=True)
	return flt(was - settled, 2)


def _rows(batch=None, counsellor=None, student=None, enrollment=None, today=None):
	"""One dict per submitted Active / On Hold enrolment that has a fee order: amounts, the
	instalments, the next and oldest unpaid due dates, hold state, who to call."""
	today = getdate(today or nowdate())
	cond, args = [], {}
	if batch:
		cond.append("e.batch = %(batch)s"); args["batch"] = batch
	if counsellor:
		cond.append("st.counsellor = %(counsellor)s"); args["counsellor"] = counsellor
	if student:
		cond.append("e.student = %(student)s"); args["student"] = student
	if enrollment:
		cond.append("e.name = %(enrollment)s"); args["enrollment"] = enrollment
	enrols = frappe.db.sql(f"""
		select e.name, e.student, e.student_name, e.batch, b.batch_name, e.sales_order, e.status, e.hold_type, e.hold_on, e.hold_reason,
			e.fee_hold, e.fee_hold_on, e.fee_hold_reason, e.fee_hold_msg_pending,
			e.enrollment_date, e.net_payable, so.advance_paid, so.status as so_status,
			-- payable = ERPNext's rounded total when rounding is on (GST orders carry paise in grand_total)
			(case when ifnull(so.disable_rounded_total, 0) = 0 and ifnull(so.rounded_total, 0) > 0 then so.rounded_total else so.grand_total end) as grand_total,
			st.mobile, st.father_mobile_no, st.mother_mobile_no, st.guardian_mobile, st.counsellor, u.full_name as counsellor_name
		from `tabStudent Batch Enrollment` e
		join `tabSales Order` so on so.name = e.sales_order and so.docstatus = 1
		left join `tabStudent Batch` b on b.name = e.batch
		left join `tabStudent` st on st.name = e.student
		left join `tabUser` u on u.name = st.counsellor
		where e.docstatus = 1 and e.status in ('Active', 'On Hold') and ifnull(e.sales_order, '') != ''
		{("and " + " and ".join(cond)) if cond else ""}
		order by e.student_name""", args, as_dict=True)
	if not enrols:
		return []
	sched = {}
	for r in frappe.db.sql("""select name, parent, payment_term, description, due_date, payment_amount, paid_amount, outstanding,
			custom_fee_reminded_on, custom_fee_reminder_kind
		from `tabPayment Schedule` where parenttype = 'Sales Order' and parent in %(so)s order by due_date asc, idx asc""",
			{"so": [e.sales_order for e in enrols]}, as_dict=True):
		sched.setdefault(r.parent, []).append(r)
	settled = settled_by_order([e.sales_order for e in enrols])
	# receipts that exist with no payment behind them (their Payment Entry was cancelled): the receipt must be cancelled too
	orphan = dict(frappe.db.sql("""select x.sales_order, sum(x.amt) from (select distinct si.name, i.sales_order, si.outstanding_amount as amt
		from `tabSales Invoice` si join `tabSales Invoice Item` i on i.parent = si.name
		where si.docstatus = 1 and si.is_return = 0 and si.outstanding_amount > 0.5 and i.sales_order in %(so)s) x group by x.sales_order""", {"so": [e.sales_order for e in enrols]}))
	out = []
	for e in enrols:
		inst = []
		for r in sched.get(e.sales_order, []):
			# ERPNext marks paid_amount on the instalment when a Payment Entry is submitted; the
			# outstanding column is derived from it, so derive it here too and never trust a stale copy
			out_amt = flt(flt(r.payment_amount) - flt(r.paid_amount), 2)
			inst.append({"name": r.name, "term": r.payment_term or r.description or "", "due_date": r.due_date, "amount": flt(r.payment_amount, 2), "paid": flt(r.paid_amount, 2),
				"outstanding": out_amt, "overdue_days": max(0, (today - getdate(r.due_date)).days) if out_amt > 0.5 and r.due_date else 0,
				"reminded_on": r.custom_fee_reminded_on, "reminder_kind": r.custom_fee_reminder_kind})
		unpaid = [i for i in inst if i["outstanding"] > 0.5]
		# same arithmetic as fees.pending_on_order (the Receive Payment dialog): order total minus what the schedule says is paid
		paid = flt(sum(i["paid"] for i in inst), 2) if inst else flt(e.advance_paid, 2)
		pending = flt(flt(e.grand_total) - paid, 2)
		schedule_total = flt(sum(i["amount"] for i in inst), 2)
		overdue = [i for i in unpaid if getdate(i["due_date"]) < today]
		nxt = unpaid[0] if unpaid else None
		oldest = overdue[0] if overdue else None
		last_rem = max((i["reminded_on"] for i in inst if i["reminded_on"]), default=None)
		e.update({
			"instalments": inst, "total": flt(e.grand_total), "paid": paid, "pending": pending,
			"overdue_amount": flt(sum(i["outstanding"] for i in overdue), 2), "overdue_count": len(overdue),
			"next_due": nxt["due_date"] if nxt else None, "next_amount": nxt["outstanding"] if nxt else 0,
			"oldest_due": oldest["due_date"] if oldest else None, "overdue_days": oldest["overdue_days"] if oldest else 0,
			"fee_hold": cint(e.fee_hold),
			# the enrolment's own status hold (Attendance / Other): shown for information, never counted on this page
			"other_hold": 1 if e.status == "On Hold" else 0,
			"last_reminder": last_rem,
			# instalments that do not add up to the order total (should never happen; shown as a warning, never silently adjusted)
			"schedule_mismatch": flt(schedule_total - flt(e.grand_total), 2) if inst and abs(schedule_total - flt(e.grand_total)) > 0.01 else 0,
			# received as the instalments say vs the payments and receipts on record; any difference is shown in red on the row
			"unpaid_receipts": flt(orphan.get(e.sales_order, 0), 2),
			"settled": settled.get(e.sales_order, 0), "ledger_mismatch": flt(paid - settled.get(e.sales_order, 0), 2) if abs(paid - settled.get(e.sales_order, 0)) > 0.01 else 0,
			"bucket": "paid" if pending <= 0.5 else "overdue" if overdue else "due_week" if nxt and (getdate(nxt["due_date"]) - today).days <= 7 else "upcoming",
		})
		out.append(e)
	return out


@frappe.whitelist()
def get_overview(batch=None, counsellor=None, collected_from=None, collected_to=None):
	"""The page. Counsellors without the manager view see only their own students."""
	manager = is_manager()
	if not manager:
		counsellor = frappe.session.user
	rows = _rows(batch=batch or None, counsellor=counsellor or None)
	today = getdate(nowdate())
	s = _s()
	# collected this month: every receipt (Sales Invoice) billed against these orders, credit notes deducted.
	# On submit ERPNext re-points the Payment Entry from the order to the receipt, so the invoices, not the
	# payment references, are the reliable link back to the order.
	# the "Collected" tile's period: the page's filter, this calendar month when none is chosen
	month_from = getdate(collected_from) if collected_from else today.replace(day=1)
	month_to = getdate(collected_to) if collected_to else today
	if month_to < month_from:
		month_from, month_to = month_to, month_from
	receipts = []
	if rows:
		receipts = frappe.db.sql("""select si.name, si.posting_date, si.customer, si.custom_student, si.is_return,
				(case when si.is_return = 1 then -abs(si.grand_total) else si.grand_total end) as amount, i.sales_order,
				(select group_concat(distinct pe.mode_of_payment) from `tabPayment Entry Reference` r join `tabPayment Entry` pe on pe.name = r.parent
					where r.reference_doctype = 'Sales Invoice' and r.reference_name = si.name and pe.docstatus = 1) as mode
			from `tabSales Invoice` si join `tabSales Invoice Item` i on i.parent = si.name
			where si.docstatus = 1 and si.posting_date between %(from)s and %(to)s and i.sales_order in %(so)s
			group by si.name order by si.posting_date desc, si.name desc""", {"from": month_from, "to": month_to, "so": [r.sales_order for r in rows]}, as_dict=True)
		by_so = {r.sales_order: r for r in rows}
		for x in receipts:
			e = by_so.get(x.sales_order) or {}
			x.update({"student": e.get("student"), "student_name": e.get("student_name"), "batch_name": e.get("batch_name") or e.get("batch"), "amount": flt(x.amount, 2)})
	collected = flt(sum(x.amount for x in receipts), 2)
	# active enrolments the page cannot show: no fee order (imported with "fees outside system"), same filters as the page
	cond, args = "", {}
	if batch:
		cond += " and e.batch = %(batch)s"; args["batch"] = batch
	if counsellor:
		cond += " and st.counsellor = %(counsellor)s"; args["counsellor"] = counsellor
	outside = frappe.db.sql(f"""select count(*) from `tabStudent Batch Enrollment` e left join `tabStudent` st on st.name = e.student
		where e.docstatus = 1 and e.status in ('Active', 'On Hold') and ifnull(e.sales_order, '') = '' {cond}""", args)[0][0]

	def bucket(key_f, label_f):
		agg = {}
		for r in rows:
			k = key_f(r)
			a = agg.setdefault(k, {"key": k, "label": label_f(r), "students": 0, "total": 0, "paid": 0, "pending": 0, "overdue": 0, "overdue_students": 0, "held": 0})
			a["students"] += 1; a["total"] += r.total; a["paid"] += r.paid; a["pending"] += r.pending; a["overdue"] += r.overdue_amount
			a["overdue_students"] += 1 if r.overdue_count else 0; a["held"] += r.fee_hold
		return sorted(agg.values(), key=lambda x: -x["pending"])
	return {
		"manager": manager, "batch": batch or None, "counsellor": counsellor or None,
		"counsellor_name": frappe.db.get_value("User", counsellor, "full_name") if counsellor else None,
		"logo": institute_logo(),
		"settings": {"grace": s.grace, "before": s.before, "every": s.every, "desk": bool(s.desk), "blocks_punch": s.blocks_punch},
		"students": len(rows), "outside_system": outside,
		"total": flt(sum(r.total for r in rows), 2), "paid": flt(sum(r.paid for r in rows), 2), "pending": flt(sum(r.pending for r in rows), 2),
		"overdue_amount": flt(sum(r.overdue_amount for r in rows), 2), "overdue_students": sum(1 for r in rows if r.overdue_count),
		"due_week": sum(1 for r in rows if r.bucket == "due_week"), "due_week_amount": flt(sum(r.next_amount for r in rows if r.bucket == "due_week"), 2),
		"fee_hold": sum(r.fee_hold for r in rows), "fully_paid": sum(1 for r in rows if r.bucket == "paid"),
		# every hold among these students, by kind, so the tile adds up: on_hold = fee + attendance + other
		"both_holds": sum(1 for r in rows if r.fee_hold and r.other_hold),
		"mismatches": sum(1 for r in rows if r.ledger_mismatch or r.schedule_mismatch or r.unpaid_receipts),
		"collected_month": collected, "receipts_month": receipts, "collected_from": month_from, "collected_to": month_to,
		"by_batch": bucket(lambda r: r.batch, lambda r: r.batch_name or r.batch) if not batch else [],
		"by_counsellor": bucket(lambda r: r.counsellor or "", lambda r: r.counsellor_name or r.counsellor or _("No counsellor")) if manager and not counsellor else [],
		"rows": rows,
	}


# ---------------------------------------------------------------------------
# messages
# ---------------------------------------------------------------------------


def _fill(text, r, inst=None):
	days = inst["overdue_days"] if inst else r.get("overdue_days", 0)
	due = inst["due_date"] if inst else (r.get("oldest_due") or r.get("next_due"))
	return text.format(student=r.student_name or r.student, batch=r.batch_name or r.batch, amount=_money(inst["outstanding"] if inst else r.pending),
		due_date=_date(due), days=days, term=(inst or {}).get("term", ""), institute=_s().institute, total_pending=_money(r.pending))


def _recipients(r):
	"""Student mobile, plus the parent number when the setting asks for it (never the same number twice)."""
	nums = [(r.mobile or "").strip()]
	if _s().guardian:
		from tnc_v2_360ithub.attendance.daily import parent_mobile
		p = parent_mobile(r.student)
		if p and p not in nums:
			nums.append(p)
	return [n for n in nums if n]


def _send(r, text):
	from tnc_v2_360ithub import notifications
	sent = 0
	for n in _recipients(r):
		resp = notifications.send_whatsapp_to_mobile(n, text, ref_doctype="Student Batch Enrollment", ref_name=r.name)
		sent += 1 if (resp or {}).get("status") else 0
	return sent


def _remind_instalment(r, inst, kind, today):
	text = _s().msg.get(kind)
	if not text:
		return 0
	n = _send(r, _fill(text, r, inst))
	# stamp only what really went out: a failed or skipped send (provider off, no mobile) is retried next day
	if n:
		frappe.db.set_value("Payment Schedule", inst["name"], {"custom_fee_reminded_on": today, "custom_fee_reminder_kind": kind}, update_modified=False)
	return n


# ---------------------------------------------------------------------------
# hold
# ---------------------------------------------------------------------------


def _hold(r, today, notify=True):
	e = frappe.get_doc("Student Batch Enrollment", r.name)
	if cint(e.fee_hold) or e.status not in ENROL_STATUSES:
		return False
	reason = _("Fee of {0} overdue since {1} ({2} days).").format(_money(r.overdue_amount), _date(r.oldest_due), r.overdue_days)
	# notify=False (the 04:00 check): hold now, leave the WhatsApp for the 07:00 job to send
	e.db_set({"fee_hold": 1, "fee_hold_on": getdate(today), "fee_hold_reason": reason, "fee_hold_msg_pending": 0 if notify else 1}, update_modified=False)
	frappe.get_doc({"doctype": "Comment", "comment_type": "Info", "reference_doctype": "Student Batch Enrollment", "reference_name": e.name,
		"content": _("Put on Fee Hold automatically: {0}").format(reason)}).insert(ignore_permissions=True)
	if notify and _s().msg.get("hold"):
		_send(r, _fill(_s().msg["hold"], r))
	return True


def _release(r, why, by=None):
	e = frappe.get_doc("Student Batch Enrollment", r.name)
	if not cint(e.fee_hold):
		return False
	# only the fee flag: the enrolment's status (and any Attendance Hold on it) is left exactly as it is
	e.db_set({"fee_hold": 0, "fee_hold_on": None, "fee_hold_reason": None, "fee_hold_msg_pending": 0}, update_modified=False)
	frappe.get_doc({"doctype": "Comment", "comment_type": "Info", "reference_doctype": "Student Batch Enrollment", "reference_name": e.name,
		"content": _("Fee Hold released{0}: {1}").format(f" by {by}" if by else _(" automatically"), why)}).insert(ignore_permissions=True)
	return True


def refresh_hold(sales_order=None, enrollment=None, today=None, notify=True):
	"""Bring the Fee Hold in line with the schedule: hold when the oldest unpaid instalment is past
	the grace days, release a Fee Hold when nothing is overdue. Called by the morning job and after
	every payment or payment cancellation. Returns ("held" | "released" | None, enrolment name)."""
	today = getdate(today or nowdate())
	grace = _s().grace
	if sales_order and not enrollment:
		enrollment = frappe.db.get_value("Student Batch Enrollment", {"sales_order": sales_order, "docstatus": 1}, "name")
	if not enrollment:
		return None, None
	rows = _rows(enrollment=enrollment, today=today)
	if not rows:
		return None, enrollment
	r = rows[0]
	if r.fee_hold and not r.overdue_count:
		_release(r, _("Nothing overdue any more; pending {0}.").format(_money(r.pending)))
		return "released", enrollment
	if grace > 0 and not r.fee_hold and r.overdue_count and r.overdue_days >= grace:
		if _hold(r, today, notify=notify):
			return "held", enrollment
	return None, enrollment


# ---------------------------------------------------------------------------
# scheduler + hooks
# ---------------------------------------------------------------------------


def hold_check(today=None):
	"""04:00, before the first class of the day. The Fee Hold check only, for every enrolment, with
	no WhatsApp at that hour: a student held here is flagged and gets the Fee Hold message from the
	07:00 job. So a punch at the 06:00 class already does not count and alerts the front desk."""
	today = getdate(today or nowdate())
	out = frappe._dict(held=0, released=0)
	for r in _rows(today=today):
		what, _n = refresh_hold(enrollment=r.name, today=today, notify=False)
		if what:
			out[what] += 1
	if not frappe.flags.in_test:
		frappe.db.commit()
	return out


def _send_pending_hold_messages(today):
	"""The Fee Hold WhatsApp for students the 04:00 check put on hold. The flag is cleared only
	when the message really went out, so a failed send is tried again the next morning."""
	text = _s().msg.get("hold")
	n = 0
	for r in _rows(today=today):
		if not (r.fee_hold and cint(r.fee_hold_msg_pending)):
			continue
		if not text or _send(r, _fill(text, r)):
			frappe.db.set_value("Student Batch Enrollment", r.name, "fee_hold_msg_pending", 0, update_modified=False)
			n += 1 if text else 0
	return n


def daily(today=None):
	"""07:00. Reminders for every unpaid instalment that is due soon / today / overdue on its cycle,
	then the Fee Hold check for every enrolment, then the Fee Hold message to students the 04:00
	check held."""
	today = getdate(today or nowdate())
	s = _s()
	out = frappe._dict(reminded=0, held=0, released=0, hold_messages=0)
	for r in _rows(today=today):
		for inst in r.instalments:
			if inst["outstanding"] <= 0.5 or not inst["due_date"] or (inst["reminded_on"] and getdate(inst["reminded_on"]) == today):
				continue
			days_to = (getdate(inst["due_date"]) - today).days
			kind = None
			if days_to > 0:
				kind = "upcoming" if (s.before and days_to == s.before) else None
			elif days_to == 0:
				kind = "due_today"
			elif s.every and (-days_to) % s.every == 0:
				kind = "overdue"
			if kind:
				out.reminded += _remind_instalment(r, inst, kind, today)
		what, _n = refresh_hold(enrollment=r.name, today=today)
		if what:
			out[what] += 1
	out.hold_messages = _send_pending_hold_messages(today)
	if not frappe.flags.in_test:
		frappe.db.commit()
	return out


def on_payment_entry(doc, method=None):
	"""Payment Entry on_submit / on_cancel: the moment money lands (or is reversed) the hold follows."""
	orders = set()
	for ref in doc.get("references") or []:
		if ref.reference_doctype == "Sales Order":
			orders.add(ref.reference_name)
		elif ref.reference_doctype == "Sales Invoice":
			orders |= set(frappe.get_all("Sales Invoice Item", filters={"parent": ref.reference_name, "sales_order": ["is", "set"]}, pluck="sales_order", distinct=True))
	if doc.get("custom_student"):
		orders |= set(frappe.get_all("Sales Order", filters={"custom_student": doc.custom_student, "docstatus": 1}, pluck="name"))
	for so in orders:
		if frappe.db.get_value("Sales Order", so, "custom_student"):
			try:
				if method == "on_cancel" or doc.docstatus == 2:
					resync_schedule(so)
				refresh_hold(sales_order=so)
			except Exception:
				frappe.log_error(title="Fee hold refresh failed", message=frappe.get_traceback())


def is_fee_held(enrolment, date=None):
	"""Do this enrolment's punches on `date` not count? Only from the day the Fee Hold started, so
	the nightly rebuild of the last days never turns an earlier Present into Absent. `enrolment`
	is a dict / doc with fee_hold and fee_hold_on, or a name."""
	if not _s().blocks_punch:
		return False
	if isinstance(enrolment, str) or "fee_hold" not in enrolment:
		enrolment = frappe.db.get_value("Student Batch Enrollment", enrolment if isinstance(enrolment, str) else enrolment.get("name"), ["fee_hold", "fee_hold_on"], as_dict=True) or {}
	if not cint(enrolment.get("fee_hold")):
		return False
	return not (date and enrolment.get("fee_hold_on") and getdate(date) < getdate(enrolment.get("fee_hold_on")))


def on_held_punch(student, date):
	"""A student on Fee Hold punched: alert the front desk once a day per enrolment."""
	s = _s()
	if not (s.blocks_punch and s.desk and s.msg.get("desk")):
		return
	for r in _rows(student=student, today=date):
		if not r.fee_hold:
			continue
		key = f"fee_desk_alert:{r.name}:{getdate(date)}"
		if frappe.cache().get_value(key):
			continue
		frappe.cache().set_value(key, 1, expires_in_sec=20 * 3600)
		from tnc_v2_360ithub import notifications
		notifications.send_whatsapp_to_mobile(s.desk, _fill(s.msg["desk"], r), ref_doctype="Student Batch Enrollment", ref_name=r.name)


# ---------------------------------------------------------------------------
# page actions
# ---------------------------------------------------------------------------


def _need_hold_role():
	if not (HOLD_ROLES & set(frappe.get_roles())):
		frappe.throw(_("Only a Counsellor, Manager or Super Admin can do this."), frappe.PermissionError)


@frappe.whitelist()
def hold_now(enrollment, remarks=None):
	_need_hold_role()
	rows = _rows(enrollment=enrollment)
	if not rows:
		frappe.throw(_("Enrolment not found or has no fee order."))
	r = rows[0]
	if r.fee_hold:
		frappe.throw(_("{0} is already on Fee Hold.").format(r.student_name))
	if r.pending <= 0.5:
		frappe.throw(_("{0} has nothing pending.").format(r.student_name))
	e = frappe.get_doc("Student Batch Enrollment", r.name)
	reason = (remarks or "").strip() or _("Fee of {0} pending.").format(_money(r.pending))
	e.db_set({"fee_hold": 1, "fee_hold_on": getdate(nowdate()), "fee_hold_reason": reason}, update_modified=False)
	frappe.get_doc({"doctype": "Comment", "comment_type": "Info", "reference_doctype": "Student Batch Enrollment", "reference_name": e.name,
		"content": _("Put on Fee Hold by {0}: {1}").format(frappe.session.user, reason)}).insert(ignore_permissions=True)
	if _s().msg.get("hold"):
		_send(r, _fill(_s().msg["hold"], r))
	return "held"


@frappe.whitelist()
def release_now(enrollment, remarks):
	_need_hold_role()
	if not (remarks or "").strip():
		frappe.throw(_("Please write why the hold is released."))
	rows = _rows(enrollment=enrollment)
	if not rows or not rows[0].fee_hold:
		frappe.throw(_("This enrolment is not on Fee Hold."))
	_release(rows[0], remarks.strip(), by=frappe.session.user)
	return "released"


@frappe.whitelist()
def remind_now(enrollment):
	"""Send the right reminder for the enrolment's oldest unpaid instalment now."""
	rows = _rows(enrollment=enrollment)
	if not rows:
		frappe.throw(_("Enrolment not found or has no fee order."))
	r = rows[0]
	unpaid = [i for i in r.instalments if i["outstanding"] > 0.5]
	if not unpaid:
		frappe.throw(_("Nothing pending for {0}.").format(r.student_name))
	inst = unpaid[0]
	today = getdate(nowdate())
	kind = "overdue" if getdate(inst["due_date"]) < today else "due_today" if getdate(inst["due_date"]) == today else "upcoming"
	# say exactly why, in the user's words, before trying
	if not _recipients(r):
		frappe.throw(_("{0} has no mobile number on the student record. Add it and try again.").format(r.student_name), title=_("Reminder not sent"))
	from tnc_v2_360ithub import notifications
	ok, reason = notifications.whatsapp_available()
	if not ok:
		if "Disabled" in reason:
			frappe.throw(_("WhatsApp sending is switched off on this site, so the reminder was not sent."), title=_("Reminder not sent"))
		frappe.throw(_("WhatsApp is not connected right now, so the reminder was not sent. Please ask the admin to reconnect the WhatsApp number and try again."), title=_("Reminder not sent"))
	n = _remind_instalment(r, inst, kind, today)
	if not n:
		frappe.throw(_("WhatsApp could not deliver the reminder to {0}. Please check the number and try again.").format(r.mobile or ""), title=_("Reminder not sent"))
	return {"sent": n, "kind": kind}


@frappe.whitelist()
def fee_holds(student):
	"""For the Student form: this student's enrolments on Fee Hold, with what is overdue."""
	return [{"enrollment": r.name, "batch": r.batch_name or r.batch, "since": r.fee_hold_on, "reason": r.fee_hold_reason,
		"overdue": r.overdue_amount, "pending": r.pending, "sales_order": r.sales_order} for r in _rows(student=student) if r.fee_hold]


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------


def audit(verbose=False):
	"""Reconcile every row of the page with ERPNext's own records. Read-only. For each enrolment:
	the page's total / paid / pending against (a) the Sales Order total, (b) the Receive Payment
	dialog's arithmetic, (c) the order's advance_paid, (d) the receipts (Sales Invoices, credit
	notes deducted) billed against the order, and (e) the instalments adding up to the order total.
	Also lists what the page cannot show: active enrolments with no fee order, orders of a student
	with no enrolment pointing at them, and two enrolments sharing one order.
	Run: bench --site <site> execute tnc_v2_360ithub.admissions.fee_overview.audit"""
	from tnc_v2_360ithub.admissions.fees import order_payable, pending_on_order
	rows = _rows()
	problems, ok = [], 0
	for r in rows:
		so = frappe.get_doc("Sales Order", r.sales_order)
		dlg_pending, dlg_paid = pending_on_order(so)
		receipts = flt(frappe.db.sql("""select sum(case when si.is_return = 1 then -abs((case when ifnull(si.disable_rounded_total, 0) = 0 and ifnull(si.rounded_total, 0) <> 0 then si.rounded_total else si.grand_total end)) else (case when ifnull(si.disable_rounded_total, 0) = 0 and ifnull(si.rounded_total, 0) <> 0 then si.rounded_total else si.grand_total end) end) from `tabSales Invoice` si
			where si.docstatus = 1 and si.name in (select parent from `tabSales Invoice Item` where sales_order = %s)""", r.sales_order)[0][0], 2)
		checks = {
			"total = order total": r.total == order_payable(so),
			"pending = payment dialog": r.pending == flt(dlg_pending, 2),
			"paid = payment dialog": r.paid == flt(dlg_paid, 2),
			"paid = order advance_paid": r.paid == flt(so.advance_paid, 2),
			"paid = receipts issued": r.paid == receipts,
			"paid = payments and receipts actually settled": not r.ledger_mismatch,
			"no receipt without a payment": not r.unpaid_receipts,
			"instalments add up to order total": not r.schedule_mismatch,
			"instalment pending adds up": flt(sum(i["outstanding"] for i in r.instalments), 2) == r.pending,
			"no instalment over-paid": all(i["outstanding"] >= -0.01 for i in r.instalments),
			"pending not negative": r.pending >= -0.01,
		}
		failed = [k for k, v in checks.items() if not v]
		if failed:
			problems.append({"enrollment": r.name, "student": r.student, "student_name": r.student_name, "batch": r.batch, "sales_order": r.sales_order,
				"page": {"total": r.total, "paid": r.paid, "pending": r.pending}, "order_total": order_payable(so), "advance_paid": flt(so.advance_paid, 2),
				"dialog_pending": flt(dlg_pending, 2), "receipts": receipts, "failed": failed})
		else:
			ok += 1
	shown = {r.sales_order for r in rows}
	no_order = frappe.db.sql("""select name, student, student_name, batch, fees_outside_system, net_payable from `tabStudent Batch Enrollment`
		where docstatus = 1 and status in ('Active', 'On Hold') and ifnull(sales_order, '') = ''""", as_dict=True)
	orphan = [o for o in frappe.get_all("Sales Order", filters={"docstatus": 1, "custom_student": ["is", "set"], "status": ["not in", ["Closed"]]},
		fields=["name", "custom_student", "grand_total", "advance_paid", "status"]) if o.name not in shown]
	shared = frappe.db.sql("""select sales_order, count(*) as n from `tabStudent Batch Enrollment` where docstatus = 1 and ifnull(sales_order, '') != '' group by sales_order having n > 1""", as_dict=True)
	out = {"enrolments_checked": len(rows), "ok": ok, "mismatched": len(problems), "problems": problems,
		"active_enrolments_without_fee_order": len(no_order), "of_which_fees_outside_system": sum(1 for x in no_order if x.fees_outside_system),
		"without_order_but_fee_expected": [x for x in no_order if not x.fees_outside_system],
		"student_orders_not_on_page": orphan, "orders_shared_by_two_enrolments": shared,
		"page_totals": {"total": flt(sum(r.total for r in rows), 2), "paid": flt(sum(r.paid for r in rows), 2), "pending": flt(sum(r.pending for r in rows), 2)}}
	if verbose:
		print(frappe.as_json(out))
	return out
