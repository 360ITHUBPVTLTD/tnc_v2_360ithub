// Copyright (c) 2026, 360ITHub and contributors
frappe.ui.form.on("Student Follow-Up", {
	refresh(frm) { frm.trigger("set_purpose_options"); frm.trigger("show_pending"); },
	reference_type(frm) { frm.trigger("set_purpose_options"); },
	onload(frm) { if (frm.is_new()) frm.trigger("fill_assignee"); },
	reference_name(frm) { frm.trigger("fill_assignee"); frm.trigger("show_pending"); },
	status(frm) { frm.trigger("show_pending"); },
	show_pending(frm) {
		// a lead keeps one open follow-up: say so before this new one silently closes it
		frm.dashboard.clear_headline();
		if (!frm.is_new() || frm.doc.status !== "Open" || frm.doc.purpose === "Fee" || !frm.doc.reference_type || !frm.doc.reference_name) return;
		frappe.db.get_list("Student Follow-Up", { filters: { reference_type: frm.doc.reference_type, reference_name: frm.doc.reference_name, status: "Open", purpose: ["!=", "Fee"] },
			fields: ["name", "next_follow_up_date", "notes"], order_by: "next_follow_up_date asc", limit: 1 }).then((rows) => {
			if (!rows || !rows.length || !frm.is_new()) return;
			const r = rows[0];
			frm.dashboard.set_headline(`<span class="indicator-pill orange no-indicator-dot">${__("Already open")}</span> ${__("A follow-up already exists for this {0}: <a href=\"/app/student-follow-up/{1}\">{1}</a>{2}{3}. Saving this one closes it; edit that one instead if you only want to change the date or notes.", [frm.doc.reference_type === "Student" ? __("student") : __("enquiry"), r.name, r.next_follow_up_date ? " · " + __("due") + " " + frappe.datetime.str_to_user(r.next_follow_up_date) : "", r.notes ? " · " + frappe.utils.escape_html(r.notes.slice(0, 80)) : ""])}`);
		});
	},
	fill_assignee(frm) {
		// the enquiry's / student's counsellor, else whoever is logging it (the server does the same on save)
		if (frm.doc.assigned_to) return;
		if (frm.doc.reference_type && frm.doc.reference_name) {
			frappe.db.get_value(frm.doc.reference_type, frm.doc.reference_name, "counsellor").then((r) => frm.set_value("assigned_to", (r.message && r.message.counsellor) || frappe.session.user));
		} else {
			frm.set_value("assigned_to", frappe.session.user);
		}
	},
	set_purpose_options(frm) {
		// an enquiry: lead or demo calls; an admitted student: fees or anything else
		const opts = frm.doc.reference_type === "Student" ? ["Fee", "General"] : ["Enquiry", "Demo", "General"];
		frm.set_df_property("purpose", "options", opts.join("\n"));
		if (frm.doc.purpose && !opts.includes(frm.doc.purpose)) frm.set_value("purpose", "General");
		frm.set_df_property("purpose", "description", "");
	},
});
