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
});
