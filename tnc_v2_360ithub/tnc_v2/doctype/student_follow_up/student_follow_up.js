// Copyright (c) 2026, 360ITHub and contributors
frappe.ui.form.on("Student Follow-Up", {
	refresh(frm) { frm.trigger("set_purpose_options"); },
	reference_type(frm) { frm.trigger("set_purpose_options"); },
	set_purpose_options(frm) {
		// an enquiry: lead or demo calls; an admitted student: fees or anything else
		const opts = frm.doc.reference_type === "Student" ? ["Fee", "General"] : ["Enquiry", "Demo", "General"];
		frm.set_df_property("purpose", "options", opts.join("\n"));
		if (frm.doc.purpose && !opts.includes(frm.doc.purpose)) frm.set_value("purpose", "General");
		frm.set_df_property("purpose", "description", "");
	},
});
