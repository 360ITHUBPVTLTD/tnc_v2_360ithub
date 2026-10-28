// Copyright (c) 2026, 360ITHub and contributors
frappe.ui.form.on("Student Batch", {
	refresh(frm) {
		// class-day ticks, start/end time and the per-batch late allowance belong to the "Batch class days"
		// attendance mode; TNC marks attendance from teacher timesheets, so hide them unless that mode is on
		const FIELDS = ["day_mon", "day_tue", "day_wed", "day_thu", "day_fri", "day_sat", "day_sun", "start_time", "end_time", "late_after_minutes"];
		const apply = (src) => FIELDS.forEach((f) => frm.toggle_display(f, src === "Batch class days"));
		if (frm._att_source === undefined) {
			apply(null);
			frappe.db.get_single_value("TNC Settings", "attendance_class_source").then((src) => { frm._att_source = src || ""; apply(frm._att_source); });
		} else {
			apply(frm._att_source);
		}
		if (frm.is_new()) return;
		frm.add_custom_button(__("Attendance"), () => { frappe.route_options = { batch: frm.doc.name }; frappe.set_route("attendance-overview"); });
		if (frm.doc.mode !== "Offline") frm.trigger("meet_buttons");
	},
	meet_buttons(frm) {
		const G = __("Google Meet"), M = "tnc_v2_360ithub.meet.";
		const done = (r, planned) => { frm.reload_doc(); frappe.msgprint({ title: G, indicator: "green", message: __("Link {0}<br>{1} guests on the meeting. {2}<br>Paste this link in the batch group.", [`<b>${frappe.utils.escape_html(r.link)}</b>`, r.guests, frappe.utils.escape_html(r.entry || "")]) }); };
		frm.add_custom_button(__("Create Meet link"), () => frappe.confirm(
			__("Create one Google Meet for {0}, from {1} to {2}, with the enrolled students as guests? It becomes the batch's current link.", [frm.doc.name, frappe.datetime.str_to_user(frm.doc.starting_date), frappe.datetime.str_to_user(frm.doc.actual_ending_date)]),
			() => frappe.call({ method: M + "create_batch_link", args: { batch: frm.doc.name }, freeze: true, freeze_message: __("Asking Google…") }).then((r) => done(r.message))), G);
		frappe.call({ method: M + "batch_links", args: { batch: frm.doc.name } }).then((r) => {
			const rows = r.message || [];
			if (!rows.length) return;
			const cur = rows.find((x) => x.current) || rows[0];
			frm.dashboard.set_headline(`<span class="indicator-pill ${cur.error ? "red" : "green"} no-indicator-dot">${G}</span> ${__("Current link")} <a href="${cur.meet_link}" target="_blank">${cur.meet_link}</a> · ${cur.guests} ${__("guests")}${cur.guests_synced_on ? " · " + __("updated") + " " + frappe.datetime.str_to_user(cur.guests_synced_on.split(" ")[0]) : ""}${cur.error ? `<br><span class="text-danger">${frappe.utils.escape_html(cur.error)}</span>` : ""} · <a href="/app/batch-meet-link?batch=${encodeURIComponent(frm.doc.name)}">${__("all links")}</a>`);
		});
	},
});
