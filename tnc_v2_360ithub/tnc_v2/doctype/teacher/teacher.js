// frappe.ui.form.on("Teacher", {
// 	refresh: function (frm) {
// 		if (!frm.is_new()) {
// 			// Add Create Payment button
// 			frm.add_custom_button(__("Create Payment"), function () {
// 				frappe.prompt(
// 					[
// 						{
// 							fieldname: "date_range",
// 							fieldtype: "DateRange",
// 							label: "Date Range",
// 							reqd: 1,
// 						},
// 					],
// 					function (values) {
// 						const [start_date, end_date] = values.date_range;

// 						// Fetch unpaid timesheets
// 						frappe.call({
// 							method: "tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher.get_unpaid_timesheets",
// 							args: {
// 								teacher_name: frm.doc.name,
// 								start_date: start_date,
// 								end_date: end_date,
// 							},
// 							callback: function (response) {
// 								let timesheets = response.message || [];

// 								if (timesheets.length === 0) {
// 									frappe.msgprint("No unpaid timesheets found.");
// 									return;
// 								}

// 								// Open the selection dialog with timesheets
// 								show_timesheet_selection_dialog(
// 									frm,
// 									start_date,
// 									end_date,
// 									timesheets,
// 								);
// 							},
// 						});
// 					},
// 					"Enter Payment Date Range",
// 					"Fetch Timesheets",
// 				);
// 			});

// 			// Load Tab Data
// 			load_teacher_payments(frm);
// 			init_timesheet_portal(frm);
// 		}
// 	},
// });

// function show_timesheet_selection_dialog(frm, start_date, end_date, timesheets) {
// 	let dialog = new frappe.ui.Dialog({
// 		title: "Select Timesheets for Payment",
// 		fields: [
// 			{
// 				fieldname: "date_range_summary",
// 				fieldtype: "HTML",
// 				options: `<div style="margin-bottom: 10px;">
//                     <strong>Date Range:</strong> ${formatDate(start_date)} to ${formatDate(end_date)}
//                 </div>`,
// 			},
// 			{
// 				fieldname: "section_break_buttons",
// 				fieldtype: "Section Break",
// 			},
// 			{
// 				fieldname: "select_all",
// 				fieldtype: "Button",
// 				label: "Select All",
// 				click: function () {
// 					dialog
// 						.get_field("timesheet_list")
// 						.$wrapper.find("input[data-timesheet]")
// 						.prop("checked", true)
// 						.trigger("change");
// 				},
// 			},
// 			{
// 				fieldname: "column_break_buttons",
// 				fieldtype: "Column Break",
// 			},
// 			{
// 				fieldname: "unselect_all",
// 				fieldtype: "Button",
// 				label: "Unselect All",
// 				click: function () {
// 					dialog
// 						.get_field("timesheet_list")
// 						.$wrapper.find("input[data-timesheet]")
// 						.prop("checked", false)
// 						.trigger("change");
// 				},
// 			},
// 			{
// 				fieldname: "timesheet_list_section",
// 				fieldtype: "Section Break",
// 			},
// 			{
// 				fieldname: "timesheet_list",
// 				fieldtype: "HTML",
// 				options: generate_timesheet_table(timesheets),
// 			},
// 			{
// 				fieldname: "total_amount",
// 				fieldtype: "Currency",
// 				label: "Total Amount",
// 				read_only: 1,
// 				default: 0,
// 			},
// 		],
// 		primary_action_label: "Create Payment",
// 		primary_action: function () {
// 			const selected_timesheets = timesheets
// 				.filter((ts) =>
// 					dialog
// 						.get_field("timesheet_list")
// 						.$wrapper.find(`[data-timesheet="${ts.name}"]`)
// 						.prop("checked"),
// 				)
// 				.map((ts) => ts.name);

// 			if (selected_timesheets.length === 0) {
// 				frappe.msgprint("Please select at least one timesheet.");
// 				return;
// 			}

// 			// Call backend to create PO
// 			frappe.call({
// 				method: "tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher.create_purchase_order_for_selected_timesheets",
// 				args: {
// 					teacher_name: frm.doc.name,
// 					name_of_the_teacher: frm.doc.full_name,
// 					start_date: start_date,
// 					end_date: end_date,
// 					timesheets: selected_timesheets,
// 				},
// 				callback: function (r) {
// 					if (r.message) {
// 						frappe.msgprint(`Purchase Order ${r.message} created successfully.`);
// 						frm.reload_doc();
// 					}
// 				},
// 			});
// 		},
// 	});

// 	dialog.size = "large";

// 	// Add event listener to update totals dynamically
// 	dialog.get_field("timesheet_list").$wrapper.on("change", "input[data-timesheet]", function () {
// 		let total_amount = 0;
// 		timesheets.forEach((ts) => {
// 			if (
// 				dialog
// 					.get_field("timesheet_list")
// 					.$wrapper.find(`[data-timesheet="${ts.name}"]`)
// 					.prop("checked")
// 			) {
// 				// Sum up grand total
// 				total_amount += ts.grand_total || 0;
// 			}
// 		});
// 		dialog.set_value("total_amount", total_amount);
// 	});

// 	dialog.show();
// }

// function generate_timesheet_table(timesheets) {
// 	let html = `<table class="table table-bordered table-hover">
//         <thead>
//             <tr>
//                 <th style="width: 10%">${__("Select")}</th>
//                 <th style="width: 20%">${__("Date")}</th>
//                 <th style="width: 50%">${__("Activities")}</th>
//                 <th style="width: 20%">${__("Grand Total")}</th>
//             </tr>
//         </thead>
//         <tbody>`;

// 	timesheets.forEach((ts) => {
// 		let activities_text = (ts.activities || [])
// 			.map((act) => {
// 				let label = act.uom === "Hour" ? "min" : "Nos";
// 				return `${act.activity_name} (${act.qty} ${label})`;
// 			})
// 			.join(", ");

// 		html += `
//             <tr>
//                 <td><input type="checkbox" data-timesheet="${ts.name}"></td>
//                 <td>${formatDate(ts.date)}</td>
//                 <td><small class="text-muted">${activities_text || "No activities"}</small></td>
//                 <td>${frappe.format(ts.grand_total, { fieldtype: "Currency" })}</td>
//             </tr>`;
// 	});

// 	html += `</tbody></table>`;
// 	return html;
// }

// // Function to format date from YYYY-MM-DD to DD-MM-YYYY
// function formatDate(dateString) {
// 	if (!dateString) return "-";
// 	let dateObj = new Date(dateString);
// 	if (isNaN(dateObj.getTime())) return dateString;
// 	let day = String(dateObj.getDate()).padStart(2, "0");
// 	let month = String(dateObj.getMonth() + 1).padStart(2, "0");
// 	let year = dateObj.getFullYear();
// 	return `${day}-${month}-${year}`;
// }

// ////////////////////////////// HTML TABLE //////////////////////////////

// function load_teacher_payments(frm) {
// 	baseURL = window.location.origin;
// 	frappe.call({
// 		method: "tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher.get_teacher_payments",
// 		args: {
// 			teacher_id: frm.doc.name,
// 		},
// 		callback: function (response) {
// 			if (response.message) {
// 				render_payment_table(frm, response.message);
// 			}
// 		},
// 	});
// }

// function render_payment_table(frm, data) {
// 	if (!data.length) {
// 		frm.set_df_property(
// 			"teacher_payment_details",
// 			"options",
// 			`<p class="text-muted">${__("No Payment Records Found.")}</p>`,
// 		);
// 		return;
// 	}

// 	let table_html = `<table class="table table-bordered table-hover" style="width: 100%;">
//         <thead>
//             <tr>
//                 <th style="text-align: center;">${__("Date")}</th>
//                 <th style="text-align: center;">${__("Total Amount")}</th>
//                 <th style="text-align: center;">${__("Payment Status")}</th>
//                 <th style="text-align: center;">${__("Outstanding")}</th>
//                 <th style="text-align: center;">${__("Action")}</th>
//             </tr>
//         </thead>
//         <tbody>`;

// 	data.forEach((entry) => {
// 		let formattedDate = formatDate(entry.date);
// 		let poLink = `<a href="${baseURL}/app/purchase-order/${entry.purchase_order_id}" target="_blank"
//             class="btn btn-xs btn-primary font-md">
//             ${__("View PO")}
//         </a>`;

// 		table_html += `
//             <tr>
//                 <td style="text-align: center;">${formattedDate}</td>
//                 <td style="text-align: center;">${frappe.format(entry.total_amount, { fieldtype: "Currency" })}</td>
//                 <td style="text-align: center;">${entry.payment_status}</td>
//                 <td style="text-align: center;">${frappe.format(entry.outstanding, { fieldtype: "Currency" })}</td>
//                 <td style="text-align: center;">${poLink}</td>
//             </tr>`;
// 	});

// 	table_html += `</tbody></table>`;

// 	frm.set_df_property("teacher_payment_details", "options", table_html);
// }

// ////////////////////////////// TEACHER TIMESHEET TAB //////////////////////////////

// ////////////////////////////// TEACHER TIMESHEET PORTAL //////////////////////////////

// function init_timesheet_portal(frm) {
// 	if (frm.timesheet_portal_initialized) return;

// 	const wrapper = frm.fields_dict.timesheet_portal.$wrapper;
// 	wrapper.empty().css({
// 		padding: "20px",
// 		backgroundColor: "var(--bg-color)",
// 		border: "1px solid var(--border-color)",
// 		borderRadius: "8px",
// 		marginTop: "10px",
// 	});

// 	// Create sub-containers for the filter and the results
// 	wrapper.append(`
// 		<div class="timesheet-portal-header" style="margin-bottom: 25px; border-bottom: 1px solid var(--border-color); padding-bottom: 15px;">
// 			<h4 style="margin: 0 0 10px 0;">${__("Timesheet History")}</h4>
// 			<p class="text-muted" style="margin: 0; font-size: 13px;">${__("Filter and view approved timesheet records for this teacher.")}</p>
// 		</div>
// 		<div class="timesheet-summary-container" style="display: flex; gap: 15px; margin-bottom: 25px;"></div>
// 		<div class="timesheet-filter-container" style="max-width: 800px; margin-bottom: 25px;"></div>
// 		<div class="timesheet-results-container"></div>
// 	`);

// 	// Initialize the Filter Group (Isolated from frm.doc)
// 	frm.timesheet_filter_group = new frappe.ui.FieldGroup({
// 		parent: wrapper.find(".timesheet-filter-container"),
// 		fields: [
// 			{
// 				fieldname: "date_range",
// 				fieldtype: "DateRange",
// 				label: __("Select Date Range"),
// 				change: () => load_teacher_timesheets(frm),
// 			},
// 			{
// 				fieldname: "cb1",
// 				fieldtype: "Column Break",
// 			},
// 			{
// 				fieldname: "status",
// 				fieldtype: "Select",
// 				label: __("Status"),
// 				options: ["All", "Draft", "Approved", "Paid"],
// 				default: "All",
// 				change: () => load_teacher_timesheets(frm),
// 			},
// 		],
// 	});

// 	frm.timesheet_filter_group.make();

// 	// Explicitly set default values to ensure they are picked up by get_values() and the UI
// 	frm.timesheet_filter_group.set_values({
// 		date_range: [
// 			frappe.datetime.add_days(frappe.datetime.get_today(), -7),
// 			frappe.datetime.get_today(),
// 		],
// 	});

// 	frm.timesheet_portal_initialized = true;

// 	// Initial load of data
// 	load_teacher_timesheets(frm);
// }

// function load_teacher_timesheets(frm) {
// 	if (!frm.timesheet_filter_group) return;

// 	// Get values from the isolated FieldGroup, not frm.doc
// 	const values = frm.timesheet_filter_group.get_values();
// 	let start_date, end_date, status;

// 	if (values) {
// 		if (values.date_range) {
// 			if (Array.isArray(values.date_range)) {
// 				[start_date, end_date] = values.date_range;
// 			} else if (typeof values.date_range === "string") {
// 				[start_date, end_date] = values.date_range.split(",");
// 			}
// 		}
// 		status = values.status || "All";
// 	}

// 	// Fallback to defaults if values are missing or incomplete
// 	if (!start_date || !end_date) {
// 		start_date = frappe.datetime.add_days(frappe.datetime.get_today(), -7);
// 		end_date = frappe.datetime.get_today();
// 	}

// 	frappe.call({
// 		method: "tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher.get_teacher_timesheets_for_portal",
// 		args: {
// 			teacher_id: frm.doc.name,
// 			start_date: start_date,
// 			end_date: end_date,
// 			status: status || "All",
// 		},
// 		callback: function (response) {
// 			const data = response.message || {
// 				timesheets: [],
// 				summary: { draft: 0, to_be_paid: 0, paid: 0 },
// 			};
// 			render_timesheet_summary(frm, data.summary);
// 			render_timesheet_list_table(frm, data.timesheets);
// 		},
// 	});
// }

// function render_timesheet_summary(frm, summary) {
// 	const container = frm.fields_dict.timesheet_portal.$wrapper.find(
// 		".timesheet-summary-container",
// 	);
// 	container.empty();

// 	const cards = [
// 		{ label: __("Draft Amount"), value: summary.draft, indicator: "gray" },
// 		{ label: __("Amount to be Paid"), value: summary.to_be_paid, indicator: "orange" },
// 		{ label: __("Already Paid"), value: summary.paid, indicator: "green" },
// 	];

// 	cards.forEach((card) => {
// 		container.append(`
// 			<div style="flex: 1; padding: 15px; background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; text-align: center; box-shadow: var(--shadow-sm);">
// 				<div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; margin-bottom: 8px;">
// 					<span class="indicator-pill ${card.indicator}" style="margin-right: 5px;"></span>
// 					${card.label}
// 				</div>
// 				<div style="font-size: 20px; font-weight: 700; color: var(--text-color);">
// 					${frappe.format(card.value, { fieldtype: "Currency" })}
// 				</div>
// 			</div>
// 		`);
// 	});
// }

// function render_timesheet_list_table(frm, data) {
// 	const container = frm.fields_dict.timesheet_portal.$wrapper.find(
// 		".timesheet-results-container",
// 	);
// 	container.empty();

// 	if (!data.length) {
// 		container.html(`
// 			<div style="padding: 40px; text-align: center; background-color: var(--bg-light-gray); border-radius: 6px; border: 1px dashed var(--border-color);">
// 				<p class="text-muted" style="margin: 0;">${__("No timesheets found for the selected period.")}</p>
// 			</div>
// 		`);
// 		return;
// 	}

// 	let table_html = `
// 		<table class="table table-bordered table-hover portal-table" style="width: 100%;">
// 			<thead>
// 				<tr>
// 					<th style="width: 15%;">${__("Date")}</th>
// 					<th style="width: 45%;">${__("Activities")}</th>
// 					<th style="text-align: right; width: 20%;">${__("Grand Total")}</th>
// 					<th style="text-align: center; width: 20%;">${__("Status")}</th>
// 				</tr>
// 			</thead>
// 			<tbody>`;

// 	data.forEach((entry) => {
// 		let activities_text = (entry.activities || [])
// 			.map((act) => {
// 				let label = act.uom === "Hour" ? "min" : "Nos";
// 				return `${act.activity_name} (${act.qty} ${label})`;
// 			})
// 			.join(", ");

// 		let status_badge = "";
// 		if (entry.status === "Draft") {
// 			status_badge = `<span class="indicator-pill gray">${__("Draft")}</span>`;
// 		} else if (entry.status === "Submitted" && !entry.purchase_order_id) {
// 			status_badge = `<span class="indicator-pill orange">${__("Approved")}</span>`;
// 		} else if (entry.status === "Submitted" && entry.purchase_order_id) {
// 			status_badge = `<span class="indicator-pill green">${__("Paid")}</span>`;
// 		}

// 		table_html += `
// 			<tr>
// 				<td>
// 					<a href="/app/teachers-timesheet/${entry.name}" target="_blank" style="font-weight: 500;">
// 						${formatDate(entry.date)}
// 					</a>
// 				</td>
// 				<td>
// 					<small class="text-muted">${activities_text || "No activities recorded"}</small>
// 				</td>
// 				<td style="text-align: right; font-weight: 600;">
// 					${frappe.format(entry.grand_total, { fieldtype: "Currency" })}
// 				</td>
// 				<td style="text-align: center;">
// 					${status_badge}
// 				</td>
// 			</tr>`;
// 	});

// 	table_html += `</tbody></table>`;

// 	container.html(table_html);
// }


frappe.ui.form.on("Teacher", {
	refresh: function (frm) {
        if (!frm.is_new()) {
            // 1. Fetch Admin Settings and check permissions
            frappe.call({
                method: "frappe.client.get",
                args: {
                    doctype: "TNC Settings",
                    name: "TNC Settings",
                },
                callback: function (r) {
                    const settings = r.message || {};
                    const allowed_users = settings.teacher_timesheet_approval ? 
                                          settings.teacher_timesheet_approval.map(row => row.user) : [];

                    // Permission logic: TNC Manager OR Admin OR listed in specific table
                    const is_tnc_manager = frappe.user_roles.includes("TNC Manager");
                    const is_admin_or_manager = is_tnc_manager || 
                                              frappe.session.user === "Administrator" || 
                                              allowed_users.includes(frappe.session.user);

                    // STORE THIS in the form object so portal grid can access it
                    frm.is_approver = is_admin_or_manager;

                    // 2. ONLY add "Finance" buttons if the user is TNC Manager or Administrator
                    if (is_admin_or_manager) {
                        frm.add_custom_button(__("Create Invoice"), function () {
                            show_unpaid_timesheet_dialog(frm);
                        });

                        frm.add_custom_button(__("Create Payment"), function () {
                            show_outstanding_invoice_dialog(frm);
                        }).addClass("btn-primary"); // Optional: highlight it
                    }

                    // 3. Load standard components
                    load_teacher_payments(frm);
                    init_timesheet_portal(frm);
                }
            });
        }
    }
});

/**
 * 1. ENHANCED PAYMENT PROMPT (Shows Invoice + Internal Item Details)
 */


/**
 * UPDATED PAYMENT DIALOG WITH AUTO-ALLOCATION & PARTIAL PAYMENT
 */
function show_outstanding_invoice_dialog(frm) {
    frappe.call({
        method: "tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher.get_outstanding_invoices_with_items",
        args: { supplier_name: frm.doc.full_name },
        callback: function (r) {
            let invoices = r.message || [];
            if (!invoices.length) return frappe.msgprint(__("No outstanding invoices found."));

            let dialog = new frappe.ui.Dialog({
                title: __("Payment Allocation - {0}", [frm.doc.full_name]),
                size: "extra-large",
                fields: [
                    {
                        label: __("Step 1: Select Invoices"),
                        fieldname: "inv_html",
                        fieldtype: "HTML",
                        options: render_detailed_allocation_table(invoices)
                    },
                    {
                        fieldname: "sb_totals",
                        fieldtype: "Section Break",
                        label: __("Step 2: Enter Amount to Pay")
                    },
                    {
                        label: __("Payment Amount"),
                        fieldname: "paid_amount",
                        fieldtype: "Currency",
                        description: __("The total amount you want to pay now.")
                    },
                    {
                        label: __("Selected Invoices Total"),
                        fieldname: "total_outstanding",
                        fieldtype: "Currency",
                        read_only: 1
                    }
                ],
                primary_action_label: __("Create Payment Entry"),
                primary_action: function () {
                    let total_to_pay = dialog.get_value("paid_amount");
                    let selected_rows = invoices.filter(i => dialog.$wrapper.find(`[data-invoice="${i.name}"]`).prop("checked"));
                    
                    if (total_to_pay <= 0 || !selected_rows.length) {
                        frappe.msgprint(__("Please select invoices and enter an amount greater than zero."));
                        return;
                    }

                    // Allocation Logic: Split 'total_to_pay' among 'selected_rows'
                    let remaining_amt = total_to_pay;
                    let references = [];

                    selected_rows.forEach(inv => {
                        let allocate = 0;
                        if (remaining_amt > 0) {
                            allocate = Math.min(remaining_amt, inv.outstanding);
                            remaining_amt -= allocate;
                            
                            references.push({
                                reference_doctype: "Purchase Invoice",
                                reference_name: inv.name,
                                total_amount: inv.grand_total,
                                outstanding_amount: inv.outstanding,
                                allocated_amount: allocate
                            });
                        }
                    });

                    // Call backend to create Payment Entry with custom allocations
                    frappe.call({
                        method: "tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher.create_payment_for_invoices_v2",
                        args: {
                            teacher_id: frm.doc.name,
                            supplier_name: frm.doc.full_name,
                            total_paid: total_to_pay,
                            references: references
                        },
                        callback: function(res) {
                            if(res.message) {
                                frappe.set_route("Form", "Payment Entry", res.message);
                            }
                        }
                    });
                }
            });

            dialog.size = "large";

            // Triggered when an invoice is checked/unchecked
            dialog.$wrapper.on("change", "input[data-invoice]", function () {
                update_allocation_totals(dialog, invoices);
            });

            // Triggered when user manually types the "Payment Amount"
            dialog.fields_dict.paid_amount.df.onchange = () => {
                update_row_previews(dialog, invoices);
            };

            dialog.show();
        }
    });
}

function update_allocation_totals(dialog, invoices) {
    let selected_total = 0;
    invoices.forEach(inv => {
        if (dialog.$wrapper.find(`[data-invoice="${inv.name}"]`).prop("checked")) {
            selected_total += inv.outstanding;
        }
    });
    dialog.set_value("total_outstanding", selected_total);
    // Auto-set payment amount to total selected by default
    dialog.set_value("paid_amount", selected_total);
    update_row_previews(dialog, invoices);
}

// Shows live "To be Allocated" column in the table
function update_row_previews(dialog, invoices) {
    let current_pay = dialog.get_value("paid_amount") || 0;
    let running_pay = current_pay;

    invoices.forEach(inv => {
        let allocate = 0;
        let is_checked = dialog.$wrapper.find(`[data-invoice="${inv.name}"]`).prop("checked");
        
        if (is_checked && running_pay > 0) {
            allocate = Math.min(running_pay, inv.outstanding);
            running_pay -= allocate;
        }

        let label_class = (allocate == inv.outstanding && is_checked) ? "label-success" : (allocate > 0 ? "label-warning" : "label-default");
        dialog.$wrapper.find(`.alloc-preview[data-invoice-id="${inv.name}"]`)
            .html(`<span class="label ${label_class}" style="font-size:12px;">${frappe.format(allocate, {fieldtype:'Currency'})}</span>`);
    });
}

function render_detailed_allocation_table(invoices) {
    let head_style = `background-color:#3498DB; color:white; text-align: left;`;
    let cell_style = `border: solid 2px #bcb9b4; vertical-align: middle; padding: 8px;`;

    let rows = invoices.map((inv, idx) => {
        let activities = inv.items.map(it => it.item_code).join(", ");
        return `<tr>
            <td style="${cell_style} text-align: center;"><input type="checkbox" data-invoice="${inv.name}" style="transform: scale(1.2);"></td>
            <td style="${cell_style} text-align: center;">${idx + 1}</td>
<td style="${cell_style} text-align: center;">
    <div style="display: flex; align-items: center; gap: 8px; justify-content: center;">
       
        <a href="/app/purchase-invoice/${inv.name}" target="_blank" style="font-size: 11px; font-weight: bold; color: #3498DB;">
            ${inv.name}
        </a>
    </div>
</td>            <td style="${cell_style}"><small class="text-muted">${activities}</small></td>
            <td style="${cell_style} text-align: right;">${frappe.format(inv.outstanding, {fieldtype:'Currency'})}</td>
            <td style="${cell_style} text-align: center;" class="alloc-preview" data-invoice-id="${inv.name}">
                <span class="label label-default" style="font-size:12px;">₹ 0.00</span>
            </td>
        </tr>`;
    }).join("");

    return `
    <table class="table table-bordered" style="width:100%; border-collapse: collapse; background: white;">
        <thead>
            <tr style="${head_style}">
                <th style="${cell_style} text-align: center;">✔</th>
                <th style="${cell_style}">S.No</th>
                <th style="${cell_style}">Invoice</th>
                <th style="${cell_style}">Child Table Activities</th>
                <th style="${cell_style} text-align: right;">Current Outstanding</th>
                <th style="${cell_style} text-align: center;">Auto Allocated</th>
            </tr>
        </thead>
        <tbody>${rows}</tbody>
    </table>`;
}

function render_detailed_invoice_table(invoices) {
	let head_style = `background-color:#3498DB; color:white; text-align: left;`;
	let cell_style = `border: solid 2px #bcb9b4; vertical-align: middle;`;

	let rows = invoices.map((inv, idx) => {
		// Summarize items for preview
		let items_preview = inv.items.map(it => `<li>${it.item_code} (${it.qty})</li>`).join("");
		
		return `<tr>
            <td style="${cell_style} text-align: center;"><input type="checkbox" data-invoice="${inv.name}" style="transform: scale(1.2);"></td>
            <td style="${cell_style} text-align: center;">${idx + 1}</td>
            <td style="${cell_style}"><b>${inv.name}</b><br><small class="text-muted">${formatDate(inv.posting_date)}</small></td>
            <td style="${cell_style}"><ul style="margin:0; padding-left:15px; font-size:11px;">${items_preview}</ul></td>
            <td style="${cell_style} text-align: right; font-weight: bold;">${frappe.format(inv.grand_total, { fieldtype: 'Currency' })}</td>
            <td style="${cell_style} text-align: right; color: red;">${frappe.format(inv.outstanding, { fieldtype: 'Currency' })}</td>
        </tr>`;
	}).join("");

	return `
    <table class="table table-bordered" style="width:100%; border-collapse: collapse;">
        <thead>
            <tr style="${head_style}">
                <th style="${cell_style} width: 40px;">Sel</th>
                <th style="${cell_style} width: 50px;">S.No</th>
                <th style="${cell_style}">Invoice ID & Date</th>
                <th style="${cell_style}">Included Activities</th>
                <th style="${cell_style} text-align: right;">Total Amount</th>
                <th style="${cell_style} text-align: right;">Outstanding</th>
            </tr>
        </thead>
        <tbody>${rows}</tbody>
    </table>`;
}

/**
 * 2. MAIN TEACHER FORM PAYMENT HISTORY (Your Design)
 */
function load_teacher_payments(frm) {
	frappe.call({
		method: "tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher.get_teacher_payments",
		args: { teacher_id: frm.doc.name },
		callback: function (r) {
			render_grid_payment_history(frm, r.message || []);
		}
	});
}

function render_grid_payment_history(frm, data) {
	let head_style = `background-color:#3498DB; color:white; text-align: left;`;
	let cell_style = `border: solid 2px #bcb9b4; vertical-align: middle;`;

	if (!data.length) {
		frm.set_df_property("teacher_payment_details", "options", `<p class='text-muted'>No transaction records found.</p>`);
		return;
	}

	let rows = data.map((row, idx) => {
		let status_color = row.payment_status === "Paid" ? "green" : (row.payment_status === "Unpaid" ? "red" : "#ff9800");
		return `<tr>
            <td style="${cell_style} text-align:center;">${idx + 1}</td>
            <td style="${cell_style}"><a href="/app/purchase-invoice/${row.purchase_order_id}" target="_blank"><b>${row.purchase_order_id}</b></a></td>
            <td style="${cell_style}">${formatDate(row.date)}</td>
            <td style="${cell_style} text-align:right;">${frappe.format(row.total_amount, { fieldtype: 'Currency' })}</td>
            <td style="${cell_style} text-align:center; color: white; font-weight:bold; background-color:${status_color};">
                ${row.payment_status.toUpperCase()}
            </td>
            <td style="${cell_style} text-align:right;">${frappe.format(row.outstanding, { fieldtype: 'Currency' })}</td>
        </tr>`;
	}).join("");

	let table_html = `
    <table class="table table-bordered" style="width:100%; border-collapse: collapse;">
        <thead>
            <tr style="${head_style}">
                <th style="${cell_style}">S. No.</th>
                <th style="${cell_style}">Purchase Invoice</th>
                <th style="${cell_style}">Posting Date</th>
                <th style="${cell_style} text-align: right;">Invoiced Amount</th>
                <th style="${cell_style} text-align: center;">Status</th>
                <th style="${cell_style} text-align: right;">Outstanding</th>
            </tr>
        </thead>
        <tbody>${rows}</tbody>
    </table>`;

	frm.set_df_property("teacher_payment_details", "options", table_html);
}

/**
 * UTILS
 */
function formatDate(d) {
	if (!d) return "-";
	return d.split("-").reverse().join("-");
}

/**
 * 3. IMPROVED TIMESHEET PORTAL (DASHBOARD STYLE)
 */
function init_timesheet_portal(frm) {
    const wrapper = frm.fields_dict.timesheet_portal.$wrapper;
    wrapper.empty().css({ "background": "#ffffff", "padding": "15px", "border": "1px solid #d1d8dd", "border-radius": "8px" });

    wrapper.append(`
        <div class="portal-header" style="margin-bottom: 15px; border-bottom: 2px solid #f0f0f0; padding-bottom: 10px;">
            <h4 style="margin: 0; color: #2c3e50;"><b>Teacher:</b> ${frm.doc.full_name || frm.doc.name}</h4>
        </div>
        <div class="portal-filters-bg" style="background:#f8f9fa; padding:15px; border-radius:5px; margin-bottom:15px; border: 1px solid #e1e8ed;"></div>
        <div class="summary-pills" style="display:flex; gap:10px; width:100%; margin-bottom:20px;"></div>
        <div class="portal-grid"></div>
    `);

    frm.portal_filters = new frappe.ui.FieldGroup({
        parent: wrapper.find(".portal-filters-bg"),
        fields: [
            { fieldtype: "DateRange", fieldname: "range", label: "Date Range", default: [frappe.datetime.add_days(frappe.datetime.get_today(), -30), frappe.datetime.get_today()] },
            { fieldtype: "Column Break" },
            { fieldtype: "Select", fieldname: "ts_status", label: "TS Status", options: ["All", "Pending", "Approved", "Rejected"], default: "All" },
            { fieldtype: "Column Break" },
            { fieldtype: "Select", fieldname: "inv_status", label: "Invoiced?", options: ["All", "Invoiced", "Not Invoiced"], default: "All" },
            { fieldtype: "Column Break" },
            { fieldtype: "Select", fieldname: "pay_status", label: "Payment", options: ["All", "Unpaid", "Partially Paid", "Paid"], default: "All" }
        ]
    });
    frm.portal_filters.make();

    // Re-bind change events for filter functionality
    wrapper.find(".portal-filters-bg").on('change', 'input, select', () => {
        setTimeout(() => { load_portal_table(frm); }, 100);
    });

    frm.portal_duration_sort = null;
    wrapper.on("click", "th[data-sort='duration']", () => {
        frm.portal_duration_sort = frm.portal_duration_sort === "asc" ? "desc" : "asc";
        render_blue_grid_ui(frm, frm._portal_data || []);
    });

    load_portal_table(frm);
}

function load_portal_table(frm) {
    let f = frm.portal_filters.get_values() || {};
    let range = f.range || [frappe.datetime.add_days(frappe.datetime.get_today(), -30), frappe.datetime.get_today()];

    frappe.call({
        method: "tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher.get_teacher_timesheets_for_portal",
        args: {
            teacher_id: frm.doc.name,
            start_date: range[0],
            end_date: range[1],
            ts_status: f.ts_status || "All",
            inv_status: f.inv_status || "All",
            payment_status: f.pay_status || "All"
        },
        callback: function (r) {
            if (r.message) {
                render_pills_ui(frm, r.message.summary);
                render_blue_grid_ui(frm, r.message.timesheets);
            }
        }
    });
}

// function render_blue_grid_ui(frm, data) {
//     let container = frm.fields_dict.timesheet_portal.$wrapper.find(".portal-grid").empty();
//     let head_css = `background-color:#3498DB; color:white; padding:12px; font-size: 11px; text-transform:uppercase; font-weight:bold;`;
//     let row_css = `border-bottom: 1px solid #f0f0f0; padding: 12px; font-size: 12px; vertical-align: middle;`;

//     let rows = data.map((item) => {
//         // --- Date (BIG) & ID (Small) ---
//         let date_parts = item.date.split("-");
//         let big_date = `<div style="font-size: 16px; font-weight: 800; color: #2c3e50;">${date_parts[2]}-${date_parts[1]}-${date_parts[0]}</div>
//                         <div style="font-size: 10px; color: #3498DB;"><a href="/app/teachers-timesheet/${item.name}" target="_blank">${item.name}</a></div>`;

//         // --- Clean Description View ---
//         let desc_txt = item.row_description || "-";
//         let desc_html = desc_txt.length > 50 ? 
//             `${desc_txt.substring(0, 50)}... <i class="fa fa-info-circle" style="color:#3498DB; cursor:pointer;" onclick="view_full_ts_desc('${item.name}', \`${desc_txt.replace(/'/g, "\\'")}\`)"></i>` : desc_txt;

//         // --- Doc Status & Modern Action Icons ---
//         let doc_bg = item.status === "Approved" ? "#27ae60" : (item.status === "Rejected" ? "#e74c3c" : "#f39c12");
//         let status_ui = "";
//         if (item.status === "Pending") {
//             status_ui = `
//                 <div style="display:flex; flex-direction:column; align-items:center; gap:5px;">
//                     <span style="color:${doc_bg}; font-size:9px; font-weight:bold; border:1px solid ${doc_bg}; padding:1px 4px; border-radius:3px;">PENDING</span>
//                     <div style="display:flex; gap:10px;">
//                         <i class="fa fa-check-circle" title="Approve" style="color:#27ae60; font-size:20px; cursor:pointer;" onclick="portal_quick_status('${item.name}', 'Approved')"></i>
//                         <i class="fa fa-times-circle" title="Reject" style="color:#e74c3c; font-size:20px; cursor:pointer;" onclick="portal_quick_status('${item.name}', 'Rejected')"></i>
//                     </div>
//                 </div>`;
//         } else {
//             status_ui = `<span style="background:${doc_bg}; color:white; padding:4px 10px; border-radius:15px; font-size:10px; font-weight:bold;">${item.status.toUpperCase()}</span>`;
//         }

//         // --- Payment Status Logic ---
//         let pay_bg = item.payment_status === "Paid" ? "#2ecc71" : (item.payment_status === "Partially Paid" ? "#f1c40f" : "#e74c3c");
//         let fin_html = `<div style="color:${pay_bg}; font-weight:800; font-size:11px;">${item.payment_status.toUpperCase()}</div>`;
//         if (item.purchase_invoice_id) {
//             fin_html += `<a href="/app/purchase-invoice/${item.purchase_invoice_id}" target="_blank" style="font-size:10px; display:block;">Invoice #${item.purchase_invoice_id}</a>`;
//         }

//         return `<tr>
//             <td style="${row_css} width:150px;">${big_date}</td>
//             <td style="${row_css} color:#555;">${desc_html}</td>
//             <td style="${row_css}">${item.activity_desc || "-"}</td>
//             <td style="${row_css} text-align:right;"><b>${frappe.format(item.grand_total, {fieldtype:'Currency'})}</b></td>
//             <td style="${row_css} text-align:center; min-width:120px;">${status_ui}</td>
//             <td style="${row_css} text-align:center; min-width:120px;">${fin_html}</td>
//         </tr>`;
//     }).join("");

//     container.html(`
//         <div class="table-responsive" style="border: 1px solid #f0f0f0; border-radius:8px;">
//             <table class="table" style="background:white; width:100%; border-collapse:collapse;">
//                 <thead style="background:#f9f9f9;">
//                     <tr>
//                         <th style="${head_css}">Work Date & ID</th>
//                         <th style="${head_css}">Description Summary</th>
//                         <th style="${head_css}">Activities & UOM</th>
//                         <th style="${head_css} text-align:right;">Amount</th>
//                         <th style="${head_css} text-align:center;">Action / Status</th>
//                         <th style="${head_css} text-align:center;">Financial State</th>
//                     </tr>
//                 </thead>
//                 <tbody>${rows || '<tr><td colspan="6" class="text-center">No Activity Found.</td></tr>'}</tbody>
//             </table>
//         </div>
//     `);
// }




function render_blue_grid_ui(frm, data) {
    let container = frm.fields_dict.timesheet_portal.$wrapper.find(".portal-grid").empty();

    // Cache raw rows so the Duration column can be re-sorted client-side without a server round trip
    frm._portal_data = data;

    if (frm.portal_duration_sort) {
        data = data.slice().sort((a, b) => {
            let diff = (a.duration_minutes || 0) - (b.duration_minutes || 0);
            return frm.portal_duration_sort === "asc" ? diff : -diff;
        });
    }

    // Monthly Name Array for dd-mmm-yyyy formatting
    const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

    // CSS Styles
    let head_css = `background-color:#3498DB; color:white; padding:12px 10px; font-size: 11px; font-weight:bold; border: 1px solid #d1d8dd;`;
    let row_css = `border: 1px solid #edf2f7; padding: 10px; font-size: 12px; vertical-align: middle;`;
    let duration_sort_icon = !frm.portal_duration_sort ? "fa-sort" : (frm.portal_duration_sort === "asc" ? "fa-sort-asc" : "fa-sort-desc");

    let rows = data.map((item) => {
        // --- 1. Date (dd-mmm-yyyy) & ID ---
        let d = item.date.split("-"); // [yyyy, mm, dd]
        let date_txt = `${d[2]}-${monthNames[parseInt(d[1]) - 1]}-${d[0]}`; // 13-Apr-2026
        
        let date_ui = `
            <div style="font-size: 13px; font-weight: 700; color: #2c3e50;">${date_txt}</div>
            <div style="font-size: 10px; color: #3498DB; margin-top: 2px;">
                <a href="/app/teachers-timesheet/${item.name}" target="_blank">${item.name}</a>
            </div>`;

        // --- 2. Clean Description (Width Reduced & Word Wrapping) ---
        let desc_txt = item.row_description || "-";
        let desc_html = `
            <div style="max-width: 200px; font-size: 11px; color: #555; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
                ${desc_txt}
            </div>
            ${desc_txt.length > 50 ? `<i class="fa fa-info-circle" style="color:#3498DB; cursor:pointer; font-size: 10px; margin-top:3px;" onclick="view_full_ts_desc('${item.name}', \`${desc_txt.replace(/'/g, "\\'")}\`)"></i>` : ""}`;

        // --- 3. Doc Status Logic ---
        let doc_bg = item.status === "Approved" ? "#27ae60" : (item.status === "Rejected" ? "#e74c3c" : "#f39c12");
        let status_ui = "";
        if (item.status === "Pending") {
            // Check the permission we calculated in the 'refresh' event
            if (frm.is_approver) {
                // If allowed: show check and cross icons
                status_ui = `
                    <div style="display:flex; flex-direction:column; align-items:center;">
                        <span style="color:${doc_bg}; font-size:9px; font-weight:bold; border:1px solid ${doc_bg}; padding:1px 4px; border-radius:3px; margin-bottom:4px;">PENDING</span>
                        <div style="display:flex; gap:12px;">
                            <i class="fa fa-check-circle" style="color:#27ae60; font-size:18px; cursor:pointer;" onclick="portal_quick_status('${item.name}', 'Approved')"></i>
                            <i class="fa fa-times-circle" style="color:#e74c3c; font-size:18px; cursor:pointer;" onclick="portal_quick_status('${item.name}', 'Rejected')"></i>
                        </div>
                    </div>`;
            } else {
                // If NOT allowed: just show the word 'PENDING' without action icons
                status_ui = `<span style="border: 1px solid ${doc_bg}; color:${doc_bg}; padding:3px 10px; border-radius:12px; font-size:10px; font-weight:bold;">PENDING</span>`;
            }
        } else {
            status_ui = `<span style="background:${doc_bg}; color:white; padding:3px 10px; border-radius:12px; font-size:10px; font-weight:bold; border: 1px solid ${doc_bg};">${item.status.toUpperCase()}</span>`;
        }

        // --- 4. Payment Status ---
        let pay_bg = item.payment_status === "Paid" ? "#2ecc71" : (item.payment_status === "Partially Paid" ? "#f1c40f" : "#e74c3c");
        let fin_html = `
            <div style="color:${pay_bg}; font-weight:800; font-size:10px; border:1px solid ${pay_bg}44; display:inline-block; padding:2px 6px; border-radius:4px; margin-bottom:4px;">${item.payment_status.toUpperCase()}</div>
            ${item.purchase_invoice_id ? `<a href="/app/purchase-invoice/${item.purchase_invoice_id}" target="_blank" style="font-size:10px; display:block; color: #4a5568;">Invoice: <b>${item.purchase_invoice_id.split("-").pop()}</b></a>` : ""}`;

        return `<tr>
            <td style="${row_css} width:120px;">${date_ui}</td>
            <td style="${row_css}">${desc_html}</td>
            <td style="${row_css} font-size:11px;">${item.activity_desc || "-"}</td>
            <td style="${row_css} text-align:center; white-space:nowrap;">${item.duration_formatted || "-"}</td>
            <td style="${row_css} text-align:right; font-weight:bold;">${frappe.format(item.grand_total, {fieldtype:'Currency'})}</td>
            <td style="${row_css} text-align:center; min-width:110px;">${status_ui}</td>
            <td style="${row_css} text-align:center;">${fin_html}</td>
        </tr>`;
    }).join("");

    container.html(`
        <div class="table-responsive" style="border: 1px solid #e1e8ed; border-radius:8px; overflow: hidden;">
            <table class="table" style="background:white; width:100%; border-collapse:collapse; margin:0;">
                <thead style="background:#f9f9f9;">
                    <tr>
                        <th style="${head_css}">Work Date</th>
                        <th style="${head_css}">Notes</th>
                        <th style="${head_css}">Activity Details</th>
                        <th class="sortable" data-sort="duration" title="Click to sort" style="${head_css} text-align:center; cursor:pointer; user-select:none;">Duration <i class="fa ${duration_sort_icon}" style="margin-left:5px;"></i></th>
                        <th style="${head_css} text-align:right;">Total</th>
                        <th style="${head_css} text-align:center;">TS Status</th>
                        <th style="${head_css} text-align:center;">Billing</th>
                    </tr>
                </thead>
                <tbody>${rows || '<tr><td colspan="7" class="text-center" style="padding:40px; color:#bdc3c7;">No Activity Records found.</td></tr>'}</tbody>
            </table>
        </div>
    `);
}

// Global action triggered by Check/Cross Icons
// window.portal_quick_status = function(name, target) {
//     frappe.confirm(`Change Status of <b>${name}</b> to <b>${target}</b>?`, () => {
//         frappe.db.set_value("Teachers Timesheet", name, "status", target).then(() => {
//             frappe.show_alert({message: `Timesheet updated to ${target}`, indicator: target === 'Approved' ? 'green' : 'red'});
//             cur_frm.reload_doc(); 
//         });
//     });
// };


window.portal_quick_status = function(name, target) {
    if (target === "Approved") {
        frappe.confirm(`Are you sure you want to <b>APPROVE</b> timesheet ${name}? <br><small>This will validate teacher rates before saving.</small>`, () => {
            execute_status_update(name, target);
        });
    } 
    else if (target === "Rejected") {
        // Prompt for Rejection Reason
        frappe.prompt([
            {
                label: 'Reason for Rejection',
                fieldname: 'reason',
                fieldtype: 'Small Text',
                reqd: 1
            }
        ], (values) => {
            execute_status_update(name, target, values.reason);
        }, __('Reject Timesheet'), __('Submit'));
    }
};

// Internal function to call the Python backend
function execute_status_update(name, status, reason = null) {
    frappe.call({
        method: "tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher.update_timesheet_status",
        args: {
            name: name,
            target_status: status,
            reason: reason
        },
        freeze: true,
        freeze_message: __("Processing..."),
        callback: function(r) {
            if (!r.exc) {
                frappe.show_alert({
                    message: __(`Timesheet ${name} is now ${status}`), 
                    indicator: status === 'Approved' ? 'green' : 'red'
                });
                cur_frm.reload_doc(); 
            }
        }
    });
}

window.view_full_ts_desc = function(id, text) {
    frappe.msgprint({ title: __('Activity Details: ') + id, message: `<div style="padding:10px;">${text}</div>`, wide: true });
};

// function render_pills_ui(frm, summary) {
//     let target = frm.fields_dict.timesheet_portal.$wrapper.find(".summary-pills").empty();
//     const cards = [
//         { label: "Unpaid Total", value: summary.total_unpaid, color: "#e74c3c" },
//         { label: "Partially Paid (Invoiced)", value: summary.total_partial, color: "#f1c40f" },
//         { label: "Successfully Paid", value: summary.total_paid, color: "#27ae60" },
//         { label: "Pending Amount", value: summary.total_pending, color: "#f39c12" }
//     ];

//     cards.forEach(card => {
//         target.append(`
//             <div style="flex:1; background:white; padding:12px; border-radius:8px; border:1px solid #e1e8ed; border-left:5px solid ${card.color};">
//                 <div style="font-size:10px; font-weight:bold; color:#7f8c8d;">${card.label}</div>
//                 <div style="font-size:18px; font-weight:800; color:#2c3e50;">${frappe.format(card.value, {fieldtype:'Currency'})}</div>
//             </div>
//         `);
//     });
// }


function render_pills_ui(frm, summary) {
    let target = frm.fields_dict.timesheet_portal.$wrapper.find(".summary-pills").empty();
    
    // Ordered with Pending First
    // Added 'is_count_only' flag for the first card
    const cards = [
        { 
            label: "Pending Timesheets", 
            value: summary.count_pending, 
            is_count_only: true, 
            color: "#f39c12" 
        },
        {
            label: "Unpaid Total",
            value: summary.total_unpaid,
            count: summary.count_unpaid,
            duration: summary.unpaid_duration_formatted,
            color: "#e74c3c"
        },
        { 
            label: "Partially Paid", 
            value: summary.total_partial, 
            count: summary.count_partial, 
            color: "#f1c40f" 
        },
        { 
            label: "Successfully Paid", 
            value: summary.total_paid, 
            count: summary.count_paid, 
            color: "#27ae60" 
        }
    ];

    cards.forEach(card => {
        let display_value = "";
        let badge_html = "";

        if (card.is_count_only) {
            // Large number is the Count, no currency formatting
            display_value = card.value; 
            badge_html = `<span style="font-size: 10px; color: ${card.color}; font-weight: bold;">Action Required</span>`;
        } else {
            // Large number is the Currency Amount
            display_value = frappe.format(card.value, {fieldtype:'Currency'});
            badge_html = `
                <span style="background: ${card.color}20; color: ${card.color}; padding: 2px 6px; border-radius: 10px; font-size: 10px; font-weight: bold;">
                    ${card.count} Items
                </span>`;
        }

        target.append(`
            <div style="flex:1; background:white; padding:12px; border-radius:8px; border:1px solid #e1e8ed; border-left:5px solid ${card.color}; min-width: 150px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                    <span style="font-size:10px; font-weight:bold; color:#7f8c8d; text-transform: uppercase;">${card.label}</span>
                    ${badge_html}
                </div>
                <div style="font-size:18px; font-weight:800; color:#2c3e50;">
                    ${display_value}
                </div>
                ${card.duration ? `<div style="font-size:11px; font-weight:600; color:#7f8c8d; margin-top:2px;">Completed: ${card.duration}</div>` : ""}
            </div>
        `);
    });
}

function show_unpaid_timesheet_dialog(frm) {
	frappe.prompt([
		{
			fieldname: "date_range",
			fieldtype: "DateRange",
			label: __("Select Work Date Range"),
			reqd: 1,
		},
	], function (values) {
		const [start_date, end_date] = values.date_range;

		frappe.call({
			method: "tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher.get_unpaid_timesheets",
			args: {
				teacher_name: frm.doc.name,
				start_date: start_date,
				end_date: end_date,
			},
			callback: function (r) {
				if (r.message && r.message.length > 0) {
					render_selection_dialog(frm, r.message, start_date, end_date);
				} else {
					frappe.msgprint(__("No unpaid timesheets found."));
				}
			}
		});
	}, __("Step 1: Select Work Range"), __("Fetch"));
}

function generate_blue_timesheet_table(timesheets, teacher_full_name) {
    const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    
    // Header Styles as requested
    const head_style = `background-color:#3498DB; color:white; padding:12px 10px; font-size: 11px; font-weight:bold; border: 1px solid #d1d8dd; text-align:right;`;
    
    // Fixed: Named this row_style and ensured it is used consistently below
    const row_style = `border: 1px solid #d1d8dd; padding: 10px; font-size: 12px; vertical-align: middle;`;

    let rows = timesheets.map((ts) => {
        // 1. dd-mmm-yyyy date format
        let d = ts.date.split("-"); 
        let formatted_date = `${d[2]}-${monthNames[parseInt(d[1]) - 1]}-${d[0]}`;

        // 2. Summary for activities child table
        let activity_summary = (ts.activities || []).map(act => {
            return `<div style="margin-bottom:2px; font-size: 11px;">${act.activity_name} (${act.qty} ${act.uom || ''})</div>`;
        }).join("");

        return `
            <tr>
                <td style="${row_style} text-align:center; width:40px;">
                    <input type="checkbox" data-timesheet="${ts.name}" data-amount="${ts.grand_total}" style="cursor:pointer;">
                </td>
                <td style="${row_style} text-align:left;">
                    <div style="font-weight:bold; color:#2c3e50;">${formatted_date}</div>
                    <div style="font-size:10px;"><a href="/app/teachers-timesheet/${ts.name}" target="_blank">${ts.name}</a></div>
                </td>
                <td style="${row_style} text-align:left;">${activity_summary || '-'}</td>
                <td style="${row_style} text-align:right; font-weight:bold;">${frappe.format(ts.grand_total, {fieldtype:'Currency'})}</td>
            </tr>
        `;
    }).join("");

    return `
        <div style="margin-bottom:10px; padding: 8px 0; border-bottom: 2px solid #3498DB;">
            <span style="font-size: 14px; color:#2c3e50; font-weight:600;">Teacher: ${teacher_full_name}</span>
        </div>
        <div style="max-height: 400px; overflow-y: auto; border: 1px solid #d1d8dd;">
            <table class="table table-bordered" style="width:100%; border-collapse: collapse; margin-bottom: 0;">
                <thead>
                    <tr>
                        <th style="${head_style} text-align:center; width:40px;">
                            <input type="checkbox" class="select-all-timesheets" style="cursor:pointer;">
                        </th>
                        <th style="${head_style} text-align:left;">Work Date & ID</th>
                        <th style="${head_style} text-align:left;">Activities Details</th>
                        <th style="${head_style}">Amount</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows || '<tr><td colspan="4" style="text-align:center; padding:20px;">No unpaid timesheets.</td></tr>'}
                </tbody>
            </table>
        </div>
    `;
}
function generate_allocation_table_html(data) {
    let style = `border: 1px solid #ddd; padding: 8px;`;
    let rows = data.map(inv => `
        <tr>
            <td style="${style} text-align:center;"><input type="checkbox" data-invoice="${inv.name}" style="transform: scale(1.1);"></td>
            <td style="${style}">${inv.name}</td>
            <td style="${style} text-align:right; font-weight:bold;">${frappe.format(inv.outstanding, { fieldtype: 'Currency' })}</td>
        </tr>`).join("");

    return `
    <table class="table table-bordered small">
        <thead style="background:#f1f3f5;"><tr>
            <th style="${style} width:40px;">✔</th><th style="${style}">Purchase Invoice No</th>
            <th style="${style} text-align:right;">Current Outstanding</th>
        </tr></thead>
        <tbody>${rows}</tbody>
    </table>`;
}


function render_large_cards(frm, s) {
    let container = frm.fields_dict.timesheet_portal.$wrapper.find(".card-area").empty();
    
    const metrics = [
        { label: "Drafted Total", val: s.draft, color: "#95a5a6" },     // Total work still in Draft
        { label: "Pending Balance Due", val: s.unpaid, color: "#e74c3c" }, // No Inv + Unpaid Inv + Partial Balance
        { label: "Actually Received", val: s.paid, color: "#27ae60" }     // Cash/Online received successfully
    ];

    metrics.forEach(m => {
        container.append(`
            <div style="flex:1; background:white; padding:25px; border-radius:12px; border-left: 8px solid ${m.color}; box-shadow: 0 4px 10px rgba(0,0,0,0.06); text-align:center;">
                <div style="font-size:10px; font-weight:700; color:#7f8c8d;  margin-bottom:8px;">${m.label}</div>
                <div style="font-size:26px; font-weight:800; color:#2c3e50;">${frappe.format(m.val, { fieldtype: 'Currency' })}</div>
            </div>
        `);
    });
}

function formatDateInDMY(dateStr) {
    if (!dateStr) return "-";
    return dateStr.split("-").reverse().join("-");
}


function render_selection_dialog(frm, timesheets, start_date, end_date) {
    let dialog = new frappe.ui.Dialog({
        title: __("Select Timesheets for Invoice"),
        size: 'large',
        fields: [
            { 
                fieldname: "ht", 
                fieldtype: "HTML", 
                options: generate_blue_timesheet_table(timesheets, frm.doc.full_name || frm.doc.name) 
            },
            { 
                fieldname: "total_amount", 
                fieldtype: "Currency", 
                label: __("Total for Invoice"), 
                read_only: 1,
                default: 0 
            }
        ],
        primary_action_label: __("Generate Purchase Invoice"),
        primary_action: function () {
            let selected_ids = [];
            dialog.$wrapper.find("input[data-timesheet]:checked").each(function() {
                selected_ids.push($(this).attr("data-timesheet"));
            });

            if (!selected_ids.length) return frappe.msgprint(__("Please select at least one timesheet."));

            frappe.call({
                method: "tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher.create_invoice_from_timesheets",
                args: {
                    teacher_name: frm.doc.name,
                    timesheets: selected_ids,
                    start_date: start_date,
                    end_date: end_date
                },
                callback: function (r) {
                    if (r.message) {
                        frappe.show_alert({ message: __("Invoice Created: {0}", [r.message]), indicator: 'green' });
                        dialog.hide();
                        frm.reload_doc();
                    }
                }
            });
        }
    });

    // Event for "Select All"
    dialog.$wrapper.on("change", ".select-all-timesheets", function () {
        let is_checked = $(this).prop("checked");
        dialog.$wrapper.find("input[data-timesheet]").prop("checked", is_checked).trigger("change");
    });

    // Event for Row Calculation
    dialog.$wrapper.on("change", "input[data-timesheet]", function () {
        let total = 0;
        dialog.$wrapper.find("input[data-timesheet]:checked").each(function() {
            total += parseFloat($(this).attr("data-amount")) || 0;
        });
        dialog.set_value("total_amount", total);
    });

    dialog.show();
}




function refresh_portal_data(frm) {
	let flt = frm.portal_filter_group.get_values();
	if (!flt) return;

	frappe.call({
		method: "tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher.get_teacher_timesheets_for_portal",
		args: { teacher_id: frm.doc.name, start_date: flt.date_range[0], end_date: flt.date_range[1], status: flt.status },
		callback: function (r) {
			render_portal_pills(frm, r.message.summary);
			render_portal_results_grid(frm, r.message.timesheets);
		}
	});
}

function render_portal_pills(frm, summary) {
	let target = frm.fields_dict.timesheet_portal.$wrapper.find(".portal-summary").empty();
	const cards = [
		{ label: "Approved (To be Paid)", value: summary.to_be_paid, color: "#3498db" },
		{ label: "Successfully Paid", value: summary.paid, color: "#27ae60" }
	];

	cards.forEach(c => {
		target.append(`
            <div style="background:white; border-left: 5px solid ${c.color}; padding: 10px 20px; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <div style="font-size:10px;  color:#7f8c8d;">${c.label}</div>
                <div style="font-size:18px; font-weight:700; color:#2c3e50;">${frappe.format(c.value, { fieldtype: 'Currency' })}</div>
            </div>
        `);
	});
}

function render_portal_results_grid(frm, data) {
	let target = frm.fields_dict.timesheet_portal.$wrapper.find(".portal-results").empty();
	let cell_style = `border: solid 2px #bcb9b4; vertical-align: middle; padding: 10px;`;

	if (!data.length) {
		target.html("<div class='alert alert-warning'>No activity records match your criteria.</div>");
		return;
	}

	let rows = data.map((item, i) => {
		let activities = (item.activities || []).map(a => `<span class="badge badge-info" style="font-weight:normal; margin-right:3px;">${a.activity_name}</span>`).join("");
		let status_pill = item.purchase_order_id ? `<span style="color:green; font-weight:bold;">● Invoiced</span>` : `<span style="color:#e67e22; font-weight:bold;">○ Unpaid</span>`;

		return `<tr>
            <td style="${cell_style} text-align:center;">${i + 1}</td>
            <td style="${cell_style}"><b>${item.name}</b></td>
            <td style="${cell_style}">${formatDate(item.date)}</td>
            <td style="${cell_style}">${activities}</td>
            <td style="${cell_style} text-align:right; font-weight:bold;">${frappe.format(item.grand_total, { fieldtype: 'Currency' })}</td>
            <td style="${cell_style} text-align:center;">${status_pill}</td>
        </tr>`;
	}).join("");

	let html = `
    <table class="table table-bordered" style="width:100%; border-collapse: collapse; background: white;">
        <thead>
            <tr style="background-color:#3498DB; color:white;">
                <th style="${cell_style}">No.</th>
                <th style="${cell_style}">Sheet ID</th>
                <th style="${cell_style}">Work Date</th>
                <th style="${cell_style}">Activities Conducted</th>
                <th style="${cell_style} text-align:right;">Daily Total</th>
                <th style="${cell_style} text-align:center;">Payment State</th>
            </tr>
        </thead>
        <tbody>${rows}</tbody>
    </table>`;

	target.html(html);
}