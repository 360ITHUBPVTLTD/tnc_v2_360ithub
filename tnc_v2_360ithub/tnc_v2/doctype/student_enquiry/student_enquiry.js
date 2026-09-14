// Copyright (c) 2026, 360ITHub and contributors
frappe.ui.form.on("Student Enquiry", {
	refresh(frm) {
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
			frm.add_custom_button(__("Convert to Student"), () => frm.trigger("convert"), null).addClass("btn-primary");
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
				{ fieldname: "batch", fieldtype: "Link", label: __("Batch"), options: "Student Batch", reqd: 1,
				  description: frm.doc.course_interested ? __("Batches of {0}", [frm.doc.course_interested]) : __("Set Course Interested on the enquiry to narrow this list"),
				  get_query: () => ({ filters: Object.assign({ status: ["in", ["Upcoming", "Ongoing"]] }, frm.doc.course_interested ? { course: frm.doc.course_interested } : {}) }) },
				{ fieldname: "demo_date", fieldtype: "Date", label: __("Date"), reqd: 1, default: frappe.datetime.get_today() },
				{ fieldname: "from_time", fieldtype: "Time", label: __("From Time"), reqd: 1, onchange: () => show_duration() },
				{ fieldname: "to_time", fieldtype: "Time", label: __("To Time"), reqd: 1, onchange: () => show_duration() },
				{ fieldname: "duration_html", fieldtype: "HTML" },
			],
			primary_action_label: __("Schedule"),
			primary_action(values) {
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
});
