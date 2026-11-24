frappe.listview_settings["Student Batch Enrollment"] = {
	add_fields: ["status", "docstatus", "fee_hold"],
	get_indicator(doc) {
		if (doc.docstatus === 0) return [__("Draft"), "red", "docstatus,=,0"];
		if (doc.fee_hold && doc.status === "On Hold") return [__("Fee + Attendance Hold"), "red", "fee_hold,=,1"];
		if (doc.fee_hold && doc.status === "Active") return [__("Fee Hold"), "orange", "fee_hold,=,1"];
		const c = { Active: "green", "On Hold": "red", Completed: "blue", Left: "gray" }[doc.status] || "gray";
		return [__(doc.status), c, "status,=," + doc.status];
	},
};
