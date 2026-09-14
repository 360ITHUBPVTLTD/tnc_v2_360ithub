// Copyright (c) 2026, 360ITHub and contributors
// Sales Orders created by an enrolment: the fee is changed through the enrolment, never here.
frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (!frm.doc.student_batch_enrollment) return;
		setTimeout(() => {
			frm.remove_custom_button(__("Update Items"));
			frm.remove_custom_button(__("Update Items"), __("Create"));
		}, 50);
		frm.add_custom_button(__("Enrolment"), () => frappe.set_route("Form", "Student Batch Enrollment", frm.doc.student_batch_enrollment));
		frm.add_custom_button(__("Student"), () => frappe.set_route("Form", "Student", frm.doc.student));
	},
});
