frappe.listview_settings["Student Enquiry"] = {
	add_fields: ["status", "next_follow_up"],
	get_indicator(doc) {
		const c = { New: "blue", "Demo Scheduled": "orange", "Demo Attended": "yellow", Converted: "green", Lost: "red" }[doc.status] || "gray";
		return [__(doc.status), c, "status,=," + doc.status];
	},
};
