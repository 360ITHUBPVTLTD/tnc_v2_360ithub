// Copyright (c) 2026, 360ITHub and contributors
// Fee Overview: every student's fee position (from the enrolment Sales Order's instalments), who is overdue,
// who is on Fee Hold, with Receive Payment / Remind / Hold / Release in the row. Same look as Enquiry Overview.
frappe.pages["fee-overview"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Fee Overview"), single_column: true });
	const API = "tnc_v2_360ithub.admissions.fee_overview.";
	const esc = frappe.utils.escape_html;
	const state = { batch: null, counsellor: null, span: "month", from: null, to: null };
	let manager = frappe.user.has_role(["TNC Manager", "TNC Super Admin", "System Manager"]);
	const canHold = frappe.user.has_role(["TNC Counsellor", "TNC Manager", "TNC Super Admin", "System Manager"]);

	const fBatch = page.add_field({ fieldname: "batch", label: __("Batch"), fieldtype: "Select", options: [{ value: "", label: __("All batches") }], change() { state.batch = fBatch.get_value() || null; load(); } });
	frappe.call("tnc_v2_360ithub.admissions.enquiry_overview.batch_options").then(r => {
		fBatch.df.options = [{ value: "", label: __("All batches") }, ...(r.message || [])];
		fBatch.refresh();
		if (state.batch) fBatch.set_value(state.batch);
	});
	const fCoun = page.add_field({ fieldname: "counsellor", label: __("Counsellor"), fieldtype: "Link", options: "User", change() { state.counsellor = fCoun.get_value() || null; load(); },
		get_query: () => ({ query: "frappe.core.doctype.user.user.user_query", filters: { ignore_user_type: 1 } }) });
	fCoun.$wrapper.toggle(manager);
	if (!manager) frappe.xcall("tnc_v2_360ithub.admissions.enquiry_overview.sees_all").then(v => { if (v) { manager = true; fCoun.$wrapper.show(); } });
	// period of the "Collected" tile (receipts dated in it); everything else on the page is the position as of today
	const SPANS = { month: __("This month"), today: __("Today"), week: __("This week"), last_month: __("Last month"), m3: __("Last 3 months"), all: __("All time"), custom: __("Custom dates") };
	const fSpan = page.add_field({ fieldname: "span", label: __("Collected in"), fieldtype: "Select", options: Object.keys(SPANS).map(k => ({ value: k, label: SPANS[k] })), default: "month", change() {
		const k = fSpan.get_value() || "month", today = frappe.datetime.get_today();
		fPeriod.$wrapper.toggle(k === "custom");
		if (k === "custom") { fromRange(); return; }
		state.span = k;
		const lm = frappe.datetime.add_months(frappe.datetime.month_start(), -1);
		state.from = k === "today" ? today : k === "week" ? frappe.datetime.week_start() : k === "last_month" ? lm : k === "m3" ? frappe.datetime.add_months(today, -3) : k === "all" ? "2000-01-01" : null;
		state.to = k === "last_month" ? frappe.datetime.add_days(frappe.datetime.month_start(), -1) : k === "month" ? null : today;
		load();
	} });
	const fromRange = () => {
		const v = fPeriod.get_value();
		state.span = "custom";
		if (v && v.length === 2 && v[0] && v[1]) { state.from = v[0]; state.to = v[1]; load(); }
	};
	const fPeriod = page.add_field({ fieldname: "period", label: __("From · To"), fieldtype: "DateRange", change: fromRange });
	fPeriod.$wrapper.hide();
	page.add_inner_button(`${frappe.utils.icon("refresh", "sm")} ${__("Refresh")}`, () => load());
	if (frappe.route_options) {
		if (frappe.route_options.batch) { state.batch = frappe.route_options.batch; fBatch.set_value(state.batch); }
		frappe.route_options = null;
	}

	$(`<style>
		.fee-ov { padding: 4px 0 48px; font-size: 14px; --ok: #16a34a; --ok-bg: #dcfce7; --warn: #d97706; --warn-bg: #fef3c7; --bad: #dc2626; --bad-bg: #fee2e2; --info: #2563eb; --info-bg: #dbeafe; --ink: #0f172a; --muted: #64748b; --line: #e2e8f0; --brand: #0f4c5c; }
		.fee-ov .card { background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px; box-shadow: 0 2px 10px rgba(15,23,42,.04); min-width: 0; }
		.fee-ov .card h6 { margin: 0 0 10px; font-size: 13px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; } .fee-ov .card h6 small { text-transform: none; letter-spacing: 0; font-weight: 400; }
		.fee-ov .head { display: flex; align-items: center; gap: 16px; background: linear-gradient(120deg, #0f766e 0%, #14b8a6 100%); color: #fff; border-radius: 16px; padding: 18px 22px; margin: 6px 0 14px; flex-wrap: wrap; }
		.fee-ov .avatar { width: 68px; height: 68px; border-radius: 50%; background: #fff; display: grid; place-items: center; flex: none; padding: 3px; box-shadow: 0 2px 8px rgba(0,0,0,.18); } .fee-ov .avatar img { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; display: block; }
		.fee-ov .hname { font-size: 22px; font-weight: 700; line-height: 1.15; } .fee-ov .hmeta { color: rgba(255,255,255,.92); font-size: 13px; margin-top: 3px; }
		.fee-ov .hbadge { margin-left: auto; flex: none; white-space: nowrap; background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.45); color: #fff; border-radius: 999px; padding: 6px 14px; font-weight: 600; font-size: 13px; } .fee-ov .hbadge.bad { background: #fee2e2; color: #991b1b; border-color: #fecaca; }
		.fee-ov .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 14px; } @media (max-width: 992px) { .fee-ov .kpis { grid-template-columns: repeat(2, 1fr); } }
		.fee-ov .kpi { display: flex; flex-direction: column; gap: 8px; align-items: center; text-align: center; } .fee-ov .kpi.pop { cursor: pointer; } .fee-ov .kpi.pop:hover { box-shadow: 0 6px 18px rgba(15,23,42,.10); border-color: #cbd5e1; }
		.fee-ov .kpi .ico { width: 44px; height: 44px; border-radius: 12px; display: grid; place-items: center; background: #e2e8f0; color: #334155; } .fee-ov .kpi .ico svg { display: block; }
		.fee-ov .kpi.good .ico { background: var(--ok-bg); color: var(--ok); } .fee-ov .kpi.warn .ico { background: var(--warn-bg); color: var(--warn); } .fee-ov .kpi.bad .ico { background: var(--bad-bg); color: var(--bad); } .fee-ov .kpi.info .ico { background: var(--info-bg); color: var(--info); }
		.fee-ov .kpi b { display: block; font-size: 1.45rem; line-height: 1.05; color: var(--ink); font-variant-numeric: tabular-nums; } .fee-ov .kpi span { font-size: .82rem; color: var(--muted); }
		.fee-ov .kpi small b.cnt { display: inline; font-size: inherit; line-height: inherit; color: var(--ink) !important; font-weight: 700; } .fee-ov .kpi.good b { color: var(--ok); } .fee-ov .kpi.warn b { color: var(--warn); } .fee-ov .kpi.bad b { color: var(--bad); }
		.fee-ov .stack { display: grid; grid-template-columns: 1fr; gap: 12px; margin-bottom: 14px; } .fee-ov .scroll { overflow-x: auto; }
		.fee-ov table { font-size: 13px; margin: 0; } .fee-ov td, .fee-ov th { padding: 9px 10px !important; vertical-align: middle; border-color: var(--line) !important; }
		.fee-ov th { background: #f1f5f9; font-weight: 700; color: #334155; font-size: 12px; text-transform: uppercase; letter-spacing: .05em; white-space: nowrap; }
		.fee-ov tbody tr:nth-child(even) td { background: #fafbfc; } .fee-ov tbody tr:hover td { background: #eef2f7; } .fee-ov tr.row-link { cursor: pointer; }
		.fee-ov .r { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; font-weight: 600; } .fee-ov th.r { text-align: right; }
		.fee-ov .n0 { color: #94a3b8; font-weight: 500; } .fee-ov .mini { font-size: 12px; color: var(--muted); }
		.fee-ov .pill { display: inline-block; font-size: 11px; font-weight: 700; padding: 2px 9px; border-radius: 10px; white-space: nowrap; }
		.fee-ov .pill.overdue { background: var(--bad-bg); color: #991b1b; } .fee-ov .pill.due_week { background: var(--warn-bg); color: #92400e; } .fee-ov .pill.upcoming { background: var(--info-bg); color: #1e40af; } .fee-ov .pill.paid { background: var(--ok-bg); color: #166534; } .fee-ov .pill.hold { background: #0f172a; color: #fff; } .fee-ov .pill.ohold { background: #e2e8f0; color: #334155; }
		.fee-ov .due { font-weight: 700; white-space: nowrap; } .fee-ov .due.overdue { color: var(--bad); } .fee-ov .due.today { color: var(--warn); } .fee-ov .due.upcoming { color: var(--info); }
		.fee-ov .toolbar { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }
		.fee-ov .seg { display: inline-flex; gap: 4px; flex-wrap: wrap; } .fee-ov .seg button { font-size: 12px; padding: 4px 10px; border: 1px solid var(--line); background: #fff; border-radius: 999px; color: #334155; } .fee-ov .seg button.on { background: var(--brand); color: #fff; border-color: var(--brand); }
		.fee-ov .toolbar input { font-size: 13px; padding: 6px 10px; border: 1px solid var(--line); border-radius: 8px; min-width: 220px; }
		.fee-ov .acts { display: flex; gap: 4px; flex-wrap: nowrap; } .fee-ov .acts .btn { padding: 2px 8px; font-size: 11px; }
		.fee-ov .empty-state { padding: 40px 20px; text-align: center; color: var(--muted); }
		.fee-ov tr.row-link td:first-child b { color: var(--brand); } .fee-ov tr.row-link:hover td:first-child b { text-decoration: underline; }
		.fee-ov .bt { width: 100%; } .fee-ov .bt td { padding-top: 12px !important; padding-bottom: 12px !important; }
		.fee-ov .setnote { font-size: 12px; color: var(--muted); margin-top: 8px; }
		.fee-pop td, .fee-pop th { border: 1px solid #94a3b8 !important; padding: 7px 9px !important; white-space: nowrap; vertical-align: middle; } .fee-pop th { background: #e2e8f0; font-weight: 700; color: #0f172a; } .fee-pop thead th { position: sticky; top: 0; z-index: 3; box-shadow: 0 1px 0 #94a3b8, 0 -1px 0 #94a3b8; } .fee-pop { margin: 0 !important; } .fee-pop thead th::before { content: ''; position: absolute; left: -1px; right: -1px; top: -24px; height: 24px; background: #fff; } .fee-pop tr.sum td { position: sticky; bottom: 0; z-index: 2; background: #f1f5f9 !important; font-weight: 700; box-shadow: 0 -1px 0 #94a3b8; } .fee-pop .r { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
		.fee-pop td.wrap { white-space: normal; min-width: 110px; max-width: 170px; } .fee-pop .acts { display: flex; gap: 4px; } .fee-pop .acts .btn { padding: 2px 8px; font-size: 11px; } .fee-pop .mini { font-size: 12px; color: #64748b; } .fee-pop .due { font-weight: 700; } .fee-pop .due.overdue { color: #dc2626; } .fee-pop .due.today { color: #d97706; } .fee-pop .due.upcoming { color: #2563eb; }
		.fee-pop .pill { display: inline-block; font-size: 11px; font-weight: 700; padding: 2px 9px; border-radius: 10px; white-space: nowrap; } .fee-pop .pill.overdue { background: #fee2e2; color: #991b1b; } .fee-pop .pill.due_week { background: #fef3c7; color: #92400e; } .fee-pop .pill.upcoming { background: #dbeafe; color: #1e40af; } .fee-pop .pill.paid { background: #dcfce7; color: #166534; } .fee-pop .pill.hold { background: #0f172a; color: #fff; } .fee-pop .pill.ohold { background: #e2e8f0; color: #334155; }
		.modal.fee-wide .modal-dialog { max-width: 96vw; width: 96vw; margin: 12px auto; } .modal.fee-wide .modal-body { padding: 10px 14px 14px; } .fee-wide .fee-q { display: flex; gap: 10px; align-items: center; margin-bottom: 8px; } .fee-wide .fee-q input { font-size: 13px; padding: 6px 10px; border: 1px solid #cbd5e1; border-radius: 8px; min-width: 280px; }
	</style>`).appendTo(page.main);
	const $body = $(`<div class="fee-ov"></div>`).appendTo(page.main);

	const money = (v) => format_currency(v || 0, "INR", 0);
	const dUser = (d) => d ? frappe.datetime.str_to_user(d) : "";
	const ICONS = {
		rupee: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 4h12M6 9h12M6 4c6 0 8 2 8 5s-2 5-8 5l8 6"/></svg>',
		alert: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l9.5 17h-19z"/><path d="M12 10v4M12 17.5v.5"/></svg>',
		clock: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
		lock: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>',
		check: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.5 2.5L16 9.5"/></svg>',
		wallet: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18M16 14h2"/></svg>',
		users: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><circle cx="17" cy="9" r="2.5"/><path d="M15.5 14.5A5 5 0 0 1 21.5 19"/></svg>',
	};
	const kpi = (n, l, c, ico, pop) => `<div class="card kpi ${c}${pop ? " pop" : ""}"${pop ? ` data-pop="${pop}" title="${__("Click for the list")}"` : ""}><div class="ico">${ICONS[ico]}</div><div><b>${n}</b><span>${l}</span></div></div>`;
	const BUCKET = { overdue: __("Overdue"), due_week: __("Due this week"), upcoming: __("Upcoming"), paid: __("Fully paid") };
	const otherPill = (r) => r.other_hold ? ` <span class="pill ohold" title="${esc(r.hold_reason || "")}${r.hold_on ? ` · ${__("since")} ${dUser(r.hold_on)}` : ""} · ${__("released from the Student form")}">${__("{0} Hold", [r.hold_type || __("Other")])}</span>` : "";
	const pill = (r) => (r.fee_hold ? `<span class="pill hold" title="${esc(r.fee_hold_reason || "")}">${__("Fee Hold")}</span>` : `<span class="pill ${r.bucket}">${BUCKET[r.bucket]}</span>`) + otherPill(r);
	const dueCell = (r) => {
		if (!r.next_due) return `<span class="n0">—</span>`;
		const today = frappe.datetime.get_today(), cls = r.next_due < today ? "overdue" : r.next_due === today ? "today" : "upcoming";
		return `<span class="due ${cls}">${dUser(r.next_due)}</span> <span class="mini">${money(r.next_amount)}</span>${r.overdue_days ? `<br><small style="color:#dc2626;font-weight:700">${__("{0} days overdue", [r.overdue_days])}${r.overdue_count > 1 ? ` · ${__("{0} instalments", [r.overdue_count])}` : ""}</small>` : cls === "today" ? `<br><small class="mini">${__("today")}</small>` : ""}`;
	};
	const acts = (r) => {
		const b = [];
		if (r.pending > 0.5) b.push(`<button class="btn btn-xs btn-primary" data-act="pay" data-row="${esc(r.name)}">${__("Receive")}</button>`);
		if (r.pending > 0.5) b.push(`<button class="btn btn-xs btn-default" data-act="remind" data-row="${esc(r.name)}" title="${__("WhatsApp the student now")}">${__("Remind")}</button>`);
		if (canHold && r.fee_hold) b.push(`<button class="btn btn-xs btn-default" data-act="release" data-row="${esc(r.name)}">${__("Release")}</button>`);
		else if (canHold && r.pending > 0.5) b.push(`<button class="btn btn-xs btn-default" data-act="hold" data-row="${esc(r.name)}">${__("Hold")}</button>`);
		b.push(`<button class="btn btn-xs btn-default" data-act="inst" data-row="${esc(r.name)}" title="${__("Instalments")}">${__("Instalments")}</button>`);
		return `<div class="acts">${b.join("")}</div>`;
	};
	const n = (v, c) => v ? `<span class="${c || ""}">${money(v)}</span>` : `<span class="n0">${money(0)}</span>`;

	let data = null;
	const byName = (name) => (data.rows || []).find(x => x.name === name);
	const studentCell = (r) => `<a href="/app/student/${esc(r.student)}"><b>${esc(r.student_name || r.student)}</b></a>${r.mobile && r.mobile !== r.student_name ? ` <small class="mini">${esc(r.mobile)}</small>` : ""}`;
	const rowCells = (r, withBatch) => `<td>${studentCell(r)}</td>${withBatch ? `<td class="wrap">${esc(r.batch_name || r.batch)}</td>` : ""}<td class="mini wrap">${esc(r.counsellor_name || "")}</td><td class="r">${money(r.total)}</td><td class="r text-success">${money(r.paid)}</td><td class="r" style="color:${r.pending > 0.5 ? "#dc2626" : "#16a34a"}">${money(r.pending)}</td><td>${dueCell(r)}</td><td>${pill(r)}${r.fee_hold && r.fee_hold_on ? `<br><small class="mini">${__("Fee Hold since")} ${dUser(r.fee_hold_on)}</small>` : ""}${r.schedule_mismatch ? `<br><small style="color:#dc2626;font-weight:700" title="${__("The instalments do not add up to the order total. Open the order and correct the payment schedule.")}">⚠ ${__("instalments off by {0}", [money(r.schedule_mismatch)])}</small>` : ""}${r.ledger_mismatch ? `<br><small style="color:#dc2626;font-weight:700" title="${__("The instalments say {0} received, the payments and receipts on record add up to {1}. Do not rely on this row until Accounts has checked the order.", [money(r.paid), money(r.settled)])}">⚠ ${__("check: payments on record {0}", [money(r.settled)])}</small>` : ""}${r.unpaid_receipts ? `<br><small style="color:#dc2626;font-weight:700" title="${__("A receipt was issued but its payment was cancelled. The amounts shown here are correct, but the receipt must be cancelled by Accounts, otherwise the money cannot be received again against this order.")}">⚠ ${__("receipt of {0} has no payment", [money(r.unpaid_receipts)])}</small>` : ""}</td><td class="mini">${r.last_reminder ? dUser(r.last_reminder) : "—"}</td><td>${acts(r)}</td>`;
	const HEAD = (withBatch) => [__("Student"), ...(withBatch ? [__("Batch")] : []), __("Counsellor"), __("Total"), __("Received"), __("Pending"), __("Next due"), __("Status"), __("Last reminder"), ""];
	const RIGHT = new Set([__("Total"), __("Received"), __("Pending")]);
	// the popup behind a card: the students behind that number, searchable, with the same row buttons
	function popStudents(title, rows, sub = "") {
		const d = new frappe.ui.Dialog({ title, size: "extra-large", fields: [{ fieldtype: "HTML", fieldname: "body" }] });
		d.$wrapper.addClass("fee-wide");
		const sumRow = `<tr class="sum"><td colspan="3">${__("Total of {0} students", [rows.length])}</td><td class="r">${money(rows.reduce((a, x) => a + x.total, 0))}</td><td class="r text-success">${money(rows.reduce((a, x) => a + x.paid, 0))}</td><td class="r" style="color:#dc2626">${money(rows.reduce((a, x) => a + x.pending, 0))}</td><td colspan="4"></td></tr>`;
		d.fields_dict.body.$wrapper.html(`${sub}<div class="fee-q"><input type="search" data-q placeholder="${__("Search name, mobile, batch, counsellor")}"><small class="text-muted"><span data-count>${rows.length}</span> ${__("shown")}</small></div>
			<div style="max-height:78vh;overflow:auto"><table class="table table-bordered fee-pop" style="font-size:13px;width:100%;margin:0"><thead><tr>${HEAD(true).map(h => `<th class="${RIGHT.has(h) ? "r" : ""}">${h}</th>`).join("")}</tr></thead><tbody>
			${rows.map(r => `<tr data-row="${esc(r.name)}">${rowCells(r, true)}</tr>`).join("") || `<tr><td colspan="10" class="text-muted">${__("Nothing to show.")}</td></tr>`}${rows.length ? sumRow : ""}</tbody></table></div></div>`);
		d.$wrapper.on("click", "[data-act]", e => { e.stopPropagation(); const $b = $(e.currentTarget); act($b.attr("data-act"), $b.attr("data-row"), () => d.hide()); });
		d.$wrapper.on("input", "[data-q]", e => { const q = ($(e.currentTarget).val() || "").toLowerCase(); let n = 0; d.$wrapper.find("tbody tr[data-row]").each((i, tr) => { const ok = !q || $(tr).text().toLowerCase().includes(q); tr.hidden = !ok; if (ok) n++; }); d.$wrapper.find("[data-count]").text(n); });
		d.show();
	}
	const NAMED = ["month", "today", "week", "last_month", "m3"];
	const rangeText = (d) => d.collected_from === d.collected_to ? dUser(d.collected_from) : `${dUser(d.collected_from)} – ${dUser(d.collected_to)}`;
	// a named period reads as its name; custom dates read as the dates themselves
	const periodLabel = (d) => state.span === "all" ? __("all time") : NAMED.includes(state.span) ? SPANS[state.span].toLowerCase() : rangeText(d);
	// for the popup title: the name plus its dates once, never the dates twice
	const periodTitle = (d) => state.span === "all" ? __("all time") : NAMED.includes(state.span) ? `${SPANS[state.span].toLowerCase()} (${rangeText(d)})` : rangeText(d);
	function popReceipts(list) {
		const d = new frappe.ui.Dialog({ title: `${__("Collected")} · ${periodTitle(data)} · ${money(list.reduce((a, x) => a + x.amount, 0))}`, size: "extra-large", fields: [{ fieldtype: "HTML", fieldname: "body" }] });
		d.$wrapper.addClass("fee-wide");
		d.fields_dict.body.$wrapper.html(`<div class="text-muted" style="margin-bottom:8px">${__("Every fee receipt (Sales Invoice) dated in this period against these students' orders. Credit notes are shown negative.")}</div>
			<div style="max-height:70vh;overflow:auto"><table class="table table-bordered fee-pop" style="font-size:13px;width:100%;margin:0"><thead><tr><th>${__("Date")}</th><th>${__("Student")}</th><th>${__("Batch")}</th><th>${__("Receipt")}</th><th>${__("Mode")}</th><th class="r">${__("Amount")}</th></tr></thead><tbody>
			${list.map(x => `<tr><td style="white-space:nowrap">${dUser(x.posting_date)}</td><td><a href="/app/student/${esc(x.student || "")}"><b>${esc(x.student_name || x.customer)}</b></a></td><td>${esc(x.batch_name || "")}</td><td><a href="/app/sales-invoice/${esc(x.name)}">${esc(x.name)}</a>${x.is_return ? ` <span class="pill overdue">${__("Credit note")}</span>` : ""}</td><td>${esc(x.mode || "")}</td><td class="r" style="font-weight:700;color:${x.amount < 0 ? "#dc2626" : "#16a34a"}">${money(x.amount)}</td></tr>`).join("") || `<tr><td colspan="6" class="text-muted">${__("No receipts in this period.")}</td></tr>`}
			</tbody></table></div>`);
		d.show();
	}

	function instalments(r) {
		const rows = r.instalments.map(i => `<tr><td>${esc(i.term)}</td><td>${dUser(i.due_date)}${i.overdue_days ? ` <small style="color:#dc2626;font-weight:700">(${__("{0} d overdue", [i.overdue_days])})</small>` : ""}</td><td class="r">${money(i.amount)}</td><td class="r">${money(i.paid)}</td><td class="r"><b style="color:${i.outstanding > 0.5 ? "#dc2626" : "#16a34a"}">${money(i.outstanding)}</b></td><td>${i.reminded_on ? `${dUser(i.reminded_on)} <small class="text-muted">${esc(i.reminder_kind || "")}</small>` : `<span class="text-muted">—</span>`}</td></tr>`).join("");
		const d = new frappe.ui.Dialog({ title: __("Instalments · {0}", [r.student_name]), size: "large", fields: [{ fieldtype: "HTML", fieldname: "body" }] });
		d.$wrapper.addClass("fee-wide");
		d.fields_dict.body.$wrapper.html(`<div class="text-muted" style="margin-bottom:8px">${esc(r.batch_name || r.batch)} · ${__("Order")} <a href="/app/sales-order/${esc(r.sales_order)}">${esc(r.sales_order)}</a> · ${__("Total")} <b>${money(r.total)}</b> · ${__("Received")} <b style="color:#16a34a">${money(r.paid)}</b> · ${__("Pending")} <b style="color:${r.pending > 0.5 ? "#dc2626" : "#16a34a"}">${money(r.pending)}</b>${r.fee_hold ? `<br><b>${__("On Fee Hold since {0}", [dUser(r.fee_hold_on)])}</b>: ${esc(r.fee_hold_reason || "")}` : ""}${r.other_hold ? `<br><span class="text-muted">${__("Also on {0} Hold since {1} (separate, released from the Student form)", [r.hold_type || __("Other"), dUser(r.hold_on)])}</span>` : ""}${r.schedule_mismatch ? `<br><b style="color:#dc2626">⚠ ${__("The instalments add up to {0} more than the order total. Correct the payment schedule on the order.", [money(r.schedule_mismatch)])}</b>` : ""}</div>
			<div style="max-height:70vh;overflow:auto"><table class="table table-bordered fee-pop" style="font-size:13px;width:100%;margin:0"><thead><tr><th>${__("Instalment")}</th><th>${__("Due")}</th><th class="r">${__("Amount")}</th><th class="r">${__("Received")}</th><th class="r">${__("Pending")}</th><th>${__("Last reminder")}</th></tr></thead><tbody>${rows || `<tr><td colspan="6" class="text-muted">${__("No instalments on the order.")}</td></tr>`}</tbody></table></div>`);
		d.show();
	}
	function act(kind, name, after) {
		const r = byName(name);
		if (!r) return;
		const done = () => { if (after) after(); load(); };
		if (kind === "inst") return instalments(r);
		if (kind === "pay") {
			if (!(window.tnc && tnc.admissions && tnc.admissions.receive_payment)) return frappe.msgprint(__("Receive Payment is not loaded. Reload the page."));
			return tnc.admissions.receive_payment({ sales_order: r.sales_order, amount: r.pending, label: r.student_name, on_done: done });
		}
		if (kind === "remind") {
			return frappe.confirm(__("Send the fee reminder to {0} on WhatsApp now?", [`<b>${esc(r.student_name)}</b> (${esc(r.mobile || "")})`]), () =>
				frappe.call({ method: API + "remind_now", args: { enrollment: r.name }, freeze: true }).then(res => { frappe.show_alert({ message: __("Reminder sent ({0})", [res.message.kind]), indicator: "green" }); done(); }));
		}
		if (kind === "hold") {
			return frappe.prompt([{ fieldname: "remarks", fieldtype: "Small Text", label: __("Reason (optional)"), description: __("The student gets the Fee Hold WhatsApp; punches stop counting until the fee is received or the hold is released. An Attendance Hold, if any, is not affected.") }],
				v => frappe.call({ method: API + "hold_now", args: { enrollment: r.name, remarks: v.remarks }, freeze: true }).then(() => { frappe.show_alert({ message: __("{0} put on Fee Hold", [r.student_name]), indicator: "orange" }); done(); }),
				__("Put {0} on Fee Hold", [r.student_name]), __("Hold"));
		}
		if (kind === "release") {
			return frappe.prompt([{ fieldname: "remarks", fieldtype: "Small Text", label: __("Why is the hold released?"), reqd: 1 }],
				v => frappe.call({ method: API + "release_now", args: { enrollment: r.name, remarks: v.remarks }, freeze: true }).then(() => { frappe.show_alert({ message: __("Fee Hold released"), indicator: "green" }); done(); }),
				__("Release Fee Hold · {0}", [r.student_name]), __("Release"));
		}
	}

	function load() {
		$body.html(`<div class="card empty-state">${__("Loading…")}</div>`);
		frappe.call({ method: API + "get_overview", args: { batch: state.batch, counsellor: state.counsellor, collected_from: state.from, collected_to: state.to } }).then(r => {
			data = r.message || {};
			$body.html(render(data));
			$body.find("[data-act]").on("click", e => { e.stopPropagation(); act($(e.currentTarget).attr("data-act"), $(e.currentTarget).attr("data-row")); });
			$body.find("tr[data-row]").on("click", e => { if ($(e.target).closest("a, button").length) return; frappe.set_route("Form", "Student", $(e.currentTarget).attr("data-student")); });
			$body.find("[data-batch]").on("click", e => { const b = $(e.currentTarget).attr("data-batch"); if (b) { state.batch = b; fBatch.set_value(b); load(); } });
			$body.find("[data-coun]").on("click", e => { const c = $(e.currentTarget).attr("data-coun"); if (c) { state.counsellor = c; fCoun.set_value(c); load(); } });
			let seg = data.overdue_students ? "overdue" : "pending";
			const match = (x, s) => s === "all" || (s === "pending" ? x.pending > 0.5 : s === "hold" ? !!x.fee_hold : x.bucket === s);
			const apply = () => {
				const q = ($body.find("#fee-q").val() || "").toLowerCase();
				let shown = 0;
				$body.find("tr[data-row]").each((i, tr) => { const x = byName($(tr).attr("data-row")); const ok = match(x, seg) && (!q || $(tr).text().toLowerCase().includes(q)); tr.hidden = !ok; if (ok) shown++; });
				$body.find("#fee-count").text(shown);
				$body.find(".seg button").removeClass("on").filter(`[data-seg='${seg}']`).addClass("on");
			};
			$body.find("#fee-q").on("input", apply);
			$body.find("[data-seg]").on("click", e => { seg = $(e.currentTarget).attr("data-seg"); apply(); });
			$body.find("[data-pop]").on("click", e => {
				const which = $(e.currentTarget).attr("data-pop"), R = data.rows || [];
				if (which === "collected") return popReceipts(data.receipts_month || []);
				const lists = {
					pending: [__("Students with fees pending"), R.filter(x => x.pending > 0.5)],
					overdue: [__("Overdue · past the due date and unpaid"), R.filter(x => x.bucket === "overdue")],
					due_week: [__("Due in the next 7 days"), R.filter(x => x.bucket === "due_week")],
					hold: [__("On Fee Hold"), R.filter(x => x.fee_hold)],
					paid: [__("Fully paid"), R.filter(x => x.bucket === "paid")],
					upcoming: [__("Upcoming · next instalment more than 7 days away"), R.filter(x => x.bucket === "upcoming")],
					all: [__("All students with fee in the system"), R],
				};
				const [title, rows] = lists[which] || [which, []];
				popStudents(title, rows);
			});
			apply();
		});
	}

	function render(d) {
		const title = d.batch ? (fBatch.df.options.find(o => o.value === d.batch) || {}).label || d.batch : !d.manager ? __("My students") : d.counsellor ? (d.counsellor_name || d.counsellor) : __("All students");
		const meta = [`${d.students} ${__("students with fee in the system")}${d.outside_system ? ` · ${__("{0} more outside the system, not shown", [d.outside_system])}` : ""}`, d.counsellor && (d.batch || !d.manager) ? `${__("Counsellor")}: ${esc(d.counsellor_name || d.counsellor)}` : "", ].filter(Boolean).join(" · ");
		const bucketTable = (rows, attr, label) => rows.length ? `<div class="scroll"><table class="table bt"><thead><tr><th>${label}</th><th class="r">${__("Students")}</th><th class="r">${__("Total fee")}</th><th class="r">${__("Received")}</th><th class="r">${__("Pending")}</th><th class="r">${__("Overdue")}</th><th class="r">${__("Overdue students")}</th><th class="r">${__("On Fee Hold")}</th></tr></thead><tbody>
			${rows.map(x => `<tr class="${x.key ? "row-link" : ""}"${x.key ? ` ${attr}="${esc(x.key)}"` : ""}><td><b>${esc(x.label)}</b></td><td class="r">${x.students}</td><td class="r">${n(x.total)}</td><td class="r">${n(x.paid, "text-success")}</td><td class="r">${n(x.pending, x.pending ? "text-warning" : "")}</td><td class="r">${n(x.overdue, x.overdue ? "text-danger" : "")}</td><td class="r">${x.overdue_students || `<span class="n0">0</span>`}</td><td class="r">${x.held || `<span class="n0">0</span>`}</td></tr>`).join("")}
			</tbody></table></div>` : `<div class="text-muted">${__("Nothing yet.")}</div>`;
		const pendingCount = d.rows.filter(x => x.pending > 0.5).length;
		const segBtn = (k, l, c) => `<button data-seg="${k}">${l}${c != null ? ` (${c})` : ""}</button>`;
		return `
			<div class="head"><div class="avatar"><img src="${esc(d.logo || "")}" alt=""></div><div style="flex:1;min-width:0"><div class="hname">${esc(title)}</div><div class="hmeta">${meta}</div></div>
				${d.mismatches ? `<div class="hbadge bad" style="margin-left:auto;margin-right:8px">⚠ ${__("{0} rows need Accounts to check", [d.mismatches])}</div>` : ""}<div class="hbadge ${d.overdue_students ? "bad" : ""}"${d.mismatches ? ' style="margin-left:0"' : ""}>${d.overdue_students ? __("{0} students overdue · {1}", [d.overdue_students, money(d.overdue_amount)]) : __("No overdue fees")}</div></div>
			<div class="kpis">
				${kpi(money(d.pending), __("Pending in total") + `<br><small><b class="cnt">${__("{0} students", [pendingCount])}</b> ${__("still to pay")}<br>${__("All {0} students: fee {1} · received {2}", [d.rows.length, money(d.total), money(d.paid)])}</small>`, d.pending ? "warn" : "good", "rupee", "pending")}
				${kpi(money(d.overdue_amount), __("Overdue") + `<br><small><b class="cnt">${__("{0} students", [d.overdue_students])}</b> · ${__("past the due date")}</small>`, d.overdue_amount ? "bad" : "good", "alert", "overdue")}
				${kpi(d.due_week, __("Due in the next 7 days") + `<br><small><b class="cnt">${__("{0} students", [d.due_week])}</b> · ${money(d.due_week_amount)}</small>`, d.due_week ? "warn" : "info", "clock", "due_week")}
				${kpi(d.fee_hold, __("On Fee Hold") + `<br><small><b class="cnt">${__("{0} students", [d.fee_hold])}</b> · ${__("fee overdue past {0} days", [d.settings.grace || "—"])}</small>`, d.fee_hold ? "bad" : "good", "lock", "hold")}
				${kpi(money(d.collected_month), `${__("Collected")} · ${periodLabel(d)}` + `<br><small><b class="cnt">${__("{0} students", [new Set((d.receipts_month || []).map(x => x.student)).size])}</b> · ${__("{0} receipts", [(d.receipts_month || []).length])}</small>`, "good", "wallet", "collected")}
				${kpi(d.fully_paid, __("Fully paid") + `<br><small><b class="cnt">${__("{0} students", [d.fully_paid])}</b> · ${__("nothing pending")}</small>`, "good", "check", "paid")}
				${kpi(d.rows.filter(x => x.bucket === "upcoming").length, __("Upcoming") + `<br><small><b class="cnt">${__("{0} students", [d.rows.filter(x => x.bucket === "upcoming").length])}</b> · ${__("nothing due this week")}</small>`, "info", "users", "upcoming")}
				${kpi(d.students, __("Students with fee in the system") + (d.outside_system ? `<br><small style="color:#b45309;font-weight:600">${__("{0} more have fees outside the system", [d.outside_system])}</small>` : ""), "info", "users", "all")}
			</div>
			<div class="stack">
				${!d.batch ? `<div class="card"><h6>${__("By batch")} <small class="text-muted">${__("click a row to open that batch")}</small></h6>${bucketTable(d.by_batch, "data-batch", __("Batch"))}</div>` : ""}
				${d.manager && !d.counsellor && d.by_counsellor.length > 1 ? `<div class="card"><h6>${__("By counsellor")} <small class="text-muted">${__("click a row to open that counsellor")}</small></h6>${bucketTable(d.by_counsellor, "data-coun", __("Counsellor"))}</div>` : ""}
			</div>
			<div class="card" id="fee-list">
				<div class="toolbar"><h6 style="margin:0">${__("Students")} <small class="text-muted">(<span id="fee-count">0</span>) · ${__("click a row to open the student")}</small></h6>
					<div class="seg">${segBtn("overdue", __("Overdue"), d.overdue_students)}${segBtn("due_week", __("Due this week"), d.due_week)}${segBtn("hold", __("Fee Hold"), d.fee_hold)}${segBtn("pending", __("All pending"), pendingCount)}${segBtn("paid", __("Fully paid"), d.fully_paid)}${segBtn("all", __("All"), d.students)}</div>
					<input id="fee-q" type="search" placeholder="${__("Search name, mobile, batch")}"></div>
				<div class="scroll"><table class="table"><thead><tr><th>${__("Student")}</th>${d.batch ? "" : `<th>${__("Batch")}</th>`}<th>${__("Counsellor")}</th><th class="r">${__("Total")}</th><th class="r">${__("Received")}</th><th class="r">${__("Pending")}</th><th>${__("Next due")}</th><th>${__("Status")}</th><th>${__("Last reminder")}</th><th></th></tr></thead><tbody>
				${d.rows.map(r => `<tr class="row-link" data-row="${esc(r.name)}" data-student="${esc(r.student)}">${rowCells(r, !d.batch)}</tr>`).join("") || `<tr><td colspan="10" class="text-muted">${__("No students with fee in the system match.")}</td></tr>`}
				</tbody></table></div>
				<div class="setnote">${__("Amounts come from each enrolment's Sales Order instalments. Receive Payment allocates to the earliest-due instalment first.")} ${__("Fee Hold after {0} days overdue · reminder {1} days before due, then every {2} days.", [d.settings.grace || "—", d.settings.before || "—", d.settings.every || "—"])}</div>
			</div>`;
	}
	load();
};
