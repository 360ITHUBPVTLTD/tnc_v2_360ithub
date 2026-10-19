// Copyright (c) 2026, 360ITHub and contributors
frappe.ui.form.on("Student Batch", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Attendance"), () => { frappe.route_options = { batch: frm.doc.name }; frappe.set_route("attendance-overview"); });
		// Put students who already study here (migrated, or fees settled outside) into the batch without a fee order
		frm.add_custom_button(__("Enrol Students"), () => {
			frappe.call({ method: "tnc_v2_360ithub.admissions.enrol_existing.candidates", args: { batch: frm.doc.name } }).then((r) => {
				const list = r.message || [];
				const d = new frappe.ui.Dialog({
					title: __("Enrol students in {0}", [frm.doc.batch_name || frm.doc.name]),
					size: "large",
					fields: [
						{ fieldtype: "HTML", fieldname: "note", options: `<div class="text-muted small" style="margin-bottom:8px">${__("For students who already study here. No fee order is made: fees are treated as settled outside the system. Tick the students and press Enrol.")}</div>` },
						{ fieldtype: "Date", fieldname: "enrollment_date", label: __("Enrolment Date"), default: frappe.datetime.get_today(), reqd: 1 },
						{ fieldtype: "Data", fieldname: "search", label: __("Search name or mobile") },
						{ fieldtype: "HTML", fieldname: "rows" },
					],
					primary_action_label: __("Enrol"),
					primary_action(v) {
						const picked = d.$wrapper.find("input.pick:checked").map((i, el) => el.value).get();
						if (!picked.length) { frappe.msgprint(__("Tick at least one student.")); return; }
						frappe.call({ method: "tnc_v2_360ithub.admissions.enrol_existing.enrol", args: { batch: frm.doc.name, students: picked, enrollment_date: v.enrollment_date }, freeze: true, freeze_message: __("Enrolling...") }).then((rr) => {
							const x = rr.message || {};
							d.hide();
							frappe.msgprint({ title: __("Done"), indicator: x.skipped && x.skipped.length ? "orange" : "green",
								message: __("{0} enrolled.", [x.made.length]) + (x.skipped && x.skipped.length ? `<br>${__("Skipped")}: ` + x.skipped.map(s => `${frappe.utils.escape_html(s[0])} (${frappe.utils.escape_html(s[1])})`).join(", ") : "") });
							frm.reload_doc();
						});
					},
				});
				const esc = frappe.utils.escape_html;
				const render = (q) => {
					q = (q || "").toLowerCase();
					const rows = list.filter(s => !q || (s.student_name || "").toLowerCase().includes(q) || (s.mobile || "").includes(q));
					d.fields_dict.rows.$wrapper.html(`<div style="max-height:50vh;overflow:auto"><table class="table table-bordered table-sm"><thead><tr><th style="width:30px"><input type="checkbox" class="pick-all"></th><th>${__("Student")}</th><th>${__("Mobile")}</th><th>${__("Status")}</th><th>${__("Biometric ID")}</th><th>${__("Interested in")}</th></tr></thead><tbody>
						${rows.map(s => `<tr><td><input type="checkbox" class="pick" value="${esc(s.name)}"></td><td><b>${esc(s.student_name)}</b> <small class="text-muted">${esc(s.name)}</small></td><td>${esc(s.mobile || "")}</td><td>${esc(s.status || "")}</td><td>${s.biometric_id ? esc(s.biometric_id) : `<span class="text-danger">${__("missing")}</span>`}</td><td>${esc(s.batch_interested || s.course_interested || "")}</td></tr>`).join("") || `<tr><td colspan="6" class="text-muted">${__("No students left to enrol.")}</td></tr>`}
					</tbody></table></div><div class="small text-muted">${__("{0} students", [rows.length])}</div>`);
					d.$wrapper.find(".pick-all").on("change", (e) => d.$wrapper.find("input.pick").prop("checked", e.target.checked));
				};
				d.fields_dict.search.$input.on("input", (e) => render(e.target.value));
				d.show(); render("");
			});
		});
	},
});
