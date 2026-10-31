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

// ---- shared by the Student Enquiry and Student forms ----
// Button colouring: green with a tick when done, amber while waiting, plain when still to do
window.tnc_style = function ($btn, state, title) {
	$btn.removeClass("btn-default");
	if (state === "done") $btn.css({ background: "#dcfce7", color: "#166534", "border-color": "#86efac", "font-weight": "600" });
	else if (state === "partial") $btn.css({ background: "#fef3c7", color: "#92400e", "border-color": "#fcd34d", "font-weight": "600" });
	else $btn.addClass("btn-default");
	if (title) $btn.attr("title", title);
	return $btn;
};

// One "Send WhatsApp" dialog for both personal links (enquiry form, admission form): shows the
// instance that will send, the recipient and the message; falls back to the user's own phone.
window.tnc_link_button = function (frm, o) {
	const enquiry = o.enquiry || frm.doc.name;
	const $btn = frm.add_custom_button(o.label, () => {
		frappe.call({ method: o.preview, args: { enquiry }, freeze: true, freeze_message: __("Checking WhatsApp instance...") }).then((rr) => {
			const p = rr.message || {}; const i = p.instance || {};
			const pill = (ok, on, off) => `<span class="indicator-pill ${ok ? "green" : "red"} no-indicator-dot">${ok ? on : off}</span>`;
			const card = `<div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px 14px;margin-bottom:8px">
				<div style="font-weight:600;margin-bottom:6px">${frappe.utils.escape_html(i.label || i.name || __("Default Instance"))}</div>
				<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;font-size:13px">
					${pill(i.connected, __("Connected"), __("Not connected"))} ${pill(i.active, __("Active"), __("Inactive"))}
					<span>${__("Credits")}: <b>${i.credits || 0}</b></span>${i.number ? `<span>${__("Number")}: <b>${frappe.utils.escape_html(i.number)}</b></span>` : ""}
				</div>
				${i.ok ? "" : `<div class="text-danger small" style="margin-top:6px">${frappe.utils.escape_html(i.msg || __("Cannot send from the institute number right now."))}</div>`}
			</div>`;
			const wa = (n) => `https://wa.me/${n.length === 10 ? "91" + n : n}?text=`;
			const d = new frappe.ui.Dialog({
				title: o.label,
				fields: [
					{ fieldtype: "HTML", fieldname: "card", options: card },
					{ fieldtype: "Data", fieldname: "mobile", label: __("Recipient Mobile Number (10 digits)"), reqd: 1, default: p.mobile },
					{ fieldtype: "Small Text", fieldname: "message", label: __("Message"), default: p.message, description: o.hint },
					{ fieldtype: "HTML", fieldname: "alt", options: `<div class="small text-muted" style="margin-top:4px">${__("Or send it from your own phone:")} <a class="btn btn-xs btn-success alt-wa" target="_blank">💬 WhatsApp</a> <a class="btn btn-xs btn-default alt-cp">${__("Copy link")}</a></div>` },
				],
				primary_action_label: __("Confirm and Send"),
				primary_action(v) {
					const digits = (v.mobile || "").replace(/\D/g, "");
					if (digits.length < 10) { frappe.msgprint(__("Please enter a valid 10-digit mobile number.")); return; }
					frappe.call({ method: o.send, args: { enquiry, mobile: digits, message: v.message }, freeze: true, freeze_message: __("Sending...") })
					.then((r2) => {
						const x = r2.message || {};
						if (x.status === "Sent") { d.hide(); frappe.show_alert({ message: __("Sent on WhatsApp to {0}", [x.mobile]), indicator: "green" }, 6); frm.reload_doc(); }
						else { frm.reload_doc(); frappe.msgprint({ title: __("Not sent"), indicator: "red", message: `${frappe.utils.escape_html(x.reason || x.status)}<br><a class="btn btn-sm btn-success" target="_blank" href="${wa(x.mobile || digits)}${encodeURIComponent(x.message || x.link)}">💬 ${__("Send from my phone")}</a>` }); }
					});
				},
			});
			d.show();
			d.$wrapper.find(".alt-wa").attr("href", wa(p.mobile || "") + encodeURIComponent((p.message || "") + "\n\n" + (p.link || "")));
			d.$wrapper.find(".alt-cp").on("click", () => { frappe.utils.copy_to_clipboard(p.link || ""); });
			if (!i.ok) d.get_primary_btn().prop("disabled", true).attr("title", i.msg || "");
		});
	}, o.group);
	if (o.state) tnc_style($btn, o.state, o.title);
};
