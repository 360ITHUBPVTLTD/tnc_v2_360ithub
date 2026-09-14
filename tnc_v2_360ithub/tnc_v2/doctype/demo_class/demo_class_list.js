frappe.listview_settings["Demo Class"] = {
	add_fields: ["result"],
	get_indicator(doc) {
		const c = { Scheduled: "orange", Attended: "green", "Not Attended": "red", Cancelled: "gray" }[doc.result] || "gray";
		return [__(doc.result), c, "result,=," + doc.result];
	},
};
