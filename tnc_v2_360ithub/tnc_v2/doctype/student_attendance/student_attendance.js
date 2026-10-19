// Copyright (c) 2026, 360ITHub and contributors
frappe.ui.form.on("Student Attendance", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.source === "Manual") {
			frm.dashboard.set_headline(`<span class="indicator-pill orange no-indicator-dot">${__("Changed by staff")}</span> ${frappe.utils.escape_html(frm.doc.marked_by || "")} · ${frappe.utils.escape_html(frm.doc.remarks || "")}`);
		}
	},
	// a status change is a staff correction: ask for the reason at once and save
	status(frm) {
		if (frm.is_new() || !frm.is_dirty()) return;
		frappe.prompt([{ fieldname: "remarks", fieldtype: "Small Text", label: __("Why is the status changed to {0}?", [frm.doc.status]), reqd: 1, default: frm.doc.remarks }], (v) => {
			frm.set_value("remarks", v.remarks);
			frm.save();
		}, __("Reason for the correction"), __("Save"));
	},
});
