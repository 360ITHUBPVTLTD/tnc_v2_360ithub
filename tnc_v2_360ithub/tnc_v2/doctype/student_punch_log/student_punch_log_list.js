frappe.listview_settings["Student Punch Log"] = {
	add_fields: ["direction", "device_id"],
	get_indicator(doc) {
		return [__(doc.direction || "Punch"), doc.device_id === "MANUAL" ? "orange" : doc.direction === "OUT" ? "blue" : "green", "direction,=," + (doc.direction || "")];
	},
	onload(listview) {
		if (!frappe.user.has_role(["System Manager", "TNC Super Admin", "TNC Manager"])) return;
		listview.page.add_inner_button(__("Add Punch (manual)"), () => {
			frappe.prompt([
				{ fieldname: "student", fieldtype: "Link", label: __("Student"), options: "Student", reqd: 1 },
				{ fieldname: "punch_time", fieldtype: "Datetime", label: __("Punch Time"), default: frappe.datetime.now_datetime(), reqd: 1 },
				{ fieldname: "direction", fieldtype: "Select", label: __("Direction"), options: ["IN", "OUT"], default: "IN", reqd: 1 },
				{ fieldtype: "HTML", options: `<div class="text-muted small">${__("For testing, or when the machine missed a punch. Saved with device MANUAL and your name. Today's attendance row refreshes at once; a past day needs Rebuild a day on the Student Attendance list.")}</div>` },
			], (v) => {
				frappe.call({ method: "tnc_v2_360ithub.attendance.punches.add_manual", args: v, freeze: true }).then((r) => {
					frappe.show_alert({ message: __("Punch {0} recorded", [r.message]), indicator: "green" });
					listview.refresh();
				});
			}, __("Add a punch by hand"), __("Add"));
		});
	},
};
