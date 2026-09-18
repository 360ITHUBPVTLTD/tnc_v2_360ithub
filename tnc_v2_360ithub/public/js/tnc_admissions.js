// Copyright (c) 2026, 360ITHub and contributors
// shared Receive Payment dialog (used by Student overview and Enrolment form)
frappe.provide("tnc.admissions");
tnc.admissions.receive_payment = function ({ sales_order, amount, label, on_done }) {
	const bank_modes = ["UPI", "Bank Transfer", "Card", "Cheque"];
	const d = new frappe.ui.Dialog({
		title: __("Receive Payment") + (label ? ` · ${label}` : ""),
		fields: [
			{ fieldname: "amount", fieldtype: "Currency", label: __("Amount"), reqd: 1, default: amount, options: "INR",
			  description: __("Prefilled with the pending amount. Enter less for a part payment.") },
			{ fieldname: "mode_of_payment", fieldtype: "Link", label: __("Mode"), options: "Mode of Payment", reqd: 1, default: "Cash",
			  get_query: () => ({ filters: { enabled: 1 } }),
			  onchange() { const m = d.get_value("mode_of_payment"); d.set_df_property("reference_no", "reqd", bank_modes.includes(m) ? 1 : 0); } },
			{ fieldname: "cb", fieldtype: "Column Break" },
			{ fieldname: "posting_date", fieldtype: "Date", label: __("Date"), reqd: 1, default: frappe.datetime.get_today() },
			{ fieldname: "reference_no", fieldtype: "Data", label: __("Reference No"), description: __("UPI / transaction / cheque number") },
			{ fieldname: "sb", fieldtype: "Section Break" },
			{ fieldname: "remarks", fieldtype: "Small Text", label: __("Remarks") },
		],
		primary_action_label: __("Receive"),
		primary_action(values) {
			frappe.call({
				method: "tnc_v2_360ithub.admissions.fees.receive_payment",
				args: { sales_order, ...values },
				freeze: true,
				freeze_message: __("Recording payment..."),
				callback: (r) => {
					d.hide();
					const m = r.message;
					frappe.msgprint({
						title: __("Payment received"),
						indicator: "green",
						message: `<b>${format_currency(values.amount, "INR")}</b> ${__("received by")} ${values.mode_of_payment}.<br>
							${__("Receipt")} <a href="/app/sales-invoice/${encodeURIComponent(m.sales_invoice)}"><b>${m.sales_invoice}</b></a> ·
							${__("Payment")} <a href="/app/payment-entry/${encodeURIComponent(m.payment_entry)}"><b>${m.payment_entry}</b></a><br>
							${__("Pending now")}: <b>${format_currency(m.pending, "INR")}</b>`,
					});
					on_done && on_done(m);
				},
			});
		},
	});
	d.show();
};

// Copyright (c) 2026, 360ITHub and contributors


// Workspace number cards: tint the box with the card's colour (Frappe 15.94, which v1 runs, did this; 15.120 shows plain white)
(function tnc_tint_cards() {
	const tint = () => document.querySelectorAll(".widget.number-widget-box").forEach((box) => {
		const num = box.querySelector(".widget-content .number"); if (!num) return;
		const c = num.style.color || getComputedStyle(num).color; if (!c || box.dataset.tinted === c) return;
		box.dataset.tinted = c; box.style.background = c.replace("rgb(", "rgba(").replace(")", ", 0.08)"); box.style.borderColor = c.replace("rgb(", "rgba(").replace(")", ", 0.25)");
	});
	$(document).on("page-change", () => setTimeout(tint, 400));
	new MutationObserver(() => tint()).observe(document.body, { childList: true, subtree: true });
})();
