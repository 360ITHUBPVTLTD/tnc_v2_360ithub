// Copyright (c) 2025, pankaj@360ithub.com and contributors
// For license information, please see license.txt

// frappe.query_reports["Teachers Timesheet Report"] = {
//     filters: [
//         {
//             fieldname: "teacher_name",
//             label: __("Teacher Name"),
//             fieldtype: "Link",
//             options: "Teacher",
//             reqd: 0  // optional
//         },
//         {
//             fieldname: "date_range",
//             label: __("Date Range"),
//             fieldtype: "DateRange",
//             reqd: 0  // optional
//         },
//     ],
//     onload: function(report) {
//         // Add a button to download PDF
//         report.page.add_inner_button(__("Download PDF"), function() {
//             const filters = report.get_values();
//             frappe.call({
//                 method: "tnc_v2_360ithub.tnc_v2.report."
//                       + "teachers_timesheet_report.teachers_timesheet_report.download_pdf",
//                 args: { filters: filters },
//                 callback: function(r) {
//                     if (r.message) {
//                         const pdf_url = r.message;
//                         window.open(pdf_url, "_blank");
//                     }
//                 }
//             });
//         });
//     },

//     // 1) Define a custom formatter to control how the link text is displayed
//     formatter: function(value, row, column, data, default_formatter) {
//         // If this is the "teacher_name" column and we have a teacher_full_name, override the link text
//         if (column.fieldname === "teacher_name" && data.teacher_full_name) {
//             // By default, "value" is the docname (e.g. "TCH-0001"), 
//             // but we want to show the teacher's full name as the hyperlink text
//             let link_text = data.teacher_full_name;
            
//             // Build an <a> tag manually so it still links to the Teacher doc, but displays the full name
//             let link_html = `<a class="grey-link" href="/app/teacher/${value}" data-doctype="Teacher">${link_text}</a>`;
            
//             return link_html;
//         }

//         // Otherwise, use the default formatter
//         return default_formatter(value, row, column, data);
//     }
// };



frappe.query_reports["Teachers Timesheet Report"] = {
    filters: [
        {
            fieldname: "teacher_id",
            label: __("Teacher ID"),
            fieldtype: "Link",
            options: "Teacher",
            reqd: 0  // optional
        },
        {
            fieldname: "date_range",
            label: __("Date Range"),
            fieldtype: "DateRange",
            default: [frappe.datetime.month_start(), frappe.datetime.month_end()],
            reqd: 0  // optional
        },
    ],
    onload: function(report) {
        // Add a button to download PDF
        report.page.add_inner_button(__("Download PDF"), function() {
            const filters = report.get_values();
            frappe.call({
                method: "tnc_v2_360ithub.tnc_v2.report."
                      + "teachers_timesheet_report.teachers_timesheet_report.download_pdf",
                args: { filters: filters },
                callback: function(r) {
                    if (r.message) {
                        const pdf_url = r.message;
                        window.open(pdf_url, "_blank");
                    }
                }
            });
        });
    },

    // formatter: function(value, row, column, data, default_formatter) {
    //     // Custom formatter for displaying full name in the "teacher_id" column
    //     if (column.fieldname === "teacher_id" && data.teacher_name) {
    //         let link_text = data.teacher_name; // Use the full name (new field: `teacher_name`)
    //         let link_html = `<a class="grey-link" href="/app/teacher/${value}" data-doctype="Teacher">${link_text}</a>`;
    //         return link_html;
    //     }
    //     return default_formatter(value, row, column, data);
    // }
};
