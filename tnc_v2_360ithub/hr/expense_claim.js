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
	validate(frm) {
		if (!frm.doc.expense_for) {
			frappe.msgprint(__("Please choose Expense For: Online Coaching Expense or Offline Coaching Expense."));
			frappe.validated = false;
		}
	},
});
