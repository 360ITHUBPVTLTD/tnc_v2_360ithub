# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Receive Payment: one call turns money received against an enrolment Sales
Order into the two standard documents ERPNext needs, and nothing else.

1. Payment Entry (Receive) against the Sales Order. ERPNext allocates it to the
   order's Payment Schedule earliest-due first, so a part payment leaves that
   instalment partly paid with the exact balance.
2. Sales Invoice for exactly the amount received, billed from the Sales Order
   in proportion (qty = amount / grand total), GST computed at receipt as the
   design decided; the Payment Entry is allocated to it so the invoice is born
   fully paid. This is the student's receipt.
"""
import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

BANK_MODES = ("UPI", "Bank Transfer", "Card", "Cheque")


def pending_on_order(so):
	paid = flt(sum(flt(r.paid_amount) for r in so.payment_schedule)) if so.payment_schedule else flt(so.advance_paid)
	return flt(flt(so.grand_total) - paid, 2), paid


@frappe.whitelist()
def get_pending(sales_order):
	so = frappe.get_doc("Sales Order", sales_order)
	so.check_permission("read")
	pending, paid = pending_on_order(so)
	return {"pending": pending, "paid": paid, "grand_total": flt(so.grand_total)}


@frappe.whitelist()
def receive_payment(sales_order, amount, mode_of_payment, reference_no=None, reference_date=None, posting_date=None, remarks=None):
	so = frappe.get_doc("Sales Order", sales_order)
	so.check_permission("write")
	if so.docstatus != 1:
		frappe.throw(_("Sales Order {0} is not submitted").format(sales_order))
	amount = flt(amount, 2)
	if amount <= 0:
		frappe.throw(_("Amount must be more than zero"))
	pending, _paid = pending_on_order(so)
	if amount > pending + 0.5:
		frappe.throw(_("Amount {0} is more than the pending {1} on {2}").format(frappe.format_value(amount, {"fieldtype": "Currency"}), frappe.format_value(pending, {"fieldtype": "Currency"}), sales_order))
	if mode_of_payment in BANK_MODES and not reference_no:
		frappe.throw(_("Reference number is required for {0}").format(mode_of_payment))
	posting_date = posting_date or nowdate()

	pe = _make_payment_entry(so, amount, mode_of_payment, reference_no, reference_date or posting_date, posting_date, remarks)
	si = _make_receipt_invoice(so, amount, pe, posting_date, remarks)
	so.reload()
	from tnc_v2_360ithub.admissions.followups import close_paid_followups
	close_paid_followups(so.name)
	pending_after, paid_after = pending_on_order(so)
	return {"payment_entry": pe.name, "sales_invoice": si.name, "paid": paid_after, "pending": pending_after,
		"student": so.get("student"), "enrollment": so.get("student_batch_enrollment")}


def _make_payment_entry(so, amount, mode, reference_no, reference_date, posting_date, remarks):
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	pe = get_payment_entry("Sales Order", so.name, party_amount=amount)
	pe.mode_of_payment = mode
	account = frappe.db.get_value("Mode of Payment Account", {"parent": mode, "company": so.company}, "default_account")
	if not account:
		frappe.throw(_("Mode of Payment {0} has no account for {1}. Set it in Mode of Payment.").format(mode, so.company))
	pe.paid_to = account
	pe.paid_amount = amount
	pe.received_amount = amount
	pe.posting_date = posting_date
	pe.reference_no = reference_no or f"{mode} {posting_date}"
	pe.reference_date = reference_date
	pe.remarks = remarks or _("Fee received against {0}").format(so.name)
	pe.student = so.get("student")
	# one reference row per instalment, earliest due first, so ERPNext marks the schedule rows paid
	pe.set("references", [])
	remaining = flt(amount)
	for row in sorted(so.payment_schedule, key=lambda x: (getdate(x.due_date), x.idx)):
		out = flt(row.outstanding) if row.outstanding is not None else flt(row.payment_amount) - flt(row.paid_amount)
		if out <= 0.005 or remaining <= 0.005:
			continue
		alloc = flt(min(out, remaining), 2)
		pe.append("references", {"reference_doctype": "Sales Order", "reference_name": so.name, "due_date": row.due_date, "payment_term": row.payment_term,
			"total_amount": flt(so.grand_total), "outstanding_amount": out, "allocated_amount": alloc})
		remaining = flt(remaining - alloc, 2)
	if remaining > 0.5:
		frappe.throw(_("Amount exceeds the pending instalments"))
	pe.flags.ignore_permissions = True
	pe.setup_party_account_field()
	pe.set_missing_values()
	pe.insert()
	pe.submit()
	return pe


def _make_receipt_invoice(so, amount, pe, posting_date, remarks):
	"""Receipt = Sales Invoice for the amount received, billed against the order's
	line in proportion. Built directly (not via make_sales_invoice, which stops once
	the line's quantity is billed) so several receipts can share one order line."""
	factor = flt(amount) / flt(so.grand_total) if flt(so.grand_total) else 1
	si = frappe.new_doc("Sales Invoice")
	si.update({
		"customer": so.customer, "company": so.company, "posting_date": posting_date, "set_posting_time": 1, "due_date": posting_date,
		"currency": so.currency, "selling_price_list": so.selling_price_list, "price_list_currency": so.price_list_currency,
		"plc_conversion_rate": so.plc_conversion_rate, "conversion_rate": so.conversion_rate, "ignore_pricing_rule": 1,
		"taxes_and_charges": so.taxes_and_charges, "tax_category": so.tax_category, "place_of_supply": so.get("place_of_supply"),
		"customer_address": so.customer_address, "shipping_address_name": so.shipping_address_name, "contact_person": so.contact_person,
		"cost_center": so.get("cost_center"), "student": so.get("student"),
		"remarks": _("Towards {0}").format(", ".join(r.payment_term for r in pe.references if r.payment_term) or so.name) + (f" — {remarks}" if remarks else ""),
		"update_stock": 0, "allocate_advances_automatically": 0,
	})
	for so_item in so.items:
		si.append("items", {
			"item_code": so_item.item_code, "item_name": so_item.item_name, "description": _("{0} — fee receipt for {1}").format(so_item.item_name, frappe.format_value(amount, {"fieldtype": "Currency"})),
			"qty": flt(so_item.qty), "uom": so_item.uom, "stock_uom": so_item.stock_uom, "conversion_factor": so_item.conversion_factor or 1,
			"rate": flt(flt(so_item.rate) * factor, 2), "price_list_rate": flt(flt(so_item.rate) * factor, 2),
			"income_account": frappe.db.get_value("Item Default", {"parent": so_item.item_code, "company": so.company}, "income_account") or frappe.get_cached_value("Company", so.company, "default_income_account"),
			"cost_center": so_item.cost_center or frappe.get_cached_value("Company", so.company, "cost_center"),
			"sales_order": so.name, "so_detail": so_item.name, "delivery_date": so_item.delivery_date,
			"gst_hsn_code": so_item.get("gst_hsn_code"), "item_tax_template": so_item.get("item_tax_template"),
		})
	for t in so.taxes:
		si.append("taxes", {"charge_type": t.charge_type, "account_head": t.account_head, "description": t.description, "rate": t.rate,
			"cost_center": t.cost_center, "included_in_print_rate": t.included_in_print_rate, "row_id": t.row_id})
	if flt(so.discount_amount):
		si.apply_discount_on = so.apply_discount_on or "Net Total"
		si.discount_amount = flt(flt(so.discount_amount) * factor, 2)
	si.flags.ignore_permissions = True
	si.run_method("set_missing_values")
	si.run_method("calculate_taxes_and_totals")
	# settle the receipt against the payment, one advance row per payment reference row
	si.set("advances", [])
	remaining = flt(si.grand_total)
	for ref in pe.references:
		if remaining <= 0.005:
			break
		alloc = flt(min(remaining, flt(ref.allocated_amount)), 2)
		si.append("advances", {"reference_type": "Payment Entry", "reference_name": pe.name, "reference_row": ref.name,
			"advance_amount": flt(ref.allocated_amount), "allocated_amount": alloc, "remarks": pe.remarks})
		remaining = flt(remaining - alloc, 2)
	si.insert()
	si.submit()
	return si


@frappe.whitelist()
def get_student_payments(student):
	"""Receipts (Sales Invoices) and Payments (Payment Entries) of a student's Customer."""
	from tnc_v2_360ithub.admissions.api import STYLE, _badge, _money
	from frappe.utils import formatdate
	from frappe.utils.html_utils import escape_html as e

	doc = frappe.get_doc("Student", student)
	doc.check_permission("read")
	if not doc.customer:
		return {"html": STYLE + f"<div class='tnc-empty'>{_('No customer linked yet.')}</div>"}
	invoices = frappe.get_all("Sales Invoice", filters={"customer": doc.customer, "docstatus": ["in", [1, 2]]},
		fields=["name", "posting_date", "grand_total", "total_taxes_and_charges", "outstanding_amount", "status", "docstatus"], order_by="posting_date desc, creation desc")
	payments = frappe.get_all("Payment Entry", filters={"party_type": "Customer", "party": doc.customer, "docstatus": ["in", [1, 2]]},
		fields=["name", "posting_date", "mode_of_payment", "reference_no", "paid_amount", "docstatus"], order_by="posting_date desc, creation desc")
	orders = {}
	for p in payments:
		refs = frappe.get_all("Payment Entry Reference", filters={"parent": p.name}, fields=["reference_doctype", "reference_name"])
		orders[p.name] = ", ".join(r.reference_name for r in refs if r.reference_doctype in ("Sales Order", "Sales Invoice"))
	kinds = {"Paid": "green", "Unpaid": "orange", "Overdue": "red", "Cancelled": "gray", "Return": "gray", "Credit Note Issued": "gray", "Partly Paid": "yellow"}
	irows = "".join(f"<tr><td><a href='/app/sales-invoice/{e(i.name)}'>{e(i.name)}</a></td><td>{e(formatdate(i.posting_date))}</td><td class='num'>{_money(i.grand_total)}</td><td class='num'>{_money(i.total_taxes_and_charges)}</td>"
		f"<td>{_badge('Cancelled' if i.docstatus == 2 else i.status, kinds.get('Cancelled' if i.docstatus == 2 else i.status, 'gray'))}</td>"
		f"<td><a class='btn btn-xs btn-default' href='/app/print/Sales%20Invoice/{e(i.name)}' target='_blank'>{_('Print')}</a></td></tr>" for i in invoices)
	prows = "".join(f"<tr><td><a href='/app/payment-entry/{e(p.name)}'>{e(p.name)}</a></td><td>{e(formatdate(p.posting_date))}</td><td>{e(p.mode_of_payment or '')}</td><td>{e(p.reference_no or '')}</td><td class='num'><b>{_money(p.paid_amount)}</b></td><td>{e(orders.get(p.name, ''))}</td>"
		f"<td>{_badge('Cancelled' if p.docstatus == 2 else 'Received', 'gray' if p.docstatus == 2 else 'green')}</td></tr>" for p in payments)
	total_received = sum(flt(p.paid_amount) for p in payments if p.docstatus == 1)
	def table(head, rows):
		return '<table class="tnc-table"><thead><tr>' + ''.join(f'<th class="{"num" if h in (_("Amount"), _("GST")) else ""}">{h}</th>' for h in head) + '</tr></thead><tbody>' + rows + '</tbody></table>'
	html = STYLE + f"""<div class="tnc-ov">
	<div class="tnc-head"><div><div style="font-size:15px;font-weight:600">{_('Payments of')} {e(doc.student_name)}</div><div class="text-muted">{len(payments)} {_('payment(s)')} · {len(invoices)} {_('receipt(s)')}</div></div>
	  <div class="tnc-stats"><div class="tnc-stat"><div class="v text-success">{_money(total_received)}</div><div class="l">{_('Total received')}</div></div></div></div>
	<div class="tnc-sec"><h6>{_('Payments')}</h6>{table([_('Payment'), _('Date'), _('Mode'), _('Reference'), _('Amount'), _('Against'), ''], prows) if payments else '<div class="tnc-empty">' + _('No payment received yet.') + '</div>'}</div>
	<div class="tnc-sec"><h6>{_('Receipts (Sales Invoices)')}</h6>{table([_('Receipt'), _('Date'), _('Amount'), _('GST'), _('Status'), ''], irows) if invoices else '<div class="tnc-empty">' + _('No receipt yet.') + '</div>'}</div>
	</div>"""
	return {"html": html, "total_received": total_received}
