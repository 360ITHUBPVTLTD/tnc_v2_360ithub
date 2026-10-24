// Copyright (c) 2026, 360ITHub and contributors
frappe.ui.form.on("Student Follow-Up", {
	refresh(frm) { frm.trigger("set_purpose_options"); },
	reference_type(frm) { frm.trigger("set_purpose_options"); },
	onload(frm) { if (frm.is_new()) frm.trigger("fill_assignee"); },
	reference_name(frm) { frm.trigger("fill_assignee"); },
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
