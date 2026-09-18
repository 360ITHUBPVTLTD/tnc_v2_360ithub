# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt

"""Verification script for the ported Teacher module (parity checklist rows
B1, B2, B3, B4, B6, B7, B11, B12). Transactional; rolls back.

	bench --site tnc-v2.local execute tnc_v2_360ithub.teachers.test_teacher_flow.run_tests
"""

import traceback

import frappe
from frappe.utils import today

TEACHER_EMAIL = "tnc-test-teacher@example.com"


def run_tests():
	frappe.db.begin()
	frappe.flags.in_test = True
	frappe.flags.mute_messages = True
	try:
		print("Starting Teacher module verification...")
		# v1 reference record the Teacher controller assigns to new users; migrated as data.
		if not frappe.db.exists("Module Profile", "No Module"):
			frappe.get_doc({"doctype": "Module Profile", "module_profile_name": "No Module"}).insert(ignore_permissions=True)

		# --- B1: Activity, Teacher with rates -> Supplier + User with TNC Teachers role ---
		print("  - Activity + Teacher creation creates Supplier and User")
		for name in ("Test Lecture", "Test Doubt Session"):
			if not frappe.db.exists("Activity", name):
				frappe.get_doc({"doctype": "Activity", "activity_name": name, "uom": "Hour", "enable": 1}).insert(ignore_permissions=True)
		teacher = frappe.get_doc(
			{
				"doctype": "Teacher",
				"full_name": "Parity Test Teacher",
				"email": TEACHER_EMAIL,
				"mobile_no": "9999900002",
				"status": "Active",
				"teachers_activity_type": [
					{"activity_name": "Test Lecture", "rate": 500},
					{"activity_name": "Test Doubt Session", "rate": 300},
				],
			}
		).insert(ignore_permissions=True)
		teacher.reload()
		assert teacher.name.startswith(("TCH-", "TEACHER-")), teacher.name  # TEACHER- when v1's Document Naming Rule is present
		assert teacher.supplier_id and frappe.db.exists("Supplier", teacher.supplier_id), "Supplier not created for teacher"
		assert frappe.db.exists("User", TEACHER_EMAIL), "User not created for teacher"
		roles = [r.role for r in frappe.get_doc("User", TEACHER_EMAIL).roles]
		assert "TNC Teachers" in roles, roles
		assert teacher.teachers_activity_type[0].uom == "Hour", "uom should fetch from Activity"

		# --- B2: duplicate activity pricing rejected ---
		print("  - duplicate pricing rejected")
		dup = frappe.get_doc("Teacher", teacher.name)
		dup.append("teachers_activity_type", {"activity_name": "Test Lecture", "rate": 999})
		blocked = False
		try:
			dup.save(ignore_permissions=True)
		except frappe.ValidationError:
			blocked = True
		assert blocked, "duplicate activity pricing was accepted"

		# --- B3: timesheet totals from the teacher's rates (v1 rule: one activity per timesheet) ---
		print("  - timesheet grand_total from rates")
		ts = frappe.get_doc(
			{"doctype": "Teachers Timesheet", "teacher_id": teacher.name, "date": today(), "activity_type": [{"activity_name": "Test Lecture", "qty": 2}]}
		).insert(ignore_permissions=True)
		ts.reload()
		assert ts.name.startswith(("TIMESHEET-", "TEAC-TMS-")), ts.name  # TEAC-TMS- when v1's Document Naming Rule is present
		assert ts.status == "Pending" and ts.payment_status == "Unpaid", (ts.status, ts.payment_status)
		assert ts.teacher_name == "Parity Test Teacher"
		row = ts.activity_type[0]
		assert row.activity_fee == 500 and row.amount == 1000, (row.activity_fee, row.amount)
		assert ts.grand_total == 1000, ts.grand_total

		# --- B4: a second activity row in one timesheet is rejected (v1 "one activity per timesheet") ---
		print("  - second activity row in one timesheet rejected")
		bad = frappe.get_doc(
			{"doctype": "Teachers Timesheet", "teacher_id": teacher.name, "date": today(), "activity_type": [{"activity_name": "Test Lecture", "qty": 1}, {"activity_name": "Test Doubt Session", "qty": 2}]}
		)
		blocked = False
		try:
			bad.insert(ignore_permissions=True)
		except frappe.ValidationError:
			blocked = True
		assert blocked, "two activity rows in a timesheet were accepted"

		# --- B6/B7: approve and reject via the whitelisted status method ---
		print("  - approve / reject through update_timesheet_status")
		from tnc_v2_360ithub.tnc_v2.doctype.teacher import teacher as teacher_api

		# approvers come from TNC Settings; a comment is mandatory; others are refused
		saved_user = frappe.session.user
		frappe.set_user("Guest")
		try:
			teacher_api.update_timesheet_status(ts.name, "Approved", reason="x")
			raise AssertionError("non-approver must not approve")
		except frappe.PermissionError:
			pass
		finally:
			frappe.set_user(saved_user)
		teacher_api.update_timesheet_status(ts.name, "Approved")
		ts.reload()
		assert ts.status == "Approved" and ts.approved_by == frappe.session.user and ts.approved_on, (ts.status, ts.approved_by)
		ts2 = frappe.get_doc({"doctype": "Teachers Timesheet", "teacher_id": teacher.name, "date": today(), "activity_type": [{"activity_name": "Test Lecture", "qty": 1}]}).insert(ignore_permissions=True)
		teacher_api.update_timesheet_status(ts2.name, "Rejected", reason="test rejection")
		ts2.reload()
		assert ts2.status == "Rejected" and ts2.rejected_reason == "test rejection", (ts2.status, ts2.rejected_reason)

		# --- unpaid approved timesheets visible to the payment flow ---
		print("  - get_unpaid_timesheets returns the approved one")
		unpaid = teacher_api.get_unpaid_timesheets(teacher.name, today(), today())
		names = [u.get("name") if isinstance(u, dict) else u for u in (unpaid or [])]
		assert ts.name in names, f"approved unpaid timesheet missing from get_unpaid_timesheets: {unpaid}"

		# --- B11/B12: both reports execute ---
		print("  - Teachers Timesheet Report and Teachers Payable Report execute")
		from tnc_v2_360ithub.tnc_v2.report.teachers_timesheet_report import teachers_timesheet_report as r1
		from tnc_v2_360ithub.tnc_v2.report.teachers_payable_report import teachers_payable_report as r2

		out1 = r1.execute({"from_date": today(), "to_date": today(), "teacher": teacher.name})
		out2 = r2.execute({"from_date": today(), "to_date": today()})
		assert out1 and out1[0], "timesheet report returned no columns"
		assert out2 and out2[0], "payable report returned no columns"
		payable_rows = out2[1] or []
		mine = [r for r in payable_rows if isinstance(r, dict) and r.get("teacher_name") == "Parity Test Teacher"]
		assert mine and mine[0].get("total_payable") == 1000 and mine[0].get("balance_amount") == 1000, f"payable report row wrong: {payable_rows[:2]}"

		print("\nAll Teacher module verification checks PASSED successfully!")
	except Exception:
		traceback.print_exc()
		raise
	finally:
		frappe.db.rollback()
		print("Cleanup completed (transaction rolled back).")
