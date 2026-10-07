// Copyright (c) 2026, 360ITHub and contributors
frappe.ui.form.on("Teacher Penalty", {
	refresh(frm) {
		frappe.call({ method: "tnc_v2_360ithub.tnc_v2.doctype.teacher_penalty.teacher_penalty.my_rights" }).then((r) => frm.events.trigger_with_rights(frm, r.message || {}));
	},
	trigger_with_rights(frm, rights) {
		const approver = !!rights.approver;
		if (frm.is_new() && !rights.imposer) frm.set_intro(__("You are not allowed to impose penalties, so this penalty cannot be submitted."), "orange");
		const pill = { Submitted: "orange", Approved: "green", Recovered: "blue", Waived: "gray", Refunded: "gray", Rejected: "red", Cancelled: "gray" }[frm.doc.status];
		if (frm.doc.docstatus === 1 && pill) {
			frm.dashboard.clear_headline();
			const who = frm.doc.approved_by ? __("{0} on {1}", [frm.doc.approved_by, frappe.datetime.str_to_user(frm.doc.decided_on)]) : __("waiting for an approver");
			frm.dashboard.set_headline(`<span class="indicator-pill ${pill} no-indicator-dot">${__(frm.doc.status)}</span> ${frappe.utils.escape_html(frm.doc.status === "Submitted" ? who : (frm.doc.approval_comment || who))}`);
		}
		if (frm.doc.docstatus === 1 && frm.doc.status === "Submitted" && approver && (frm.doc.imposed_by !== frappe.session.user || rights.can_self_approve)) {
			const ask = (action) => frappe.prompt([{ fieldname: "c", fieldtype: "Small Text", label: action === "Approved" ? __("Approval comment") : __("Reason for rejection"), reqd: 1 }],
				(v) => frappe.call({ method: "tnc_v2_360ithub.tnc_v2.doctype.teacher_penalty.teacher_penalty.decide", args: { name: frm.doc.name, action, comment: v.c }, freeze: true })
					.then(() => { frappe.show_alert({ message: __("Penalty {0}", [action.toLowerCase()]), indicator: action === "Approved" ? "green" : "red" }); frm.reload_doc(); }),
				action === "Approved" ? __("Approve this penalty?") : __("Reject this penalty?"), __(action === "Approved" ? "Approve" : "Reject"));
			frm.add_custom_button(__("Approve"), () => ask("Approved")).addClass("btn-success");
			frm.add_custom_button(__("Reject"), () => ask("Rejected")).addClass("btn-danger");
		}
		// Approval is final: no waive, no refund. Cancel only corrects a mistake before anything is
		// deducted, by an approver (or the person who raised it while it waits), with a reason.
		if (frm.doc.docstatus === 1) frm.page.clear_secondary_action();
		const nothing_deducted = !flt(frm.doc.recovered_amount);
		const own_waiting = frm.doc.status === "Submitted" && frm.doc.imposed_by === frappe.session.user;
		if (frm.doc.docstatus === 1 && nothing_deducted && ["Submitted", "Approved"].includes(frm.doc.status) && (approver || own_waiting)) {
			frm.add_custom_button(__("Cancel penalty"), () => frappe.prompt(
				[{ fieldname: "reason", fieldtype: "Small Text", label: __("Why is this penalty a mistake?"), reqd: 1 }],
				(v) => frappe.call({ method: "tnc_v2_360ithub.tnc_v2.doctype.teacher_penalty.teacher_penalty.cancel_penalty", args: { name: frm.doc.name, reason: v.reason }, freeze: true })
					.then(() => { frappe.show_alert({ message: __("Penalty cancelled"), indicator: "orange" }); frm.reload_doc(); }),
				__("Cancel this penalty?"), __("Cancel penalty")));
		}
		if (frm.is_new() && !frm.doc.imposed_by) frm.set_value("imposed_by", frappe.session.user);
		frm.set_query("penalty_type", () => ({ filters: { disabled: 0 } }));
		frm.set_query("teacher", () => ({ filters: { status: "Active" } }));
	},
	penalty_type(frm) {
		if (!frm.doc.penalty_type) return;
		frappe.db.get_value("Penalty Type", frm.doc.penalty_type, "default_amount").then((r) => {
			if (r.message && flt(r.message.default_amount)) frm.set_value("amount", r.message.default_amount);
		});
	},
});
