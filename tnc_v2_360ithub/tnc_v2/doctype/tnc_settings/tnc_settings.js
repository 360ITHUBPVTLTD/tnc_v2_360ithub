// Copyright (c) 2026, 360ITHub and contributors
frappe.ui.form.on("TNC Settings", {
	setup(frm) {
		frm.set_query("penalty_account", () => ({ filters: { is_group: 0, root_type: "Income", company: frappe.defaults.get_user_default("Company") } }));
	},
	refresh(frm) {
		// Google Meet: connect once (Allow page for the TNC account), then test / sync by hand
		const connected = !!frm.doc.meet_account;
		frm.add_custom_button(connected ? __("Reconnect Google") : __("Connect Google Meet"), () => {
			if (frm.is_dirty()) { frappe.msgprint(__("Save the settings first.")); return; }
			frappe.call({ method: "tnc_v2_360ithub.meet.connect_url" }).then((r) => { window.open(r.message, "_blank"); });
		}, __("Google Meet"));
		if (connected) {
			frm.add_custom_button(__("Test connection"), () => frappe.call({ method: "tnc_v2_360ithub.meet.test_connection", freeze: true }).then((r) => {
				const m = r.message || {};
				frappe.msgprint({ title: __("Google Meet"), indicator: "green", message: __("Connected as {0}. {1} meeting sessions in the last 7 days across {2} meetings.", [m.account, m.sessions, Object.keys(m.meetings || {}).length]) + (Object.keys(m.meetings || {}).length ? "<br><small>" + Object.entries(m.meetings).map(([c, n]) => `${c}: ${n}`).join(" · ") + "</small>" : "") });
			}), __("Google Meet"));
			frm.add_custom_button(__("Sync now"), () => frappe.call({ method: "tnc_v2_360ithub.meet.sync_now", freeze: true }).then((r) => {
				const m = r.message || {};
				frappe.msgprint({ title: __("Google Meet sync"), indicator: m.errors && m.errors.length ? "orange" : "green", message: m.skipped ? m.skipped : __("{0} class windows pulled.", [(m.synced || []).length]) + (m.errors && m.errors.length ? "<br>" + m.errors.join("<br>") : "") });
				frm.reload_doc();
			}), __("Google Meet"));
		}
		if (frm.doc.meet_last_error) frm.dashboard.set_headline(`<span class="indicator-pill red no-indicator-dot">${__("Google Meet")}</span> ${frappe.utils.escape_html(frm.doc.meet_last_error)}`);
	},
});
