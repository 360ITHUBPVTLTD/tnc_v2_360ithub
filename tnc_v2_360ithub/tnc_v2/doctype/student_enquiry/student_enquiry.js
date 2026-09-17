// Copyright (c) 2026, 360ITHub and contributors
frappe.ui.form.on("Student Enquiry", {
	refresh(frm) {
		if (frm.__demo_fee_amount === undefined) frappe.db.get_single_value("TNC Settings", "demo_fee_amount").then((v) => { frm.__demo_fee_amount = flt(v) || 500; });
		frm.trigger("render_overview");
		if (frm.is_new()) return;
		if (!frm.is_new() && frm.doc.status !== "Converted" && frm.doc.status !== "Lost") {
			frappe.call({ method: "tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry.admission_form_status", args: { enquiry: frm.doc.name } }).then((r) => {
				const m = r.message || {};
				frm.dashboard.clear_headline();
				if (m.pending) {
					frm.dashboard.set_headline(`<span class="indicator-pill green no-indicator-dot">${__("Admission form received")}</span> &nbsp;
						<a href="/app/admission-form/${m.pending.name}"><b>${m.pending.name}</b></a> · ${__("consent accepted")} ${frappe.datetime.str_to_user(m.pending.accepted_on)} ·
						<b>${__("Convert to Student will use it.")}</b>`);
				}
				const $btn = frm.add_custom_button(__("Send Admission Form"), () => {
					frappe.call({ method: "tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry.admission_link_preview", args: { enquiry: frm.doc.name }, freeze: true, freeze_message: __("Checking WhatsApp instance...") })
					.then((rr) => {
						const p = rr.message || {}; const i = p.instance || {};
						const pill = (ok, on, off) => `<span class="indicator-pill ${ok ? "green" : "red"} no-indicator-dot">${ok ? on : off}</span>`;
						const card = `<div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px 14px;margin-bottom:8px">
							<div style="font-weight:600;margin-bottom:6px">${frappe.utils.escape_html(i.label || i.name || __("Default Instance"))}</div>
							<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;font-size:13px">
								${pill(i.connected, __("Connected"), __("Not connected"))} ${pill(i.active, __("Active"), __("Inactive"))}
								<span>${__("Credits")}: <b>${i.credits || 0}</b></span>${i.number ? `<span>${__("Number")}: <b>${frappe.utils.escape_html(i.number)}</b></span>` : ""}
							</div>
							${i.ok ? "" : `<div class="text-danger small" style="margin-top:6px">${frappe.utils.escape_html(i.msg || __("Cannot send from the institute number right now."))}</div>`}
						</div>`;
						const wa = (n) => `https://wa.me/${n.length === 10 ? "91" + n : n}?text=`;
						const d = new frappe.ui.Dialog({
							title: __("Send WhatsApp"),
							fields: [
								{ fieldtype: "HTML", fieldname: "card", options: card },
								{ fieldtype: "Data", fieldname: "mobile", label: __("Recipient Mobile Number (10 digits)"), reqd: 1, default: p.mobile },
								{ fieldtype: "Small Text", fieldname: "message", label: __("Message"), default: p.message, description: __("The admission form link is added automatically at the end of the message.") },
								{ fieldtype: "HTML", fieldname: "alt", options: i.ok ? "" : `<div class="small text-muted" style="margin-top:4px">${__("Or send it from your own phone:")} <a class="btn btn-xs btn-success alt-wa" target="_blank">💬 WhatsApp</a> <a class="btn btn-xs btn-default alt-cp">${__("Copy link")}</a></div>` },
							],
							primary_action_label: __("Confirm and Send"),
							primary_action(v) {
								const digits = (v.mobile || "").replace(/\D/g, "");
								if (digits.length < 10) { frappe.msgprint(__("Please enter a valid 10-digit mobile number.")); return; }
								frappe.call({ method: "tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry.send_admission_link", args: { enquiry: frm.doc.name, mobile: digits, message: v.message }, freeze: true, freeze_message: __("Sending...") })
								.then((r2) => {
									const x = r2.message || {};
									if (x.status === "Sent") { d.hide(); frappe.show_alert({ message: __("Sent on WhatsApp to {0}", [x.mobile]), indicator: "green" }, 6); frm.reload_doc(); }
									else { frappe.msgprint({ title: __("Not sent"), indicator: "red", message: `${frappe.utils.escape_html(x.reason || x.status)}<br><a class="btn btn-sm btn-success" target="_blank" href="${wa(x.mobile || digits)}${encodeURIComponent(x.message || x.link)}">💬 ${__("Send from my phone")}</a>` }); }
								});
							},
						});
						d.show();
						if (!i.ok) {
							d.get_primary_btn().prop("disabled", true).attr("title", i.msg || "");
							d.$wrapper.find(".alt-wa").attr("href", wa(p.mobile || "") + encodeURIComponent((p.message || "") + "\n\n" + p.link));
							d.$wrapper.find(".alt-cp").on("click", () => frappe.utils.copy_to_clipboard(p.link));
						}
					});
				});
				$btn.removeClass("btn-default").css({ background: "#dcfce7", color: "#166534", "border-color": "#86efac", "font-weight": "600" });
			});
		}
		if (frm.doc.status === "Lost") {
			frm.add_custom_button(__("Reopen"), () => {
				frappe.confirm(
					`<p>${__("This enquiry was marked Lost on {0} ({1}).", [`<b>${frappe.datetime.str_to_user(frm.doc.lost_on)}</b>`, frm.doc.lost_reason || ""])}</p><p><b>${__("Are you sure you want to reopen it?")}</b></p>`,
					() => frappe.call({ method: "tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry.reopen", args: { enquiry: frm.doc.name },
						callback: () => { frm.reload_doc(); frappe.show_alert({ message: __("Enquiry reopened"), indicator: "green" }); } })
				);
			});
		} else if (frm.doc.status !== "Converted") {
			frm.add_custom_button(__("Schedule Demo"), () => frm.trigger("schedule_demo"));
			frm.add_custom_button(__("Admit"), () => frm.trigger("admit"), null).addClass("btn-primary");
			frm.add_custom_button(__("Convert to Student only"), () => frm.trigger("convert"), __("More"));
			frm.add_custom_button(__("Mark Lost"), () => frm.trigger("mark_lost"));
		} else if (frm.doc.student) {
			frm.add_custom_button(__("Open Student"), () => frappe.set_route("Form", "Student", frm.doc.student)).addClass("btn-primary");
		}
		frm.add_custom_button(__("Add Follow-up"), () => {
			frappe.new_doc("Student Follow-Up", { reference_type: "Student Enquiry", reference_name: frm.doc.name });
		});
		frm.add_custom_button(__("Follow-ups page"), () => { frappe.route_options = { reference_type: "Student Enquiry", reference_name: frm.doc.name }; frappe.set_route("follow-ups"); });
	},
	mark_lost(frm) {
		const d = new frappe.ui.Dialog({
			title: __("Mark Enquiry as Lost"),
			fields: [
				{ fieldname: "reason", fieldtype: "Select", label: __("Reason"), reqd: 1,
				  options: "\nFee too high\nJoined another institute\nNot interested now\nNo response\nTiming or location\nCourse not suitable\nOther" },
				{ fieldname: "note", fieldtype: "Small Text", label: __("Note") },
				{ fieldtype: "HTML", options: `<div class="text-muted small">${__("Open follow-ups will be closed and scheduled demos cancelled. You can reopen later.")}</div>` },
			],
			primary_action_label: __("Mark Lost"),
			primary_action(values) {
				frappe.call({
					method: "tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry.mark_lost",
					args: { enquiry: frm.doc.name, ...values },
					callback: (r) => {
						d.hide(); frm.reload_doc();
						const m = r.message || {};
						frappe.show_alert({ indicator: "red", message: __("Marked Lost. {0} follow-up(s) closed, {1} demo(s) cancelled.", [m.closed_follow_ups || 0, m.cancelled_demos || 0]) }, 6);
					},
				});
			},
		});
		d.show();
	},
	mobile(frm) {
		if (!frm.doc.mobile || frm.doc.mobile.replace(/\D/g, "").length < 10) return;
		frappe.call({ method: "tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry.check_duplicates",
			args: { mobile: frm.doc.mobile, exclude_enquiry: frm.doc.name } }).then((r) => {
			const m = r.message || {}; const parts = [];
			(m.students || []).forEach((s) => parts.push(`${__("Student")} <a href="/app/student/${s.name}"><b>${s.student_name}</b></a> (${s.status})`));
			(m.enquiries || []).forEach((e) => parts.push(`${__("Open enquiry")} <a href="/app/student-enquiry/${e.name}"><b>${e.student_name}</b></a> (${e.status})`));
			if (parts.length) frm.set_intro(`⚠ ${__("This mobile is already on file:")} ${parts.join(" · ")}`, "orange");
			else frm.set_intro("", "blue");
		});
	},
	schedule_demo(frm) {
		const to_sec = (t) => { if (!t) return null; const p = t.split(":").map(Number); return p[0] * 3600 + (p[1] || 0) * 60 + (p[2] || 0); };
		const show_duration = () => {
			const a = to_sec(d.get_value("from_time")), b = to_sec(d.get_value("to_time"));
			const $w = d.get_field("duration_html").$wrapper;
			if (a === null || b === null) { $w.empty(); return; }
			if (b <= a) { $w.html(`<div class="text-danger small">${__("To Time must be after From Time")}</div>`); return; }
			const m = Math.round((b - a) / 60), h = Math.floor(m / 60), mm = m % 60;
			$w.html(`<div class="small" style="padding:6px 10px;border-radius:6px;background:#dbeafe;color:#1e40af;display:inline-block"><b>${__("Duration")}:</b> ${h ? h + " h " : ""}${mm} min</div>`);
		};
		const d = new frappe.ui.Dialog({
			title: __("Schedule Demo Class"),
			fields: [
				{ fieldname: "batch", fieldtype: "Link", label: __("Batch"), options: "Student Batch", reqd: 1, default: frm.doc.batch_interested || undefined,
				  description: frm.doc.course_interested ? __("Batches of {0}", [frm.doc.course_interested]) : __("Open batches"),
				  get_query: () => ({ filters: Object.assign({ status: ["in", ["Upcoming", "Ongoing"]] }, frm.doc.course_interested ? { course: frm.doc.course_interested } : {}) }) },
				{ fieldname: "demo_date", fieldtype: "Date", label: __("Date"), reqd: 1, default: frappe.datetime.get_today() },
				{ fieldname: "from_time", fieldtype: "Time", label: __("From Time"), reqd: 1, onchange: () => show_duration() },
				{ fieldname: "to_time", fieldtype: "Time", label: __("To Time"), reqd: 1, onchange: () => show_duration() },
				{ fieldname: "duration_html", fieldtype: "HTML" },
				{ fieldname: "sb_fee", fieldtype: "Section Break", label: __("Demo fee") },
				{ fieldname: "collect_fee", fieldtype: "Check", label: __("Collect demo fee now"), default: 0 },
				{ fieldname: "fee_amount", fieldtype: "Currency", label: __("Amount"), depends_on: "collect_fee", default: frm.__demo_fee_amount || 500 },
				{ fieldname: "cb_fee", fieldtype: "Column Break" },
				{ fieldname: "mode_of_payment", fieldtype: "Link", label: __("Mode"), options: "Mode of Payment", default: "Cash", depends_on: "collect_fee", get_query: () => ({ filters: { enabled: 1 } }) },
				{ fieldname: "reference_no", fieldtype: "Data", label: __("Reference No"), depends_on: "eval:doc.collect_fee && doc.mode_of_payment && doc.mode_of_payment !== 'Cash'" },
			],
			primary_action_label: __("Schedule"),
			primary_action(values) {
				if (values.collect_fee && values.mode_of_payment !== "Cash" && !values.reference_no) { frappe.msgprint(__("Reference number is required for {0}", [values.mode_of_payment])); return; }
				frappe.call({
					method: "tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry.schedule_demo",
					args: { enquiry: frm.doc.name, ...values },
					callback: () => { d.hide(); frm.reload_doc(); frappe.show_alert({ message: __("Demo scheduled"), indicator: "green" }); },
				});
			},
		});
		d.show();
	},
	convert(frm) {
		frappe.call({ method: "tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry.check_duplicates",
			args: { mobile: frm.doc.mobile, exclude_enquiry: frm.doc.name } }).then((r) => {
			const st = (r.message && r.message.students) || [];
			if (!st.length) return frm.trigger("convert_new");
			const s = st[0];
			const d2 = new frappe.ui.Dialog({
				title: __("Student already exists"),
				fields: [{ fieldtype: "HTML", options: `<p>${__("A student with mobile {0} already exists:", [`<b>${frm.doc.mobile}</b>`])}</p>
					<p style="padding:8px 12px;border-radius:6px;background:#dbeafe"><b>${s.student_name}</b> · ${s.name} · ${s.status}</p>
					<p>${__("Is this the same person?")}</p>` }],
				primary_action_label: __("Yes, link this student"),
				primary_action() {
					frappe.call({ method: "tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry.convert_to_student",
						args: { enquiry: frm.doc.name, link_student: s.name }, freeze: true,
						callback: (rr) => { d2.hide(); frappe.show_alert({ message: __("Linked to {0}", [rr.message]), indicator: "green" }); frappe.set_route("Form", "Student", rr.message); } });
				},
				secondary_action_label: __("No, create a new student"),
				secondary_action() { d2.hide(); frm.trigger("convert_new"); },
			});
			d2.show();
		});
	},
	convert_new(frm) {
		const d = new frappe.ui.Dialog({
			title: __("Convert to Student"),
			fields: [
				{ fieldtype: "HTML", options: `<p class="text-muted">${__("Name, mobile, email, gender and city are copied from this enquiry. Add only what is new.")}</p>` },
				{ fieldname: "date_of_birth", fieldtype: "Date", label: __("Date of Birth") },
				{ fieldname: "gender", fieldtype: "Select", label: __("Gender"), options: "\nMale\nFemale\nOther", default: frm.doc.gender },
				{ fieldname: "aadhar_number", fieldtype: "Data", label: __("Aadhaar Number") },
				{ fieldname: "fathers_name", fieldtype: "Data", label: __("Father's Name") },
				{ fieldname: "guardian_mobile", fieldtype: "Data", label: __("Guardian Mobile") },
			],
			primary_action_label: __("Create Student"),
			primary_action(values) {
				frappe.call({
					method: "tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry.convert_to_student",
					args: { enquiry: frm.doc.name, extra: values },
					freeze: true,
					callback: (r) => { d.hide(); frappe.show_alert({ message: __("Student {0} created", [r.message]), indicator: "green" }); frappe.set_route("Form", "Student", r.message); },
				});
			},
		});
		d.show();
	},
	render_overview(frm) {
		const $w = frm.get_field("overview").$wrapper;
		if (frm.is_new()) { $w.empty(); return; }
		frappe.call({
			method: "tnc_v2_360ithub.admissions.api.get_enquiry_overview",
			args: { enquiry: frm.doc.name },
			callback: (r) => r.message && $w.html(r.message.html),
		});
	},
	admit(frm) {
		if (frm.is_dirty()) { frappe.msgprint(__("Please save the enquiry first.")); return; }
		const A = "tnc_v2_360ithub.admissions.admit.";
		const money = (n) => format_currency(flt(n), "INR");
		const dt = (x) => (x ? frappe.datetime.str_to_user(x) : "");
		const st = { plan: null, link_student: null, busy: false, generated: false };
		const CSS = `<style>
		.adm-sum{box-sizing:border-box;width:100%;padding:14px 16px;border:1px solid #dbeafe;border-radius:10px;background:#f8fbff;font-size:13.5px;overflow:hidden}
		.adm-sum .row{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding:7px 2px;border-bottom:1px solid #e8eef7;margin:0}.adm-sum .row:last-of-type{border-bottom:0}
		.adm-sum .l{color:#64748b;white-space:nowrap}.adm-sum .v{font-weight:600;text-align:right;white-space:nowrap}.adm-sum .big{background:#dbeafe;border-radius:6px;padding:8px 10px;margin:4px -2px}.adm-sum .big .v{font-size:18px;color:#1e3a8a}.adm-sum .minus .v{color:#b91c1c}
		.adm-dlg .modal-dialog{max-width:min(1400px,96vw)!important;width:96vw}.adm-dlg .modal-body{padding:14px 22px 6px}
		.adm-dlg .form-section .section-head{font-weight:700;color:#1e3a8a;background:#dbeafe;display:inline-block;padding:3px 10px;border-radius:6px;font-size:12px;letter-spacing:.06em;text-transform:uppercase}
		.adm-dlg .frappe-control[data-fieldname="regenerate"] .btn{margin-top:24px;background:#1e3a8a;color:#fff;border:0;font-weight:600}
		.adm-dlg .form-grid .grid-heading-row{background:#dbeafe!important;border-bottom:1px solid #bfdbfe}
		.adm-dlg .form-grid .grid-heading-row .grid-static-col,.adm-dlg .form-grid .grid-heading-row .row-index{color:#1e3a8a!important;font-weight:700}

		.adm-top{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:4px}
		.adm-send{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;font-weight:600;color:#15803d;background:#dcfce7;border:1px solid #86efac;border-radius:999px;padding:3px 12px 3px 8px;cursor:pointer;margin-bottom:8px}
		.adm-send input{accent-color:#15803d;width:15px;height:15px;margin:0}
		.adm-chip{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11.5px;font-weight:600;background:#dbeafe;color:#1e3a8a;margin:0 6px 8px 0}.adm-chip.g{background:#dcfce7;color:#15803d}.adm-chip.o{background:#ffedd5;color:#9a3412}
		</style>`;
		const rows_from_table = () => (d.get_value("installments") || []).filter((r) => r.due_date || flt(r.amount)).map((r) => ({ due_date: r.due_date, amount: flt(r.amount), description: r.description }));
		const recalc = frappe.utils.debounce(() => {
			const v = d.get_values(true) || {};
			if (!v.batch) { d.fields_dict.summary.$wrapper.html(CSS + `<div class="adm-sum text-muted">${__("Choose a batch to see the fee plan.")}</div>`); return; }
			const rows = st.generated ? rows_from_table() : null;
			frappe.call({ method: A + "plan", args: { enquiry: frm.doc.name, batch: v.batch, number_of_installments: v.number_of_installments, installment_gap_days: v.installment_gap_days,
				first_due_date: v.first_due_date, discount_type: v.discount_type, discount_value: v.discount_value, discount_reason: v.discount_reason, gst_applicable: v.gst_applicable,
				installments: rows && rows.length ? JSON.stringify(rows) : null } }).then((r) => {
				st.plan = r.message; d.set_value("standard_fee", st.plan.fee);
				d.fields_dict.batch_dates.$wrapper.html(st.plan.batch_start ? `<div class="small" style="margin:-4px 0 10px;padding:6px 10px;border-radius:6px;background:#dbeafe;color:#1e3a8a;display:inline-block"><b>${__("Batch")}:</b> ${dt(st.plan.batch_start)} → ${dt(st.plan.batch_end)}</div>` : "");
				if (!st.generated) { fill_table(st.plan.rows); st.generated = true; }
				render_check(st.plan); render_summary(st.plan);
			});
		}, 250);
		const regenerate = () => { st.generated = false; recalc(); };
		function fill_table(rows) {
			const grid = d.fields_dict.installments;
			grid.df.data = rows.map((r) => ({ installment_no: r.installment_no, due_date: r.due_date, amount: r.amount, description: r.description }));
			grid.grid.refresh();
		}
		function render_check(p) {
			const $w = d.fields_dict.instalment_check_html.$wrapper;
			const late = p.rows.filter((r) => r.beyond_batch);
			d.fields_dict.confirm_beyond_batch.toggle(late.length > 0);
			if (!p.batch_end) { $w.empty(); return; }
			const end_user = dt(p.batch_end);
			const errors = p.warnings.filter((w) => w.kind === "error").map((w) => `<div style="padding:8px 12px;border-radius:6px;background:#fee2e2;color:#7f1d1d;border:1px solid #fca5a5;font-weight:600;margin-top:6px">${w.text}</div>`).join("");
			if (!late.length) { $w.html(`<div class="small" style="color:#166534">✓ ${__("Batch runs {0} to {1}", [`<b>${dt(p.batch_start)}</b>`, `<b>${end_user}</b>`])} · ${__("all instalments fall within the batch")}</div>${errors}`); return; }
			const last = late.map((r) => r.due_date).sort().pop();
			$w.html(`<div style="padding:8px 12px;border-radius:6px;background:#fee2e2;color:#991b1b;border:1px solid #fecaca"><b>⚠ ${__("Batch ends on {0}", [end_user])}.</b> ${__("{0} instalment(s) are due after that, the last on {1}.", [late.length, dt(last)])} ${__("Collect the fee within the batch unless this was agreed.")}</div>${errors}`);
		}
		function render_summary(p) {
			const row = (l, v, cls = "") => `<div class="row ${cls}"><span class="l">${l}</span><span class="v">${v}</span></div>`;
			const first = p.rows[0], last = p.rows[p.rows.length - 1];
			d.fields_dict.summary.$wrapper.html(CSS + `<div class="adm-sum">
				${row(__("Standard fee"), money(p.fee))}${p.discount ? row(__("Discount"), "− " + money(p.discount), "minus") : ""}${p.demo_fee ? row(__("Demo fee already paid"), "− " + money(p.demo_fee), "minus") : ""}
				${row(__("Net payable"), money(p.net))}${p.gst ? row(__("GST"), "+ " + money(p.gst)) : ""}${row(__("Total payable"), money(p.grand_total), "big")}
				${row(__("Instalments"), `${p.rows.length} · ${dt(first && first.due_date)} → ${dt(last && last.due_date)}`)}
				<div class="small text-muted" style="margin-top:8px">${__("Fees are received afterwards from the student's Payments tab.")}</div></div>`);
			d.get_primary_btn().prop("disabled", !p.can_admit);
		}
		const d = new frappe.ui.Dialog({
			title: __("Admit {0}", [frm.doc.student_name || frm.doc.mobile]),
			size: "extra-large",
			fields: [
				{ fieldname: "chips", fieldtype: "HTML" },
				{ fieldtype: "Section Break", label: __("Batch and fee") },
				{ fieldname: "batch", fieldtype: "Link", label: __("Batch"), options: "Student Batch", reqd: 1, default: frm.doc.batch_interested || undefined, get_query: () => ({ filters: { status: ["in", ["Upcoming", "Ongoing"]] } }), onchange: regenerate },
				{ fieldname: "standard_fee", fieldtype: "Currency", label: __("Standard fee"), read_only: 1 },
				{ fieldname: "batch_dates", fieldtype: "HTML" },
				{ fieldname: "discount_type", fieldtype: "Select", label: __("Discount"), options: "\nAmount\nPercentage", onchange: regenerate },
				{ fieldname: "discount_value", fieldtype: "Float", label: __("Discount value"), depends_on: "discount_type", onchange: regenerate },
				{ fieldname: "discount_reason", fieldtype: "Data", label: __("Discount reason"), depends_on: "discount_type", mandatory_depends_on: "discount_type" },
				{ fieldname: "gst_applicable", fieldtype: "Check", label: __("GST applicable"), onchange: recalc },
				{ fieldtype: "Column Break" },
				{ fieldname: "summary", fieldtype: "HTML" },
				{ fieldtype: "Section Break", label: __("Instalments") },
				{ fieldname: "number_of_installments", fieldtype: "Int", label: __("Number of instalments"), default: 1 },
				{ fieldtype: "Column Break" },
				{ fieldname: "installment_gap_days", fieldtype: "Int", label: __("Days between instalments"), default: 30 },
				{ fieldtype: "Column Break" },
				{ fieldname: "first_due_date", fieldtype: "Date", label: __("First due date"), default: frappe.datetime.get_today() },
				{ fieldtype: "Column Break" },
				{ fieldname: "regenerate", fieldtype: "Button", label: __("Generate Instalments"), click: regenerate },
				{ fieldtype: "Section Break" },
				{ fieldname: "grid_note", fieldtype: "HTML", options: `<div class="text-muted small" style="margin-bottom:4px">${__("Edit any amount or date; the total must equal Net Payable.")}</div>` },
				{ fieldname: "installments", fieldtype: "Table", label: "", cannot_add_rows: false, in_place_edit: true, data: [], get_data: () => d.fields_dict.installments.df.data,
				  fields: [
					{ fieldname: "installment_no", fieldtype: "Int", label: __("No"), read_only: 1 },
					{ fieldname: "due_date", fieldtype: "Date", label: __("Due Date"), in_list_view: 1, reqd: 1, columns: 3 },
					{ fieldname: "amount", fieldtype: "Currency", label: __("Amount"), in_list_view: 1, reqd: 1, columns: 3 },
					{ fieldname: "description", fieldtype: "Data", label: __("Description"), in_list_view: 1, columns: 4 },
				  ] },
				{ fieldname: "instalment_check_html", fieldtype: "HTML" },
				{ fieldname: "confirm_beyond_batch", fieldtype: "Check", label: __("Some instalments fall after the batch ends. I know, continue."), hidden: 1 },
			],
			primary_action_label: __("Admit now"),
			primary_action(v) {
				if (st.busy || !st.plan) return;
				if (v.discount_type && !(v.discount_reason || "").trim()) { frappe.msgprint(__("Please give the reason for the discount.")); return; }
				if (st.plan.rows.some((r) => r.beyond_batch) && !v.confirm_beyond_batch) { frappe.msgprint(__("Some instalments fall after the batch ends. Tick 'I know, continue' or change the dates.")); return; }
				const rows = rows_from_table();
				if (!rows.length) { frappe.msgprint(__("Press Generate Instalments first.")); return; }
				st.busy = true;
				frappe.call({ method: A + "admit", args: { enquiry: frm.doc.name, link_student: st.link_student, batch: v.batch, discount_type: v.discount_type, discount_value: v.discount_value, discount_reason: v.discount_reason,
					gst_applicable: v.gst_applicable, number_of_installments: rows.length, installment_gap_days: v.installment_gap_days, first_due_date: v.first_due_date, send_form: d.fields_dict.chips.$wrapper.find(".send-form").is(":checked") ? 1 : 0,
					confirm_beyond_batch: v.confirm_beyond_batch, installments: JSON.stringify(rows) }, freeze: true, freeze_message: __("Admitting...") }).then((res) => {
					st.busy = false; d.hide(); const x = res.message;
					const line = (l, val) => `<tr><td class="text-muted" style="padding:4px 12px 4px 0">${l}</td><td style="padding:4px 0"><b>${val}</b></td></tr>`;
					frappe.msgprint({ title: __("Admitted"), indicator: "green", message: `<table>
						${line(__("Student"), `<a href="/app/student/${x.student}">${x.student}</a>`)}${line(__("Enrolment"), `<a href="/app/student-batch-enrollment/${x.enrollment}">${x.enrollment}</a>`)}
						${line(__("Fee order"), `<a href="/app/sales-order/${x.sales_order}">${x.sales_order}</a> · ${money(x.grand_total)}`)}${x.demo_fee_adjusted ? line(__("Demo fee adjusted"), money(x.demo_fee_adjusted)) : ""}
						${line(__("To collect"), money(x.pending) + ` · <span class="text-muted">${__("Receive Payment from the student's Payments tab")}</span>`)}
						${x.form_sent ? line(__("Admission form"), x.form_sent.status === "Sent" ? __("link sent on WhatsApp") : __("link not sent: {0}", [frappe.utils.escape_html(x.form_sent.reason || x.form_sent.status)])) : ""}</table>`,
						primary_action: { label: __("Open Student"), action: () => frappe.set_route("Form", "Student", x.student) } });
					frm.reload_doc();
				}).catch(() => { st.busy = false; });
			},
		});
		d.$wrapper.addClass("adm-dlg"); d.$wrapper.find(".modal-dialog").css({ "max-width": "min(1400px, 96vw)", width: "96vw" });
		$(document.head).find("#adm-dlg-css").remove(); $(CSS).attr("id", "adm-dlg-css").appendTo(document.head);
		// the table's rows drive the summary and the batch check
		d.fields_dict.installments.grid.wrapper.on("change", () => { if (st.generated) recalc(); });
		frappe.call({ method: A + "preview", args: { enquiry: frm.doc.name } }).then((r) => {
			const p = r.message || {};
			d.fields_dict.chips.$wrapper.html(CSS + `<div class="adm-top"><div>${p.demo_fee_paid ? `<span class="adm-chip g">${__("Demo fee paid {0}", [money(p.demo_fee_paid)])}</span>` : ""}${p.form_received ? `<span class="adm-chip g">${__("Admission form received")}</span>` : `<span class="adm-chip o">${__("Form not submitted by student")}</span>`}<span class="adm-chip">${__("Counsellor")}: ${p.counsellor || "—"}</span></div>
				${p.form_received ? "" : `<label class="adm-send"><input type="checkbox" class="send-form" checked> 💬 ${__("Send admission form on WhatsApp to get the student's details")}</label>`}</div>`);
			const dup = p.duplicate_students || [];
			const show = () => { d.show(); recalc(); };
			if (!dup.length) return show();
			const s = dup[0];
			frappe.confirm(`${__("A student with mobile {0} already exists:", [`<b>${p.mobile}</b>`])}<p style="padding:8px 12px;border-radius:6px;background:#dbeafe"><b>${s.student_name}</b> · ${s.name} · ${s.status}</p>${__("Admit this same person into a batch?")}`,
				() => { st.link_student = s.name; show(); }, show);
		});
	},
});
