frappe.listview_settings["Student Attendance"] = {
	add_fields: ["status"],
	get_indicator(doc) {
		const c = { Present: "green", Late: "orange", Absent: "red", Leave: "blue" }[doc.status] || "gray";
		return [__(doc.status), c, "status,=," + doc.status];
	},
	onload(listview) {
		listview.page.add_inner_button(__("Rebuild a day"), () => {
			frappe.prompt([{ fieldname: "date", fieldtype: "Date", label: __("Date"), default: frappe.datetime.get_today(), reqd: 1 }], (v) => {
				frappe.call({ method: "tnc_v2_360ithub.attendance.daily.rebuild_day", args: { date: v.date }, freeze: true }).then((r) => {
					const m = r.message || {};
					frappe.show_alert({ message: __("{0}: {1} present, {2} late, {3} absent", [v.date, m.present || 0, m.late || 0, m.absent || 0]), indicator: "green" });
					listview.refresh();
				});
			}, __("Rebuild attendance from the machine punches"), __("Rebuild"));
		});
	},
};
