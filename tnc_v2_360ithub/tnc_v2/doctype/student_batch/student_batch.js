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

	},
});
