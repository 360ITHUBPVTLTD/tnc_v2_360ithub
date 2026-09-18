# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Server-rendered overview panels: the bird's-eye view on the Student form and
the demo/follow-up summary on the Enquiry form. Pure reads; HTML is escaped."""
import frappe
from frappe import _
from frappe.utils import flt, fmt_money, formatdate, getdate, nowdate
from frappe.utils.html_utils import escape_html as e

REQUIRED_DOCS = ("Photo", "Aadhaar", "ID Proof", "Marksheet")

STYLE = """
<style>
.tnc-ov,.tnc-enq{font-size:13px}
.tnc-head{display:flex;gap:16px;align-items:center;padding:14px 16px;border-radius:10px;background:linear-gradient(135deg,#e8f3ff 0%,#f4f9ff 100%);border:1px solid #cfe3fa}
.tnc-photo{width:64px;height:64px;border-radius:50%;object-fit:cover;background:#dbeafe;display:flex;align-items:center;justify-content:center;font-size:26px;font-weight:600;color:#1d4ed8}
.tnc-stat .v{font-size:18px;font-weight:700;color:#1e3a8a} .tnc-stat .l{color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.04em}
.tnc-rows{margin-top:8px} .tnc-row{display:flex;flex-wrap:wrap;align-items:center;border:1px solid #cfe3fa;border-radius:10px;padding:12px 16px;background:#fff;box-shadow:0 1px 2px rgba(30,64,175,.06);margin-bottom:10px}
.tnc-col{box-sizing:border-box;padding:0 16px} .tnc-col-batch{flex:1.3 1 200px;padding-left:0} .tnc-col-fee{flex:1.2 1 220px} .tnc-col-pay{flex:1.2 1 220px} .tnc-col-act{flex:0 0 170px;padding-right:0}
.tnc-col-fee,.tnc-col-pay,.tnc-col-act{border-left:2px solid #cbd5e1} .tnc-col-act .btn{display:block;text-align:center;margin-bottom:6px;white-space:nowrap} .tnc-col-act .btn:last-child{margin-bottom:0}
.tnc-head>div:nth-child(2){flex:1 1 auto;min-width:0} .tnc-stats{display:flex;flex:0 0 auto;margin-left:auto;flex-wrap:nowrap;align-items:flex-end} .tnc-stat{text-align:right;margin-left:28px;white-space:nowrap}
@media (max-width:1100px){.tnc-head{flex-wrap:wrap} .tnc-stats{flex:1 1 100%;margin-left:0;justify-content:flex-start} .tnc-stat{margin:8px 28px 0 0}}
@media (max-width:700px){.tnc-col{flex:1 1 100%;padding:6px 0;border-left:0}}

.tnc-card{border:1px solid #cfe3fa;border-radius:10px;padding:12px 14px;background:#fff;box-shadow:0 1px 2px rgba(30,64,175,.06)} .tnc-card-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;font-size:14px}
.tnc-kv{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px dashed #cbd5e1} .tnc-kv:last-of-type{border-bottom:0} .tnc-actions{display:flex;gap:6px;margin-top:10px;flex-wrap:wrap}
.tnc-sec{margin-top:18px} .tnc-sec h6,.tnc-enq h6{display:inline-block;margin:0 0 8px;padding:4px 10px;border-radius:999px;background:#dbeafe;color:#1e40af;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em}
.tnc-table{width:100%;border-collapse:separate;border-spacing:0;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;background:#fff}
.tnc-table th{background:#dbeafe;color:#1e3a8a;font-weight:600;padding:8px 10px;border-bottom:1px solid #bfdbfe;white-space:nowrap;text-align:left} .tnc-table th.num{text-align:right}
.tnc-table td{padding:8px 10px;border-bottom:1px solid #cbd5e1;vertical-align:middle} .tnc-table tr:last-child td{border-bottom:0}
.tnc-table .num{text-align:right;font-variant-numeric:tabular-nums}
.tnc-pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:600}
.tnc-pill.green{background:#dcfce7;color:#166534} .tnc-pill.red{background:#fee2e2;color:#991b1b} .tnc-pill.orange{background:#ffedd5;color:#9a3412} .tnc-pill.blue{background:#dbeafe;color:#1e40af} .tnc-pill.yellow{background:#fef9c3;color:#854d0e} .tnc-pill.gray{background:#e5e7eb;color:#374151}
.tnc-two{display:grid;grid-template-columns:1fr 1fr;gap:16px} .tnc-ov ul,.tnc-enq ul{padding-left:0;list-style:none;margin:0} .tnc-ov li{padding:6px 4px;border-bottom:1px solid #cbd5e1} .tnc-ov li:last-child{border-bottom:0}
.tnc-box{border:1px solid #e5e7eb;border-radius:8px;background:#fff;padding:6px 12px;min-height:60px}
.tnc-timeline li{position:relative;padding-left:16px} .tnc-timeline li::before{content:"";position:absolute;left:4px;top:13px;width:7px;height:7px;border-radius:50%;background:#93c5fd}
.tnc-empty{color:#64748b;padding:10px 12px;border:1px dashed #cfe3fa;border-radius:8px;background:#fbfdff}
.progress{background:#e0ecfb} .progress-bar{background:#2563eb}
.tnc-table a,.tnc-ov li a{color:#1d4ed8;font-weight:600;text-decoration:underline;text-decoration-style:dotted;text-underline-offset:3px} 
@media (max-width:760px){.tnc-two{grid-template-columns:1fr} .tnc-stats{margin-left:0}}
</style>"""


def _badge(text, kind):
	return f'<span class="tnc-pill {kind}">{e(text)}</span>'


def _money(v):
	return e(fmt_money(flt(v), currency="INR"))


@frappe.whitelist()
def get_student_overview(student):
	doc = frappe.get_doc("Student", student)
	doc.check_permission("read")
	enrollments = frappe.get_all("Student Batch Enrollment", filters={"student": student, "docstatus": 1},
		fields=["name", "batch", "course_name", "status", "standard_fee", "discount_amount", "demo_fee_adjusted", "net_payable", "gst_applicable", "sales_order", "enrollment_date"], order_by="enrollment_date desc")
	total_fee = paid_total = pending_total = 0
	next_due = None
	cards, rows = [], []
	for en in enrollments:
		so = frappe.db.get_value("Sales Order", en.sales_order, ["grand_total", "advance_paid", "status", "per_billed"], as_dict=True) if en.sales_order else None
		grand = flt(so.grand_total) if so else flt(en.net_payable)
		paid = _paid_against_order(en.sales_order) if en.sales_order else 0
		pending = flt(grand - paid, 2)
		total_fee += grand; paid_total += paid; pending_total += pending
		sched = frappe.get_all("Payment Schedule", filters={"parent": en.sales_order, "parenttype": "Sales Order"},
			fields=["idx", "due_date", "payment_amount", "paid_amount", "outstanding", "description"], order_by="idx") if en.sales_order else []
		for s in sched:
			out = flt(s.outstanding) if s.outstanding is not None else flt(s.payment_amount) - flt(s.paid_amount)
			state = "Paid" if out <= 0.5 else ("Partly paid" if flt(s.paid_amount) > 0.5 else ("Overdue" if getdate(s.due_date) < getdate(nowdate()) else "Due"))
			if state == "Partly paid" and getdate(s.due_date) < getdate(nowdate()):
				state = "Overdue"
			if state != "Paid" and (next_due is None or getdate(s.due_date) < next_due):
				next_due = getdate(s.due_date)
			rows.append((en, s, out, state))
		pct = int(paid / grand * 100) if grand else 0
		kind = {"Active": "green", "On Hold": "red", "Completed": "blue", "Left": "gray"}.get(en.status, "gray")
		cards.append(f"""
		<div class="tnc-row">
		  <div class="tnc-col tnc-col-batch">
		    <div class="tnc-card-head"><b>{e(en.batch)}</b> {_badge(en.status, kind)}</div>
		    <div class="text-muted small">{e(en.course_name or '')}</div>
		    <div class="text-muted small">{_('enrolled')} {e(formatdate(en.enrollment_date))}{' · GST' if en.gst_applicable else ''}</div>
		  </div>
		  <div class="tnc-col tnc-col-fee">
		    <div class="tnc-kv"><span>{_('Fee')}</span><span>{_money(en.standard_fee)}</span></div>
		    {'<div class="tnc-kv"><span>' + _('Discount') + '</span><span>- ' + _money(en.discount_amount) + '</span></div>' if flt(en.discount_amount) else ''}
		    {'<div class="tnc-kv"><span>' + _('Demo fee paid') + '</span><span>- ' + _money(en.demo_fee_adjusted) + '</span></div>' if flt(en.demo_fee_adjusted) else ''}
		    <div class="tnc-kv"><span>{_('Total') + (' (incl. GST)' if en.gst_applicable else '')}</span><b>{_money(grand)}</b></div>
		  </div>
		  <div class="tnc-col tnc-col-pay">
		    <div class="tnc-kv"><span>{_('Paid')}</span><span class="text-success"><b>{_money(paid)}</b></span></div>
		    <div class="tnc-kv"><span>{_('Pending')}</span><span class="{'text-danger' if pending > 0.5 else 'text-success'}"><b>{_money(pending)}</b></span></div>
		    <div class="progress" style="height:8px;margin-top:8px"><div class="progress-bar" style="width:{pct}%"></div></div>
		    <div class="text-muted small" style="margin-top:4px">{pct}% {_('paid')}</div>
		  </div>
		  <div class="tnc-col tnc-col-act">
		    {'<a class="btn btn-sm btn-primary" data-action="receive" data-so="' + e(en.sales_order) + '">' + _('Receive Payment') + '</a>' if en.sales_order and pending > 0.5 else '<span class="tnc-pill green">' + _('Fully paid') + '</span>'}
		    {'<a class="btn btn-sm btn-default" href="/app/sales-order/' + e(en.sales_order) + '">' + _('Sales Order') + '</a>' if en.sales_order else ''}
		    <a class="btn btn-sm btn-default" href="/app/student-batch-enrollment/{e(en.name)}">{_('Enrolment')}</a>
		  </div>
		</div>""")
	# instalments table
	inst_html = ""
	if rows:
		trs = []
		for en, s, out, state in rows:
			kind = {"Paid": "green", "Overdue": "red", "Due": "orange", "Partly paid": "yellow"}[state]
			btn = f'<a class="btn btn-xs btn-primary" data-action="receive" data-so="{e(en.sales_order)}" data-amount="{flt(out)}" data-label="{e(s.description or s.idx)}">{_("Receive")}</a>' if state != "Paid" else ""
			trs.append(f"<tr><td>{e(en.batch)}</td><td>{e(s.description or s.idx)}</td><td>{e(formatdate(s.due_date))}</td><td class='num'>{_money(s.payment_amount)}</td><td class='num'>{_money(s.paid_amount)}</td><td class='num'><b>{_money(out)}</b></td><td>{_badge(state, kind)}</td><td>{btn}</td></tr>")
		inst_html = f"""<table class="tnc-table"><thead><tr><th>{_('Batch')}</th><th>{_('Instalment')}</th><th>{_('Due')}</th><th class='num'>{_('Amount')}</th><th class='num'>{_('Paid')}</th><th class='num'>{_('Pending')}</th><th>{_('Status')}</th><th></th></tr></thead><tbody>{''.join(trs)}</tbody></table>"""
	else:
		inst_html = f"<div class='tnc-empty'>{_('No instalments yet. Enrol the student in a batch.')}</div>"
	# documents checklist
	have = {d.document_type: d for d in doc.documents}
	docs = []
	missing = 0
	for t in REQUIRED_DOCS:
		d = have.get(t)
		if d and d.file:
			mark = "✓" if d.verified else "•"
			docs.append(f"<li class='{'text-success' if d.verified else ''}'>{mark} {e(t)} <a href='{e(d.file)}' target='_blank'>{_('view')}</a>{' · ' + _('verified') if d.verified else ' · ' + _('not verified')}</li>")
		else:
			missing += 1
			docs.append(f"<li class='text-danger'>✗ {e(t)} <span class='text-muted'>{_('missing')}</span></li>")
	for t, d in have.items():
		if t not in REQUIRED_DOCS and d.file:
			docs.append(f"<li>• {e(t)} <a href='{e(d.file)}' target='_blank'>{_('view')}</a></li>")
	# timeline
	events = []
	if doc.enquiry:
		enq = frappe.db.get_value("Student Enquiry", doc.enquiry, ["enquiry_date", "source", "counsellor"], as_dict=True)
		if enq:
			events.append((getdate(enq.enquiry_date), _("Enquiry {0} via {1}").format(e(doc.enquiry), e(enq.source or "")), "/app/student-enquiry/" + doc.enquiry))
		for d in frappe.get_all("Demo Class", filters={"enquiry": doc.enquiry}, fields=["name", "demo_date", "batch", "result"]):
			events.append((getdate(d.demo_date), _("Demo in {0}: {1}").format(e(d.batch), e(d.result)), "/app/demo-class/" + d.name))
	events.append((getdate(doc.creation), _("Admitted as {0}").format(e(doc.name)), None))
	for en in enrollments:
		events.append((getdate(en.enrollment_date), _("Enrolled in {0}").format(e(en.batch)), "/app/student-batch-enrollment/" + en.name))
	for f in frappe.get_all("Student Follow-Up", filters={"reference_type": "Student", "reference_name": student}, fields=["name", "follow_up_date", "followup_type", "notes"]):
		events.append((getdate(f.follow_up_date), _("Follow-up ({0}): {1}").format(e(f.followup_type or ""), e((f.notes or "")[:80])), "/app/student-follow-up/" + f.name))
	# payments are listed on the Payments tab, not repeated here
	events.sort(key=lambda x: x[0], reverse=True)
	tl = "".join(f"<li><span class='text-muted small'>{e(formatdate(d))}</span> &nbsp; {'<a href=' + chr(34) + e(link) + chr(34) + '>' + txt + '</a>' if link else txt}</li>" for d, txt, link in events)
	due_txt = e(formatdate(next_due)) if next_due else "—"
	due_kind = "red" if next_due and next_due < getdate(nowdate()) else ("orange" if next_due else "gray")
	status_kind = {"Enrolment Pending": "orange", "Active": "green", "Attendance Hold": "red", "Completed": "blue", "Discontinued": "gray"}.get(doc.status, "gray")
	photo = f'<img src="{e(doc.student_photo)}" class="tnc-photo">' if doc.student_photo else f'<div class="tnc-photo tnc-photo-empty">{e((doc.student_name or "?")[:1])}</div>'
	html = STYLE + f"""
	<div class="tnc-ov">
	  <div class="tnc-head">{photo}
	    <div><div style="font-size:16px;font-weight:600">{e(doc.student_name)} {_badge(doc.status, status_kind)}</div>
	      <div class="text-muted">{e(doc.mobile or '')}{' · ' + e(doc.email) if doc.email else ''}{' · ' + _('counsellor') + ' ' + e(doc.counsellor) if doc.counsellor else ''}</div>
	      <div class="text-muted small">{(e(doc.course_interested) + ' · ') if doc.course_interested else ''}{len(enrollments)} {_('enrolment(s)')} · {missing} {_('document(s) missing')}</div></div>
	    <div class="tnc-stats">
	      <div class="tnc-stat"><div class="v">{_money(total_fee)}</div><div class="l">{_('Total fee')}</div></div>
	      <div class="tnc-stat"><div class="v text-success">{_money(paid_total)}</div><div class="l">{_('Paid')}</div></div>
	      <div class="tnc-stat"><div class="v {'text-danger' if pending_total > 0.5 else ''}">{_money(pending_total)}</div><div class="l">{_('Pending')}</div></div>
	      <div class="tnc-stat"><div class="v">{_badge(due_txt, due_kind)}</div><div class="l">{_('Next due')}</div></div>
	    </div>
	  </div>
	  <div class="tnc-sec"><h6>{_('Enrolments')}</h6>
	    {'<div class="tnc-rows">' + ''.join(cards) + '</div>' if cards else '<div class="tnc-empty">' + _('Not enrolled in any batch yet.') + '</div>'}
	  </div>
	  <div class="tnc-sec"><h6>{_('Instalments')}</h6>{inst_html}</div>
	  <div class="tnc-two">
	    <div class="tnc-sec"><h6>{_('Documents')}</h6><div class="tnc-box"><ul>{''.join(docs)}</ul></div></div>
	    <div class="tnc-sec"><h6>{_('Timeline')}</h6><div class="tnc-box tnc-timeline"><ul>{tl}</ul></div></div>
	  </div>
	</div>"""
	return {"html": html, "pending": pending_total, "missing_docs": missing, "customer": doc.customer}


def _paid_against_order(sales_order):
	"""Paid = what ERPNext has allocated to the order's Payment Schedule (advances
	received against the order). Receipt invoices are settled by those same advances,
	so they are not added again."""
	rows = frappe.get_all("Payment Schedule", filters={"parent": sales_order, "parenttype": "Sales Order"}, pluck="paid_amount")
	if rows:
		return flt(sum(flt(x) for x in rows), 2)
	return flt(frappe.db.get_value("Sales Order", sales_order, "advance_paid"))


@frappe.whitelist()
def get_enquiry_overview(enquiry):
	doc = frappe.get_doc("Student Enquiry", enquiry)
	doc.check_permission("read")
	demos = frappe.get_all("Demo Class", filters={"enquiry": enquiry}, fields=["name", "demo_date", "from_time", "to_time", "batch", "result", "counsellor_rating", "student_rating", "rated_on", "rating_sent_on", "demo_fee_status", "demo_fee_amount"], order_by="demo_date desc, from_time desc, creation desc")
	fups = frappe.get_all("Student Follow-Up", filters={"reference_type": "Student Enquiry", "reference_name": enquiry},
		fields=["name", "follow_up_date", "followup_type", "notes", "next_follow_up_date", "status", "done_by"], order_by="follow_up_date desc, creation desc")
	kinds = {"Scheduled": "orange", "Attended": "green", "Not Attended": "red", "Cancelled": "gray"}
	def _slot(d):
		if not d.from_time:
			return ""
		return " " + e(str(d.from_time)[:5]) + (" - " + e(str(d.to_time)[:5]) if d.to_time else "")
	def _stars(v):
		n = int(round((v or 0) * 5))
		return ("<span style='color:#f5b301'>" + "★" * n + "</span><span style='color:#d4d7dd'>" + "★" * (5 - n) + "</span>") if n else "<span class='text-muted'>–</span>"
	def _rating(d):
		if d.result != "Attended":
			return ""
		stu = _stars(d.student_rating) if d.rated_on else ("<span class='text-muted small'>" + _("link sent") + "</span>" if d.rating_sent_on else "<span class='text-muted small'>" + _("not asked") + "</span>")
		return f"<div class='small'>{_('Counsellor')}: {_stars(d.counsellor_rating)}</div><div class='small'>{_('Student')}: {stu}</div>"
	fee_kinds = {"Paid": "green", "Adjusted": "blue", "Refunded": "gray"}
	def _fee(d):
		if not d.demo_fee_status or d.demo_fee_status == "Not Collected":
			return "<span class='text-muted small'>" + _("not collected") + "</span>"
		return _badge(f"{d.demo_fee_status} {_money(d.demo_fee_amount)}", fee_kinds.get(d.demo_fee_status, "gray"))
	drows = "".join(f"<tr><td><a href='/app/demo-class/{e(d.name)}'>{e(formatdate(d.demo_date))}{_slot(d)}</a></td><td>{e(d.batch)}</td><td>{_badge(d.result, kinds.get(d.result, 'gray'))}</td><td>{_fee(d)}</td><td>{_rating(d)}</td></tr>" for d in demos)
	frows = "".join(f"<tr><td><a href='/app/student-follow-up/{e(f.name)}'>{e(formatdate(f.follow_up_date))}</a></td><td>{e(f.followup_type or '')}</td><td>{e((f.notes or '')[:90])}</td><td>{e(formatdate(f.next_follow_up_date)) if f.next_follow_up_date else ''}</td><td>{_badge(f.status, 'green' if f.status == 'Closed' else 'orange')}</td></tr>" for f in fups)
	def table(head, rows):
		return '<table class="tnc-table"><thead><tr>' + ''.join(f'<th>{h}</th>' for h in head) + '</tr></thead><tbody>' + rows + '</tbody></table>'
	html = STYLE + f"""<div class="tnc-enq"><div class="tnc-two">
	<div><h6>{_('Demo classes')} ({len(demos)})</h6>
	{table([_('When'), _('Batch'), _('Result'), _('Demo fee'), _('Rating')], drows) if demos else '<div class="tnc-empty">' + _('No demo yet.') + '</div>'}</div>
	<div><h6>{_('Follow-ups')} ({len(fups)})</h6>
	{table([_('Date'), _('Type'), _('Notes'), _('Next'), ''], frows) if fups else '<div class="tnc-empty">' + _('No follow-up yet.') + '</div>'}</div></div></div>"""
	return {"html": html, "demos": len(demos), "attended": sum(1 for d in demos if d.result == "Attended")}

