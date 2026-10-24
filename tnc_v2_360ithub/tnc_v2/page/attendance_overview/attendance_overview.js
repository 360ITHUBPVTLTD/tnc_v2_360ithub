// Copyright (c) 2026, 360ITHub and contributors
// Student Attendance dashboard: a batch at a glance, or one student's days, subjects and hold.
frappe.pages["attendance-overview"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Student Attendance"), single_column: true });
	const M = "tnc_v2_360ithub.attendance.overview.get_overview";
	const esc = frappe.utils.escape_html;
	const state = { batch: null, student: null, from: frappe.datetime.month_start(), to: frappe.datetime.month_end() };

	const fBatch = page.add_field({ fieldname: "batch", label: __("Batch"), fieldtype: "Link", options: "Student Batch", change() { state.batch = fBatch.get_value(); state.student = null; fStudent.set_value(""); load(); } });
	const fStudent = page.add_field({ fieldname: "student", label: __("Student"), fieldtype: "Link", options: "Student", change() { state.student = fStudent.get_value(); load(); } });
	const fPeriod = page.add_field({ fieldname: "period", label: __("Period"), fieldtype: "DateRange", default: [state.from, state.to], change() {
		const v = fPeriod.get_value(); if (v && v.length === 2 && v[0] && v[1]) { state.from = v[0]; state.to = v[1]; load(); }
	} });
	page.add_inner_button(`${frappe.utils.icon("refresh", "sm")} ${__("Refresh")}`, () => load());
	page.set_secondary_action(__("Reports"), () => frappe.set_route("query-report", "Student Attendance Summary"));
	if (frappe.route_options) {
		if (frappe.route_options.student) { state.student = frappe.route_options.student; fStudent.set_value(state.student); }
		if (frappe.route_options.batch) { state.batch = frappe.route_options.batch; fBatch.set_value(state.batch); }
		frappe.route_options = null;
	}

	$(`<style>
		.att-ov { padding: 4px 0 48px; font-size: 14px; --ok: #16a34a; --ok-bg: #dcfce7; --warn: #d97706; --warn-bg: #fef3c7; --bad: #dc2626; --bad-bg: #fee2e2; --info: #2563eb; --info-bg: #dbeafe; --ink: #0f172a; --muted: #64748b; --line: #e2e8f0; --brand: #0f4c5c; }
		.att-ov .card { background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px; box-shadow: 0 2px 10px rgba(15,23,42,.04); min-width: 0; }
		.att-ov .card h6 { margin: 0 0 10px; font-size: 13px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; }
		.att-ov .head { display: flex; align-items: center; gap: 16px; background: linear-gradient(120deg, #2a7f95 0%, #3a9bb4 100%); color: #fff; border: 1px solid #2a7f95; border-radius: 16px; padding: 18px 22px; margin: 6px 0 14px; flex-wrap: wrap; }
		.att-ov .avatar { width: 68px; height: 68px; border-radius: 50%; background: #fff; display: grid; place-items: center; flex: none; padding: 3px; box-shadow: 0 2px 8px rgba(0,0,0,.18); } .att-ov .avatar img { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; display: block; }
		.att-ov .hname { font-size: 22px; font-weight: 700; line-height: 1.15; } .att-ov .hmeta { color: rgba(255,255,255,.92); font-size: 13px; margin-top: 3px; }
		.att-ov .hbadge { margin-left: auto; background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.45); color: #fff; border-radius: 999px; padding: 6px 14px; font-weight: 600; font-size: 13px; }
		.att-ov .hbadge.bad { background: #fee2e2; color: #991b1b; border-color: #fecaca; }
		.att-ov .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin-bottom: 14px; }
		.att-ov .kpi { display: flex; flex-direction: column; gap: 10px; align-items: center; text-align: center; } .att-ov .kpi.pop { cursor: pointer; } .att-ov .kpi.pop:hover { box-shadow: 0 6px 18px rgba(15,23,42,.10); border-color: #cbd5e1; }
		.att-ov .kpi .ico { width: 44px; height: 44px; border-radius: 12px; display: grid; place-items: center; background: #e2e8f0; color: #334155; flex: none; } .att-ov .kpi .ico svg { display: block; }
		.att-ov .kpi.good .ico { background: var(--ok-bg); color: var(--ok); } .att-ov .kpi.warn .ico { background: var(--warn-bg); color: var(--warn); } .att-ov .kpi.bad .ico { background: var(--bad-bg); color: var(--bad); } .att-ov .kpi.info .ico { background: var(--info-bg); color: var(--info); }
		.att-ov .kpi b { display: block; font-size: 1.6rem; line-height: 1.05; color: var(--ink); } .att-ov .kpi span { font-size: .82rem; color: var(--muted); }
		.att-ov .kpi.good b { color: var(--ok); } .att-ov .kpi.warn b { color: var(--warn); } .att-ov .kpi.bad b { color: var(--bad); }
		.att-ov .grid2 { display: grid; grid-template-columns: 1.4fr 1fr; gap: 12px; margin-bottom: 14px; }
		.att-ov .grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 14px; align-items: start; }
		@media (max-width: 992px) { .att-ov .grid2, .att-ov .grid3 { grid-template-columns: 1fr; } }
		.att-ov .chart { min-height: 0; }
		.att-ov .donut-wrap { display: flex; align-items: center; gap: 14px; } .att-ov .donut-wrap .chart { flex: 0 0 40%; min-width: 0; display: flex; align-items: center; justify-content: center; align-self: stretch; } .att-ov .donut-wrap .chart svg { width: 100%; height: auto; overflow: visible; transform: translateY(16%) scale(1.8); transform-origin: 50% 50%; } .att-ov .donut-wrap .chart-legend { display: none; }
		.att-ov .donut-wrap .lg { flex: 0 0 calc(60% - 14px); display: flex; flex-direction: column; gap: 6px; min-width: 0; } .att-ov .lg-row { display: flex; align-items: center; gap: 8px; font-size: 13px; padding: 4px 8px; } .att-ov .lg-row i { width: 10px; height: 10px; border-radius: 3px; flex: none; } .att-ov .lg-row span { flex: 1; color: var(--ink); } .att-ov .lg-row b { font-weight: 800; font-variant-numeric: tabular-nums; }
		.att-ov .donut-wrap .graph-svg-tip { font-size: 11px !important; padding: 0 !important; } .att-ov .donut-wrap .graph-svg-tip .title { font-size: 11px !important; font-weight: 600; text-transform: none; padding: 5px 8px !important; margin: 0 !important; } .att-ov .donut-wrap .graph-svg-tip ul.data-point-list li { min-width: 0 !important; padding: 0 8px 5px !important; font-size: 11px !important; } .att-ov .donut-wrap .graph-svg-tip ul.data-point-list { margin: 0 !important; } .att-ov .donut-wrap .graph-svg-tip .svg-pointer { display: none; } .att-ov .chart .chart-container, .att-ov .chart svg { overflow: visible; }
		.att-ov table { font-size: 13px; margin: 0; } .att-ov td, .att-ov th { padding: 9px 10px !important; vertical-align: middle; border-color: var(--line) !important; }
		.att-ov th { background: #f1f5f9; font-weight: 700; color: #334155; font-size: 12px; text-transform: uppercase; letter-spacing: .05em; }
		.att-ov tbody tr:hover td { background: #f1f5f9; } .att-ov tr.row-link { cursor: pointer; }
		.att-ov tr.day-start td { border-top: 2px solid #94a3b8 !important; } .att-ov tbody tr:first-child td { border-top: 0 !important; }
		.att-ov .bar { display: inline-flex; align-items: center; gap: 8px; min-width: 150px; } .att-ov .bar i { flex: 1; height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden; display: block; } .att-ov .bar i b { display: block; height: 100%; }
		.att-ov .pill { display: inline-block; font-size: 11px; font-weight: 700; padding: 2px 9px; border-radius: 10px; }
		.att-ov .pill.Present { background: var(--ok-bg); color: #166534; } .att-ov .pill.Partial, .att-ov .pill.Late { background: var(--warn-bg); color: #92400e; } .att-ov .pill.Absent { background: var(--bad-bg); color: #991b1b; } .att-ov .pill.Leave { background: var(--info-bg); color: #1e40af; }
		.att-ov .chap { font-size: 12px; color: var(--brand); }
		.att-ov .subj-list { max-height: 260px; overflow-y: scroll; overflow-x: hidden; display: flex; flex-direction: column; gap: 8px; padding-right: 12px; scrollbar-width: thin; scrollbar-color: #cbd5e1 transparent; }
		.att-ov .subj-list::-webkit-scrollbar { width: 6px; } .att-ov .subj-list::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; } .att-ov .subj-list::-webkit-scrollbar-track { background: transparent; }
		.att-ov .subj-row { display: grid; grid-template-columns: minmax(0, 1fr) 150px; gap: 10px; align-items: center; }
		.att-ov .subj-name { font-weight: 600; font-size: 13px; min-width: 0; }
		.att-ov .subj-name small { display: block; font-weight: 400; color: var(--muted); white-space: normal; line-height: 1.3; }
		.att-ov .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 5px; }
		.att-ov .cal-head { font-size: 11px; color: #334155; font-weight: 700; text-align: center; text-transform: uppercase; letter-spacing: .05em; padding-bottom: 4px; }
		.att-ov .cal-cell { border-radius: 8px; min-height: 44px; padding: 4px 6px; font-size: 12px; border: 1px solid var(--line); background: #fff; }
		.att-ov .cal-cell b { display: block; font-weight: 600; } .att-ov .cal-cell span { font-size: 11px; font-weight: 600; }
		.att-ov .cal-cell.empty { border: 0; background: transparent; } .att-ov .cal-cell.none { color: #94a3b8; background: #f8fafc; border-color: #f1f5f9; }
		.att-ov .cal-cell.Present { background: var(--ok-bg); border-color: #86efac; color: #166534; cursor: pointer; } .att-ov .cal-cell.Late { background: var(--warn-bg); border-color: #fcd34d; color: #92400e; cursor: pointer; }
		.att-ov .cal-cell.Partial { background: #fef9c3; border-color: #fde047; color: #854d0e; cursor: pointer; }
		.att-ov .cal-cell.Absent { background: var(--bad-bg); border-color: #fca5a5; color: #991b1b; cursor: pointer; } .att-ov .cal-cell.Leave { background: var(--info-bg); border-color: #93c5fd; color: #1e40af; cursor: pointer; }
		.att-ov .legend { font-size: 12px; color: var(--muted); margin-top: 10px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
		.att-ov .legend span { padding: 1px 8px; border-radius: 6px; } .att-ov .legend .Present { background: var(--ok-bg); } .att-ov .legend .Late { background: var(--warn-bg); } .att-ov .legend .Absent { background: var(--bad-bg); } .att-ov .legend .Leave { background: var(--info-bg); } .att-ov .legend .none { background: #f1f5f9; }
		.att-ov .toolbar { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }
		.att-ov .toolbar input { font-size: 13px; padding: 6px 10px; border: 1px solid var(--line); border-radius: 8px; min-width: 220px; }
		.att-ov .empty-state { padding: 40px 20px; text-align: center; color: var(--muted); }
		.att-ov .empty-state b { display: block; font-size: 16px; color: var(--ink); margin-bottom: 6px; }
	</style>`).appendTo(page.main);
	const $body = $(`<div class="att-ov"></div>`).appendTo(page.main);

	const col = (v) => v >= 75 ? "#16a34a" : v >= 50 ? "#d97706" : "#dc2626";  // plain colours: also used inside dialogs, outside the page's CSS variables
	const cls = (v) => v >= 75 ? "good" : v >= 50 ? "warn" : "bad";
	const bar = (v) => `<span class="bar" style="display:inline-flex;align-items:center;gap:8px;width:100%;min-width:120px"><i style="flex:1;height:8px;background:#e2e8f0;border-radius:4px;overflow:hidden;display:block"><b style="display:block;height:100%;width:${Math.min(100, v)}%;background:${col(v)}"></b></i><span style="color:${col(v)};font-weight:700;white-space:nowrap">${v}%</span></span>`;
	const pill = (s) => `<span class="pill ${esc(s)}">${__(s)}</span>`;
	// line icons (stroke follows the card colour)
	const ICONS = {
		check: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.5 2.5L16 9.5"/></svg>',
		calendar: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
		book: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5a2 2 0 0 1 2-2h12v16H6a2 2 0 0 0-2 2z"/><path d="M4 19a2 2 0 0 1 2-2h12"/><path d="M9 7h6"/></svg>',
		clock: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
		users: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><circle cx="17" cy="9" r="2.5"/><path d="M15.5 14.5a5 5 0 0 1 6 5"/></svg>',
		pause: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M10 9v6M14 9v6"/></svg>',
		alert: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l9.5 17h-19z"/><path d="M12 10v4M12 17.5v.5"/></svg>',
	};
	const kpi = (n, l, c, ico, pop) => `<div class="card kpi ${c}${pop ? " pop" : ""}"${pop ? ` data-pop="${pop}" title="${__("Click for details")}"` : ""}><div class="ico">${ICONS[ico] || ico}</div><div><b>${n}</b><span>${l}</span></div></div>`;
	// wide only for tables with many columns; the rest open at the normal dialog width
	const popTable = (title, head, rows, wide = false) => {
		const d = new frappe.ui.Dialog({ title, size: wide ? "extra-large" : "large", fields: [{ fieldtype: "HTML", fieldname: "body" }] });
		d.fields_dict.body.$wrapper.html(`<style>.att-pop td, .att-pop th { border: 1px solid #94a3b8 !important; padding: 8px 10px !important; vertical-align: top; } .att-pop th { background: #e2e8f0; font-weight: 700; color: #0f172a; white-space: nowrap; } .att-pop td[rowspan] { background: #f8fafc; white-space: nowrap; } .att-pop tbody tr:nth-child(even) td { background: #fafafa; } .att-pop .nw { white-space: nowrap; } .att-pop a, .att-pop a.plink { color: #2563eb; text-decoration: underline; font-weight: 600; }</style><div style="max-height:75vh;overflow-y:auto;overflow-x:hidden"><table class="table table-bordered att-pop" style="font-size:13px;width:100%;margin:0"><thead><tr>${head.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("") || `<tr><td colspan="${head.length}" class="text-muted">${__("Nothing to show.")}</td></tr>`}</tbody></table></div>`);
		d.show();
	};
	const hhmm = (t) => { if (!t) return ""; const [h, m] = String(t).split(":"); const H = parseInt(h, 10); return `${H % 12 || 12}:${m} ${H < 12 ? "AM" : "PM"}`; };
	const inout = (x) => x.in_time ? `${hhmm(x.in_time)}${x.out_time ? " – " + hhmm(x.out_time) : ""}` : "—";
	const dshort = (d) => moment(d).format("D MMM");
	const DONUT = [["Present", "#16a34a"], ["Late", "#d97706"], ["Partial", "#eab308"], ["Absent", "#dc2626"], ["Leave", "#2563eb"]];
	const donutCard = (title, vals) => `<div class="card"><h6>${title}</h6><div class="donut-wrap"><div id="c-donut" class="chart"></div><div class="lg">${DONUT.map(([l, c], i) => `<div class="lg-row"><i style="background:${c}"></i><span>${__(l)}</span><b>${vals[i] || 0}</b></div>`).join("")}</div></div></div>`;

	function chart(sel, opts) {
		const el = $body.find(sel)[0];
		if (!el) return;
		try { new frappe.Chart(el, Object.assign({ height: 230, animate: false }, opts)); } catch (e) { $(el).html(`<div class="text-muted">${__("Chart unavailable")}</div>`); }
	}
	// subjects as a scrollable list with a bar each (28 subjects do not fit a bar chart)
	const subjectList = (subjects, batchView) => subjects.length
		? `<div class="subj-list">${subjects.map(x => `<div class="subj-row"><div class="subj-name" title="${esc(x.subject)}">${esc(x.subject)}<small>${batchView
			? `${x.classes} ${x.classes === 1 ? __("class") : __("classes")} · ${__("{0} of {1} attended", [x.present, x.held - x.leave])}`
			: `${x.classes} ${x.classes === 1 ? __("class") : __("classes")} · ${__("attended")} ${x.present}/${x.held - x.leave}`}${!batchView && x.partial ? ` · ${__("partial")} ${x.partial}` : ""}${!batchView && x.leave ? ` · ${__("leave")} ${x.leave}` : ""}</small></div>${bar(x.pct)}</div>`).join("")}</div>`
		: `<div class="text-muted">${__("No classes with times yet.")}</div>`;
	function subjectChart() {}
	function calendar(days, from, to) {
		const by = {}; days.forEach(x => by[x.date] = x);
		const start = frappe.datetime.str_to_obj(from), end = frappe.datetime.str_to_obj(to);
		const months = [];
		for (let m = new Date(start.getFullYear(), start.getMonth(), 1); m <= end; m = new Date(m.getFullYear(), m.getMonth() + 1, 1)) months.push(m);
		const label = { Present: "P", Late: "L", Partial: "Pt", Absent: "A", Leave: "Lv" };
		return months.map(m => {
			const first = new Date(m.getFullYear(), m.getMonth(), 1), last = new Date(m.getFullYear(), m.getMonth() + 1, 0);
			let cells = "";
			for (let i = 0; i < (first.getDay() + 6) % 7; i++) cells += `<div class="cal-cell empty"></div>`;
			for (let dd = 1; dd <= last.getDate(); dd++) {
				const dt = new Date(m.getFullYear(), m.getMonth(), dd), key = frappe.datetime.obj_to_str(dt), x = by[key], out = dt < start || dt > end;
				cells += x ? `<div class="cal-cell ${x.status}" data-att="${esc(x.name)}" title="${esc(inout(x))}"><b>${dd}</b><span>${label[x.status] || ""}${x.classes_held ? ` ${x.classes_present}/${x.classes_held}` : ""}</span></div>`
					: `<div class="cal-cell ${out ? "empty" : "none"}"><b>${dd}</b></div>`;
			}
			return `<div style="margin-bottom:10px"><div style="font-weight:700;margin-bottom:6px">${moment(m).format("MMMM YYYY")}</div><div class="cal-grid">${["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(w => `<div class="cal-head">${w}</div>`).join("")}${cells}</div></div>`;
		}).join("") + `<div class="legend"><span class="Present">P ${__("Present")}</span><span class="Late">L ${__("Late")}</span><span class="Partial" style="background:#fef9c3">Pt ${__("Partial · one punch")}</span><span class="Absent">A ${__("Absent")}</span><span class="Leave">Lv ${__("Leave")}</span><span class="none">${__("no class")}</span><span>· 3/4 = ${__("classes attended")} · ${__("click a day to open it")}</span></div>`;
	}

	function load() {
		if (!state.batch && !state.student) {
			$body.html(`<div class="card empty-state"><b>${__("Pick a batch or a student")}</b>${__("The batch view ranks students by attendance; the student view shows the calendar, subjects and every class.")}</div>`); return;
		}
		frappe.call({ method: M, args: { batch: state.batch, student: state.student, from_date: state.from, to_date: state.to } }).then((r) => {
			const d = r.message || {};
			$body.html(state.student ? renderStudent(d) : renderBatch(d));
			$body.find("[data-att]").on("click", (e) => frappe.set_route("Form", "Student Attendance", $(e.currentTarget).attr("data-att")));
			$body.find("[data-student]").on("click", (e) => { state.student = $(e.currentTarget).attr("data-student"); fStudent.set_value(state.student); load(); });
			if (state.student) {
				const stPill = (st) => `<span style="font-weight:700;color:${({ Present: "#15803d", Late: "#b45309", Partial: "#b45309", Absent: "#b91c1c", Leave: "#1e40af" })[st] || "#334155"}">${__(st)}</span>`;
				const mins = (t) => { const [h, m] = String(t).split(":").map(Number); return h * 60 + m; };
				const firstStart = (x) => { const t = x.classes.map(c => c.from_time).filter(Boolean).sort((a, b) => mins(a) - mins(b)); return t.length ? t[0] : null; };
				$body.find("[data-pop]").on("click", (e) => {
					const which = $(e.currentTarget).attr("data-pop"), days = d.days.slice().reverse(), held = d.enrolments.filter(x => x.status === "On Hold");
					if (which === "sdays") popTable(__("Class days"), [__("Date"), __("Status"), __("In / Out"), __("Classes attended")],
						days.map(x => `<tr><td class="nw"><a href="/app/student-attendance/${esc(x.name)}">${frappe.datetime.str_to_user(x.date)}</a></td><td>${stPill(x.status)}</td><td>${inout(x)}</td><td>${x.classes_held ? `${x.classes_present}/${x.classes_held}` : "—"}</td></tr>`));
					if (which === "smissed") popTable(__("Classes missed or partly attended"), [__("Date · in / out"), __("Subject"), __("Class time"), __("Status")],
						days.flatMap(x => { const miss = x.classes.filter(c => !["Present", "Late"].includes(c.status)); return miss.map((c, i) => `<tr>${i === 0 ? `<td rowspan="${miss.length}" class="nw"><b>${frappe.datetime.str_to_user(x.date)}</b><br><small class="text-muted">${inout(x)}</small></td>` : ""}<td><b>${esc(c.subject || "")}</b>${c.chapter ? `<br><small>${esc(c.chapter)}</small>` : ""}<br><small class="text-muted">${esc(c.teacher_name || "")}</small></td><td class="nw">${hhmm(c.from_time)} – ${hhmm(c.to_time)}</td><td>${stPill(c.status)}${c.status === "Partial" ? ` <small class="text-muted">${c.covered_minutes}/${c.class_minutes} ${__("min")}</small>` : ""}</td></tr>`); }));
					if (which === "slate") popTable(__("Late arrivals"), [__("Date"), __("Class"), __("Class start"), __("First punch"), __("Late by")],
						days.flatMap(x => x.classes.filter(c => c.status === "Late").map(c => { const mins = x.in_time ? Math.max(0, Math.round((frappe.datetime.str_to_obj(x.date + " " + x.in_time) - frappe.datetime.str_to_obj(x.date + " " + c.from_time)) / 60000)) : null; return `<tr><td class="nw"><a href="/app/student-attendance/${esc(x.name)}" class="plink">${frappe.datetime.str_to_user(x.date)}</a></td><td><b>${esc(c.subject || "")}</b>${c.chapter ? `<br><small>${esc(c.chapter)}</small>` : ""}<br><small class="text-muted">${esc(c.teacher_name || "")}</small></td><td class="nw">${hhmm(c.from_time)}</td><td class="nw">${hhmm(x.in_time)}</td><td class="nw">${mins != null ? `<b style="color:#b45309">${mins} ${__("min")}</b>` : "—"}</td></tr>`; })));
					if (which === "sstreak") { const streak = []; for (const x of days) { if (x.status === "Absent") streak.push(x); else break; }
						popTable(held.length ? __("Consecutive absences · on hold") : __("Consecutive absences"), [__("Date"), __("Classes missed")],
							[...(held.length ? [`<tr><td colspan="2" style="background:#fee2e2;color:#991b1b"><b>${__("On Hold")}</b> ${held[0].hold_on ? __("since {0}", [frappe.datetime.str_to_user(held[0].hold_on)]) : ""} · ${esc(held[0].hold_reason || "")} · ${__("Release Hold on the student record")}</td></tr>`] : []),
							...streak.map(x => `<tr><td>${frappe.datetime.str_to_user(x.date)}</td><td>${x.classes_held ? x.classes.map(c => esc(c.subject || "")).join(", ") : __("day")}</td></tr>`)]); }
				});
				subjectChart(d.subjects);
				if (d.daily.length) chart("#c-trend", { type: "line", data: { labels: d.daily.map(x => dshort(x.date)), datasets: [{ name: __("Classes attended %"), values: d.daily.map(x => x.pct) }] },
					colors: ["#146b7f"], lineOptions: { regionFill: 1, hideDots: 0 }, axisOptions: { xAxisMode: "tick", xIsSeries: true }, tooltipOptions: { formatTooltipY: (v) => v + "%" } });
				const t = d.totals;
				chart("#c-donut", { type: "donut", height: 230, maxSlices: 5, data: { labels: [__("Present"), __("Late"), __("Partial"), __("Absent"), __("Leave")], datasets: [{ values: [t.present - t.late, t.late, t.partial || 0, t.absent, t.leave] }] }, colors: ["#16a34a", "#d97706", "#eab308", "#dc2626", "#2563eb"] });
			} else {
				subjectChart(d.subjects);
				if (d.daily.length) chart("#c-trend", { type: "line", data: { labels: d.daily.map(x => dshort(x.date)), datasets: [{ name: __("Students present %"), values: d.daily.map(x => x.pct) }] },
					colors: ["#146b7f"], lineOptions: { regionFill: 1 }, axisOptions: { xAxisMode: "tick", xIsSeries: true }, tooltipOptions: { formatTooltipY: (v) => v + "%" } });
				const sc = d.status_counts || {};
				chart("#c-donut", { type: "donut", height: 230, maxSlices: 5, data: { labels: [__("Present"), __("Late"), __("Partial"), __("Absent"), __("Leave")], datasets: [{ values: [sc.Present || 0, sc.Late || 0, sc.Partial || 0, sc.Absent || 0, sc.Leave || 0] }] }, colors: ["#16a34a", "#d97706", "#eab308", "#dc2626", "#2563eb"] });
				// one-punch days: add the missing punch after the teacher confirms; the row rebuilds at once
				$body.find("[data-addpunch]").on("click", (e) => {
					e.stopPropagation();
					const $b = $(e.currentTarget), student = $b.attr("data-student"), date = $b.attr("data-date"), dir = $b.attr("data-dir"), tm = $b.attr("data-time") || "17:00:00";
					frappe.prompt([
						{ fieldname: "punch_time", fieldtype: "Datetime", label: __("Punch time"), default: `${date} ${tm}`, reqd: 1 },
						{ fieldname: "direction", fieldtype: "Select", label: __("Direction"), options: ["IN", "OUT"], default: dir, reqd: 1 },
						{ fieldtype: "HTML", options: `<div class="text-muted small">${__("Only after the teacher confirms the student was in class. Saved with device MANUAL and your name; the day is rebuilt at once.")}</div>` },
					], (v) => frappe.call({ method: "tnc_v2_360ithub.attendance.punches.add_manual", args: { student, punch_time: v.punch_time, direction: v.direction }, freeze: true }).then(() => { frappe.show_alert({ message: __("Punch added"), indicator: "green" }); load(); }),
					__("Add the missing {0} punch for {1}", [dir, $b.attr("data-name")]), __("Add punch"));
				});
				$body.find("[data-pop]").on("click", (e) => {
					const which = $(e.currentTarget).attr("data-pop");
					if (which === "days") popTable(__("Class days"), [__("Date"), __("Subject"), __("Teacher"), __("Time"), __("Attendance")],
						(d.class_days_detail || []).flatMap(x => x.classes.length ? x.classes.map((c, i) => `<tr>${i === 0 ? `<td rowspan="${x.classes.length}"><b style="white-space:nowrap">${frappe.datetime.str_to_user(x.date)}</b><br><small class="text-muted">${x.present}/${x.total} ${__("came")}</small></td>` : ""}<td>${esc(c.subject || "")}${c.chapter ? `<br><span class="chap">${esc(c.chapter)}</span>` : ""}</td><td class="nw">${esc(c.teacher_name || "")}</td><td class="nw">${hhmm(c.from_time)} – ${hhmm(c.to_time)}</td><td style="white-space:nowrap"><span style="color:#15803d;font-weight:700">${c.present} ${__("present")}</span>${c.partial ? ` · <span style="color:#b45309;font-weight:700">${c.partial} ${__("partial")}</span>` : ""} · <span style="color:#b91c1c;font-weight:700">${c.absent} ${__("absent")}</span></td></tr>`)
							: [`<tr><td><b>${frappe.datetime.str_to_user(x.date)}</b></td><td colspan="3" class="text-muted">${__("day only, no class times")}</td><td>${x.present}/${x.total} ${__("came")}</td></tr>`]), true);
					if (which === "low") popTable(__("Students below 75%"), [__("Student"), __("Attendance"), __("Days"), __("Classes"), __("Consecutive absences")],
						d.students.filter(s => (s.classes ? s.class_pct : s.day_pct) < 75).map(s => `<tr><td><a href="/app/student/${esc(s.student)}">${esc(s.student_name)}</a></td><td>${bar(s.classes ? s.class_pct : s.day_pct)}</td><td>${s.present + s.late}/${s.days}</td><td>${s.classes ? `${s.classes_present}/${s.classes}` : "—"}</td><td>${s.consecutive_absences}</td></tr>`));
					if (which === "hold") popTable(__("Students on hold"), [__("Student"), __("Since"), __("Reason"), __("Consecutive absences")],
						d.students.filter(s => s.enrol_status === "On Hold").map(s => `<tr><td><a href="/app/student/${esc(s.student)}">${esc(s.student_name)}</a><br><a href="/app/student/${esc(s.student)}" style="font-size:12px;font-weight:400">${__("Release Hold")}</a></td><td>${s.hold_on ? frappe.datetime.str_to_user(s.hold_on) : ""}</td><td>${esc(s.hold_reason || "")}</td><td>${s.consecutive_absences}</td></tr>`));
				});
				$body.find("#stu-q").on("input", (e) => { const q = e.target.value.toLowerCase(); $body.find("tr[data-student]").each((i, tr) => { tr.hidden = q && !$(tr).text().toLowerCase().includes(q); }); });
			}
		});
	}

	function renderStudent(d) {
		const t = d.totals, s = d.student, held = d.enrolments.filter(e => e.status === "On Hold");
		const inRow = Math.max(0, ...d.enrolments.map(e => e.consecutive_absences || 0));
		const initials = (s.student_name || "?").split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();
		return `
			<div class="head"><div class="avatar"><img src="${esc(d.logo || "")}" alt=""></div><div><div class="hname">${esc(s.student_name)}</div><div class="hmeta">${esc(s.mobile || "")} · ${d.enrolments.map(e => esc(e.batch)).join(", ") || __("not enrolled")} · ${frappe.datetime.str_to_user(d.from_date)} – ${frappe.datetime.str_to_user(d.to_date)}${s.biometric_id ? "" : ` · ${__("no Biometric ID")}`}</div></div>
				<div class="hbadge ${held.length ? "bad" : ""}">${held.length ? __("ON HOLD since {0}", [frappe.datetime.str_to_user(held[0].hold_on)]) : __("Active")}</div></div>
			<div class="kpis">
				${kpi(t.day_pct + "%", __("Attendance · {0} of {1} days", [t.present, t.class_days - t.leave]) + (t.leave ? ` · ${t.leave} ${__("leave")}` : ""), cls(t.day_pct), "check", "sdays")}
				${kpi(`${t.classes_present}/${t.classes_held}`, __("Classes attended"), t.classes_held ? cls(t.class_pct) : "info", "book", "smissed")}
				${kpi(d.days.reduce((n, x) => n + x.classes.filter(c => c.status === "Late").length, 0), __("Late arrivals (classes)"), d.days.some(x => x.classes.some(c => c.status === "Late")) ? "warn" : "good", "clock", "slate")}
				${kpi(inRow, __("Consecutive absences") + (held.length ? " · " + __("hold") : ""), inRow >= 3 || held.length ? "bad" : "good", held.length ? "pause" : "alert", "sstreak")}
			</div>
			<div class="grid3">
				<div class="card"><h6>${__("Classes attended, day by day")}</h6><div id="c-trend" class="chart"></div></div>
				<div class="card"><h6>${__("By subject")} <small class="text-muted" style="text-transform:none;letter-spacing:0">${__("lowest first")}</small></h6>${subjectList(d.subjects)}</div>
				${donutCard(__("Days"), [t.present - t.late, t.late, t.partial || 0, t.absent, t.leave])}
			</div>
			<div class="grid2">
				<div class="card"><h6>${__("Calendar")}</h6>${calendar(d.days, d.from_date, d.to_date)}</div>
				<div class="card"><h6>${__("Subjects")}</h6>
					${d.subjects.length ? `<table class="table"><thead><tr><th>${__("Subject")}</th><th>${__("Classes")}</th><th>${__("Attended")}</th><th>${__("Attendance")}</th></tr></thead><tbody>${d.subjects.map(x => `<tr><td><b>${esc(x.subject)}</b></td><td>${x.held}</td><td>${x.present}${x.partial ? ` <small class="text-muted">+${x.partial} ${__("partial")}</small>` : ""}</td><td>${bar(x.pct)}</td></tr>`).join("")}</tbody></table>` : `<div class="text-muted">${__("No classes with times yet.")}</div>`}
				</div>
			</div>
			<div class="card"><h6>${__("Every class")}</h6>
			<table class="table"><thead><tr><th>${__("Date")}</th><th>${__("Subject")}</th><th>${__("Class time")}</th><th>${__("Student in / out")}</th><th>${__("Status")}</th></tr></thead><tbody>
			${d.days.slice().reverse().flatMap(x => x.classes.length ? x.classes.map((c, i) => `<tr class="row-link${i === 0 ? " day-start" : ""}" data-att="${esc(x.name)}"><td>${i === 0 ? `<b>${frappe.datetime.str_to_user(x.date)}</b>` : ""}</td><td><b>${esc(c.subject || "")}</b>${c.chapter ? `<br><span class="chap">${esc(c.chapter)}</span>` : ""}<br><small class="text-muted">${esc(c.teacher_name || "")}</small></td><td>${hhmm(c.from_time)} – ${hhmm(c.to_time)}</td><td>${inout(x)}</td><td>${pill(c.status)}${c.status === "Late" && x.in_time ? ` <small style="color:#b45309;font-weight:600">${__("by {0} min", [Math.max(0, Math.round((frappe.datetime.str_to_obj(x.date + " " + x.in_time) - frappe.datetime.str_to_obj(x.date + " " + c.from_time)) / 60000))])}</small>` : ""}${x.source === "Manual" ? ` <small class="text-muted">· ${__("marked by staff")}</small>` : c.status !== "Absent" ? ` <small class="text-muted">· ${c.covered_minutes} ${__("min")}</small>` : ""}</td></tr>`) : [`<tr class="row-link day-start" data-att="${esc(x.name)}"><td><b>${frappe.datetime.str_to_user(x.date)}</b></td><td class="text-muted">${__("day only")}</td><td></td><td>${inout(x)}</td><td>${pill(x.status)}${x.source === "Manual" ? ` <small class="text-muted">· ${__("marked by staff")}</small>` : ""}</td></tr>`]).join("") || `<tr><td colspan="5" class="text-muted">${__("Nothing yet.")}</td></tr>`}
			</tbody></table></div>`;
	}

	function renderBatch(d) {
		const name = d.batch.batch_name || d.batch.name;
		return `
			<div class="head"><div class="avatar"><img src="${esc(d.logo || "")}" alt=""></div><div><div class="hname">${esc(name)}</div><div class="hmeta">${esc(d.batch.mode || "")} · ${d.enrolled} ${__("students")} · ${frappe.datetime.str_to_user(d.from_date)} – ${frappe.datetime.str_to_user(d.to_date)}</div></div>
				<div class="hbadge ${d.on_hold ? "bad" : ""}">${d.on_hold ? __("{0} on hold", [d.on_hold]) : __("No holds")}</div></div>
			<div class="kpis">
				${kpi(d.avg_pct + "%", __("Average attendance"), cls(d.avg_pct), "check")}
				${kpi(`${d.class_days} <small style="font-size:.9rem;font-weight:600;color:#64748b">${d.class_days === 1 ? __("day") : __("days")}</small>`, __("{0} classes · {1} subjects", [d.classes_held, d.subjects.length]), "info", "calendar", "days")}
				${kpi(d.students.filter(s => (s.classes ? s.class_pct : s.day_pct) < 75).length, __("Students below 75%"), "warn", "users", "low")}
				${kpi(d.on_hold, __("Students on hold"), d.on_hold ? "bad" : "good", "pause", "hold")}
			</div>
			<div class="grid3">
				<div class="card"><h6>${__("Students present, by class day")}</h6><div id="c-trend" class="chart"></div></div>
				<div class="card"><h6 title="${__("% = students who attended the subject's classes ÷ students expected (less leave). Each student in each class counts once: 2 classes × 257 students = 514.")}">${__("By subject")} <small class="text-muted" style="text-transform:none;letter-spacing:0">${__("% of students who attended, lowest first")}</small></h6>${subjectList(d.subjects, true)}</div>
				${donutCard(__("Student-days"), [(d.status_counts || {}).Present || 0, (d.status_counts || {}).Late || 0, (d.status_counts || {}).Partial || 0, (d.status_counts || {}).Absent || 0, (d.status_counts || {}).Leave || 0])}
			</div>
			${(d.single_punch || []).length ? `<div class="card" style="margin-bottom:14px"><h6>${__("One punch only")} <small class="text-muted" style="text-transform:none;letter-spacing:0">${__("{0} days · IN without OUT or OUT without IN · add the missing punch once the teacher confirms", [d.single_punch.length])}</small></h6>
				<table class="table"><thead><tr><th>${__("Student")}</th><th>${__("Date")}</th><th>${__("Punch")}</th><th>${__("Status")}</th><th></th></tr></thead><tbody>
				${d.single_punch.slice().reverse().map(x => { const inOnly = (x.note || "").startsWith("In only"); return `<tr class="row-link" data-att="${esc(x.name)}"><td><b>${esc(x.student_name)}</b></td><td>${frappe.datetime.str_to_user(x.date)}</td><td>${inOnly ? `${__("IN")} ${hhmm(x.in_time)} · <span style="color:#b45309">${__("no OUT")}</span>` : `<span style="color:#b45309">${__("no IN")}</span> · ${__("OUT")} ${hhmm(x.out_time)}`}</td><td>${pill(x.status)}</td><td><button class="btn btn-xs btn-default" data-addpunch data-student="${esc(x.student)}" data-name="${esc(x.student_name)}" data-date="${esc(x.date)}" data-dir="${inOnly ? "OUT" : "IN"}" data-time="${inOnly ? "" : "10:00:00"}">${__("Add {0} punch", [inOnly ? "OUT" : "IN"])}</button></td></tr>`; }).join("")}
				</tbody></table></div>` : ""}
			<div class="card">
				<div class="toolbar"><h6 style="margin:0">${__("Students")} <small class="text-muted" style="text-transform:none;letter-spacing:0">${__("lowest first · click a name")}</small></h6><input id="stu-q" type="search" placeholder="${__("Search student")}"></div>
				<table class="table"><thead><tr><th>${__("Student")}</th><th title="${__("Classes attended out of classes held; days when the timesheet has no class time")}">${__("Attendance (classes)")}</th><th>${__("Days present")}</th><th>${__("Classes attended")}</th><th>${__("Late")}</th><th title="${__("Classes missed one after another; resets when the student attends")}">${__("Consecutive absences")}</th><th>${__("Status")}</th></tr></thead><tbody>
				${d.students.map(s => `<tr class="row-link" data-student="${esc(s.student)}"><td><b>${esc(s.student_name)}</b></td><td>${bar(s.classes ? s.class_pct : s.day_pct)}</td><td>${s.present + s.late}/${s.days}${s.partial ? ` <small style="color:#854d0e">${s.partial} ${__("partial")}</small>` : ""}${s.leave ? ` <small class="text-muted">${s.leave} ${__("leave")}</small>` : ""}</td><td>${s.classes ? `${s.classes_present}/${s.classes}` : "—"}</td><td>${s.late || 0}</td><td>${s.consecutive_absences ? `<b style="color:var(--bad)">${s.consecutive_absences}</b>` : 0}</td><td>${s.enrol_status === "On Hold" ? `<span class="pill Absent">${__("On Hold")}</span>` : `<span class="pill Present">${__("Active")}</span>`}</td></tr>`).join("") || `<tr><td colspan="7" class="text-muted">${__("No attendance in this period. Students need a Biometric ID, an enrolment in the batch, and a teacher timesheet with class time.")}</td></tr>`}
				</tbody></table>
			</div>`;
	}
	load();
};
