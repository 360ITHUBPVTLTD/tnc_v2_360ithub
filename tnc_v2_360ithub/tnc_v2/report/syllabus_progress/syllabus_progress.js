// Copyright (c) 2026, 360ITHub and contributors
const SP_METHOD = "tnc_v2_360ithub.tnc_v2.report.syllabus_progress.syllabus_progress.chapter_classes";

frappe.query_reports["Syllabus Progress"] = {
	filters: [
		{ fieldname: "batch", label: __("Batch"), fieldtype: "Link", options: "Student Batch" },
		{ fieldname: "subject", label: __("Subject"), fieldtype: "Link", options: "Subject" },
		{ fieldname: "teacher", label: __("Teacher"), fieldtype: "Link", options: "Teacher" },
		{ fieldname: "period", label: __("Period"), fieldtype: "DateRange" },
		{ fieldname: "include_pending", label: __("Count classes waiting for approval"), fieldtype: "Check", default: 0 },
		{ fieldname: "show_chapters", label: __("Show chapters"), fieldtype: "Check", default: 0 },
	],
	onload(report) {
		// a click anywhere on a row opens its classes: one chapter, or all of a subject in a batch
		report.page.main.on("click", ".report-wrapper .dt-scrollable .dt-row[data-row-index]", (e) => {
			if ($(e.target).closest("a").length) return;
			const data = (frappe.query_report.data || [])[cint($(e.currentTarget).attr("data-row-index"))];
			if (data && data.seq && data.classes) this.show_classes({ seq: data.seq }, data.chapter);
			else if (data && data.subject && data.classes) this.show_classes({ subject: data.subject, batch: data.batch || "" }, `${data.subject} · ${data.batch || ""}`);
		});
	},
	get_datatable_options(options) {
		return Object.assign(options, { serialNoColumn: false, checkboxColumn: false });
	},
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (column.fieldname === "pct" && data.done_text) {
			const c = data.pct >= 75 ? "green" : data.pct >= 40 ? "orange" : "red";
			value = `<div style="display:flex;align-items:center;gap:6px"><div style="flex:1;height:8px;background:var(--gray-200);border-radius:4px"><div style="width:${Math.min(100, data.pct)}%;height:8px;background:var(--${c}-500);border-radius:4px"></div></div><span style="color:var(--${c}-600);font-weight:600;min-width:38px;text-align:right">${data.pct}%</span></div>`;
		}
		if (column.fieldname === "status") {
			const c = { [__("Done")]: "green", [__("Started")]: "orange" }[data.status] || "gray";
			value = `<span class="indicator-pill ${c} no-indicator-dot">${value}</span>`;
		}
		if ((column.fieldname === "chapter" && data.classes) || (["subject", "last_chapter"].includes(column.fieldname) && data.classes)) {
			value = `<span style="cursor:pointer;color:var(--text-color);text-decoration:underline dotted">${value}</span>`;
		}
		return value;
	},
	show_classes(args, title) {
		const filters = frappe.query_report.get_filter_values();
		const whole = !args.seq;
		frappe.call(SP_METHOD, { filters, ...args }).then(({ message: rows }) => {
			const esc = (v) => frappe.utils.escape_html(v || "");
			const body = (rows || []).map((r) => `<tr>
				<td>${frappe.datetime.str_to_user(r.date)}</td>${whole ? `<td>${esc(r.chapter)}</td>` : ""}<td>${esc(r.teacher)}</td><td>${r.time || ""}</td>
				<td>${r.completed ? `<span class="indicator-pill green no-indicator-dot">${__("Completed")}</span>` : `<span class="indicator-pill orange no-indicator-dot">${__("Continued")}</span>`}${r.status !== "Approved" ? ` <span class="text-muted small">${__("waiting for approval")}</span>` : ""}</td>
				<td><a href="/app/teachers-timesheet/${encodeURIComponent(r.timesheet)}" target="_blank">${r.timesheet}</a></td></tr>`).join("");
			frappe.msgprint({
				title: esc(title) || __("Classes"),
				message: `<table class="table table-bordered small"><thead><tr><th>${__("Date")}</th>${whole ? `<th>${__("Chapter")}</th>` : ""}<th>${__("Teacher")}</th><th>${__("Time")}</th><th>${__("Status")}</th><th>${__("Timesheet")}</th></tr></thead><tbody>${body}</tbody></table>`,
				wide: true,
			});
		});
	},
};
