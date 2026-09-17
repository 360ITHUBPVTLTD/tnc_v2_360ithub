frappe.listview_settings["Student"] = {
	add_fields: ["status", "terms_accepted"],
	get_indicator(doc) {
		if (doc.status === "Active" && !doc.terms_accepted) return [__("Active · form not submitted by student"), "orange", "status,=,Active|terms_accepted,=,0"];
		const c = { "Enrolment Pending": "orange", Active: "green", "Attendance Hold": "red", Completed: "blue", Discontinued: "gray" }[doc.status] || "gray";
		return [__(doc.status), c, "status,=," + doc.status];
	},
};
