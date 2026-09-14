frappe.ui.form.on("Activity", {
	refresh(frm) {
		frm.set_query("uom", () => {
			return {
				filters: {
					name: ["in", ["Nos", "Hour","Minute"]],
				},
			};
		});
	},
});

