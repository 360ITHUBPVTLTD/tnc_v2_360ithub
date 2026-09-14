// Copyright (c) 2026, 360ITHub and contributors
frappe.ui.form.on("Student Follow-Up", {
	refresh(frm) { frm.trigger("set_purpose_options"); },
	reference_type(frm) { frm.trigger("set_purpose_options"); },
	set_purpose_options(frm) {
		// an enquiry is followed up as a lead; an admitted student for fees or anything else
		const opts = frm.doc.reference_type === "Student" ? ["Fee", "General"] : ["Enquiry", "General"];
		frm.set_df_property("purpose", "options", opts.join("\n"));
		if (!opts.includes(frm.doc.purpose)) frm.set_value("purpose", opts[0] === "Fee" ? "General" : opts[0]);
		frm.set_df_property("purpose", "description",
			frm.doc.reference_type === "Student"
				? __("Fee: about an instalment (usually created automatically). General: attendance, documents, batch change, anything else.")
				: __("Enquiry: a lead not yet admitted. General: anything else."));
	},
});
