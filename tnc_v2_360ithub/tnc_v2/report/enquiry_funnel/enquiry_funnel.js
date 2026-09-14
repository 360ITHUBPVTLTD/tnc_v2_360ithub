// Copyright (c) 2026, 360ITHub and contributors
frappe.query_reports["Enquiry Funnel"] = {
	filters: [
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.add_months(frappe.datetime.get_today(), -3), reqd: 1 },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "group_by", label: __("Group By"), fieldtype: "Select", options: "Counsellor\nSource\nCourse\nLost Reason", default: "Counsellor", reqd: 1 },
		{ fieldname: "counsellor", label: __("Counsellor"), fieldtype: "Link", options: "User" },
		{ fieldname: "source", label: __("Source"), fieldtype: "Select", options: "\nCall\nWalk-in\nExisting Student\nTeacher\nSocial Media\nWebsite\nOther" },
		{ fieldname: "course_interested", label: __("Course"), fieldtype: "Link", options: "Course" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && column.fieldname === "conversion_pct" && data.enquiries) {
			const c = data.conversion_pct >= 30 ? "green" : data.conversion_pct >= 15 ? "orange" : "red";
			value = `<span style="color:var(--${c}-600);font-weight:600">${value}</span>`;
		}
		if (data && column.fieldname === "lost" && data.lost) value = `<span style="color:var(--red-600)">${value}</span>`;
		return value;
	},
};
