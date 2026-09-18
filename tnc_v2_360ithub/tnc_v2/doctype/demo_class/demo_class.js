// Copyright (c) 2026, 360ITHub and contributors
frappe.ui.form.on("Demo Class", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.trigger("demo_fee_buttons");
		if (frm.doc.result !== "Attended") return;
		if (frm.doc.rated_on) {
			frm.dashboard.clear_headline();
			frm.dashboard.set_headline(`<span class="indicator-pill green no-indicator-dot">${__("Student rated {0}/5", [Math.round((frm.doc.student_rating || 0) * 5)])}</span> ${frappe.utils.escape_html(frm.doc.student_feedback || "")}`);
			return;
		}
		frm.add_custom_button(__("Send Rating Link"), () => {
			frappe.prompt([{ fieldname: "mobile", fieldtype: "Data", label: __("Send to mobile"), default: frm.doc.mobile, reqd: 1 }], (v) => {
				frappe.call({ method: "tnc_v2_360ithub.admissions.demo_rating.send_rating_link", args: { demo: frm.doc.name, mobile: v.mobile }, freeze: true, freeze_message: __("Sending...") }).then((r) => {
					const x = r.message || {};
					if (x.status === "Sent") { frappe.show_alert({ message: __("Rating link sent to {0}", [x.mobile]), indicator: "green" }); frm.reload_doc(); }
					else frappe.msgprint({ title: __("Not sent"), indicator: "red", message: `${frappe.utils.escape_html(x.reason || "")}<br><a class="btn btn-sm btn-success" target="_blank" href="https://wa.me/91${x.mobile}?text=${encodeURIComponent(x.message || "")}">💬 ${__("Send from my phone")}</a>` });
				});
			}, __("Ask the student to rate this demo"), __("Send on WhatsApp"));
		}).addClass("btn-success");
		if (frm.doc.rating_sent_on) frm.dashboard.set_headline(`<span class="indicator-pill orange no-indicator-dot">${__("Rating link sent {0}", [frappe.datetime.prettyDate(frm.doc.rating_sent_on)])}</span> ${__("waiting for the student")}`);
	},
	demo_fee_buttons(frm) {
		const P = "tnc_v2_360ithub.admissions.demo_fee.";
		const st = frm.doc.demo_fee_status || "Not Collected";
		if (st === "Not Collected" && frm.doc.result !== "Cancelled") {
			frm.add_custom_button(__("Collect Demo Fee"), () => {
				frappe.db.get_single_value("TNC Settings", "demo_fee_amount").then((v) => {
					frappe.prompt([
						{ fieldname: "amount", fieldtype: "Currency", label: __("Amount"), default: flt(v) || 500, reqd: 1 },
						{ fieldname: "mode_of_payment", fieldtype: "Link", label: __("Mode"), options: "Mode of Payment", default: "Cash", reqd: 1, get_query: () => ({ filters: { enabled: 1 } }) },
						{ fieldname: "reference_no", fieldtype: "Data", label: __("Reference No"), depends_on: "eval:doc.mode_of_payment && doc.mode_of_payment !== 'Cash'" },
					], (val) => {
						frappe.call({ method: P + "collect", args: { demo: frm.doc.name, ...val }, freeze: true, freeze_message: __("Saving receipt...") }).then((r) => {
							frappe.show_alert({ message: __("Demo fee received. Receipt {0}", [r.message.invoice]), indicator: "green" });
							frm.reload_doc();
						});
					}, __("Collect demo fee"), __("Receive"));
				});
			}).addClass("btn-success");
		}
		if (["Paid", "Adjusted", "Refunded"].includes(st)) {
			frm.dashboard.clear_headline();
			const amt = format_currency(frm.doc.demo_fee_amount, "INR");
			const msg = { Paid: __("Demo fee {0} paid on {1}", [amt, frappe.datetime.str_to_user(frm.doc.demo_fee_paid_on)]),
				Adjusted: __("Demo fee {0} adjusted in enrolment {1}", [amt, frm.doc.demo_fee_adjusted_in]),
				Refunded: __("Demo fee {0} refunded on {1}", [amt, frappe.datetime.str_to_user(frm.doc.demo_fee_refunded_on)]) + (frm.doc.demo_fee_refund_payment ? ` · <a href="/app/payment-entry/${frm.doc.demo_fee_refund_payment}">${__("refund payment")}</a> · <a href="/app/sales-invoice/${frm.doc.demo_fee_credit_note}">${__("credit note")}</a>` : "") }[st];
			frm.dashboard.set_headline(`<span class="indicator-pill ${st === "Refunded" ? "gray" : "green"} no-indicator-dot">${st}</span> ${msg}`);
			if (frm.doc.demo_fee_invoice) frm.add_custom_button(__("Print Receipt"), () => window.open(`/printview?doctype=Sales%20Invoice&name=${encodeURIComponent(frm.doc.demo_fee_invoice)}&format=Fee%20Receipt&no_letterhead=0`, "_blank"));
		}
		if (st === "Paid") {
			frm.add_custom_button(__("Refund Demo Fee"), () => {
				frappe.db.get_value("Student Enquiry", frm.doc.enquiry, "status").then((r) => {
					const open_enq = r.message && !["Converted", "Lost"].includes(r.message.status);
					frappe.prompt([
						{ fieldname: "mode_of_payment", fieldtype: "Link", label: __("Refund by"), options: "Mode of Payment", default: "Cash", reqd: 1 },
						{ fieldname: "reference_no", fieldtype: "Data", label: __("Reference No") },
						{ fieldname: "mark_lost", fieldtype: "Check", label: __("Also mark the enquiry Lost"), default: open_enq ? 1 : 0, hidden: open_enq ? 0 : 1 },
						{ fieldname: "lost_reason", fieldtype: "Select", label: __("Reason"), options: "Fee too high\nJoined another institute\nNot interested now\nNo response\nTiming or location\nCourse not suitable\nOther", default: "Not interested now", depends_on: "mark_lost" },
					], (val) => frappe.call({ method: P + "refund", args: { demo: frm.doc.name, ...val }, freeze: true }).then((rr) => {
						frappe.show_alert({ message: rr.message.enquiry_lost ? __("Demo fee refunded, enquiry marked Lost") : __("Demo fee refunded"), indicator: "orange" }); frm.reload_doc();
					}), __("Refund the demo fee to the student?"), __("Refund"));
				});
			});
		}
	},
});
