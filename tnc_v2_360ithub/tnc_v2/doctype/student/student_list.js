frappe.listview_settings["Student"] = {
	add_fields: ["status"],
	get_indicator(doc) {
		const c = { "Enrolment Pending": "orange", Active: "green", "Attendance Hold": "red", Completed: "blue", Discontinued: "gray" }[doc.status] || "gray";
		return [__(doc.status), c, "status,=," + doc.status];
	},
};
