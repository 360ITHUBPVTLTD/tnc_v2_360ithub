// Copyright (c) 2026, 360ITHub and contributors
// Enquiry Overview: the enquiry pipeline for a batch, a counsellor, or everything, in the Student Attendance dashboard style.
frappe.pages["enquiry-overview"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Enquiry Overview"), single_column: true });
	const M = "tnc_v2_360ithub.admissions.enquiry_overview.get_overview";
	const esc = frappe.utils.escape_html;
	const state = { batch: null, counsellor: null, from: null, to: null };
	const manager = frappe.user.has_role(["TNC Manager", "TNC Super Admin", "System Manager"]);

	const fBatch = page.add_field({ fieldname: "batch", label: __("Batch"), fieldtype: "Select", options: [{ value: "", label: __("All batches") }], change() { state.batch = fBatch.get_value() || null; load(); } });
	frappe.call("tnc_v2_360ithub.admissions.enquiry_overview.batch_options").then(r => {
		fBatch.df.options = [{ value: "", label: __("All batches") }, ...(r.message || [])];
		fBatch.refresh();
		if (state.batch) fBatch.set_value(state.batch);
	});
	const fCoun = manager ? page.add_field({ fieldname: "counsellor", label: __("Counsellor"), fieldtype: "Link", options: "User", change() { state.counsellor = fCoun.get_value() || null; load(); },
		get_query: () => ({ query: "frappe.core.doctype.user.user.user_query", filters: { ignore_user_type: 1 } }) }) : null;
	const fPeriod = page.add_field({ fieldname: "period", label: __("Enquiry date"), fieldtype: "DateRange", change() {
		const v = fPeriod.get_value();
		if (v && v.length === 2 && v[0] && v[1]) { state.from = v[0]; state.to = v[1]; } else { state.from = state.to = null; }
		load();
	} });
	page.add_inner_button(`${frappe.utils.icon("refresh", "sm")} ${__("Refresh")}`, () => load());
	page.set_secondary_action(__("Follow-ups"), () => frappe.set_route("follow-ups"));
	page.set_primary_action(__("New Enquiry"), () => frappe.new_doc("Student Enquiry", state.batch ? { batch_interested: state.batch } : {}), "add");
	if (frappe.route_options) {
		if (frappe.route_options.batch) { state.batch = frappe.route_options.batch; fBatch.set_value(state.batch); }
		if (frappe.route_options.counsellor && fCoun) { state.counsellor = frappe.route_options.counsellor; fCoun.set_value(state.counsellor); }
		frappe.route_options = null;
	}

	$(`<style>
		.enq-ov { padding: 4px 0 48px; font-size: 14px; --ok: #16a34a; --ok-bg: #dcfce7; --warn: #d97706; --warn-bg: #fef3c7; --bad: #dc2626; --bad-bg: #fee2e2; --info: #2563eb; --info-bg: #dbeafe; --hot: #ea580c; --hot-bg: #ffedd5; --ink: #0f172a; --muted: #64748b; --line: #e2e8f0; --brand: #0f4c5c; }
		.enq-ov .card { background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px; box-shadow: 0 2px 10px rgba(15,23,42,.04); min-width: 0; }
		.enq-ov .card h6 { margin: 0 0 10px; font-size: 13px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; }
		.enq-ov .card h6 small { text-transform: none; letter-spacing: 0; font-weight: 400; }
		.enq-ov .head { display: flex; align-items: center; gap: 16px; background: linear-gradient(120deg, #6a5acd 0%, #8b7fd9 100%); color: #fff; border: 1px solid #6a5acd; border-radius: 16px; padding: 18px 22px; margin: 6px 0 14px; flex-wrap: wrap; }
		.enq-ov .avatar { width: 68px; height: 68px; border-radius: 50%; background: #fff; display: grid; place-items: center; flex: none; padding: 3px; box-shadow: 0 2px 8px rgba(0,0,0,.18); } .enq-ov .avatar img { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; display: block; }
		.enq-ov .hname { font-size: 22px; font-weight: 700; line-height: 1.15; } .enq-ov .hmeta { color: rgba(255,255,255,.92); font-size: 13px; margin-top: 3px; }
		.enq-ov .hbadge { margin-left: auto; background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.45); color: #fff; border-radius: 999px; padding: 6px 14px; font-weight: 600; font-size: 13px; }
		.enq-ov .hbadge.bad { background: #fee2e2; color: #991b1b; border-color: #fecaca; }
		.enq-ov .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 14px; }
		@media (max-width: 992px) { .enq-ov .kpis { grid-template-columns: repeat(2, 1fr); } }
		.enq-ov .kpi { display: flex; flex-direction: column; gap: 10px; align-items: center; text-align: center; } .enq-ov .kpi.pop { cursor: pointer; } .enq-ov .kpi.pop:hover { box-shadow: 0 6px 18px rgba(15,23,42,.10); border-color: #cbd5e1; }
		.enq-ov .kpi .ico { width: 44px; height: 44px; border-radius: 12px; display: grid; place-items: center; background: #e2e8f0; color: #334155; flex: none; } .enq-ov .kpi .ico svg { display: block; }
		.enq-ov .kpi.good .ico { background: var(--ok-bg); color: var(--ok); } .enq-ov .kpi.warn .ico { background: var(--warn-bg); color: var(--warn); } .enq-ov .kpi.bad .ico { background: var(--bad-bg); color: var(--bad); } .enq-ov .kpi.info .ico { background: var(--info-bg); color: var(--info); } .enq-ov .kpi.hot .ico { background: var(--hot-bg); color: var(--hot); }
		.enq-ov .kpi b { display: block; font-size: 1.6rem; line-height: 1.05; color: var(--ink); } .enq-ov .kpi span { font-size: .82rem; color: var(--muted); }
		.enq-ov .kpi.good b { color: var(--ok); } .enq-ov .kpi.warn b { color: var(--warn); } .enq-ov .kpi.bad b { color: var(--bad); } .enq-ov .kpi.hot b { color: var(--hot); }
		.enq-ov .stack { display: grid; grid-template-columns: 1fr; gap: 12px; margin-bottom: 14px; }
		.enq-ov .scroll { overflow-x: auto; }
		.enq-ov .c { text-align: center; } .enq-ov td.c .bar { justify-content: center; min-width: 0; }
		.enq-ov .grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 14px; align-items: start; }
		@media (max-width: 992px) { .enq-ov .grid3 { grid-template-columns: 1fr; } }
		.enq-ov .chart { min-height: 0; } .enq-ov .donut-wrap { display: flex; align-items: center; gap: 14px; } .enq-ov .donut-wrap .chart { flex: 0 0 40%; min-width: 0; } .enq-ov .donut-wrap .chart svg { width: 100%; height: auto; overflow: visible; transform: translateY(16%) scale(1.8); transform-origin: 50% 50%; }
		.enq-ov .donut-wrap .graph-svg-tip { font-size: 11px !important; padding: 0 !important; line-height: 1.3; } .enq-ov .donut-wrap .graph-svg-tip .title { font-size: 11px !important; font-weight: 600; text-transform: none; padding: 5px 8px !important; margin: 0 !important; } .enq-ov .donut-wrap .graph-svg-tip ul.data-point-list li { min-width: 0 !important; padding: 0 8px 5px !important; font-size: 11px !important; } .enq-ov .donut-wrap .graph-svg-tip ul.data-point-list { margin: 0 !important; } .enq-ov .donut-wrap .graph-svg-tip .svg-pointer { display: none; }
		.enq-ov .donut-wrap .chart { display: flex; align-items: center; justify-content: center; align-self: stretch; } .enq-ov .donut-wrap .lg { flex: 0 0 calc(60% - 14px); } .enq-ov .donut-wrap .chart-legend { display: none; }
		.enq-ov .lg { flex: 1; display: flex; flex-direction: column; gap: 6px; min-width: 0; } .enq-ov .lg-row { display: flex; align-items: center; gap: 8px; font-size: 13px; padding: 4px 8px; border-radius: 8px; } .enq-ov .lg-row i { width: 10px; height: 10px; border-radius: 3px; flex: none; } .enq-ov .lg-row span { flex: 1; color: var(--ink); } .enq-ov .lg-row b { font-weight: 800; font-variant-numeric: tabular-nums; } .enq-ov .chart .chart-container, .enq-ov .chart svg { overflow: visible; }
		.enq-ov table { font-size: 13px; margin: 0; } .enq-ov td, .enq-ov th { padding: 9px 10px !important; vertical-align: middle; border-color: var(--line) !important; }
		.enq-ov th { background: #f1f5f9; font-weight: 700; color: #334155; font-size: 12px; text-transform: uppercase; letter-spacing: .05em; white-space: nowrap; }
		.enq-ov tbody tr:hover td { background: #f1f5f9; } .enq-ov tr.row-link { cursor: pointer; }
		.enq-ov .bar { display: inline-flex; align-items: center; gap: 8px; min-width: 0; width: 100%; } .enq-ov .bar i { flex: 1; height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden; display: block; } .enq-ov .bar i b { display: block; height: 100%; }
		.enq-ov .pill { display: inline-block; font-size: 11px; font-weight: 700; padding: 2px 9px; border-radius: 10px; white-space: nowrap; }
		.enq-ov .pill.New { background: #e2e8f0; color: #334155; } .enq-ov .pill.DemoScheduled { background: var(--info-bg); color: #1e40af; } .enq-ov .pill.DemoAttended { background: var(--hot-bg); color: #9a3412; } .enq-ov .pill.Converted { background: var(--ok-bg); color: #166534; } .enq-ov .pill.Lost { background: var(--bad-bg); color: #991b1b; }
		.enq-ov .due { font-weight: 700; white-space: nowrap; } .enq-ov .due.overdue { color: var(--bad); } .enq-ov .due.today { color: var(--warn); } .enq-ov .due.upcoming { color: var(--info); } .enq-ov .due.none { color: #94a3b8; font-weight: 400; }
		.enq-ov .toolbar { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }
		.enq-ov .toolbar .seg { display: inline-flex; gap: 4px; flex-wrap: wrap; } .enq-ov .toolbar .seg button { font-size: 12px; padding: 4px 10px; border: 1px solid var(--line); background: #fff; border-radius: 999px; color: #334155; } .enq-ov .toolbar .seg button.on { background: var(--brand); color: #fff; border-color: var(--brand); }
		.enq-ov .toolbar input { font-size: 13px; padding: 6px 10px; border: 1px solid var(--line); border-radius: 8px; min-width: 220px; }
		.enq-ov .empty-state { padding: 40px 20px; text-align: center; color: var(--muted); } .enq-ov .empty-state b { display: block; font-size: 16px; color: var(--ink); margin-bottom: 6px; }
		.enq-ov .work { display: flex; flex-direction: column; }
		.enq-ov .work-row { display: flex; align-items: center; gap: 10px; padding: 10px 10px; border-bottom: 1px solid var(--line); border-radius: 8px; }
		.enq-ov .work-row:last-child { border-bottom: 0; } .enq-ov .work-label { flex: 1; font-weight: 500; color: var(--ink); }
		.enq-ov .work-row.pop { cursor: pointer; } .enq-ov .work-row.pop:hover { background: #f1f5f9; } .enq-ov .work-row.pop:hover .work-label { color: var(--brand); }
		.enq-ov .work-row .chev { color: #94a3b8; display: grid; } .enq-ov .work-row.pop:hover .chev { color: var(--brand); }
		.enq-ov .count { min-width: 34px; text-align: center; font-weight: 800; font-size: 13px; padding: 3px 10px; border-radius: 999px; background: #f1f5f9; color: #334155; }
		.enq-ov .count.warn { background: var(--warn-bg); color: #92400e; } .enq-ov .count.bad { background: var(--bad-bg); color: #991b1b; } .enq-ov .count.info { background: var(--info-bg); color: #1e40af; } .enq-ov .count.ok { background: var(--ok-bg); color: #166534; } .enq-ov .count.ink { background: #e2e8f0; color: var(--ink); }
		.enq-ov tr.row-link td:first-child b { color: var(--brand); } .enq-ov tr.row-link a.due:hover { text-decoration: underline; } .enq-ov tr.row-link:hover td:first-child b { text-decoration: underline; }
		.enq-ov tr.row-link td:first-child { position: relative; padding-left: 14px !important; } .enq-ov tr.row-link:hover td:first-child::before { content: ""; position: absolute; left: 0; top: 8px; bottom: 8px; width: 3px; border-radius: 2px; background: var(--brand); }
		.enq-ov .c { white-space: nowrap; font-variant-numeric: tabular-nums; font-size: 14px; font-weight: 600; color: var(--ink); } .enq-ov th.c { font-size: 12px; }
		.enq-ov .bt { width: 100%; } .enq-ov .bt th:first-child, .enq-ov .bt td:first-child { width: 24%; } .enq-ov .bt th:last-child, .enq-ov .bt td:last-child { width: 17%; } .enq-ov .bt th { white-space: normal; } .enq-ov .bt td { padding-top: 12px !important; padding-bottom: 12px !important; }
		.enq-ov .n0 { color: #94a3b8; font-weight: 500; }
		.enq-ov .np { display: inline-block; min-width: 30px; padding: 2px 9px; border-radius: 999px; font-weight: 800; font-size: 13px; } .enq-ov .np.ok { background: var(--ok-bg); color: #166534; } .enq-ov .np.bad { background: var(--bad-bg); color: #991b1b; } .enq-ov .np.warn { background: var(--warn-bg); color: #92400e; } .enq-ov .np.hot { background: var(--hot-bg); color: #9a3412; } .enq-ov .np.info { background: var(--info-bg); color: #1e40af; }
		.enq-ov tbody tr:nth-child(even) td { background: #fafbfc; } .enq-ov tbody tr:hover td { background: #eef2f7; }
		.enq-ov .mini { font-size: 12px; color: var(--muted); } .enq-ov .notes { font-size: 12px; color: #475569; max-width: 260px; white-space: normal; }
		.enq-ov .reason-list { display: flex; flex-direction: column; gap: 8px; } .enq-ov .reason-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; align-items: center; font-size: 13px; padding: 4px 10px; }
	</style>`).appendTo(page.main);
	const $body = $(`<div class="enq-ov"></div>`).appendTo(page.main);

	const col = (v) => v >= 30 ? "#16a34a" : v >= 15 ? "#d97706" : "#dc2626";
	const rateCls = (v, total) => !total ? "info" : v >= 30 ? "good" : v >= 15 ? "warn" : "bad";
	const bar = (v, c) => `<span class="bar"><i><b style="width:${Math.min(100, v)}%;background:${c || col(v)}"></b></i><span style="color:${c || col(v)};font-weight:700;white-space:nowrap">${v}%</span></span>`;
	const pill = (s) => `<span class="pill ${esc(String(s).replace(/ /g, ""))}">${__(s)}</span>`;
	const dUser = (d) => d ? frappe.datetime.str_to_user(d) : "";
	const dueCell = (r) => !r.next_followup_on || !["New", "Demo Scheduled", "Demo Attended"].includes(r.status) ? `<span class="due none">—</span>`
		: `<span class="due ${r.due}">${r.next_followup ? `<a href="/app/student-follow-up/${esc(r.next_followup)}" class="due ${r.due}" title="${__("Open the follow-up")}">${dUser(r.next_followup_on)}</a>` : dUser(r.next_followup_on)}${r.due === "overdue" ? ` <small>(${__("overdue")})</small>` : r.due === "today" ? ` <small>(${__("today")})</small>` : ""}</span>`;
	const ICONS = {
		inbox: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 13l2.5-8h13L21 13v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/><path d="M3 13h5l1.5 3h5L16 13h5"/></svg>',
		check: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.5 2.5L16 9.5"/></svg>',
		flame: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3c1 3 4 5 4 9a4 4 0 0 1-8 0c0-1 .3-2 1-3 0 2 1 3 2 3 0-3-1-5 1-9z"/><path d="M8 13a6 6 0 0 0 8 6"/></svg>',
		clock: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
		alert: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l9.5 17h-19z"/><path d="M12 10v4M12 17.5v.5"/></svg>',
		phone: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/></svg>',
		percent: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 5L5 19"/><circle cx="7" cy="7" r="2.5"/><circle cx="17" cy="17" r="2.5"/></svg>',
		chev: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>',
		x: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/></svg>',
	};
	const kpi = (n, l, c, ico, pop) => `<div class="card kpi ${c}${pop ? " pop" : ""}"${pop ? ` data-pop="${pop}" title="${__("Click for the list")}"` : ""}><div class="ico">${ICONS[ico] || ico}</div><div><b>${n}</b><span>${l}</span></div></div>`;
	const popTable = (title, head, rows, wide = false, sub = "", data = null) => {
		const d = new frappe.ui.Dialog({ title, size: wide ? "extra-large" : "large", fields: [{ fieldtype: "HTML", fieldname: "body" }] });
		d.$wrapper.on("click", "[data-logcall]", (e) => { const $b = $(e.currentTarget); logCall($b.attr("data-logcall"), $b.attr("data-name"), () => d.hide(), $b.attr("data-plan"), $b.attr("data-due")); });
		// status chips: when the list mixes statuses, let the user narrow it to one
		const ORDER = ["New", "Demo Scheduled", "Demo Attended", "Converted", "Lost"];
		const counts = data ? ORDER.map(st => [st, data.filter(x => x.status === st).length]).filter(x => x[1]) : [];
		if (counts.length > 1) {
			const chip = (k, l, n, on) => `<button class="btn btn-xs ${on ? "btn-primary" : "btn-default"}" data-chip="${k}" style="margin:0 6px 10px 0;border-radius:12px">${l} <b>${n}</b></button>`;
			sub = `<div data-chips>${chip("", __("All"), data.length, true)}${counts.map(([st, n]) => chip(st, __(st), n, false)).join("")}</div>` + sub;
			d.$wrapper.on("click", "[data-chip]", (e) => {
				const k = $(e.currentTarget).attr("data-chip");
				d.$wrapper.find("[data-chip]").removeClass("btn-primary").addClass("btn-default");
				$(e.currentTarget).removeClass("btn-default").addClass("btn-primary");
				d.$wrapper.find("table.enq-pop tbody").html(popRows(k ? data.filter(x => x.status === k) : data).join("") || `<tr><td colspan="${head.length}" class="text-muted">${__("Nothing to show.")}</td></tr>`);
			});
		}
		d.fields_dict.body.$wrapper.html(`<style>.enq-pop td, .enq-pop th { border: 1px solid #94a3b8 !important; padding: 8px 10px !important; vertical-align: top; } .enq-pop th { background: #e2e8f0; font-weight: 700; color: #0f172a; white-space: nowrap; } .enq-pop tbody tr:nth-child(even) td { background: #fafafa; } .enq-pop .nw { white-space: nowrap; } .enq-pop a { color: #2563eb; text-decoration: underline; font-weight: 600; } .enq-pop .pill { display: inline-block; font-size: 11px; font-weight: 700; padding: 2px 9px; border-radius: 10px; white-space: nowrap; } .enq-pop .pill.New { background: #e2e8f0; color: #334155; } .enq-pop .pill.DemoScheduled { background: #dbeafe; color: #1e40af; } .enq-pop .pill.DemoAttended { background: #ffedd5; color: #9a3412; } .enq-pop .pill.Converted { background: #dcfce7; color: #166534; } .enq-pop .pill.Lost { background: #fee2e2; color: #991b1b; } .enq-pop .due { font-weight: 700; white-space: nowrap; } .enq-pop .due.overdue { color: #dc2626; } .enq-pop .due.today { color: #d97706; } .enq-pop .due.upcoming { color: #2563eb; } .enq-pop .due.none { color: #94a3b8; font-weight: 400; }</style>${sub}<div style="max-height:75vh;overflow-y:auto;overflow-x:hidden"><table class="table table-bordered enq-pop" style="font-size:13px;width:100%;margin:0"><thead><tr>${head.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("") || `<tr><td colspan="${head.length}" class="text-muted">${__("Nothing to show.")}</td></tr>`}</tbody></table></div>`);
		d.show();
	};
	const enqLink = (r) => `<a href="/app/student-enquiry/${esc(r.name)}"><b>${esc(r.student_name || r.mobile || r.name)}</b></a><br><small class="text-muted">${esc(r.mobile || "")}</small>`;
	const popRows = (rows) => rows.map(r => `<tr><td>${enqLink(r)}</td><td>${esc(r.batch_name || "")}</td><td>${pill(r.status)}</td><td class="nw">${esc(r.counsellor_name)}</td><td class="nw"><a href="/app/student-follow-up?reference_name=${encodeURIComponent(r.name)}&status=Closed">${r.followups_done} ${__("done")}</a>${r.followups_open ? ` · <a href="${r.next_followup ? `/app/student-follow-up/${esc(r.next_followup)}` : `/app/student-follow-up?reference_name=${encodeURIComponent(r.name)}&status=Open`}">${r.followups_open} ${__("open")}</a>` : ""}</td><td>${nextCell(r)}</td><td class="notes">${esc(r.last_followup_notes || "")}</td><td>${callBtn(r)}</td></tr>`);
	const POP_HEAD = [__("Enquiry"), __("Batch"), __("Status"), __("Counsellor"), __("Follow-ups"), __("Next follow-up"), __("Last call"), ""];
	const nextCell = (r) => `${dueCell(r)}${r.next_followup_notes && OPEN.includes(r.status) ? `<br><small class="notes">${esc(r.next_followup_notes.slice(0, 80))}${r.next_followup_notes.length > 80 ? "…" : ""}</small>` : ""}`;
	const OPEN = ["New", "Demo Scheduled", "Demo Attended"];
	const callBtn = (r) => OPEN.includes(r.status) ? `<button class="btn btn-xs btn-default" data-logcall="${esc(r.name)}" data-name="${esc(r.student_name || r.mobile || r.name)}" data-plan="${esc(r.next_followup_notes || "")}" data-due="${esc(r.next_followup_on || "")}">${r.followups_open ? __("Log call") : __("Log first call")}</button>` : "";
	function logCall(enquiry, who, after, plan, due) {
		frappe.prompt([
			{ fieldtype: "HTML", options: plan || due ? `<div style="background:#fef3c7;border:1px solid #fcd34d;border-radius:8px;padding:8px 12px;margin-bottom:8px"><b>${__("Pending call")}${due ? ` · ${__("due")} ${frappe.datetime.str_to_user(due)}` : ""}</b><br>${esc(plan || "")}<br><small class="text-muted">${__("Saving marks it done.")}</small></div>` : `<div class="text-muted small" style="margin-bottom:8px">${__("No call pending; this records the first one.")}</div>` },
			{ fieldname: "notes", fieldtype: "Small Text", label: __("What was said"), reqd: 1 },
			{ fieldname: "followup_type", fieldtype: "Select", label: __("How"), options: ["Call", "WhatsApp", "Message", "Email", "Meeting"], default: "Call", reqd: 1 },
			{ fieldname: "next_date", fieldtype: "Date", label: __("Next follow-up on"), description: __("Leave empty if no further call is planned") },
		], (v) => frappe.call({ method: "tnc_v2_360ithub.admissions.enquiry_overview.log_call", args: { enquiry, notes: v.notes, followup_type: v.followup_type, next_date: v.next_date || null }, freeze: true }).then(() => { frappe.show_alert({ message: __("Follow-up recorded"), indicator: "green" }); if (after) after(); load(); }),
			__("Log a call with {0}", [who]), __("Save"));
	}
	const dshort = (k, byMonth) => byMonth ? moment(k + "-01").format("MMM YY") : moment(k).format("D MMM");

	function chart(sel, opts) {
		const el = $body.find(sel)[0];
		if (!el) return;
		try { new frappe.Chart(el, Object.assign({ height: 230, animate: false }, opts)); } catch (e) { $(el).html(`<div class="text-muted">${__("Chart unavailable")}</div>`); }
	}

	function load() {
		$body.html(`<div class="card empty-state"><span class="text-muted">${__("Loading…")}</span></div>`);
		frappe.call({ method: M, args: { batch: state.batch, counsellor: state.counsellor, from_date: state.from, to_date: state.to } }).then((r) => {
			const d = r.message || {};
			$body.html(render(d));
			$body.find("[data-logcall]").on("click", (e) => { e.stopPropagation(); const $b = $(e.currentTarget); logCall($b.attr("data-logcall"), $b.attr("data-name"), null, $b.attr("data-plan"), $b.attr("data-due")); });
			$body.find("[data-enq]").on("click", (e) => { if ($(e.target).closest("a, button").length) return; frappe.set_route("Form", "Student Enquiry", $(e.currentTarget).attr("data-enq")); });
			$body.find("[data-batch]").on("click", (e) => {
				const b = $(e.currentTarget).attr("data-batch");
				if (!b) return;
				state.batch = b; fBatch.set_value(b); load();
			});
			if (fCoun) $body.find("[data-coun]").on("click", (e) => { state.counsellor = $(e.currentTarget).attr("data-coun"); fCoun.set_value(state.counsellor); load(); });
			const open = (x) => ["New", "Demo Scheduled", "Demo Attended"].includes(x.status);
			$body.find("[data-pop]").on("click", (e) => {
				const which = $(e.currentTarget).attr("data-pop"), E = d.enquiries;
				const lists = {
					all: [__("All enquiries"), E],
					open: [__("Remaining (not yet admitted, not lost)"), E.filter(open)],
					demo: [__("Demo attended, not yet admitted · hot leads"), E.filter(x => x.hot)],
					converted: [__("Converted to admission"), E.filter(x => x.status === "Converted")],
					lost: [__("Lost"), E.filter(x => x.status === "Lost")],
					today: [__("Follow-ups due today"), E.filter(x => x.due === "today")],
					overdue: [__("Overdue follow-ups"), E.filter(x => x.due === "overdue")],
					upcoming: [__("Upcoming follow-ups"), E.filter(x => x.due === "upcoming")],
					none: [__("Open enquiries with no follow-up yet"), E.filter(x => open(x) && !x.followups_done && !x.followups_open)],
				};
				if (which === "done") return popTable(__("Follow-ups done"), [__("Enquiry"), __("Date"), __("Purpose"), __("How"), __("By"), __("What was said")],
					(d.done_list || []).map(f => `<tr><td><a href="/app/student-enquiry/${esc(f.enquiry)}"><b>${esc(f.student_name || f.mobile || f.enquiry)}</b></a><br><small class="text-muted">${esc(f.mobile || "")}</small></td><td class="nw"><a href="/app/student-follow-up/${esc(f.name)}" title="${__("Open the follow-up")}">${dUser(f.follow_up_date)}</a></td><td class="nw">${esc(f.purpose || "")}</td><td class="nw">${esc(f.followup_type || "")}</td><td class="nw">${esc(f.done_by)}</td><td class="notes" style="max-width:360px">${esc(f.notes || "")}</td></tr>`), true);
				const [title, rows] = lists[which] || [which, []];
				const sub = which === "lost" && d.lost_reasons.length ? `<div style="margin:0 0 10px;font-size:13px;color:#475569"><b>${__("Why")}:</b> ${d.lost_reasons.map(x => `${esc(x.reason)} <b style="color:#dc2626">${x.count}</b>`).join(" · ")}</div>` : "";
				popTable(title, POP_HEAD, popRows(rows), true, sub, rows);
			});
			if (d.trend && d.trend.length > 1) chart("#c-trend", { type: "line", data: { labels: d.trend.map(x => dshort(x.key, d.trend_by_month)), datasets: [{ name: __("Enquiries"), values: d.trend.map(x => x.total) }, { name: __("Converted"), values: d.trend.map(x => x.converted) }] },
				colors: ["#6d5bc4", "#16a34a"], lineOptions: { regionFill: 1, hideDots: 0 }, axisOptions: { xAxisMode: "tick", xIsSeries: true }, tooltipOptions: { formatTooltipY: (v) => Math.round(v) } });
			else $body.find("#c-trend").html(`<div class="text-muted">${__("Needs enquiries on at least two dates.")}</div>`);
			const sc = d.status_counts || {};
			chart("#c-donut", { type: "donut", height: 230, maxSlices: 5, data: { labels: [__("New"), __("Demo Scheduled"), __("Demo Attended"), __("Converted"), __("Lost")], datasets: [{ values: [sc.New || 0, sc["Demo Scheduled"] || 0, sc["Demo Attended"] || 0, sc.Converted || 0, sc.Lost || 0] }] }, colors: ["#94a3b8", "#2563eb", "#f97316", "#16a34a", "#dc2626"] });
			// list filters: search box + status segment
			let seg = "open";
			const apply = () => { const q = ($body.find("#enq-q").val() || "").toLowerCase(); $body.find("tr[data-enq]").each((i, tr) => { const $tr = $(tr), st = $tr.attr("data-status"), due = $tr.attr("data-due"); const ok = seg === "all" || (seg === "open" ? ["New", "Demo Scheduled", "Demo Attended"].includes(st) : seg === "due" ? ["today", "overdue"].includes(due) : st === seg); tr.hidden = !ok || (q && !$tr.text().toLowerCase().includes(q)); }); $body.find("#enq-count").text($body.find("tr[data-enq]:not([hidden])").length); };
			$body.find("#enq-q").on("input", apply);
			$body.find(".seg button").on("click", (e) => { seg = $(e.currentTarget).attr("data-seg"); $body.find(".seg button").removeClass("on"); $(e.currentTarget).addClass("on"); apply(); });
			apply();
		});
	}

	function render(d) {
		const title = d.batch ? (d.batch.batch_name || d.batch.name) : !d.manager ? __("My enquiries") : d.counsellor ? (d.counsellor_name || d.counsellor) : __("All enquiries");
		const meta = [
			d.batch ? `${esc(d.batch.mode || "")} · ${esc(d.batch.status || "")}${d.enrolled != null ? ` · ${d.enrolled} ${__("enrolled")}${d.batch.seats ? ` / ${d.batch.seats} ${__("seats")}` : ""}` : ""}` : "",
			d.counsellor && (d.batch || !d.manager) ? `${__("Counsellor")}: ${esc(d.counsellor_name || d.counsellor)}` : "",
			!d.batch && !d.counsellor ? __("every batch and counsellor") : "",
			d.from_date ? `${__("enquired")} ${dUser(d.from_date)} – ${dUser(d.to_date)}` : __("all time"),
		].filter(Boolean).join(" · ");
		const attn = d.overdue + d.due_today, sc = d.status_counts || {};
		const work = (pop, label, n, c) => `<div class="work-row${pop ? " pop" : ""}"${pop ? ` data-pop="${pop}"` : ""}><span class="work-label">${label}</span><span class="count ${c}">${n}</span>${pop ? `<span class="chev">${ICONS.chev}</span>` : `<span class="chev" style="visibility:hidden">${ICONS.chev}</span>`}</div>`;
		const seg = (k, l, n) => `<button data-seg="${k}"${k === "open" ? ' class="on"' : ""}>${l}${n != null ? ` (${n})` : ""}</button>`;
		const n = (v, c) => v ? (c ? `<span class="np ${c}">${v}</span>` : `<span>${v}</span>`) : `<span class="n0">0</span>`;
		const bucketTable = (rows, key, label, attr) => rows.length ? `<div class="scroll"><table class="table bt"><thead><tr><th>${label}</th><th class="c">${__("Total")}</th><th class="c" title="${__("Still being worked: not converted, not lost")}">${__("Remaining")}</th><th class="c" title="${__("Attended a demo, not yet admitted or lost")}">${__("Hot leads")}</th><th class="c">${__("Converted")}</th><th class="c">${__("Lost")}</th><th class="c" title="${__("Follow-ups due today / overdue")}">${__("Due / overdue")}</th><th class="c">${__("Conversion")}</th></tr></thead><tbody>
			${rows.map(x => `<tr class="${attr && x.key ? "row-link" : ""}"${attr && x.key ? ` ${attr}="${esc(x.key)}"` : ""}><td><b>${esc(x.label)}</b></td><td class="c">${n(x.total)}</td><td class="c">${n(x.open, "warn")}</td><td class="c">${n(x.demo, "hot")}</td><td class="c">${n(x.converted, "ok")}</td><td class="c">${n(x.lost, "bad")}</td><td class="c">${x.due_today || x.overdue ? `${n(x.due_today, "warn")} <span class="n0">/</span> ${n(x.overdue, "bad")}` : `<span class="n0">0 / 0</span>`}</td><td class="c">${bar(x.rate)}</td></tr>`).join("")}
			</tbody></table></div>` : `<div class="text-muted">${__("Nothing yet.")}</div>`;
		return `
			<div class="head"><div class="avatar"><img src="${esc(d.logo || "")}" alt=""></div><div><div class="hname">${esc(title)}</div><div class="hmeta">${meta}</div></div>
				<div class="hbadge ${attn ? "bad" : ""}">${attn ? __("{0} follow-ups due today or overdue", [attn]) : __("No follow-ups due")}</div></div>
			<div class="kpis">
				${kpi(d.total, __("Total enquiries") + `<br><small>${__("= remaining + converted + lost")}</small>`, "info", "inbox", "all")}
				${kpi(d.converted, __("Converted · admissions"), d.converted ? "good" : "info", "check", "converted")}
				${kpi(d.open, __("Remaining to work on") + `<br><small>${__("{0} new · {1} demo scheduled · {2} demo attended", [d.open_new, d.open_scheduled, d.demo_attended])}</small>`, d.open ? "warn" : "good", "phone", "open")}
				${kpi(d.demo_attended, __("Hot leads · demo attended, not yet admitted"), d.demo_attended ? "hot" : "info", "flame", "demo")}
				${kpi(d.due_today, __("Follow-ups due today"), d.due_today ? "warn" : "good", "clock", "today")}
				${kpi(d.overdue, __("Overdue follow-ups"), d.overdue ? "bad" : "good", "alert", "overdue")}
				${kpi(d.rate + "%", __("Conversion rate"), rateCls(d.rate, d.total), "percent")}
				${kpi(d.lost, __("Lost"), d.lost ? "bad" : "good", "x", "lost")}
			</div>
			<div class="grid3">
				<div class="card"><h6>${__("Enquiries over time")} <small class="text-muted">${d.trend_by_month ? __("by month") : __("by day")}</small></h6><div id="c-trend" class="chart"></div></div>
				<div class="card"><h6>${__("Where they stand")}</h6><div class="donut-wrap"><div id="c-donut" class="chart"></div><div class="lg">${[["New", "#94a3b8", sc.New], ["Demo Scheduled", "#2563eb", sc["Demo Scheduled"]], ["Demo Attended", "#f97316", sc["Demo Attended"]], ["Converted", "#16a34a", sc.Converted], ["Lost", "#dc2626", sc.Lost]].map(([l, c, v]) => `<div class="lg-row"><i style="background:${c}"></i><span>${__(l)}</span><b>${v || 0}</b></div>`).join("")}</div></div></div>
				<div class="card"><h6>${__("Follow-up work")}</h6>
					<div class="work">
						${work("today", __("Due today"), d.due_today, "warn")}
						${work("overdue", __("Overdue"), d.overdue, "bad")}
						${work("upcoming", __("Upcoming"), d.upcoming, "info")}
						${work("none", __("Open, never followed up"), d.no_followup, "ink")}
						${work("done", __("Follow-ups done so far"), d.followups_done, "ok")}
					</div>
				</div>
			</div>
			<div class="stack">
				${!d.batch ? `<div class="card"><h6>${__("By batch")} <small class="text-muted">${__("click a row to open that batch")}</small></h6>${bucketTable(d.by_batch, "batch", __("Batch"), "data-batch")}</div>` : ""}
				${d.manager && !d.counsellor ? `<div class="card"><h6>${__("By counsellor")} <small class="text-muted">${__("click a row to open that counsellor")}</small></h6>${bucketTable(d.by_counsellor, "counsellor", __("Counsellor"), "data-coun")}</div>` : ""}
				${(d.batch || d.counsellor) && d.by_source.length ? `<div class="card"><h6>${__("By source")}</h6>${bucketTable(d.by_source, "source", __("Source"))}</div>` : ""}
			</div>
			<div class="card">
				<div class="toolbar"><h6 style="margin:0">${__("Enquiries")} <small class="text-muted">(<span id="enq-count">0</span>) · ${__("click a row to open")}</small></h6>
					<div class="seg">${seg("open", __("Remaining"), d.open)}${seg("due", __("Due / overdue"), d.due_today + d.overdue)}${seg("Demo Attended", __("Hot leads"), d.demo_attended)}${seg("Converted", __("Converted"), d.converted)}${seg("Lost", __("Lost"), d.lost)}${seg("all", __("All"), d.total)}</div>
					<input id="enq-q" type="search" placeholder="${__("Search name, mobile, counsellor")}"></div>
				<div class="scroll"><table class="table"><thead><tr><th>${__("Enquiry")}</th><th>${__("Date")}</th>${d.batch ? "" : `<th>${__("Batch")}</th>`}<th title="${__("Remaining = New, Demo Scheduled or Demo Attended")}">${__("Status")}</th><th>${__("Counsellor")}</th><th class="c" title="${__("Follow-ups done so far · open ones")}">${__("Follow-ups")}</th><th>${__("Last call")}</th><th>${__("Next follow-up")}</th><th>${__("Source")}</th><th></th></tr></thead><tbody>
				${d.enquiries.map(r => `<tr class="row-link" data-enq="${esc(r.name)}" data-status="${esc(r.status)}" data-due="${esc(r.due || "")}"><td>${enqLink(r)}</td><td class="nw">${dUser(r.enquiry_date)}${r.days_open != null && r.days_open > 0 ? `<br><small class="mini">${__("{0} days open", [r.days_open])}</small>` : ""}</td>${d.batch ? "" : `<td>${esc(r.batch_name)}</td>`}<td>${pill(r.status)}${r.status === "Lost" && r.lost_reason ? `<br><small class="mini">${esc(r.lost_reason)}</small>` : ""}</td><td>${esc(r.counsellor_name)}</td><td class="c"><a href="/app/student-follow-up?reference_name=${encodeURIComponent(r.name)}&status=Closed" title="${__("Completed follow-ups of this enquiry")}">${n(r.followups_done, "info")}</a>${r.followups_open ? ` <small class="mini">· <a href="${r.next_followup ? `/app/student-follow-up/${esc(r.next_followup)}` : `/app/student-follow-up?reference_name=${encodeURIComponent(r.name)}&status=Open`}" title="${__("Open the pending follow-up")}">${r.followups_open} ${__("open")}</a></small>` : ""}</td><td>${r.last_followup_on ? `<span class="nw">${dUser(r.last_followup_on)}</span>${r.last_followup_notes ? `<br><small class="notes">${esc(r.last_followup_notes.slice(0, 90))}${r.last_followup_notes.length > 90 ? "…" : ""}</small>` : ""}` : `<span class="due none">—</span>`}</td><td>${nextCell(r)}</td><td class="mini">${esc(r.source || "")}</td><td>${callBtn(r)}</td></tr>`).join("") || `<tr><td colspan="10" class="text-muted">${__("No enquiries match. Create one with New Enquiry, or widen the filters.")}</td></tr>`}
				</tbody></table></div>
			</div>`;
	}
	load();
};
