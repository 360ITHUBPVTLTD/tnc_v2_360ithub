// Copyright (c) 2026, 360ITHub and contributors
frappe.ui.form.on("Teacher Settlement", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Regenerate"), () => frappe.call({ method: "tnc_v2_360ithub.tnc_v2.doctype.teacher_settlement.teacher_settlement.generate_now", args: { on: frm.doc.week_start, teacher: frm.doc.teacher }, freeze: true }).then(() => frm.reload_doc()));
		frm.add_custom_button(__("Send on WhatsApp"), () => frappe.call({ method: "tnc_v2_360ithub.tnc_v2.doctype.teacher_settlement.teacher_settlement.send_now", args: { name: frm.doc.name }, freeze: true }).then((r) => {
			const m = r.message || {};
			frappe.msgprint({ title: __("Report card {0}", [m.status]), message: `<pre style="white-space:pre-wrap">${frappe.utils.escape_html(m.message || "")}</pre>` });
			frm.reload_doc();
		})).addClass("btn-success");
	},
});
