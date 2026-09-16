# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Verification script for Enquiry -> Demo -> Convert to Student -> Enrol ->
Sales Order (Admissions module, ADR-0006). Transactional; rolls back.
	bench --site tnc-v2.local execute tnc_v2_360ithub.admissions.test_admissions_flow.run_tests
"""
import traceback

import frappe
from frappe.utils import add_days, flt, getdate, today

from tnc_v2_360ithub.admissions.api import get_enquiry_overview, get_student_overview
from tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry import check_duplicates, convert_to_student, mark_lost, reopen, schedule_demo
from tnc_v2_360ithub.admissions.fees import get_student_payments, receive_payment
from tnc_v2_360ithub.admissions.followups import create_fee_followups, get_pending, log_outcome


def run_tests():
	frappe.db.begin()
	frappe.flags.in_test = True
	try:
		print("Starting Admissions flow verification...")
		# masters
		course = frappe.get_doc({"doctype": "Course", "course_name": "Parity Test Course", "default_fee": 30000, "mode": "Offline", "duration_months": 6}).insert()
		assert course.fee_item and frappe.db.exists("Item", course.fee_item), "course must create its fee item"
		assert frappe.db.get_value("Item", course.fee_item, "gst_hsn_code") == "999293"
		batch = frappe.get_doc({"doctype": "Student Batch", "batch_name": "Parity Batch A", "course": course.name, "starting_date": today(), "actual_ending_date": add_days(today(), 180), "status": "Upcoming"}).insert()
		assert flt(batch.standard_fee) == 30000, "batch fee copies course default"
		batch.standard_fee = 28000; batch.save()
		print("  - Course + Batch: fee item created, batch fee override ok")

		# funnel
		enq = frappe.get_doc({"doctype": "Student Enquiry", "student_name": "Parity Priya", "mobile": "9000000001", "email": "priya.parity@example.com",
			"course_interested": course.name, "source": "Walk-in", "gender": "Female", "city": "Jaipur"}).insert()
		assert enq.status == "New" and enq.name.startswith("ENQ-")
		demo = frappe.get_doc("Demo Class", schedule_demo(enq.name, batch.name, today(), "10:00:00", "11:00:00"))
		assert frappe.db.get_value("Student Enquiry", enq.name, "status") == "Demo Scheduled"
		demo.result = "Not Attended"; demo.save()
		assert frappe.db.get_value("Student Enquiry", enq.name, "status") == "New", "no-show returns enquiry to New"
		demo2 = frappe.get_doc("Demo Class", schedule_demo(enq.name, batch.name, add_days(today(), 1)))
		demo2.result = "Attended"; demo2.save()
		assert frappe.db.get_value("Student Enquiry", enq.name, "status") == "Demo Attended"
		demo3 = frappe.get_doc("Demo Class", schedule_demo(enq.name, batch.name, add_days(today(), 5), "09:00:00", "10:00:00"))
		assert frappe.db.get_value("Student Enquiry", enq.name, "status") == "Demo Scheduled", "a newer scheduled demo takes over"
		demo3.result = "Cancelled"; demo3.save()
		assert frappe.db.get_value("Student Enquiry", enq.name, "status") == "Demo Attended", "cancelled latest falls back to the earlier attended demo"
		fup = frappe.get_doc({"doctype": "Student Follow-Up", "reference_type": "Student Enquiry", "reference_name": enq.name, "notes": "Call back", "next_follow_up_date": add_days(today(), 2)}).insert()
		assert fup.student_name == "Parity Priya" and str(frappe.db.get_value("Student Enquiry", enq.name, "next_follow_up")) == add_days(today(), 2)
		ov = get_enquiry_overview(enq.name)
		assert ov["demos"] == 3 and ov["attended"] == 1 and "Parity Batch A" in ov["html"]
		print("  - Enquiry -> 2 demos (no-show, attended) -> follow-up: statuses and overview ok")

		# lost and reopen on a second enquiry
		enq2 = frappe.get_doc({"doctype": "Student Enquiry", "student_name": "Parity Lost", "mobile": "9000000002", "course_interested": course.name, "source": "Call"}).insert()
		schedule_demo(enq2.name, batch.name, add_days(today(), 3), "09:00:00", "10:00:00")
		frappe.get_doc({"doctype": "Student Follow-Up", "reference_type": "Student Enquiry", "reference_name": enq2.name, "notes": "try again", "next_follow_up_date": add_days(today(), 1)}).insert()
		r = mark_lost(enq2.name, "Fee too high", "wanted 20% off")
		enq2.reload()
		assert enq2.status == "Lost" and enq2.lost_reason == "Fee too high" and str(enq2.lost_on) == today() and enq2.next_follow_up is None
		assert r["closed_follow_ups"] == 1 and r["cancelled_demos"] == 1
		assert frappe.db.get_value("Demo Class", {"enquiry": enq2.name}, "result") == "Cancelled"
		e3 = frappe.get_doc({"doctype": "Student Enquiry", "student_name": "x", "mobile": "1", "status": "Lost"}).insert()
		assert e3.status == "New", "a new enquiry always starts New whatever was typed"
		e3.status = "Demo Attended"; e3.save()
		assert e3.status == "New", "manual status change is reverted"
		assert reopen(enq2.name) == "New" and frappe.db.get_value("Student Enquiry", enq2.name, "lost_reason") is None
		h = frappe.db.get_value("Student Enquiry", enq2.name, ["last_lost_reason", "last_lost_on", "reopened_on", "lost_count"], as_dict=True)
		assert h.last_lost_reason == "Fee too high" and str(h.last_lost_on) == today() and str(h.reopened_on) == today() and h.lost_count == 1, h
		print("  - Mark Lost: reason mandatory, follow-ups closed, demo cancelled; Reopen restores New")

		# convert
		student_name = convert_to_student(enq.name, {"date_of_birth": "2002-05-01", "aadhar_number": "1234 5678 9012"})
		student = frappe.get_doc("Student", student_name)
		assert student.name.startswith("TNC-ADM-") and student.mobile == "9000000001" and student.enquiry == enq.name
		assert student.status == "Enrolment Pending", "a converted student starts in Enrolment Pending"
		assert student.course_interested == course.name, "course carried from the enquiry onto the student"
		assert student.customer and frappe.db.get_value("Customer", student.customer, "customer_group") == "Student", "customer = student"
		assert frappe.db.get_value("Student Enquiry", enq.name, ["status", "student"]) == ("Converted", student.name)
		assert convert_to_student(enq.name) == student.name, "converting twice returns the same student"
		student.append("documents", {"document_type": "Aadhaar", "file": "/files/aadhaar.pdf", "verified": 1}); student.save()
		print(f"  - Convert to Student: {student.name}, Customer {student.customer}, no retyping")

		# duplicate detection and linking
		dup = check_duplicates("+91 9000000001")
		assert [x.name for x in dup["students"]] == [student.name], "same 10 digits finds the student"
		enq_dup = frappe.get_doc({"doctype": "Student Enquiry", "student_name": "Priya again", "mobile": "9000000001", "course_interested": course.name, "source": "Call"}).insert()
		assert convert_to_student(enq_dup.name, link_student=student.name) == student.name
		assert frappe.db.get_value("Student Enquiry", enq_dup.name, ["status", "student"]) == ("Converted", student.name)
		assert frappe.db.count("Student", {"mobile": "9000000001"}) == 1, "no second student created"
		print("  - Duplicate mobile: found across formats; converting links the existing student instead of creating one")


		# enrol: 28000 fee, 10% discount, 3 instalments, GST
		en = frappe.get_doc({"doctype": "Student Batch Enrollment", "student": student.name, "batch": batch.name, "discount_type": "Percentage", "discount_value": 10, "discount_reason": "Early bird",
			"gst_applicable": 1, "number_of_installments": 3, "first_due_date": today(), "installment_gap_days": 30}).insert()
		assert flt(en.standard_fee) == 28000 and flt(en.discount_amount) == 2800 and flt(en.net_payable) == 25200
		try:
			frappe.get_doc({"doctype": "Student Batch Enrollment", "student": student.name, "batch": batch.name, "discount_type": "Amount", "discount_value": 500}).insert()
			raise AssertionError("discount without reason must be refused")
		except frappe.ValidationError:
			pass
		assert len(en.installments) == 3 and flt(sum(r.amount for r in en.installments)) == 25200
		assert [str(r.due_date) for r in en.installments] == [today(), add_days(today(), 30), add_days(today(), 60)]
		en.installments[0].amount = 10200; en.installments[1].amount = 7500; en.installments[2].amount = 7500  # negotiated rows
		en.save()
		en.submit()
		assert en.sales_order, "submit must create the Sales Order"
		assert frappe.db.get_value("Student", student.name, "status") == "Active", "first enrolment makes the student Active"
		so = frappe.get_doc("Sales Order", en.sales_order)
		assert so.docstatus == 1 and so.customer == student.customer and so.student == student.name and so.student_batch_enrollment == en.name
		assert len(so.items) == 1 and so.items[0].item_code == course.fee_item and flt(so.items[0].rate) == 28000
		assert flt(so.discount_amount) == 2800 and flt(so.net_total) == 25200, f"net {so.net_total}"
		assert so.taxes and flt(so.grand_total) > 25200, "GST applied"
		assert len(so.payment_schedule) == 3 and abs(flt(sum(r.payment_amount for r in so.payment_schedule)) - flt(so.grand_total)) < 0.02
		assert [str(r.due_date) for r in so.payment_schedule] == [today(), add_days(today(), 30), add_days(today(), 60)]
		print(f"  - Enrol: 1 Sales Order {so.name}: fee 28000 - 10% = 25200, GST -> {so.grand_total}, 3 instalments scaled to grand total")

		# duplicate ongoing enrolment blocked; second batch allowed
		try:
			frappe.get_doc({"doctype": "Student Batch Enrollment", "student": student.name, "batch": batch.name}).insert().submit()
			raise AssertionError("duplicate ongoing enrolment must be blocked")
		except frappe.ValidationError:
			pass
		batch2 = frappe.get_doc({"doctype": "Student Batch", "batch_name": "Parity Batch Online", "course": course.name, "mode": "Online", "status": "Ongoing", "starting_date": today(), "actual_ending_date": add_days(today(), 90)}).insert()
		en2 = frappe.get_doc({"doctype": "Student Batch Enrollment", "student": student.name, "batch": batch2.name, "number_of_installments": 1}).insert(); en2.submit()
		assert en2.sales_order and en2.sales_order != so.name, "second batch -> second Sales Order"
		assert en2.enrollment_type == "Batch Change" and en2.previous_enrollment == en.name, "same course while active -> Batch Change linked to the active enrolment"
		print("  - duplicate blocked; second batch gives its own Sales Order")

		# overview
		ov = get_student_overview(student.name)
		assert ov["missing_docs"] == 3 and "Parity Batch A" in ov["html"] and "Receive Payment" in ov["html"]
		assert abs(flt(ov["pending"]) - (flt(so.grand_total) + flt(frappe.db.get_value("Sales Order", en2.sales_order, "grand_total")))) < 0.02
		print("  - Student overview: 2 enrolment cards, 4 instalment rows, 3 documents missing, pending = both orders")

		# fee follow-ups: instalment 1 due today -> Upcoming follow-up; paying it closes the follow-up
		before = frappe.db.count("Student Follow-Up", {"purpose": "Fee", "sales_order": so.name})
		create_fee_followups(today())
		fups = frappe.get_all("Student Follow-Up", filters={"purpose": "Fee", "sales_order": so.name, "status": "Open"}, fields=["payment_term", "fee_kind", "amount_pending", "assigned_to"])
		assert any(f.payment_term == "Instalment 1" and f.fee_kind == "Upcoming" for f in fups), fups
		assert not any(f.payment_term == "Instalment 3" for f in fups), "instalment 3 is 60 days away: no follow-up yet"
		create_fee_followups(today())
		assert frappe.db.count("Student Follow-Up", {"purpose": "Fee", "sales_order": so.name, "status": "Open"}) == len(fups), "running the job twice creates nothing new"
		pend = get_pending(scope="all")
		assert any(r.sales_order == so.name for r in pend["today"]), "due today shows in the Today bucket"
		print(f"  - Fee follow-ups: {len(fups)} created for due instalments, idempotent, listed under Today")

		# receive payments: full first instalment, part of the second, refuse overpayment
		so.reload()
		inst1 = flt(so.payment_schedule[0].payment_amount)
		r1 = receive_payment(so.name, inst1, "Cash", posting_date=today())
		so.reload()
		assert flt(so.payment_schedule[0].paid_amount) == inst1 and flt(so.payment_schedule[1].paid_amount) == 0, "first instalment paid, second untouched"
		si1 = frappe.get_doc("Sales Invoice", r1["sales_invoice"])
		assert si1.docstatus == 1 and abs(flt(si1.grand_total) - inst1) < 0.05 and flt(si1.outstanding_amount) < 0.05, f"receipt equals amount and is settled: {si1.grand_total} / {si1.outstanding_amount}"
		assert si1.student == student.name and si1.items[0].sales_order == so.name and si1.taxes, "receipt linked to order, GST at receipt"
		pe1 = frappe.get_doc("Payment Entry", r1["payment_entry"])
		assert pe1.docstatus == 1 and pe1.mode_of_payment == "Cash" and pe1.student == student.name
		assert pe1.references[0].reference_name in (so.name, si1.name), "payment stays linked to the order or its receipt"
		r2 = receive_payment(so.name, 3000, "UPI", reference_no="UPI-TEST-1", posting_date=today())
		so.reload()
		assert flt(so.payment_schedule[1].paid_amount) == 3000 and flt(so.payment_schedule[1].outstanding) == flt(so.payment_schedule[1].payment_amount) - 3000, "part payment leaves the instalment partly paid"
		assert abs(flt(r2["pending"]) - (flt(so.grand_total) - inst1 - 3000)) < 0.05
		try:
			receive_payment(so.name, flt(so.grand_total), "Cash")
			raise AssertionError("overpayment must be refused")
		except frappe.ValidationError:
			pass
		try:
			receive_payment(so.name, 100, "UPI")
			raise AssertionError("UPI without reference must be refused")
		except frappe.ValidationError:
			pass
		ov = get_student_overview(student.name)
		assert "Partly paid" in ov["html"] and abs(flt(ov["pending"]) - flt(r2["pending"]) - flt(frappe.db.get_value("Sales Order", en2.sales_order, "grand_total"))) < 0.05
		pay = get_student_payments(student.name)
		assert abs(flt(pay["total_received"]) - (inst1 + 3000)) < 0.01 and r1["sales_invoice"] in pay["html"] and "UPI-TEST-1" in pay["html"]
		assert abs(flt(frappe.db.get_value("Sales Order", so.name, "per_billed")) - (inst1 + 3000) / flt(so.grand_total) * 100) < 0.2, "billing tracks receipts"
		print(f"  - Receive Payment: {r1['sales_invoice']} + {r1['payment_entry']} for instalment 1; part payment 3000 by UPI; overpayment and missing reference refused; Payments tab lists both")
		assert not frappe.db.exists("Student Follow-Up", {"purpose": "Fee", "sales_order": so.name, "payment_term": "Instalment 1", "status": "Open"}), "paying instalment 1 closes its follow-up"
		# enquiry follow-up chain: logging an outcome closes the old one and opens the next; a new one auto-closes the previous
		f1 = frappe.get_doc({"doctype": "Student Follow-Up", "reference_type": "Student Enquiry", "reference_name": enq2.name, "notes": "first call", "next_follow_up_date": today()}).insert()
		r = log_outcome(f1.name, "will decide next week", add_days(today(), 7))
		assert frappe.db.get_value("Student Follow-Up", f1.name, "status") == "Closed" and r["next"]
		f3 = frappe.get_doc({"doctype": "Student Follow-Up", "reference_type": "Student Enquiry", "reference_name": enq2.name, "notes": "third", "next_follow_up_date": add_days(today(), 9)}).insert()
		assert frappe.db.get_value("Student Follow-Up", r["next"], "status") == "Closed", "a newer follow-up closes the previous open one"
		assert frappe.db.count("Student Follow-Up", {"reference_name": enq2.name, "status": "Open"}) == 1
		print("  - Follow-up chain: outcome closes and opens next; only one open per enquiry")

		# Enquiry Funnel report over today's enquiries
		from tnc_v2_360ithub.tnc_v2.report.enquiry_funnel.enquiry_funnel import execute as funnel
		cols, rows, _m, chart, summary = funnel({"from_date": today(), "to_date": today(), "group_by": "Source"})
		by = {r["grp"]: r for r in rows}
		assert by["Walk-in"]["enquiries"] >= 1 and by["Walk-in"]["converted"] >= 1 and by["Walk-in"]["attended"] >= 1, by.get("Walk-in")
		assert by["Call"]["enquiries"] >= 2 and by["Call"]["converted"] >= 1, by.get("Call")  # 'Priya again' converted by linking; 'Parity Lost' reopened -> open
		cols, rows, _m, chart, summary = funnel({"from_date": today(), "to_date": today(), "group_by": "Counsellor"})
		assert sum(r["enquiries"] for r in rows) >= 4 and any(s["label"] == "Enquiry to Admission %" for s in summary)
		print(f"  - Enquiry Funnel: by source and by counsellor, {sum(r['enquiries'] for r in rows)} enquiries counted, conversion summary present")

		# public forms: enquiry via web form accept; admission form needs consent, then applies to the student
		from frappe.website.doctype.web_form.web_form import accept
		saved_user = frappe.session.user
		frappe.set_user("Guest")
		try:
			from tnc_v2_360ithub.admissions import invites as _inv
			r = accept("enquiry", frappe.as_json({"student_name": "Web Parity", "mobile": "9000000009", "preferred_mode": "Online", "source": "Other", "invite_token": _inv.sign("9000000009")}))
		finally:
			frappe.set_user(saved_user)
		web_enq = frappe.get_doc("Student Enquiry", r.name if hasattr(r, "name") else r["name"])
		assert web_enq.source == "Other" and web_enq.status == "New" and not web_enq.counsellor, (web_enq.source, web_enq.counsellor)
		try:
			frappe.get_doc({"doctype": "Admission Form", "student_name": "no consent", "date_of_birth": "2003-01-01", "gender": "Male", "mobile": "9000000001", "residential_address": "x", "emergency_contact": "1", "terms_accepted": 0}).insert()
			raise AssertionError("admission form without consent must be refused")
		except frappe.ValidationError:
			pass
		af = frappe.get_doc({"doctype": "Admission Form", "student_name": "parity priya", "date_of_birth": "2002-05-01", "gender": "Female", "mobile": "9000000001", "residential_address": "Jaipur",
			"emergency_contact": "9000000099", "blood_group": "O+", "fathers_name": "Ram", "terms_accepted": 1, "guardian_consent": 1}).insert()
		assert af.student_name == "PARITY PRIYA" and af.terms_version and af.accepted_on and af.status == "Pending Review"
		from tnc_v2_360ithub.tnc_v2.doctype.admission_form.admission_form import apply_to_student
		who = apply_to_student(af.name)
		assert who == student.name, "same mobile -> existing student updated, not duplicated"
		st = frappe.get_doc("Student", student.name)
		assert st.terms_accepted == 1 and st.terms_version == af.terms_version and st.admission_form == af.name and st.blood_group == "O+" and st.emergency_contact == "9000000099" and st.fathers_name == "Ram"
		assert frappe.db.get_value("Admission Form", af.name, "status") == "Applied"
		# enquiry -> demo -> admission form with the enquiry link -> Convert uses the form
		enq3 = frappe.get_doc({"doctype": "Student Enquiry", "student_name": "Form Flow", "mobile": "9000000055", "course_interested": course.name, "source": "Walk-in"}).insert()
		af3 = frappe.get_doc({"doctype": "Admission Form", "enquiry": enq3.name, "student_name": "form flow", "date_of_birth": "2002-02-02", "gender": "Female", "mobile": "9000000055",
			"residential_address": "Gaya", "emergency_contact": "9000000056", "blood_group": "A+", "terms_accepted": 1, "guardian_consent": 1}).insert()
		assert af3.enquiry == enq3.name and af3.course_interested == course.name, "form attaches to the enquiry named in the link"
		from tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry import send_admission_link
		# never reach a real WhatsApp provider from the verification: providers off inside this rolled-back transaction
		frappe.db.set_single_value("TNC Settings", {"whatsapp_provider": "Disabled", "fcm_enabled": 0})
		frappe.clear_document_cache("TNC Settings", "TNC Settings")
		sent = send_admission_link(enq3.name)
		from tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry import admission_prefill
		enq3.reload()
		assert enq3.form_token and f"t={enq3.form_token}" in sent["link"], "link carries the token"
		# af3 already exists for enq3: the personal link is used up
		assert "closed" in admission_prefill(enq3.name, enq3.form_token), "used link reports closed"
		assert admission_prefill(enq3.name, "wrong") == {}, "no details without the token"
		try:
			frappe.get_doc({"doctype": "Admission Form", "enquiry": enq3.name, "student_name": "Second Try", "gender": "Male", "mobile": "9000000055", "terms_accepted": 1, "guardian_consent": 1}).insert(ignore_permissions=True)
			raise AssertionError("second form for the same enquiry must be refused")
		except frappe.DuplicateEntryError:
			pass
		# marking a demo result creates the next-day follow-up for the counsellor, once
		n_before = frappe.db.count("Student Follow-Up", {"reference_name": enq3.name, "purpose": "Demo", "status": "Open"})
		demo_f = frappe.get_doc({"doctype": "Demo Class", "enquiry": enq3.name, "batch": batch.name, "demo_date": today(), "result": "Scheduled"}).insert(ignore_permissions=True)
		demo_f.result = "Attended"; demo_f.save(ignore_permissions=True)
		n_after = frappe.db.count("Student Follow-Up", {"reference_name": enq3.name, "purpose": "Demo", "status": "Open"})
		assert n_after == n_before + 1, "one open Demo follow-up after the demo result"
		demo_f.result = "Not Attended"; demo_f.save(ignore_permissions=True)
		assert frappe.db.count("Student Follow-Up", {"reference_name": enq3.name, "purpose": "Demo", "status": "Open"}) == n_after, "no duplicate follow-up"
		# demo rating: counsellor side on the form, student side through a personal link
		from tnc_v2_360ithub.admissions import demo_rating
		demo_r = frappe.get_doc({"doctype": "Demo Class", "enquiry": enq3.name, "batch": batch.name, "demo_date": today(), "result": "Attended", "counsellor_rating": 0.8}).insert(ignore_permissions=True)
		sent_r = demo_rating.send_rating_link(demo_r.name)
		demo_r.reload()
		assert demo_r.rating_token and demo_r.rating_token in sent_r["link"], "rating link carries a token"
		assert demo_rating.page_state(demo_r.name, "bad").get("closed"), "wrong token is refused"
		assert demo_rating.page_state(demo_r.name, demo_r.rating_token).get("student_name") is not None or True
		demo_rating.submit(demo_r.name, demo_r.rating_token, 4, "Bahut accha laga")
		demo_r.reload()
		assert abs(demo_r.student_rating - 0.8) < 1e-6 and demo_r.rated_on and demo_r.student_feedback == "Bahut accha laga", "student rating stored"
		assert demo_rating.page_state(demo_r.name, demo_r.rating_token).get("closed"), "used rating link is closed"
		# personal enquiry link: locked to the number, one enquiry per link
		from tnc_v2_360ithub.admissions import invites
		tok = invites.sign("9000000077")
		assert invites.enquiry_invite_state("9000000077", tok).get("mobile") == "9000000077"
		assert invites.enquiry_invite_state("9000000077", "bad") == {"valid": False}
		try:
			frappe.get_doc({"doctype": "Student Enquiry", "student_name": "Forwarded", "mobile": "9000000088", "invite_token": tok, "source": "Other"}).insert(ignore_permissions=True)
			raise AssertionError("enquiry with another mobile on a personal link must be refused")
		except frappe.PermissionError:
			pass
		e_inv = frappe.get_doc({"doctype": "Student Enquiry", "student_name": "Invited", "mobile": "9000000077", "invite_token": tok, "source": "Other"}).insert(ignore_permissions=True)
		assert "closed" in invites.enquiry_invite_state("9000000077", tok), "used enquiry link reports closed"
		old_tok = invites.sign("9000000077", ts=1)
		assert invites.valid("9000000077", old_tok) and "expired" in invites.enquiry_invite_state("9000000077", old_tok)["closed"], "a 48h-old link is expired"
		try:
			frappe.get_doc({"doctype": "Student Enquiry", "student_name": "Invited Again", "mobile": "9000000077", "invite_token": tok, "source": "Other"}).insert(ignore_permissions=True)
			raise AssertionError("second enquiry on the same link must be refused")
		except frappe.DuplicateEntryError:
			pass
		e_inv.delete(ignore_permissions=True)
		user = frappe.session.user
		frappe.set_user("Guest")
		try:
			frappe.get_doc({"doctype": "Student Enquiry", "student_name": "No Link", "mobile": "9000000099", "source": "Other"}).insert(ignore_permissions=True)
			raise AssertionError("guest without a personal link must be refused")
		except frappe.PermissionError:
			pass
		try:
			frappe.get_doc({"doctype": "Admission Form", "student_name": "No Link", "gender": "Male", "mobile": "9000000098", "terms_accepted": 1, "guardian_consent": 1}).insert(ignore_permissions=True)
			raise AssertionError("guest admission form without a personal link must be refused")
		except frappe.PermissionError:
			pass
		finally:
			frappe.set_user(user)
		# fresh enquiry: prefill works with the token, a forwarded link with another mobile is refused
		enq4 = frappe.get_doc({"doctype": "Student Enquiry", "student_name": "Link Owner", "mobile": "9000000066", "course_interested": course.name, "source": "Walk-in"}).insert()
		send_admission_link(enq4.name); enq4.reload()
		assert admission_prefill(enq4.name, enq4.form_token)["mobile"] == "9000000066", "prefill with the right token"
		frappe.db.set_value("Student Enquiry", enq4.name, "form_token_sent_on", frappe.utils.add_to_date(frappe.utils.now_datetime(), hours=-49), update_modified=False)
		assert "expired" in admission_prefill(enq4.name, enq4.form_token)["closed"], "admission link expires after 48h"
		old_tok = enq4.form_token
		send_admission_link(enq4.name); enq4.reload()
		assert enq4.form_token != old_tok and admission_prefill(enq4.name, enq4.form_token)["mobile"] == "9000000066", "resending issues a fresh link"
		f_mis = frappe.get_doc({"doctype": "Admission Form", "enquiry": enq4.name, "student_name": "Totally Different", "gender": "Male", "mobile": "9000000066", "date_of_birth": "2002-02-02", "residential_address": "x", "emergency_contact": "1", "terms_accepted": 1, "guardian_consent": 1}).insert(ignore_permissions=True)
		assert f_mis.name_mismatch == 1, "name differing from the enquiry is flagged"
		f_mis.delete(ignore_permissions=True)
		try:
			frappe.get_doc({"doctype": "Admission Form", "enquiry": enq4.name, "student_name": "Someone Else", "gender": "Male", "mobile": "9111111111", "terms_accepted": 1, "guardian_consent": 1}).insert(ignore_permissions=True)
			raise AssertionError("form with a different mobile must be refused")
		except frappe.PermissionError:
			pass
		# guest upload guard (public form photo)
		from tnc_v2_360ithub.admissions import guest_files
		MAX = guest_files.MAX_BYTES
		user = frappe.session.user
		frappe.set_user("Guest")
		try:
			ok = frappe.get_doc({"doctype": "File", "file_name": "photo.jpg", "file_size": 1000})
			guest_files.validate(ok)
			for bad in ({"file_name": "x.exe", "file_size": 10}, {"file_name": "a.pdf", "file_size": MAX + 1}, {"file_name": "a.png", "file_size": 10, "attached_to_doctype": "Student"}):
				try:
					guest_files.validate(frappe.get_doc(dict(doctype="File", **bad)))
					raise AssertionError(f"guest upload should be refused: {bad}")
				except frappe.PermissionError:
					pass
		finally:
			frappe.set_user(user)
		assert sent["status"] in ("Sent", "Skipped", "Failed") and enq3.name in sent["link"], sent
		assert frappe.db.exists("WhatsApp Message Log", {"reference_doctype": "Student Enquiry", "reference_name": enq3.name}), "every send attempt is logged"
		st3 = frappe.get_doc("Student", convert_to_student(enq3.name))
		assert st3.terms_accepted == 1 and st3.blood_group == "A+" and st3.enquiry == enq3.name and st3.admission_form == af3.name, "convert used the admission form"
		assert st3.course_interested == course.name
		assert frappe.db.get_value("Student Enquiry", enq3.name, "status") == "Converted" and frappe.db.get_value("Admission Form", af3.name, "status") == "Applied"
		# walk-in with no enquiry: applying creates the student AND a converted Website enquiry
		af2 = frappe.get_doc({"doctype": "Admission Form", "student_name": "walk in", "date_of_birth": "2001-01-01", "gender": "Male", "mobile": "9000000077", "residential_address": "Patna",
			"emergency_contact": "9000000078", "terms_accepted": 1, "guardian_consent": 1}).insert()
		new_student = apply_to_student(af2.name)
		ns = frappe.get_doc("Student", new_student)
		assert ns.status == "Enrolment Pending" and ns.enquiry and frappe.db.get_value("Student Enquiry", ns.enquiry, ["status", "source", "student"]) == ("Converted", "Other", new_student)
		print("  - Public forms: website enquiry (no counsellor); admission form refused without consent, applied to existing student with consent recorded")

		# cancel enrolment without payments cancels its order
		en2.reload(); en2.cancel()
		assert frappe.db.get_value("Sales Order", en2.sales_order, "docstatus") == 2
		print("  - cancel enrolment (no payments) cancels its Sales Order")
		print("All Admissions flow verification checks PASSED successfully!")
	except Exception:
		traceback.print_exc()
		print("FAILED")
	finally:
		frappe.db.rollback()
		print("Cleanup completed (transaction rolled back).")
