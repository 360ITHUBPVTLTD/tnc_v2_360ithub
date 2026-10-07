frappe.listview_settings["Subject"] = {
	add_fields: ["disabled"],
	get_indicator(doc) {
		return doc.disabled ? [__("Disabled"), "gray", "disabled,=,1"] : [__("Active"), "green", "disabled,=,0"];
	},
};
