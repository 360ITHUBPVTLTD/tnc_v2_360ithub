// Copyright (c) 2026, pankaj@360ithub.com and contributors
// For license information, please see license.txt

frappe.query_reports["Monthly Teacher Task Summary Report"] = {
	"filters": [
		{
			"fieldname": "date_range",
			"label": __("Date Range"),
			"fieldtype": "DateRange",
			"default": [frappe.datetime.add_months(frappe.datetime.get_today(), -1), frappe.datetime.get_today()],
			"reqd": 1,
		},
		{
			"fieldname": "task_owner",
			"label": __("Task Owner"),
			"fieldtype": "Link",
			"options": "User",
		},
		{
			"fieldname": "department",
			"label": __("Department"),
			"fieldtype": "Link",
			"options": "Department",
		},
		{
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": ["", "Open", "Working", "Pending Review", "Completed", "Cancelled", "Overdue"],
		},
		{
			"fieldname": "priority",
			"label": __("Priority"),
			"fieldtype": "Select",
			"options": ["", "Low", "Medium", "High", "Urgent"],
		},
		{
			"fieldname": "task_reporter",
			"label": __("Task Reporter"),
			"fieldtype": "Link",
			"options": "User",
		},
		{
			"fieldname": "subject",
			"label": __("Subject"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "sort_by",
			"label": __("Sort By"),
			"fieldtype": "Select",
			"options": ["Overdue Days", "Expected End Date", "Expected Start Date", "Priority", "Status", "Task ID", "Task Owner"],
			"default": "Overdue Days",
		},
		{
			"fieldname": "sort_order",
			"label": __("Sort Order"),
			"fieldtype": "Select",
			"options": ["Descending", "Ascending"],
			"default": "Descending",
		}
	],
	"onload": function(report) {
		report.page.add_inner_button(__("Export Excel Report"), function() {
			let filters = report.get_filter_values();
			let query_params = {};
			for (let k in filters) {
				if (filters[k] !== undefined && filters[k] !== null) {
					query_params[k] = JSON.stringify(filters[k]);
				}
			}
			let url = "/api/method/tnc_v2_360ithub.teachers.monthly_summary.download_excel_report?" + $.param(query_params);
			window.open(url, '_blank');
		});
	}
};
