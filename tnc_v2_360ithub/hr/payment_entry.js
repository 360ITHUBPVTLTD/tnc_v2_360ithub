// Paying an Expense Claim: only approved, submitted, still-unpaid claims can be picked (client meeting 17 Sep).
frappe.ui.form.on("Payment Entry", {
	setup(frm) {
		frm.set_query("reference_name", "references", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			if (row.reference_doctype === "Expense Claim") {
				return { filters: { docstatus: 1, approval_status: "Approved", status: ["!=", "Paid"], employee: doc.party_type === "Employee" && doc.party ? doc.party : ["is", "set"] } };
			}
			return {};
		});
	},
	refresh(frm) {
		// payment to a teacher: send the PDF receipt on WhatsApp again from here
		if (frm.doc.docstatus !== 1 || frm.doc.party_type !== "Supplier" || frm.doc.payment_type !== "Pay") return;
		frappe.db.get_value("Teacher", { supplier_id: frm.doc.party }, "name").then(({ message }) => {
			if (!message || !message.name) return;
			frm.add_custom_button(__("Send receipt to teacher"), () => {
				frappe.call("tnc_v2_360ithub.teachers.teacher_documents.resend_payment_receipt", { name: frm.doc.name }).then(({ message: r }) => {
					frappe.show_alert({ message: r.status === "Sent" ? __("Receipt sent on WhatsApp") : __("Could not send: {0}", [r.message || ""]), indicator: r.status === "Sent" ? "green" : "red" });
				});
			});
		});
	},
});
