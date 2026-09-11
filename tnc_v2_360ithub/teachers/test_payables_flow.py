# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Verification script for teacher payables (parity checklist rows B8, B9, B10):
approved unpaid timesheets -> Purchase Invoice -> Payment Entry -> cancel both.
	bench --site tnc-v2.local execute tnc_v2_360ithub.teachers.test_payables_flow.run_tests
Unlike the other flow scripts this one cannot roll back: the ported v1 code
commits inside create_invoice_from_timesheets. It therefore cancels and deletes
every document it created and leaves the chosen timesheets as it found them
(Approved, Unpaid, no invoice). Needs the accounts from
setup_helpers.ensure_teacher_payable_accounts.
"""
import traceback

import frappe
from frappe.utils import flt, today

from tnc_v2_360ithub.teachers.doctype.teacher.teacher import create_invoice_from_timesheets


def _ts(names):
	return frappe.get_all("Teachers Timesheet", filters={"name": ["in", names]},
		fields=["name", "status", "payment_status", "purchase_invoice_id"])


def _pick_teacher():
	rows = frappe.db.sql("""
		select ts.teacher_id, count(*) n
		from `tabTeachers Timesheet` ts join tabTeacher t on t.name = ts.teacher_id
		where ts.status = 'Approved' and ts.payment_status = 'Unpaid'
		  and ifnull(ts.purchase_invoice_id, '') = '' and ts.grand_total > 0
		group by ts.teacher_id having n between 1 and 6 order by n limit 1""")
	assert rows, "no teacher with approved unpaid timesheets"
	return rows[0][0]


def run_tests():
	created = {"pi": None, "pe": None}
	try:
		teacher = _pick_teacher()
		names = frappe.get_all("Teachers Timesheet", pluck="name", filters={
			"teacher_id": teacher, "status": "Approved", "payment_status": "Unpaid",
			"purchase_invoice_id": ["in", ["", None]], "grand_total": [">", 0]})
		expected_total = sum(flt(x) for x in frappe.get_all("Teachers Timesheet",
			filters={"name": ["in", names]}, pluck="grand_total"))
		print(f"teacher {teacher}: {len(names)} approved unpaid timesheets, total {expected_total}")

		# B8: create the Purchase Invoice
		pi_name = create_invoice_from_timesheets(teacher, names, today(), today())
		created["pi"] = pi_name
		pi = frappe.get_doc("Purchase Invoice", pi_name)
		assert pi.docstatus == 1, "PI not submitted"
		assert pi.supplier == frappe.db.get_value("Teacher", teacher, "supplier_id")
		assert abs(flt(pi.grand_total) - expected_total) < 0.01, f"PI total {pi.grand_total} != {expected_total}"
		assert pi.credit_to == "TNC Teachers Salary Paid A/c - IND"
		for r in _ts(names):
			assert r.purchase_invoice_id == pi_name and r.payment_status == "Unpaid", r
		print(f"  B8 ok: {pi_name}, {len(pi.items)} lines, grand_total {pi.grand_total}, timesheets linked and Unpaid")

		# B9: pay it in full
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
		pe = get_payment_entry("Purchase Invoice", pi_name)
		pe.paid_from = "BOI TNC A/c - Bank of india - IND"
		pe.reference_no = "parity-check"
		pe.reference_date = today()
		pe.insert(ignore_permissions=True)
		pe.submit()
		created["pe"] = pe.name
		for r in _ts(names):
			assert r.payment_status == "Paid", r
		print(f"  B9 ok: {pe.name} submitted, timesheets Paid")

		# B9 reverse: cancelling the payment returns them to Unpaid
		pe.reload(); pe.cancel()
		for r in _ts(names):
			assert r.payment_status == "Unpaid", r
		print("  B9 cancel ok: timesheets back to Unpaid")

		# B10: cancelling the invoice unlinks them
		pi.reload(); pi.cancel()
		for r in _ts(names):
			assert not r.purchase_invoice_id and r.payment_status == "Unpaid", r
		assert not frappe.db.count("Activities", {"purchase_invoice_id": pi_name})
		print("  B10 ok: invoice cancelled, timesheets and activity rows unlinked")
		print("All teacher payables verification checks PASSED successfully!")
	except Exception:
		traceback.print_exc()
		print("FAILED")
	finally:
		frappe.db.commit()
		for key in ("pe", "pi"):
			name = created[key]
			if not name:
				continue
			dt = "Payment Entry" if key == "pe" else "Purchase Invoice"
			try:
				doc = frappe.get_doc(dt, name)
				if doc.docstatus == 1:
					doc.cancel()
				frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
				print(f"  cleanup: deleted {dt} {name}")
			except Exception as e:
				print(f"  cleanup FAILED for {dt} {name}: {e}")
		frappe.db.commit()
