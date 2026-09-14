// Copyright (c) 2026, 360ITHub and contributors
// Follow-ups desk: Overdue / Today / Upcoming, mine or everyone's, with one-click outcome and payment.
frappe.pages["follow-ups"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Follow-ups"), single_column: true });
	const state = { scope: "mine", user: frappe.session.user, purpose: "", reference_type: null, reference_name: null, q: "" };
	const is_manager = frappe.user.has_role(["TNC Manager", "TNC Super Admin", "System Manager"]);

	const scope = page.add_field({ fieldname: "scope", fieldtype: "Select", label: __("Show"), options: is_manager ? "Mine\nEveryone\nOne counsellor" : "Mine", default: "Mine",
		change() { state.scope = { Mine: "mine", Everyone: "all", "One counsellor": "user" }[scope.get_value()]; user_field.$wrapper.toggle(state.scope === "user"); load(); } });
	const user_field = page.add_field({ fieldname: "user", fieldtype: "Link", label: __("Counsellor"), options: "User", change() { state.user = user_field.get_value(); load(); } });
	user_field.$wrapper.hide();
	const purpose = page.add_field({ fieldname: "purpose", fieldtype: "Select", label: __("Purpose"), options: "\nEnquiry\nFee\nGeneral", change() { state.purpose = purpose.get_value(); load(); } });
	const search = page.add_field({ fieldname: "q", fieldtype: "Data", label: __("Search"), placeholder: __("Name, mobile, batch, note..."),
		change() { state.q = (search.get_value() || "").trim().toLowerCase(); render(); } });
	search.$input && search.$input.on("input", frappe.utils.debounce(() => { state.q = (search.get_value() || "").trim().toLowerCase(); render(); }, 200));
	page.set_primary_action(__("Refresh"), load, "refresh");
	page.add_menu_item(__("Calendar view"), () => frappe.set_route("List", "Student Follow-Up", "Calendar", "default"));
	page.add_menu_item(__("All follow-ups (list)"), () => frappe.set_route("List", "Student Follow-Up"));

	const $body = $(`<div class="tnc-fu">
		<style>
		.tnc-fu{padding:8px 0} .tnc-fu .tabs{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap}
		.tnc-fu .tab{padding:6px 14px;border-radius:999px;border:1px solid #bfdbfe;background:#eff6ff;cursor:pointer;font-weight:600;font-size:12px;color:#1e3a8a}
		.tnc-fu .tab.active{background:#dbeafe;color:#1e3a8a;border-color:#93c5fd} .tnc-fu .tab .n{margin-left:6px;padding:1px 7px;border-radius:999px;background:#e5e7eb;color:#111;font-size:11px}
		.tnc-fu .tab .n{background:#fff;color:#111}
		.tnc-fu .tab.overdue .n{background:#fee2e2;color:#991b1b} .tnc-fu .tab.today .n{background:#ffedd5;color:#9a3412}
		.tnc-fu table{width:100%;border-collapse:collapse;border:1px solid #e5e7eb;background:#fff;font-size:13px}
		.tnc-fu th{background:#dbeafe;color:#1e3a8a;text-align:left;padding:10px;font-weight:700;border-bottom:1px solid #bfdbfe;white-space:nowrap}
		.tnc-fu td{padding:10px;border-bottom:1px solid #e5e7eb;vertical-align:middle}
		.tnc-fu .pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:600} .pill.Fee{background:#fee2e2;color:#991b1b} .pill.Enquiry{background:#e5e7eb;color:#111} .pill.General{background:#e5e7eb;color:#374151}
		.tnc-fu .acts{display:flex;gap:6px;flex-wrap:wrap} .tnc-fu .note{color:#475569;max-width:360px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
		.tnc-fu .empty{padding:24px;text-align:center;color:#64748b;border:1px dashed #d1d5db;border-radius:6px}
		.tnc-fu a.name{color:#111;font-weight:600;text-decoration:underline}
		.tnc-fu .contact a{margin-right:6px;font-size:12px;color:#374151}
		</style>
		<div class="tabs"></div><div class="list"></div></div>`).appendTo(page.body);

	let data = null, active = "overdue";
	const $chip = $(`<div class="tnc-chip" style="display:none;margin:0 0 10px"><span class="indicator-pill gray no-indicator-dot"></span> <a href="#" class="clear small">${__("show all")}</a></div>`).prependTo($body);
	$chip.find(".clear").on("click", (e) => { e.preventDefault(); state.reference_type = state.reference_name = null; $chip.hide(); load(); });
	function apply_route_options() {
		const ro = frappe.route_options || {};
		if (ro.reference_type && ro.reference_name) {
			state.reference_type = ro.reference_type; state.reference_name = ro.reference_name;
			$chip.find(".indicator-pill").text(`${ro.reference_type}: ${ro.reference_name}`); $chip.show();
		}
		frappe.route_options = null;
	}
	function load() {
		frappe.call({ method: "tnc_v2_360ithub.admissions.followups.get_pending", args: { scope: state.scope, user: state.user, purpose: state.purpose || null,
			reference_type: state.reference_type, reference_name: state.reference_name } }).then((r) => {
			data = r.message || {}; if (state.reference_type && !((data.overdue||[]).length) && (data.today||[]).length) active = "today"; render();
		});
	}
	$(wrapper).on("show", () => { apply_route_options(); load(); });
	function render() {
		const tabs = [["overdue", __("Overdue")], ["today", __("Today")], ["upcoming", __("Upcoming")], ["no_date", __("No date")]];
		const cnt = (k) => (data[k] || []).filter((r) => !state.q || [r.student_name, r.reference_name, r.mobile, r.notes, r.payment_term, r.sales_order, r.assigned_to, r.purpose].some((v) => (v || "").toString().toLowerCase().includes(state.q))).length;
		$body.find(".tabs").html(tabs.map(([k, l]) => `<span class="tab ${k} ${k === active ? "active" : ""}" data-k="${k}">${l}<span class="n">${cnt(k)}</span></span>`).join(""));
		$body.find(".tab").on("click", (e) => { active = $(e.currentTarget).data("k"); render(); });
		const match = (r) => !state.q || [r.student_name, r.reference_name, r.mobile, r.notes, r.payment_term, r.sales_order, r.assigned_to, r.purpose]
			.some((v) => (v || "").toString().toLowerCase().includes(state.q));
		const rows = (data[active] || []).filter(match);
		if (!rows.length) { $body.find(".list").html(`<div class="empty">${state.q ? __("No match for \"{0}\" in this tab.", [frappe.utils.escape_html(state.q)]) : __("Nothing here. Good.")}</div>`); return; }
		const fmt = (d) => d ? frappe.datetime.str_to_user(d) : "";
		const html = `<table><thead><tr><th>${__("Who")}</th><th>${__("Contact")}</th><th>${__("Purpose")}</th><th>${__("Last note")}</th><th>${__("Next")}</th><th>${__("Assigned")}</th><th></th></tr></thead><tbody>` +
			rows.map((r) => {
				const link = r.reference_type === "Student" ? `/app/student/${encodeURIComponent(r.reference_name)}` : `/app/student-enquiry/${encodeURIComponent(r.reference_name)}`;
				const mob = (r.mobile || "").replace(/\D/g, "");
				const contact = mob ? `<span class="contact"><a href="tel:${mob}">📞 ${r.mobile}</a><a href="https://wa.me/${mob.length === 10 ? "91" + mob : mob}" target="_blank">💬 WhatsApp</a></span>` : "";
				const fee = r.purpose === "Fee" ? `<div class="small text-muted">${r.payment_term || ""} · ${__("due")} ${fmt(r.instalment_due_date)} · <b class="text-danger">${format_currency(r.amount_pending, "INR")}</b></div>` : "";
				const acts = [`<a class="btn btn-xs btn-primary" data-act="log" data-name="${r.name}">${__("Log outcome")}</a>`];
				if (r.purpose === "Fee" && r.sales_order) acts.push(`<a class="btn btn-xs btn-default" data-act="pay" data-so="${r.sales_order}" data-amount="${r.amount_pending}" data-label="${r.payment_term || ""}">${__("Receive Payment")}</a>`);
				if (r.reference_type === "Student Enquiry") acts.push(`<a class="btn btn-xs btn-default" href="${link}">${__("Open")}</a>`);
				else acts.push(`<a class="btn btn-xs btn-default" href="${link}">${__("Student")}</a>`);
				return `<tr><td><a class="name" href="${link}">${frappe.utils.escape_html(r.student_name || r.reference_name)}</a><div class="small text-muted">${r.reference_type === "Student" ? __("Student") : __("Enquiry")} ${r.reference_name}</div></td>
					<td>${contact}</td><td><span class="pill ${r.purpose}">${r.purpose}</span>${fee}</td>
					<td class="note" title="${frappe.utils.escape_html(r.notes || "")}">${frappe.utils.escape_html((r.notes || "").split("\n").pop())}</td>
					<td>${fmt(r.next_follow_up_date)}</td><td class="small">${frappe.user.full_name(r.assigned_to) || r.assigned_to || ""}</td><td><div class="acts">${acts.join("")}</div></td></tr>`;
			}).join("") + "</tbody></table>";
		$body.find(".list").html(html);
		$body.find("[data-act=log]").on("click", (e) => log_outcome($(e.currentTarget).data("name")));
		$body.find("[data-act=pay]").on("click", (e) => {
			const $b = $(e.currentTarget);
			if (window.tnc && tnc.admissions && tnc.admissions.receive_payment) {
				tnc.admissions.receive_payment({ sales_order: $b.data("so"), amount: $b.data("amount"), label: $b.data("label"), on_done: load });
			} else {
				frappe.set_route("Form", "Sales Order", $b.data("so"));
			}
		});
	}
	function log_outcome(name) {
		const d = new frappe.ui.Dialog({
			title: __("Log outcome"),
			fields: [
				{ fieldname: "followup_type", fieldtype: "Select", label: __("How"), options: "Call\nWhatsApp\nMessage\nEmail\nMeeting", default: "Call" },
				{ fieldname: "notes", fieldtype: "Small Text", label: __("What was said"), reqd: 1 },
				{ fieldname: "next_follow_up_date", fieldtype: "Date", label: __("Next follow-up on"), description: __("Leave empty if no further follow-up is needed") },
				{ fieldname: "lost", fieldtype: "Check", label: __("Mark enquiry Lost") },
				{ fieldname: "lost_reason", fieldtype: "Select", label: __("Lost reason"), depends_on: "eval:doc.lost", options: "\nFee too high\nJoined another institute\nNot interested now\nNo response\nTiming or location\nCourse not suitable\nOther" },
			],
			primary_action_label: __("Save"),
			primary_action(v) {
				frappe.call({ method: "tnc_v2_360ithub.admissions.followups.log_outcome", args: { name, ...v, close: 1 }, freeze: true }).then(() => {
					d.hide(); frappe.show_alert({ message: __("Saved"), indicator: "green" }); load();
				});
			},
		});
		d.show();
	}
	apply_route_options();
	load();
};
