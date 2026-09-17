# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Enquiry Funnel (SOW 1: counsellor-wise enquiry and conversion report).
One row per counsellor / source / course / lost reason, for enquiries whose
enquiry_date falls in the period: how many came in, got a demo, attended,
converted, were lost, are still open, plus conversion rate and days to admission."""
import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate

GROUPS = {"Counsellor": "counsellor", "Source": "source", "Course": "course_interested", "Lost Reason": "lost_reason"}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	group_field = GROUPS.get(filters.get("group_by") or "Counsellor", "counsellor")
	conds, vals = ["1=1"], {}
	if filters.get("from_date"):
		conds.append("e.enquiry_date >= %(from_date)s"); vals["from_date"] = filters.from_date
	if filters.get("to_date"):
		conds.append("e.enquiry_date <= %(to_date)s"); vals["to_date"] = filters.to_date
	for f in ("counsellor", "source", "course_interested"):
		if filters.get(f):
			conds.append(f"e.{f} = %({f})s"); vals[f] = filters.get(f)
	where = " and ".join(conds)
	rows = frappe.db.sql(f"""
		select e.name, e.{group_field} as grp, e.status, e.enquiry_date, e.lost_reason, e.converted_on,
			(select count(*) from `tabDemo Class` d where d.enquiry = e.name) as demos,
			(select count(*) from `tabDemo Class` d where d.enquiry = e.name and d.result = 'Attended') as attended,
			(select min(s.creation) from tabStudent s where s.enquiry = e.name) as admitted_on,
			(select ifnull(sum(d2.demo_fee_amount), 0) from `tabDemo Class` d2 where d2.enquiry = e.name and d2.demo_fee_status in ('Paid', 'Adjusted')) as demo_fee
		from `tabStudent Enquiry` e where {where}""", vals, as_dict=True)

	agg = {}
	for r in rows:
		key = r.grp or (_("Not lost") if group_field == "lost_reason" else (_("No counsellor assigned") if group_field == "counsellor" else _("Not set")))
		a = agg.setdefault(key, {"grp": key, "enquiries": 0, "with_demo": 0, "demos": 0, "attended": 0, "converted": 0, "lost": 0, "open": 0, "days": [], "demo_fee": 0})
		a["enquiries"] += 1
		a["demo_fee"] += flt(r.demo_fee)
		a["demos"] += r.demos or 0
		if r.demos:
			a["with_demo"] += 1
		if r.attended:
			a["attended"] += 1
		if r.status == "Converted":
			a["converted"] += 1
			done_on = r.converted_on or r.admitted_on
			if done_on and r.enquiry_date and getdate(done_on) >= getdate(r.enquiry_date):
				a["days"].append(date_diff(getdate(done_on), getdate(r.enquiry_date)))
		elif r.status == "Lost":
			a["lost"] += 1
		else:
			a["open"] += 1

	label = filters.get("group_by") or "Counsellor"
	opts = {"Counsellor": "User", "Course": "Course"}.get(label)
	data = []
	for a in sorted(agg.values(), key=lambda x: (-x["enquiries"], str(x["grp"]))):
		n = a["enquiries"]
		data.append({
			"grp": a["grp"], "grp_doctype": opts if (opts and frappe.db.exists(opts, a["grp"])) else None, "enquiries": n, "with_demo": a["with_demo"], "demos": a["demos"], "attended": a["attended"],
			"converted": a["converted"], "lost": a["lost"], "open": a["open"], "demo_fee": flt(a["demo_fee"], 2),
			"conversion_pct": flt(a["converted"] / n * 100, 1) if n else 0,
			"demo_attend_pct": flt(a["attended"] / a["with_demo"] * 100, 1) if a["with_demo"] else 0,
			"avg_days": flt(sum(a["days"]) / len(a["days"]), 1) if a["days"] else None,
		})

	columns = [
		{"fieldname": "grp", "label": _(label), "fieldtype": "Dynamic Link" if opts else "Data", "options": "grp_doctype", "width": 260},
		{"fieldname": "enquiries", "label": _("Total Enquiries"), "fieldtype": "Int", "width": 120},
		{"fieldname": "with_demo", "label": _("Scheduled Demo"), "fieldtype": "Int", "width": 160},
		{"fieldname": "attended", "label": _("Students Attended Demo"), "fieldtype": "Int", "width": 170},
		{"fieldname": "demo_attend_pct", "label": _("Demo Attendance %"), "fieldtype": "Percent", "precision": 1, "width": 160},
		{"fieldname": "demo_fee", "label": _("Demo Fee Collected"), "fieldtype": "Currency", "width": 150},
		{"fieldname": "converted", "label": _("Admissions Taken"), "fieldtype": "Int", "width": 140},
		{"fieldname": "conversion_pct", "label": _("Enquiry to Admission %"), "fieldtype": "Percent", "precision": 1, "width": 170},
		{"fieldname": "lost", "label": _("Enquiries Lost"), "fieldtype": "Int", "width": 120},
		{"fieldname": "open", "label": _("Enquiries Still Open"), "fieldtype": "Int", "width": 150},
		{"fieldname": "avg_days", "label": _("Avg Days: Enquiry to Admission"), "fieldtype": "Float", "precision": 1, "width": 200},
	]
	chart = {
		"data": {"labels": [d["grp"] for d in data], "datasets": [
			{"name": _("Total Enquiries"), "values": [d["enquiries"] for d in data]},
			{"name": _("Students Attended Demo"), "values": [d["attended"] for d in data]},
			{"name": _("Admissions Taken"), "values": [d["converted"] for d in data]},
			{"name": _("Enquiries Lost"), "values": [d["lost"] for d in data]}]},
		"type": "bar", "colors": ["#93c5fd", "#fdba74", "#86efac", "#fca5a5"],
	}
	total_enq = sum(d["enquiries"] for d in data)
	summary = [
		{"label": _("Total Enquiries"), "value": total_enq, "datatype": "Int"},
		{"label": _("Admissions Taken"), "value": sum(d["converted"] for d in data), "datatype": "Int", "indicator": "Green"},
		{"label": _("Enquiry to Admission %"), "value": flt(sum(d["converted"] for d in data) / total_enq * 100, 1) if total_enq else 0, "datatype": "Percent", "indicator": "Blue"},
		{"label": _("Enquiries Lost"), "value": sum(d["lost"] for d in data), "datatype": "Int", "indicator": "Red"},
		{"label": _("Still Open"), "value": sum(d["open"] for d in data), "datatype": "Int", "indicator": "Orange"},
	]
	return columns, data, None, chart, summary
