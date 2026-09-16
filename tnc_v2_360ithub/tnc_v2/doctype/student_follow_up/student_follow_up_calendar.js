frappe.views.calendar["Student Follow-Up"] = {
	field_map: { start: "next_follow_up_date", end: "next_follow_up_date", id: "name", title: "student_name", allDay: "allDay" },
	get_events_method: "tnc_v2_360ithub.admissions.followups.get_calendar_events",
	filters: [
		{ fieldtype: "Link", fieldname: "assigned_to", options: "User", label: __("Assigned To") },
		{ fieldtype: "Select", fieldname: "purpose", options: "\nEnquiry\nDemo\nFee\nGeneral", label: __("Purpose") },
	],
};
