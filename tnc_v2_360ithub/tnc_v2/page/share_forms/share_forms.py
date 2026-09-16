# Copyright (c) 2026, 360ITHub and contributors
import frappe
from frappe.utils import get_url


@frappe.whitelist()
def send_enquiry_link(mobile, message=None):
	"""Send the public enquiry form link to one number from the institute's WhatsApp instance."""
	from frappe import _
	from tnc_v2_360ithub import notifications
	frappe.only_for(("TNC Manager", "TNC Counsellor", "System Manager"))
	digits = "".join(ch for ch in (mobile or "") if ch.isdigit())
	if len(digits) < 10:
		frappe.throw(_("Please enter a valid 10-digit mobile number."))
	to = digits[-10:]
	from tnc_v2_360ithub.admissions.invites import link as invite_link
	link = invite_link(to)
	msg = (message or "").strip() or _("Namaste! Thank you for your interest in Team Nursing Classes. Please fill this short form and our counsellor will call you.")
	if link not in msg:
		msg = msg + "\n\n" + link
	result = notifications.send_whatsapp_to_mobile(to, msg, ref_doctype="Web Form", ref_name="enquiry")
	ok = bool(result.get("status")) if isinstance(result, dict) else bool(result)
	reason = (result.get("msg") or result.get("message") or result.get("error")) if isinstance(result, dict) else None
	return {"status": "Sent" if ok else "Failed", "reason": reason, "mobile": to, "message": msg, "link": link}


@frappe.whitelist()
def instance_state():
	from tnc_v2_360ithub.tnc_v2.doctype.student_enquiry.student_enquiry import whatsapp_instance_state
	return whatsapp_instance_state()
