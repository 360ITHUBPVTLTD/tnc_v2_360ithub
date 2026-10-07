// Copyright (c) 2026, 360ITHub and contributors
frappe.dom.set_style(".hide-row-no .grid-row .row-index, .hide-row-no .grid-heading-row .row-index { display: none !important; }");

frappe.ui.form.on("Subject", {
	refresh(frm) {
		// The sheet often numbers chapters itself ("01. ..."); then the grid's own row number repeats it.
		const numbered = (frm.doc.chapters || []).length && frm.doc.chapters.every((c) => /^\s*\d/.test(c.chapter_name || ""));
		frm.fields_dict.chapters.$wrapper.toggleClass("hide-row-no", !!numbered);
		if (!frm.is_new()) {
			frm.add_custom_button(__("Syllabus Progress"), () => frappe.set_route("query-report", "Syllabus Progress", { subject: frm.doc.name }));
		}
	},
});
