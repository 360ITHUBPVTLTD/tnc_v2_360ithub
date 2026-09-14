
// frappe.ui.form.on("Teachers Timesheet", {
//     refresh: function (frm) {
//         if (!frm.is_new()) {
//             // Approval logic (unchanged)
//             frappe.call({
//                 method: "frappe.client.get",
//                 args: {
//                     doctype: "TNC Settings",
//                     name: "TNC Settings",
//                 },
//                 callback: function (r) {
//                     if (r.message && r.message.teacher_timesheet_approval) {
//                         const allowed_users = r.message.teacher_timesheet_approval.map(row => row.user);
//                         if ((allowed_users.includes(frappe.session.user) || frappe.session.user === "Administrator") && frm.doc.status === "Draft") {
//                             frm.add_custom_button(__("Approve"), function () {
//                                 frappe.confirm(__("Are you sure you want to approve?"), function () {
//                                     frm.set_value("status", "Submitted");
//                                     frm.save();
//                                 });
//                             }).addClass("btn-primary");
//                         }
//                     }
//                 },
//             });
//         }

//         // Updated Note: Removing mention of minutes
//         frm.set_intro(__("Note: Please enter the duration in <b>Hours</b> (e.g., 1.5 for 1 hour 30 mins)."), "blue");

//         if (frm.doc.status === "Submitted") {
//             frm.disable_form();
//         }
//         toggle_activity_add_row(frm);
//     },

//     onload: function (frm) {
//         if (!frm.doc.teacher_id) {
//             frappe.call({
//                 method: "frappe.client.get_list",
//                 args: {
//                     doctype: "Teacher",
//                     filters: { email: frappe.session.user },
//                     fields: ["name"],
//                 },
//                 callback: function (r) {
//                     if (r.message && r.message.length > 0) {
//                         frm.set_value("teacher_id", r.message[0].name);
//                         frm.set_df_property("teacher_id", "read_only", 1);
//                     }
//                 },
//             });
//         }
//     },
// });

// frappe.ui.form.on("Activities", {
//     activity_name: function (frm, cdt, cdn) {
//         let row = locals[cdt][cdn];
//         if (row.activity_name && frm.doc.teacher_id) {
//             frappe.call({
//                 method: "tnc_v2_360ithub.tnc_v2.doctype.teachers_timesheet.teachers_timesheet.get_rate_for_activity",
//                 args: {
//                     teacher_id: frm.doc.teacher_id,
//                     activity_name: row.activity_name,
//                 },
//                 callback: function (r) {
//                     if (r.message) {
//                         let rate = typeof r.message === 'object' ? r.message.rate : r.message;
//                         let uom = typeof r.message === 'object' ? r.message.uom : row.uom;
//                         frappe.model.set_value(cdt, cdn, "activity_fee", rate);
//                         frappe.model.set_value(cdt, cdn, "uom", uom);
//                         calculate_row_amount(frm, cdt, cdn);
//                     }
//                 },
//             });
//         }
//     },
//     qty: function (frm, cdt, cdn) {
//         calculate_row_amount(frm, cdt, cdn);
//     },
//     activity_fee: function (frm, cdt, cdn) {
//         calculate_row_amount(frm, cdt, cdn);
//     },
//     activity_type_remove: function (frm) {
//         calculate_grand_total(frm);
//     }
// });

// /** 
//  * UPDATED: Pure Hourly Calculation
//  */
// function calculate_row_amount(frm, cdt, cdn) {
//     let child = locals[cdt][cdn];
//     let qty = flt(child.qty) || 0;
//     let rate = flt(child.activity_fee) || 0;

//     // Direct multiplication (Amount = Quantity * Rate)
//     let amount = qty * rate;

//     frappe.model.set_value(cdt, cdn, "amount", amount);
//     calculate_grand_total(frm);
// }

// function calculate_grand_total(frm) {
//     let grand_total = 0;
//     (frm.doc.activity_type || []).forEach((row) => {
//         grand_total += flt(row.amount);
//     });
//     frm.set_value("grand_total", grand_total);
// }

// function toggle_activity_add_row(frm) {
//     if (frm.doc.activity_type && frm.doc.activity_type.length >= 1) {
//         frm.get_field("activity_type").grid.cannot_add_rows = true;
//     } else {
//         frm.get_field("activity_type").grid.cannot_add_rows = false;
//     }
//     frm.refresh_field("activity_type");
// }



frappe.ui.form.on("Teachers Timesheet", {
    refresh: function (frm) {
        // 1. Clear buttons to prevent duplicates
         frm.clear_custom_buttons();

        if (!frm.is_new()) {
            frappe.call({
                method: "frappe.client.get",
                args: {
                    doctype: "TNC Settings",
                    name: "TNC Settings",
                },
                callback: function (r) {
                    if (r.message && r.message.teacher_timesheet_approval) {
                        const allowed_users = r.message.teacher_timesheet_approval.map(row => row.user);
                        const is_approver = allowed_users.includes(frappe.session.user) || frappe.session.user === "Administrator";

                        if (is_approver && frm.doc.status === "Pending") {
                            
                            // APPROVE ACTION
                            frm.add_custom_button(__("Approve"), function () {
                                frappe.confirm(__("Are you sure you want to <b>APPROVE</b> this timesheet? <br><small>This will validate rates in Teacher Master before approval.</small>"), function () {
                                    handle_status_update(frm, "Approved");
                                });
                            }, __("Actions")).addClass("btn-primary");

                            // REJECT ACTION
                            frm.add_custom_button(__("Reject"), function () {
                                frappe.prompt([
                                    {
                                        label: 'Reason for Rejection',
                                        fieldname: 'reason',
                                        fieldtype: 'Small Text',
                                        reqd: 1
                                    }
                                ], (values) => {
                                    handle_status_update(frm, "Rejected", values.reason);
                                }, __('Provide Rejection Reason'), __('Submit'));
                            }, __("Actions")).addClass("btn-danger");
                        }
                    }
                },
            });
        }

        if (frm.doc.status === "Approved" || frm.doc.status === "Rejected") {
            frm.disable_form();
        }
        toggle_activity_add_row(frm);
    
    },

    onload: function (frm) {
        if (!frm.doc.teacher_id) {
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Teacher",
                    filters: { email: frappe.session.user },
                    fields: ["name"],
                },
                callback: function (r) {
                    if (r.message && r.message.length > 0) {
                        frm.set_value("teacher_id", r.message[0].name);
                        frm.set_df_property("teacher_id", "read_only", 1);
                    }
                },
            });
        }
    },
});

// --- Calculations Logic ---

frappe.ui.form.on("Activities", {
    activity_name: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.activity_name && frm.doc.teacher_id) {
            frappe.call({
                method: "tnc_v2_360ithub.tnc_v2.doctype.teachers_timesheet.teachers_timesheet.get_rate_for_activity",
                args: {
                    teacher_id: frm.doc.teacher_id,
                    activity_name: row.activity_name,
                },
                callback: function (r) {
                    if (r.message) {
                        let rate = typeof r.message === 'object' ? r.message.rate : r.message;
                        let uom = typeof r.message === 'object' ? r.message.uom : row.uom;
                        frappe.model.set_value(cdt, cdn, "activity_fee", rate);
                        frappe.model.set_value(cdt, cdn, "uom", uom);
                        calculate_row_amount(frm, cdt, cdn);
                    }
                },
            });
        }
    },
    qty: function (frm, cdt, cdn) {
        calculate_row_amount(frm, cdt, cdn);
    },
    activity_fee: function (frm, cdt, cdn) {
        calculate_row_amount(frm, cdt, cdn);
    }
});

function calculate_row_amount(frm, cdt, cdn) {
    let child = locals[cdt][cdn];
    let qty = flt(child.qty) || 0;
    let rate = flt(child.activity_fee) || 0;
    let amount = qty * rate;
    frappe.model.set_value(cdt, cdn, "amount", amount);
    calculate_grand_total(frm);
}

function calculate_grand_total(frm) {
    let grand_total = 0;
    (frm.doc.activity_type || []).forEach((row) => {
        grand_total += flt(row.amount);
    });
    frm.set_value("grand_total", grand_total);
}

function toggle_activity_add_row(frm) {
    // Prevent adding rows if status is not Pending or if a row already exists
    if (frm.doc.status !== "Pending" || (frm.doc.activity_type && frm.doc.activity_type.length >= 1)) {
        frm.get_field("activity_type").grid.cannot_add_rows = true;
    } else {
        frm.get_field("activity_type").grid.cannot_add_rows = false;
    }
    frm.refresh_field("activity_type");
}


function handle_status_update(frm, status, reason = null) {
    frappe.call({
        method: "tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher.update_timesheet_status",
        args: {
            name: frm.doc.name,
            target_status: status,
            reason: reason
        },
        freeze: true,
        callback: function(r) {
            if (!r.exc) {
                frm.reload_doc();
                frappe.show_alert({
                    message: __(`Timesheet has been ${status}`), 
                    indicator: status === 'Approved' ? 'green' : 'red'
                });
            }
        }
    });
}