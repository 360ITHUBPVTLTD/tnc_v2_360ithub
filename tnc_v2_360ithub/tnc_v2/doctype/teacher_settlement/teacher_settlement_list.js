frappe.listview_settings["Teacher Settlement"] = {
	add_fields: ["status"],
	get_indicator(doc) { return doc.status === "Sent" ? [__("Sent"), "green", "status,=,Sent"] : [__("Generated"), "blue", "status,=,Generated"]; },
	onload(listview) {
		listview.page.add_inner_button(__("Generate this week"), () => frappe.call({ method: "tnc_v2_360ithub.tnc_v2.doctype.teacher_settlement.teacher_settlement.generate_now", freeze: true }).then((r) => {
			frappe.show_alert({ message: __("{0} settlements generated", [(r.message || []).length]), indicator: "green" }); listview.refresh();
		}));
	},
};
