frappe.listview_settings["Student Enquiry"] = {
	add_fields: ["status", "next_follow_up", "counsellor"],
	// converted enquiries stay as history but are hidden by default; "Show converted" brings them back
	onload(listview) {
		const has_status = (listview.filter_area.get() || []).some((f) => f[1] === "status");
		if (!has_status && !(frappe.route_options && frappe.route_options.status)) listview.filter_area.add([["Student Enquiry", "status", "!=", "Converted"]]);
		listview.page.add_inner_button(__("Show converted"), () => {
			listview.filter_area.remove("status");
			listview.filter_area.add([["Student Enquiry", "status", "=", "Converted"]]);
		});
	},
	get_indicator(doc) {
		const c = { New: "blue", "Demo Scheduled": "orange", "Demo Attended": "yellow", Converted: "green", Lost: "red" }[doc.status] || "gray";
		return [__(doc.status), c, "status,=," + doc.status];
	},
};
