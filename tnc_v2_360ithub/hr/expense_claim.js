// Expense Claim (client meeting 14 Sep): Expense For (online / offline classes) is required on the desk form,
// and a rejected claim shows no Create menu at all.
frappe.ui.form.on("Expense Claim", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.docstatus === 0 && frm.doc.approval_status === "Draft") frm.trigger("review_buttons");
		if (frm.doc.approval_status === "Rejected") {
			frm.remove_custom_button(__("Payment"), __("Create"));
			frm.remove_custom_button(__("Purchase Invoice"), __("Create"));
			frm.remove_custom_button(__("Journal Entry"), __("Create"));
			frm.page.remove_inner_button && frm.page.remove_inner_button(__("Create"));
			frm.dashboard.clear_headline();
			frm.dashboard.set_headline(`<span class="indicator-pill red no-indicator-dot">${__("Rejected")}</span> ${__("No payment can be made against this claim.")}`);
		}
	},
	review_buttons(frm) {
		const M = "tnc_v2_360ithub.hr.expense_claim.";
		const ask = (title, label, method, done) => frappe.prompt([{ fieldname: "c", fieldtype: "Small Text", label, reqd: 1 }],
			(v) => frappe.call({ method: M + method, args: { name: frm.doc.name, comment: v.c }, freeze: true }).then(() => { frappe.show_alert({ message: done, indicator: "green" }); frm.reload_doc(); }), title, __("Send"));
		if (frm.doc.custom_review_status === "Review Requested") {
			frm.dashboard.set_headline(`<span class="indicator-pill orange no-indicator-dot">${__("Review requested")}</span> ${frappe.utils.escape_html(frm.doc.custom_review_comment || "")}`);
		} else if (frm.doc.custom_review_status === "Reviewed") {
			frm.dashboard.set_headline(`<span class="indicator-pill blue no-indicator-dot">${__("Reviewed by employee")}</span> ${frappe.utils.escape_html(frm.doc.custom_review_reply || "")}`);
		}
		const roles = frappe.user_roles || [];
		const approver = frappe.session.user === frm.doc.expense_approver || roles.includes("Expense Approver") || roles.includes("System Manager");
		if (approver && frm.doc.custom_review_status !== "Review Requested") {
			frm.add_custom_button(__("Send for Review"), () => ask(__("Send this claim back to the employee"), __("What should the employee check or change?"), "request_review", __("Sent for review"))).addClass("btn-warning");
		}
		if (frm.doc.custom_review_status === "Review Requested" && (frappe.session.user === frm.doc.owner || !approver)) {
			frm.add_custom_button(__("Reply to Review"), () => ask(__("Reply to the approver"), __("Your reply"), "reply_review", __("Reply sent"))).addClass("btn-primary");
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
			frappe.msgprint(__("Please choose Expense For: Online coaching classes or Offline coaching classes."));
			frappe.validated = false;
		}
	},
});
