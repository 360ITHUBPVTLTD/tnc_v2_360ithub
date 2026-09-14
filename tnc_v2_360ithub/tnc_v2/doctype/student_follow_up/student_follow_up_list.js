frappe.listview_settings["Student Follow-Up"] = {
	add_fields: ["status", "next_follow_up_date", "purpose"],
	get_indicator(doc) {
		if (doc.status === "Closed") return [__("Closed"), "gray", "status,=,Closed"];
		const today = frappe.datetime.get_today();
		if (doc.next_follow_up_date && doc.next_follow_up_date < today) return [__("Overdue"), "red", "next_follow_up_date,<," + today];
		if (doc.next_follow_up_date === today) return [__("Today"), "orange", "next_follow_up_date,=," + today];
		return [__("Open"), "blue", "status,=,Open"];
	},
};
