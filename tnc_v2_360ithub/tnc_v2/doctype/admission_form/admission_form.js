// Copyright (c) 2026, 360ITHub and contributors
frappe.ui.form.on("Admission Form", {
	refresh(frm) {
		if (frm.doc.name_mismatch && frm.doc.status === "Pending Review") {
			frm.dashboard.clear_headline();
			frm.dashboard.set_headline(`<span class="indicator-pill red">${__("Name differs from enquiry")}</span> ${__("Form says {0}; the enquiry {1} says {2}. Check with the student before applying.", [`<b>${frappe.utils.escape_html(frm.doc.student_name)}</b>`, frm.doc.enquiry, `<b>${frappe.utils.escape_html(frm.doc.__onload && frm.doc.__onload.enquiry_name || "")}</b>`])}`);
		}
		frappe.call({ method: "tnc_v2_360ithub.admissions.terms.terms_html_api" }).then((r) => frm.get_field("terms_html").$wrapper.html(r.message || ""));
		if (frm.is_new() || frm.doc.status === "Applied") {
			if (frm.doc.student) frm.add_custom_button(__("Student"), () => frappe.set_route("Form", "Student", frm.doc.student)).addClass("btn-primary");
			return;
		}
		frm.add_custom_button(__("Apply to Student"), () => {
			frappe.call({ method: "tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry.check_duplicates", args: { mobile: frm.doc.mobile } }).then((r) => {
				const st = (r.message && r.message.students) || [];
				const go = (student) => frappe.call({ method: "tnc_v2_360ithub.tnc_v2.doctype.admission_form.admission_form.apply_to_student", args: { name: frm.doc.name, student }, freeze: true })
					.then((rr) => { frappe.show_alert({ message: __("Applied to {0}", [rr.message]), indicator: "green" }); frappe.set_route("Form", "Student", rr.message); });
				const summary = `<p><b>${frappe.utils.escape_html(frm.doc.student_name)}</b> · ${frm.doc.mobile}${frm.doc.course_interested ? " · " + frappe.utils.escape_html(frm.doc.course_interested) : ""}</p>
					<p class="small text-muted">${__("Consent accepted")} ${frappe.datetime.str_to_user(frm.doc.accepted_on)} · ${__("terms")} ${frm.doc.terms_version || ""}${frm.doc.enquiry ? " · " + __("enquiry") + " " + frm.doc.enquiry : ""}</p>`;
				if (!st.length) {
					frappe.confirm(`<p>${__("Create a new Student from this admission form?")}</p>${summary}<p>${__("The student's details, photo and consent will be copied. Their enquiry will be marked Converted.")}</p>`, () => go(null));
					return;
				}
				const s = st[0];
				const d = new frappe.ui.Dialog({
					title: __("Student already exists"),
					fields: [{ fieldtype: "HTML", options: `${summary}<p>${__("A student with this mobile already exists:")}</p><p style="padding:8px 12px;border-radius:6px;background:#f1f5f9"><b>${frappe.utils.escape_html(s.student_name)}</b> · ${s.name} · ${s.status}</p><p>${__("Update that student with this form, or create a new one?")}</p>` }],
					primary_action_label: __("Update existing student"),
					primary_action() { d.hide(); go(s.name); },
					secondary_action_label: __("Create new student"),
					secondary_action() { d.hide(); go(null); },
				});
				d.show();
			});
		}).addClass("btn-primary");
		frm.add_custom_button(__("Reject"), () => frappe.prompt({ fieldname: "why", fieldtype: "Small Text", label: __("Reason"), reqd: 1 },
			(v) => frappe.call({ method: "tnc_v2_360ithub.tnc_v2.doctype.admission_form.admission_form.reject", args: { name: frm.doc.name, reason: v.why } }).then(() => frm.reload_doc()), __("Reject admission form")));
	},
});
