// Copyright (c) 2025, pankaj@360ithub.com and contributors
// For license information, please see license.txt

frappe.query_reports["Teachers Payable Report"] = {
	"filters": [
		{
			"fieldname": "timespan",
			"label": __("Timespan"),
			"fieldtype": "Select",
			"options": ["Today", "Tomorrow", "This Week", "This Month", "Custom"],
			"default": "This Month",
			"reqd": 1,
		},
		{
			"fieldname": "date_range",
			"label": __("Date Range"),
			"fieldtype": "DateRange",
			"depends_on": "eval:doc.timespan == 'Custom'",
		},
		{
			"fieldname": "teacher_name",
			"label": __("Teacher Name"),
			"fieldtype": "Link",
			"options": "Teacher",
		},
	],
};
