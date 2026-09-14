frappe.listview_settings["Admission Form"] = {
	add_fields: ["status"],
	get_indicator(doc) {
		const c = { "Pending Review": "orange", Applied: "green", Rejected: "red" }[doc.status] || "gray";
		return [__(doc.status), c, "status,=," + doc.status];
	},
};
