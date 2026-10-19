// Copyright (c) 2026, 360ITHub and contributors
frappe.query_reports["Student Attendance Summary"] = {
	filters: [
		{ fieldname: "period", label: __("Period"), fieldtype: "DateRange", default: [frappe.datetime.month_start(), frappe.datetime.get_today()] },
		{ fieldname: "view", label: __("View"), fieldtype: "Select", options: ["Student", "Batch", "Month", "Subject"], default: "Student", reqd: 1 },
		{ fieldname: "subject", label: __("Subject"), fieldtype: "Link", options: "Subject", depends_on: "eval:doc.view=='Subject'" },
		{ fieldname: "batch", label: __("Batch"), fieldtype: "Link", options: "Student Batch" },
		{ fieldname: "student", label: __("Student"), fieldtype: "Link", options: "Student" },
		{ fieldname: "only_on_hold", label: __("Only students on hold"), fieldtype: "Check", default: 0 },
	],
	get_datatable_options(options) {
		return Object.assign(options, { checkboxColumn: false });
	},
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		// the student's name as the link text, not the ID
		if (column.fieldname === "student" && data.student) value = `<a href="/app/student/${encodeURIComponent(data.student)}" data-doctype="Student" data-name="${frappe.utils.escape_html(data.student)}">${frappe.utils.escape_html(data.student_name || data.student)}</a>`;
		if (column.fieldname === "pct" && (data.class_days || data.classes)) {
			const c = data.pct >= 75 ? "green" : data.pct >= 50 ? "orange" : "red";
			value = `<div style="display:flex;align-items:center;gap:6px"><div style="flex:1;height:8px;background:var(--gray-200);border-radius:4px"><div style="width:${Math.min(100, data.pct)}%;height:8px;background:var(--${c}-500);border-radius:4px"></div></div><span style="color:var(--${c}-600);font-weight:600;min-width:42px;text-align:right">${data.pct}%</span></div>`;
		}
		if (column.fieldname === "enrol_status" && data.enrol_status) {
			const c = { Active: "green", "On Hold": "red", Completed: "blue", Left: "gray" }[data.enrol_status] || "gray";
			value = `<span class="indicator-pill ${c} no-indicator-dot">${__(data.enrol_status)}</span>`;
		}
		if (column.fieldname === "consecutive_absences" && cint(data.consecutive_absences) > 0) {
			value = `<span style="color:var(--red-600);font-weight:600">${data.consecutive_absences}</span>`;
		}
		return value;
	},
};
