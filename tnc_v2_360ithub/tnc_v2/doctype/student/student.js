frappe.ui.form.on("Student", {
	refresh(frm) {
		frm.trigger("render_overview");
		frm.trigger("render_payments");
		frm.trigger("render_followups");
		if (!frm.is_new()) {
			frm.add_custom_button(__("Enrol in Batch"), () => {
				frappe.db.get_list("Student Batch Enrollment", { filters: { student: frm.doc.name, docstatus: 1, status: ["in", ["Active", "On Hold"]] },
					fields: ["name", "batch", "course_name", "status"], limit: 20 }).then((rows) => {
					const go = () => frappe.new_doc("Student Batch Enrollment", { student: frm.doc.name });
					if (!rows.length) return go();
					const list = rows.map((r) => `<li><b>${r.batch}</b> · ${r.course_name || ""} · ${r.status}</li>`).join("");
					frappe.confirm(
						`<p>${__("{0} is already enrolled in:", [`<b>${frm.doc.student_name}</b>`])}</p><ul>${list}</ul><p><b>${__("Enrol in another batch?")}</b></p>`,
						go
					);
				});
			}).addClass("btn-primary");
			frm.add_custom_button(__("Add Follow-up"), () => {
				frappe.new_doc("Student Follow-Up", { reference_type: "Student", reference_name: frm.doc.name });
			});
			frm.add_custom_button(__("Follow-ups"), () => { frappe.route_options = { reference_type: "Student", reference_name: frm.doc.name }; frappe.set_route("follow-ups"); }, __("View"));
			if (frm.doc.customer) {
				frm.add_custom_button(__("Customer"), () => frappe.set_route("Form", "Customer", frm.doc.customer), __("View"));
				frm.add_custom_button(__("Sales Orders"), () => frappe.set_route("List", "Sales Order", { student: frm.doc.name }), __("View"));
			}
		}
	},
	render_followups(frm) {
		const $w = frm.get_field("followups_html").$wrapper;
		if (frm.is_new()) { $w.empty(); return; }
		frappe.call({ method: "tnc_v2_360ithub.admissions.followups.get_reference_followups", args: { reference_type: "Student", reference_name: frm.doc.name },
			callback: (r) => {
				if (!r.message) return;
				$w.html(r.message.html);
				$w.find("[data-action=followups-page]").on("click", () => { frappe.route_options = { reference_type: "Student", reference_name: frm.doc.name }; frappe.set_route("follow-ups"); });
			} });
	},
	render_payments(frm) {
		const $w = frm.get_field("payments_html").$wrapper;
		if (frm.is_new()) { $w.empty(); return; }
		frappe.call({ method: "tnc_v2_360ithub.admissions.fees.get_student_payments", args: { student: frm.doc.name },
			callback: (r) => r.message && $w.html(r.message.html) });
	},
	render_overview(frm) {
		const $w = frm.get_field("overview").$wrapper;
		if (frm.is_new()) {
			$w.html(`<div class="text-muted">${__("Save the student to see the overview.")}</div>`);
			return;
		}
		frappe.call({
			method: "tnc_v2_360ithub.admissions.api.get_student_overview",
			args: { student: frm.doc.name },
			callback: (r) => {
				if (!r.message) return;
				$w.html(r.message.html);
				$w.find("[data-action=receive]").on("click", (ev) => {
					const $b = $(ev.currentTarget);
					tnc.admissions.receive_payment({
						sales_order: $b.data("so"), amount: $b.data("amount") || null, label: $b.data("label") || "",
						on_done: (m) => {
							frm.trigger("render_overview"); frm.trigger("render_payments");
						},
					});
				});
				frm.dashboard.clear_headline();
				if (r.message.pending > 0) {
					frm.dashboard.set_headline_alert(
						`${__("Pending fee")}: <b>${format_currency(r.message.pending, "INR")}</b>` +
						(r.message.missing_docs ? ` · ${r.message.missing_docs} ${__("document(s) missing")}` : ""),
						r.message.missing_docs ? "orange" : "blue"
					);
				}
			},
		});
	},
});
