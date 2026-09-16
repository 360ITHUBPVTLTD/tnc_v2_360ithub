// Copyright (c) 2026, 360ITHub and contributors
frappe.pages["share-forms"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Share Forms"), single_column: true });
	const $b = $(`<div class="sf" style="max-width:820px">
	<style>.sf .card{border:1px solid #e5e7eb;border-radius:8px;padding:16px 18px;margin-bottom:16px;background:#fff}.sf h5{margin:0 0 6px;font-size:14px}.sf .lnk{font-family:monospace;background:#f8fafc;border:1px solid #e5e7eb;border-radius:6px;padding:8px 10px;display:inline-block;margin:6px 0}.sf .acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}</style>
	<div class="card"><h5>${__("Enquiry form")} · ${__("personal, sent to one number")}</h5>
	  <div class="text-muted small">${__("The link is locked to the number you send it to and works once. The student's mobile is already filled; they add name, course and city.")}</div>
	  <div class="send" style="margin-top:14px;padding:12px;border:1px solid #dbeafe;border-radius:8px;background:#f8fbff">
	    <div style="font-weight:600;font-size:13px;margin-bottom:6px">${__("Send to a student by WhatsApp")} <span class="inst small text-muted" style="font-weight:400"></span></div>
	    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center"><input class="form-control mob" style="max-width:220px" placeholder="${__("10-digit mobile")}" maxlength="13"><button class="btn btn-sm btn-success go">💬 ${__("Send enquiry form")}</button></div>
	    <div class="res small" style="margin-top:6px"></div>
	  </div>
	</div>
	<div class="card"><h5>${__("Admission form")} · ${__("sent from the enquiry only")}</h5>
	  <div class="text-muted small">${__("Open the student's enquiry and press the green Send Admission Form button. The link is personal to that enquiry: details are prefilled, the mobile is locked and it works once. There is no open admission link.")}</div>
	</div></div>`).appendTo(page.body);
	const P = "tnc_v2_360ithub.tnc_v2.page.share_forms.share_forms.";
	frappe.call({ method: P + "instance_state" }).then((r) => {
		const i = r.message || {};
		$b.find(".inst").text(i.ok ? `· ${i.label || i.name} · ${i.number || ""} · ${__("{0} credits", [i.credits])}` : `· ${i.msg || __("WhatsApp instance not available")}`);
		if (!i.ok) $b.find(".go").prop("disabled", true).attr("title", i.msg || "");
	});
	$b.find(".go").on("click", () => {
		const digits = ($b.find(".mob").val() || "").replace(/\D/g, "");
		if (digits.length < 10) { frappe.show_alert({ message: __("Enter a 10-digit mobile number"), indicator: "orange" }); return; }
		const $res = $b.find(".res").text(__("Sending..."));
		frappe.call({ method: P + "send_enquiry_link", args: { mobile: digits }, freeze: true }).then((r) => {
			const x = r.message || {};
			if (x.status === "Sent") { $res.html(`<span style="color:#15803d">✔ ${__("Sent to {0}", [x.mobile])}</span>`); $b.find(".mob").val(""); }
			else $res.html(`<span style="color:#b91c1c">${__("Not sent")}: ${frappe.utils.escape_html(x.reason || "")}</span> <a target="_blank" href="https://wa.me/91${x.mobile}?text=${encodeURIComponent(x.message || "")}">${__("Send from my phone")}</a>`);
		}).catch(() => $res.text(""));
	});
};
