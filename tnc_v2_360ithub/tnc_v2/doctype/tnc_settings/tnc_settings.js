// Copyright (c) 2026, 360ITHub and contributors
frappe.ui.form.on("TNC Settings", {
	setup(frm) {
		frm.set_query("penalty_account", () => ({ filters: { is_group: 0, root_type: "Income", company: frappe.defaults.get_user_default("Company") } }));
	},
});
