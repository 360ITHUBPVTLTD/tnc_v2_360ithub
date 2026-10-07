frappe.listview_settings["Teacher Penalty"] = {
	add_fields: ["status", "amount", "outstanding_amount"],
	get_indicator(doc) {
		const c = { Draft: "gray", Submitted: "orange", Approved: "green", Recovered: "blue", Waived: "gray", Refunded: "gray", Rejected: "red", Cancelled: "gray" }[doc.status] || "gray";
		return [__(doc.status), c, "status,=," + doc.status];
	},
};
