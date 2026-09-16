// Copyright (c) 2026, 360ITHub and contributors
frappe.ui.form.on("Demo Class", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.result !== "Attended") return;
		if (frm.doc.rated_on) {
			frm.dashboard.clear_headline();
			frm.dashboard.set_headline(`<span class="indicator-pill green no-indicator-dot">${__("Student rated {0}/5", [Math.round((frm.doc.student_rating || 0) * 5)])}</span> ${frappe.utils.escape_html(frm.doc.student_feedback || "")}`);
			return;
		}
		frm.add_custom_button(__("Send Rating Link"), () => {
			frappe.prompt([{ fieldname: "mobile", fieldtype: "Data", label: __("Send to mobile"), default: frm.doc.mobile, reqd: 1 }], (v) => {
				frappe.call({ method: "tnc_v2_360ithub.admissions.demo_rating.send_rating_link", args: { demo: frm.doc.name, mobile: v.mobile }, freeze: true, freeze_message: __("Sending...") }).then((r) => {
					const x = r.message || {};
					if (x.status === "Sent") { frappe.show_alert({ message: __("Rating link sent to {0}", [x.mobile]), indicator: "green" }); frm.reload_doc(); }
					else frappe.msgprint({ title: __("Not sent"), indicator: "red", message: `${frappe.utils.escape_html(x.reason || "")}<br><a class="btn btn-sm btn-success" target="_blank" href="https://wa.me/91${x.mobile}?text=${encodeURIComponent(x.message || "")}">💬 ${__("Send from my phone")}</a>` });
				});
			}, __("Ask the student to rate this demo"), __("Send on WhatsApp"));
		}).addClass("btn-success");
		if (frm.doc.rating_sent_on) frm.dashboard.set_headline(`<span class="indicator-pill orange no-indicator-dot">${__("Rating link sent {0}", [frappe.datetime.prettyDate(frm.doc.rating_sent_on)])}</span> ${__("waiting for the student")}`);
	},
});
