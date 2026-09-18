// Expense Claim list opens without paid claims; the filter can be removed to see them.
frappe.listview_settings["Expense Claim"] = Object.assign(frappe.listview_settings["Expense Claim"] || {}, {
	onload(listview) {
		const has_status = (listview.filter_area.get() || []).some((f) => f[1] === "status");
		if (!has_status && !(frappe.route_options && frappe.route_options.status)) listview.filter_area.add([["Expense Claim", "status", "!=", "Paid"]]);
		listview.page.add_inner_button(__("Show paid"), () => { listview.filter_area.remove("status"); listview.filter_area.add([["Expense Claim", "status", "=", "Paid"]]); });
	},
});
