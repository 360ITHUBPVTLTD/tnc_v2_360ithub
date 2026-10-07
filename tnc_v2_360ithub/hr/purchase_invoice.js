// Purchase Invoice approval: a hand-entered bill goes to the approvers when it is saved. Before that
// happens the user sees a small popup with an optional note, so they know it is being sent.
// Non-approvers never see Submit (it would only refuse); approvers keep Submit, which counts as approval.
const BILL = "tnc_v2_360ithub.hr.invoice_approval.";

function bill_will_be_sent(frm) {
	const m = frm.__bill_rights || {};
	return m.approval_on && !m.approver && !frm.doc.custom_teacher && frm.doc.docstatus === 0
		&& !["Pending Approval", "Approved"].includes(frm.doc.custom_approval_status || "");
}

function ask_note(frm, on_send) {
	const d = new frappe.ui.Dialog({
		title: __("Send for approval"),
		fields: [
			{ fieldtype: "HTML", options: `<p class="text-muted">${__("This bill will go to the approver. You will be notified when it is approved or rejected.")}</p>` },
			{ fieldname: "note", fieldtype: "Small Text", label: __("Note to approver (optional)"), default: frm.doc.custom_note_to_approver || "" },
		],
		primary_action_label: __("Send for approval"),
		primary_action(v) { d.hide(); on_send((v.note || "").trim()); },
		secondary_action_label: __("Cancel"),
		secondary_action() { d.hide(); },
	});
	d.show();
}

frappe.ui.form.on("Purchase Invoice", {
	setup(frm) {
		// hand-entered bills are for real suppliers; teacher payouts come from the Teacher form
		frm.set_query("supplier", () => (frm.doc.custom_teacher ? {} : { query: BILL + "supplier_query" }));
		// a file added to a rejected bill is usually the correction: offer to send it back
		$(frm.wrapper).on("attachments_change", () => {
			const n = (frm.get_docinfo().attachments || []).length;
			const before = frm.__att_count;
			frm.__att_count = n;
			if (before === undefined || n <= before || frm.is_new() || frm.is_dirty()) return;
			if (frm.doc.custom_approval_status !== "Rejected" || !bill_will_be_sent(frm)) return;
			ask_note(frm, (note) => frappe.call({ method: BILL + "send_for_approval", args: { name: frm.doc.name, note }, freeze: true })
				.then(() => { frappe.show_alert({ message: __("Sent for approval"), indicator: "green" }); frm.reload_doc(); }));
		});
	},
	validate(frm) {
		// first save, or saving a corrected rejected bill: confirm with an optional note first
		if (!bill_will_be_sent(frm) || frm.__send_confirmed) return;
		frappe.validated = false;
		ask_note(frm, (note) => {
			frm.__send_confirmed = true;
			frm.set_value("custom_note_to_approver", note).then(() => frm.save());
		});
	},
	after_save(frm) {
		if (frm.__send_confirmed) {
			frm.__send_confirmed = false;
			frappe.show_alert({ message: __("Sent for approval"), indicator: "green" });
		}
	},
	refresh(frm) {
		frm.__att_count = (frm.get_docinfo && frm.get_docinfo() && (frm.get_docinfo().attachments || []).length) || 0;
		if (frm.doc.docstatus !== 0 || frm.doc.custom_teacher) return;
		frappe.call({ method: BILL + "my_rights" }).then((r) => {
			const m = r.message || {};
			frm.__bill_rights = m;
			if (!m.approval_on) return;
			const st = frm.doc.custom_approval_status;
			if (frm.is_new()) {
				if (!m.approver) frm.set_intro(__("This bill needs approval. When you save it, it is sent to the approver."), "blue");
				return;
			}
			if (!m.approver && !frm.is_dirty()) frm.page.clear_primary_action();  // no Submit for people who cannot submit
			if (st === "Pending Approval") {
				frm.dashboard.clear_headline();
				frm.dashboard.set_headline(`<span class="indicator-pill orange no-indicator-dot">${__("Waiting for approval")}</span> ${__("sent by {0}", [frm.doc.custom_sent_for_approval_by || ""])}`);
				if (m.approver) {
					const ask = (action) => frappe.prompt([{ fieldname: "c", fieldtype: "Small Text", label: action === "Approved" ? __("Approval comment") : __("Reason for rejection"), reqd: 1 }],
						(v) => frappe.call({ method: BILL + "decide", args: { name: frm.doc.name, action, comment: v.c }, freeze: true }).then(() => frm.reload_doc()),
						action === "Approved" ? __("Approve and submit this bill?") : __("Reject this bill?"), __(action === "Approved" ? "Approve" : "Reject"));
					frm.add_custom_button(__("Approve"), () => ask("Approved")).addClass("btn-success");
					frm.add_custom_button(__("Reject"), () => ask("Rejected")).addClass("btn-danger");
				} else {
					frm.set_intro(__("Sent for approval. You will be notified when it is approved or rejected."), "blue");
				}
			} else if (st === "Rejected") {
				frm.dashboard.clear_headline();
				frm.dashboard.set_headline(`<span class="indicator-pill red no-indicator-dot">${__("Rejected")}</span> ${frappe.utils.escape_html(frm.doc.custom_approval_comment || "")}`);
				if (!m.approver) frm.set_intro(__("Correct the bill, add the missing file, or answer in the note, then save. You will be asked before it is sent back."), "orange");
			} else if (!m.approver) {
				frm.set_intro(__("Save this bill to send it for approval."), "blue");
			}
		});
	},
});
