// Copyright (c) 2026, 360ITHub and contributors
frappe.pages["share-forms"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Share Forms"), single_column: true });
	const $b = $(`<div class="sf" style="max-width:820px">
	<style>.sf .card{border:1px solid #e5e7eb;border-radius:8px;padding:16px 18px;margin-bottom:16px;background:#fff}.sf h5{margin:0 0 6px;font-size:14px}.sf .lnk{font-family:monospace;background:#f8fafc;border:1px solid #e5e7eb;border-radius:6px;padding:8px 10px;display:inline-block;margin:6px 0}.sf .acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}.sf img{border:1px solid #e5e7eb;border-radius:8px;padding:8px;background:#fff}</style>
	<div class="card"><h5>${__("Enquiry form")} · ${__("public, share with everyone")}</h5>
	  <div class="text-muted small">${__("Website button, WhatsApp status, Instagram bio, flyers, notice board.")}</div>
	  <div class="lnk enq"></div><div class="acts enq-acts"></div>
	  <div style="margin-top:12px;display:flex;gap:18px;align-items:flex-start"><img class="qr" width="180" height="180"><div class="small text-muted">${__("QR code for print. Right-click the image to save it, or use Download.")}<br><a class="btn btn-sm btn-default dl" style="margin-top:8px">${__("Download QR (PNG)")}</a></div></div>
	</div>
	<div class="card"><h5>${__("Admission form")} · ${__("personal, send from the enquiry")}</h5>
	  <div class="text-muted small">${__("Do not publish this one. Open the student's enquiry and press Send Admission Form Link, so the form attaches to their enquiry. The plain link below is for the counter tablet only.")}</div>
	  <div class="lnk adm"></div><div class="acts adm-acts"></div>
	</div></div>`).appendTo(page.body);
	frappe.call({ method: "tnc_v2_360ithub.tnc_v2.page.share_forms.share_forms.get_links" }).then((r) => {
		const m = r.message;
		$b.find(".enq").text(m.enquiry); $b.find(".adm").text(m.admission); $b.find(".qr").attr("src", m.qr_png);
		$b.find(".dl").attr({ href: m.qr_png, download: "tnc-enquiry-qr.png" });
		const acts = (link, text) => `<a class="btn btn-sm btn-default cp">${__("Copy link")}</a>
			<a class="btn btn-sm btn-success" target="_blank" href="https://wa.me/?text=${encodeURIComponent(text + " " + link)}">💬 ${__("Share on WhatsApp")}</a>
			<a class="btn btn-sm btn-default" target="_blank" href="${link}">${__("Open")}</a>`;
		$b.find(".enq-acts").html(acts(m.enquiry, __("Team Nursing Classes – enquire here:")));
		$b.find(".adm-acts").html(acts(m.admission, __("TNC admission form:")));
		$b.find(".enq-acts .cp").on("click", () => frappe.utils.copy_to_clipboard(m.enquiry));
		$b.find(".adm-acts .cp").on("click", () => frappe.utils.copy_to_clipboard(m.admission));
	});
};
