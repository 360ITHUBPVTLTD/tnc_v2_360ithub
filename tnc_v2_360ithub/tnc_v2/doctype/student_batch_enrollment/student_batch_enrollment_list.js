frappe.listview_settings["Student Batch Enrollment"] = {
	add_fields: ["status", "docstatus"],
	get_indicator(doc) {
		if (doc.docstatus === 0) return [__("Draft"), "red", "docstatus,=,0"];
		const c = { Active: "green", "On Hold": "red", Completed: "blue", Left: "gray" }[doc.status] || "gray";
		return [__(doc.status), c, "status,=," + doc.status];
	},
};
