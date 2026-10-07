# Copyright (c) 2026, 360ITHub and contributors
"""Teacher-facing documents: the payment receipt and the weekly statement, as PDFs on WhatsApp.

The letterhead (logo, address, phone, email, GSTIN) is read from the Company record and its
address, so the institute changes it there, never in code. The two print formats call the
`tnc_*` functions below through the Jinja hooks.

What a teacher sees is kept simple: penalties are shown net (after any waiver or refund) and
no line says "waived" or "refunded"; the totals still match the settlement exactly.
"""
import base64
import json
import mimetypes

import frappe
from frappe import _
from frappe.utils import flt, get_url, getdate

RECEIPT_FORMAT = "Teacher Payment Receipt"
STATEMENT_FORMAT = "Teacher Weekly Statement"


# ---------- letterhead ----------

def _data_uri(file_url):
	"""Embed an attached image so the PDF never needs to fetch it (private files included)."""
	try:
		f = frappe.get_doc("File", {"file_url": file_url})
		mime = mimetypes.guess_type(f.file_name or file_url)[0] or "image/png"
		return f"data:{mime};base64,{base64.b64encode(f.get_content()).decode()}"
	except Exception:
		return None


def tnc_letterhead(company=None):
	company = company or frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
	c = frappe.get_cached_doc("Company", company)
	addr = frappe.get_all("Address", filters=[["Dynamic Link", "link_doctype", "=", "Company"], ["Dynamic Link", "link_name", "=", company], ["disabled", "=", 0]],
		fields=["address_line1", "address_line2", "city", "state", "pincode", "phone", "email_id", "gstin"],
		order_by="is_your_company_address desc, is_primary_address desc", limit=1)
	a = addr[0] if addr else frappe._dict()
	place = ", ".join(x for x in [a.get("address_line1"), a.get("address_line2"), a.get("city"),
		" - ".join(x for x in [a.get("state"), a.get("pincode")] if x)] if x)
	return frappe._dict(
		name=frappe.db.get_single_value("TNC Settings", "document_institute_name") or c.company_name,
		logo=_data_uri(c.company_logo) if c.get("company_logo") else None,
		address=place,
		phone=c.get("phone_no") or a.get("phone"),
		email=c.get("email") or a.get("email_id"),
		gstin=c.get("tax_id") or a.get("gstin"),
		website=c.get("website"),
	)


# ---------- weekly statement ----------

def tnc_statement_view(doc):
	"""Teacher-facing figures and lines of a Teacher Settlement.

	-> {summary: [(label, amount, sign)], lines: [{date, details, ref, amount}], net_penalties}"""
	if isinstance(doc, str):
		doc = frappe.get_doc("Teacher Settlement", doc)
	adjust = {}  # penalty -> waived/refunded this week
	for l in doc.lines:
		if l.line_type in ("Waiver", "Refund"):
			adjust[l.reference_name] = adjust.get(l.reference_name, 0) + flt(l.amount)
	lines = []
	for l in doc.lines:
		if l.line_type == "Timesheet":
			act = frappe.db.get_value("Activities", {"parent": l.reference_name, "parenttype": "Teachers Timesheet"},
				["activity_name", "qty", "uom", "subject", "chapter"], as_dict=True) or {}
			bits = [act.get("activity_name") or _("Class")]
			if act.get("qty"):
				bits.append(f"{flt(act.qty):g} {act.get('uom') or ''}".strip())
			if act.get("subject"):
				bits.append(" · ".join(x for x in [act.subject, act.get("chapter")] if x))
			lines.append({"date": l.line_date, "details": " — ".join(bits), "ref": l.reference_name, "amount": flt(l.amount)})
		elif l.line_type == "Penalty":
			net = flt(l.amount) + adjust.pop(l.reference_name, 0)  # amount is negative
			if net < -0.005:
				lines.append({"date": l.line_date, "details": _("Penalty: {0}").format(l.description or ""), "ref": l.reference_name, "amount": net})
		elif l.line_type in ("Waiver", "Refund"):
			continue  # folded into the penalty above, or shown once below as an adjustment
		elif l.line_type == "Payment":
			lines.append({"date": l.line_date, "details": _("Paid to you"), "ref": l.reference_name, "amount": flt(l.amount)})
	for penalty, amt in adjust.items():  # waiver/refund of a penalty from an earlier week
		if amt > 0.005:
			ptype = frappe.db.get_value("Teacher Penalty", penalty, "penalty_type") or ""
			lines.append({"date": None, "details": _("Penalty adjusted: {0}").format(ptype), "ref": penalty, "amount": amt})
	net_pen = flt(doc.penalties) - flt(doc.adjustments) - flt(doc.refunds)
	summary = [(_("Balance before this week"), flt(doc.opening_balance), "")]
	summary.append((_("Classes approved this week"), flt(doc.approved_payable), "+"))
	if net_pen >= 0:
		summary.append((_("Penalties"), net_pen, "-"))
	else:
		summary.append((_("Penalty adjusted"), -net_pen, "+"))
	summary.append((_("Paid to you"), flt(doc.payments), "-"))
	summary.append((_("Your balance now"), flt(doc.closing_balance), "="))
	return frappe._dict(summary=summary, lines=lines, net_penalties=net_pen)


def statement_text(doc):
	"""WhatsApp caption: the same simple plus/minus list as the PDF."""
	inr = lambda v: "₹{:,.0f}".format(flt(v))
	d = lambda v: frappe.format_value(v, {"fieldtype": "Date"})
	v = tnc_statement_view(doc)
	rows = []
	for label, amount, sign in v.summary:
		rows.append(f"{sign + ' ' if sign else ''}{label}: {inr(amount)}")
	return (_("Team Nursing Classes, weekly payment summary {0} to {1}").format(d(doc.week_start), d(doc.week_end)) + "\n"
		+ (doc.teacher_name or doc.teacher).strip() + "\n\n" + "\n".join(rows) + "\n\n" + _("Questions? Please contact the office."))


# ---------- payment receipt ----------

def teacher_for_payment(pe):
	"""The Teacher a Payment Entry pays (its supplier is the teacher's supplier), or None."""
	if pe.party_type != "Supplier" or pe.payment_type != "Pay":
		return None
	return frappe.db.get_value("Teacher", {"supplier_id": pe.party}, "name")


def tnc_payment_view(doc):
	"""Teacher-facing figures of a teacher Payment Entry: invoices settled, penalties deducted, net paid."""
	if isinstance(doc, str):
		doc = frappe.get_doc("Payment Entry", doc)
	invoices = []
	for r in doc.references:
		if r.reference_doctype != "Purchase Invoice":
			continue
		pi = frappe.db.get_value("Purchase Invoice", r.reference_name, ["posting_date", "custom_period_from", "custom_period_to", "grand_total"], as_dict=True) or {}
		period = " to ".join(frappe.format_value(x, {"fieldtype": "Date"}) for x in [pi.get("custom_period_from"), pi.get("custom_period_to")] if x)
		invoices.append({"name": r.reference_name, "date": pi.get("posting_date"), "period": period, "amount": flt(r.allocated_amount)})
	penalties = []
	for x in json.loads(doc.get("custom_penalty_allocations") or "[]"):
		p = frappe.db.get_value("Teacher Penalty", x.get("penalty"), ["penalty_type", "penalty_date"], as_dict=True) or {}
		penalties.append({"name": x.get("penalty"), "type": p.get("penalty_type"), "date": p.get("penalty_date"), "amount": flt(x.get("amount"))})
	gross = sum(i["amount"] for i in invoices) or flt(doc.paid_amount) + flt(doc.get("custom_penalty_deduction"))
	teacher = teacher_for_payment(doc)
	t = frappe.db.get_value("Teacher", teacher, ["full_name", "mobile_no"], as_dict=True) if teacher else {}
	return frappe._dict(teacher=teacher, teacher_name=(t or {}).get("full_name") or doc.party_name, mobile=(t or {}).get("mobile_no"),
		invoices=invoices, penalties=penalties, gross=gross, deducted=flt(doc.get("custom_penalty_deduction")), net=flt(doc.paid_amount))


def receipt_text(doc):
	v = tnc_payment_view(doc)
	inr = lambda x: "₹{:,.0f}".format(flt(x))
	lines = [_("Team Nursing Classes, payment receipt"), (v.teacher_name or "").strip(), "",
		_("Amount for classes: {0}").format(inr(v.gross))]
	if v.deducted:
		lines.append(_("Penalty deducted: {0}").format(inr(v.deducted)))
	lines += [_("Paid to you: {0} on {1}").format(inr(v.net), frappe.format_value(doc.posting_date, {"fieldtype": "Date"})), "",
		_("The receipt is attached. Questions? Please contact the office.")]
	return "\n".join(lines)


# ---------- PDF and sending ----------

def public_pdf(doctype, name, print_format):
	"""Render the print format and store it as a public file with an unguessable name; the
	WhatsApp provider fetches the file from this link."""
	pdf = frappe.get_print(doctype, name, print_format=print_format, as_pdf=True, no_letterhead=1)
	fname = f"{frappe.scrub(print_format)}-{frappe.scrub(name)}-{frappe.generate_hash(length=12)}.pdf"
	f = frappe.get_doc({"doctype": "File", "file_name": fname, "is_private": 0, "content": pdf,
		"attached_to_doctype": doctype, "attached_to_name": name}).insert(ignore_permissions=True)
	return get_url(f.file_url)


def send_document(mobile, caption, doctype, name, print_format):
	"""PDF with the caption; if the PDF cannot be made, the caption alone still goes."""
	from tnc_v2_360ithub import notifications
	try:
		link = public_pdf(doctype, name, print_format)
	except Exception:
		frappe.log_error(title=f"{print_format} PDF failed", message=frappe.get_traceback())
		link = None
	if link:
		return notifications.send_whatsapp_file_to_mobile(mobile, caption, link, ref_doctype=doctype, ref_name=name)
	return notifications.send_whatsapp_to_mobile(mobile, caption, ref_doctype=doctype, ref_name=name)


def on_payment_entry_submit(doc, method=None):
	"""Payment to a teacher: queue the receipt for WhatsApp when the setting is on."""
	if not frappe.db.get_single_value("TNC Settings", "send_payment_receipt"):
		return
	if teacher_for_payment(doc):
		frappe.enqueue("tnc_v2_360ithub.teachers.teacher_documents.send_payment_receipt", queue="short", enqueue_after_commit=True, name=doc.name)


def send_payment_receipt(name):
	doc = frappe.get_doc("Payment Entry", name)
	v = tnc_payment_view(doc)
	if not v.mobile:
		return {"status": False, "msg": "No mobile number on the Teacher record"}
	return send_document(v.mobile, receipt_text(doc), "Payment Entry", name, RECEIPT_FORMAT)


@frappe.whitelist()
def resend_payment_receipt(name):
	"""Desk button on a teacher payment."""
	if not ({"System Manager", "TNC Super Admin", "TNC Manager"} & set(frappe.get_roles())):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	doc = frappe.get_doc("Payment Entry", name)
	if doc.docstatus != 1 or not teacher_for_payment(doc):
		frappe.throw(_("Only a submitted payment to a teacher has a receipt."))
	r = send_payment_receipt(name)
	ok = bool(r.get("status")) if isinstance(r, dict) else bool(r)
	return {"status": "Sent" if ok else "Failed", "message": (r or {}).get("msg") if isinstance(r, dict) else None}
