frappe.ui.form.on("Student Batch Enrollment", {
	refresh(frm) {
		frm.trigger("check_batch_window");
		if (frm.doc.docstatus === 1 && frm.doc.sales_order) {
			frm.add_custom_button(__("Receive Payment"), () => {
				frappe.call({ method: "tnc_v2_360ithub.admissions.fees.get_pending", args: { sales_order: frm.doc.sales_order } }).then((r) => {
					tnc.admissions.receive_payment({ sales_order: frm.doc.sales_order, amount: r.message ? r.message.pending : null,
						label: __("total pending"), on_done: () => frm.reload_doc() });
				});
			}).addClass("btn-primary");
			frm.add_custom_button(__("Sales Order"), () => frappe.set_route("Form", "Sales Order", frm.doc.sales_order));
			frm.add_custom_button(__("Student"), () => frappe.set_route("Form", "Student", frm.doc.student));
			frm.dashboard.clear_headline();
			frm.dashboard.set_headline(
				`<span class="indicator-pill green no-indicator-dot">${__("Enrolled")}</span> &nbsp; ${__("Sales Order")}
				 <a href="/app/sales-order/${encodeURIComponent(frm.doc.sales_order)}"><b>${frm.doc.sales_order}</b></a> ${__("created for")}
				 <a href="/app/student/${encodeURIComponent(frm.doc.student)}"><b>${frm.doc.student_name || frm.doc.student}</b></a>.`
			);
		}
		frm.set_query("previous_enrollment", () => ({ filters: { student: frm.doc.student, docstatus: 1 } }));
		frm.set_query("batch", () => {
			const f = { status: ["in", ["Upcoming", "Ongoing"]] };
			// narrow to the student's course of interest until a batch is chosen
			if (!frm.doc.batch && frm.__student_course) f.course = frm.__student_course;
			return { filters: f };
		});
		if (frm.doc.student && !frm.doc.batch && frm.is_new()) {
			frappe.db.get_value("Student", frm.doc.student, "batch_interested").then((r) => { if (r.message && r.message.batch_interested && !frm.doc.batch) frm.set_value("batch", r.message.batch_interested); });
		}
		if (frm.doc.student && !frm.doc.batch && frm.__student_course === undefined) {
			frappe.db.get_value("Student", frm.doc.student, ["course_interested", "enquiry"]).then((r) => {
				const v = r.message || {};
				if (v.course_interested) { frm.__student_course = v.course_interested; return; }
				if (!v.enquiry) { frm.__student_course = null; return; }
				frappe.db.get_value("Student Enquiry", v.enquiry, "course_interested").then((e) => { frm.__student_course = (e.message && e.message.course_interested) || null; });
			});
		}
	},
	on_submit(frm) {
		// the Sales Order link arrives from the server after submit; reload to show it
		frm.reload_doc().then(() => {
			if (frm.doc.sales_order) {
				frappe.msgprint({
					title: __("Enrolment complete"),
					indicator: "green",
					message: `${__("Sales Order")} <a href="/app/sales-order/${encodeURIComponent(frm.doc.sales_order)}"><b>${frm.doc.sales_order}</b></a> ${__("was created with")} ${(frm.doc.installments || []).length} ${__("instalment(s)")}.`,
					primary_action: { label: __("Open Sales Order"), action: () => frappe.set_route("Form", "Sales Order", frm.doc.sales_order) },
				});
			}
		});
	},
	batch(frm) {
		if (!frm.doc.batch) { frm.set_value({ batch_start: null, batch_end: null }); return; }
		if (frm.doc.student && frm.doc.docstatus === 0) {
			const picked = frm.doc.batch;
			frappe.call({ method: "tnc_v2_360ithub.tnc_v2.doctype.student_batch_enrollment.student_batch_enrollment.active_enrolments",
				args: { student: frm.doc.student, batch: picked } }).then((r) => {
				const a = r.message || {};
				const who = `<b>${frm.doc.student_name || frm.doc.student}</b>`;
				if (a.same_batch) {
					frappe.msgprint({ title: __("Already enrolled"), indicator: "red",
						message: __("{0} is already active in {1} ({2}). Choose another batch.", [who, `<b>${a.same_batch.batch}</b>`, a.same_batch.name]) });
					frm.set_value("batch", null);
					return;
				}
				if (a.same_course) {
					frappe.confirm(
						`<p>${__("{0} is already active in {1} of the same course.", [who, `<b>${a.same_course.batch}</b>`])}</p><p><b>${__("Is this a batch change?")}</b></p>`,
						() => { frm.set_value({ enrollment_type: "Batch Change", previous_enrollment: a.same_course.name }); },
						() => { frm.set_value("batch", null); }
					);
					return;
				}
				if (a.other && a.other.length) {
					const list = a.other.map((o) => `<b>${o.batch}</b> (${o.course_name || o.course})`).join(", ");
					frappe.confirm(
						`<p>${__("{0} is already active in {1}.", [who, list])}</p><p><b>${__("Enrol in {0} as well?", [`<b>${picked}</b>`])}</b></p>`,
						() => {},
						() => { frm.set_value("batch", null); }
					);
				}
			});
		}
		frappe.db.get_value("Student Batch", frm.doc.batch, ["starting_date", "actual_ending_date"]).then((r) => {
			const b = r.message || {};
			frm.set_value({ batch_start: b.starting_date || null, batch_end: b.actual_ending_date || null });
			frm.trigger("check_batch_window");
		});
	},
	standard_fee: (frm) => frm.trigger("recalc"),
	discount_type: (frm) => frm.trigger("recalc"),
	discount_value: (frm) => frm.trigger("recalc"),
	recalc(frm) {
		const fee = flt(frm.doc.standard_fee);
		let disc = 0;
		if (frm.doc.discount_type === "Percentage") disc = flt(fee * flt(frm.doc.discount_value) / 100, 2);
		else if (frm.doc.discount_type === "Amount") disc = flt(frm.doc.discount_value, 2);
		frm.set_value("discount_amount", disc);
		frm.set_value("net_payable", flt(fee - disc - flt(frm.doc.demo_fee_adjusted), 2));
		if ((frm.doc.installments || []).length) {
			frm.set_intro(__("Net Payable changed. Press Generate Instalments, or edit the rows so they add up."), "orange");
		}
	},
	regenerate(frm) {
		// only from the Generate Instalments button (or an empty table on save, server side)
		if (frm.doc.docstatus !== 0) return;
		frm.set_intro("", "blue");
		const n = Math.max(cint(frm.doc.number_of_installments) || 1, 1);
		const gap = cint(frm.doc.installment_gap_days) || 30;
		const start = frm.doc.first_due_date || frappe.datetime.get_today();
		const net = flt(frm.doc.net_payable);
		const base = flt(net / n, 2);
		frm.clear_table("installments");
		let running = 0;
		for (let i = 0; i < n; i++) {
			const amount = i === n - 1 ? flt(net - running, 2) : base;
			running += amount;
			const row = frm.add_child("installments");
			row.installment_no = i + 1;
			row.due_date = frappe.datetime.add_days(start, gap * i);
			row.amount = amount;
			row.description = __("Instalment {0} of {1}", [i + 1, n]);
		}
		frm.refresh_field("installments");
		frm.trigger("check_batch_window");
	},
	late_installments(frm) {
		if (!frm.doc.batch_end) return [];
		return (frm.doc.installments || []).filter((r) => r.due_date && r.due_date > frm.doc.batch_end);
	},
	check_batch_window(frm) {
		const $table = frm.get_field("instalment_check_html") && frm.get_field("instalment_check_html").$wrapper;
		const $note = frm.get_field("batch_window_note") && frm.get_field("batch_window_note").$wrapper;
		if (!$table || !$note) return;
		if (!frm.doc.batch_end) { $table.empty(); $note.empty(); return; }
		const end_user = frappe.datetime.str_to_user(frm.doc.batch_end);
		const late = frm.events.late_installments(frm);
		if (!late.length) {
			$note.html(`<div class="small" style="margin-top:6px;color:#166534">✓ ${__("Batch ends")} <b>${end_user}</b> · ${__("all instalments fall within the batch")}</div>`);
			$table.empty();
			return;
		}
		const last = late.map((r) => r.due_date).sort().pop();
		$note.html(`<div class="small" style="margin-top:6px;color:#991b1b"><b>⚠ ${__("Batch ends")} ${end_user}</b> · ${__("{0} instalment(s) go beyond it", [late.length])}</div>`);
		$table.html(`<div style="padding:8px 12px;border-radius:6px;background:#fee2e2;color:#991b1b;border:1px solid #fecaca">
			<b>⚠ ${__("Batch ends on {0}", [end_user])}.</b> ${__("{0} instalment(s) are due after that, the last on {1}.", [late.length, frappe.datetime.str_to_user(last)])}
			${__("Collect the fee within the batch unless this was agreed.")}</div>`);
	},
	before_submit(frm) {
		const late = frm.events.late_installments(frm);
		if (!late.length || frm.__batch_end_confirmed) { frm.__batch_end_confirmed = false; return; }
		frappe.validated = false;
		const end_user = frappe.datetime.str_to_user(frm.doc.batch_end);
		const last = frappe.datetime.str_to_user(late.map((r) => r.due_date).sort().pop());
		frappe.confirm(
			`<p>${__("Batch ends on {0}.", [`<b>${end_user}</b>`])}</p>
			 <p>${__("{0} instalment(s) are after this date. Last one is on {1}.", [`<b>${late.length}</b>`, `<b>${last}</b>`])}</p>
			 <p><b>${__("Are you sure you want to submit?")}</b></p>`,
			() => { frm.__batch_end_confirmed = true; frm.savesubmit(); },
			() => { frm.__batch_end_confirmed = false; }
		);
	},
});
frappe.ui.form.on("Enrollment Installment", {
	due_date(frm) { frm.trigger("check_batch_window"); },
	installments_remove(frm) { frm.trigger("check_batch_window"); },
	amount(frm) {
		const total = (frm.doc.installments || []).reduce((s, r) => s + flt(r.amount), 0);
		const diff = flt(flt(frm.doc.net_payable) - total, 2);
		if (Math.abs(diff) > 0.5) frm.set_intro(__("Instalments differ from Net Payable by {0}", [format_currency(diff, "INR")]), "orange");
		else frm.set_intro("", "blue");
	},
});
