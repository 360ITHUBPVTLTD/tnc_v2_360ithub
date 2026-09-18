// Expense Claim (client meeting 14 Sep): Expense For (online / offline classes) is required on the desk form,
// and a rejected claim shows no Create menu at all.
frappe.ui.form.on("Expense Claim", {
	refresh(frm) {
		if (frm.doc.approval_status === "Rejected") {
			frm.remove_custom_button(__("Payment"), __("Create"));
			frm.remove_custom_button(__("Purchase Invoice"), __("Create"));
			frm.remove_custom_button(__("Journal Entry"), __("Create"));
			frm.page.remove_inner_button && frm.page.remove_inner_button(__("Create"));
			frm.dashboard.clear_headline();
			frm.dashboard.set_headline(`<span class="indicator-pill red no-indicator-dot">${__("Rejected")}</span> ${__("No payment can be made against this claim.")}`);
		}
	},
	approval_status(frm) {
		if (!["Approved", "Rejected"].includes(frm.doc.approval_status) || frm.doc.custom_approval_comment) return;
		frappe.prompt([{ fieldname: "c", fieldtype: "Small Text", label: frm.doc.approval_status === "Approved" ? __("Approval comment") : __("Reason for rejection"), reqd: 1 }],
			(v) => frm.set_value("custom_approval_comment", v.c),
			frm.doc.approval_status === "Approved" ? __("Approve this claim?") : __("Reject this claim?"), __("Save comment"));
	},
	validate(frm) {
		if (!frm.doc.custom_expense_for) {
			frappe.msgprint(__("Please choose Expense For: Online or Offline."));
			frappe.validated = false;
		}
	},
});
