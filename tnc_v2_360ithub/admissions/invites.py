"""Personal enquiry-form links.

Share Forms can WhatsApp the public enquiry form to one number. That link carries the
mobile and a signature, so the form is locked to that number and can be submitted once.
The plain link and the QR code stay open for flyers, Instagram and the notice board.
"""

import hashlib, hmac

import frappe
from frappe import _


def _key():
	return (frappe.local.conf.get("encryption_key") or frappe.local.conf.get("secret") or frappe.local.site).encode()


def digits10(mobile):
	return "".join(ch for ch in (mobile or "") if ch.isdigit())[-10:]


LINK_HOURS = 48  # a personal enquiry link works for this long after it is sent


def _sig(mobile, ts):
	return hmac.new(_key(), f"{digits10(mobile)}|{ts}".encode(), hashlib.sha256).hexdigest()[:20]


def sign(mobile, ts=None):
	"""Token = issue time + signature over (mobile, time)."""
	import time
	ts = ts or int(time.time())
	return f"{ts}.{_sig(mobile, ts)}"


def parse(token):
	try:
		ts, sig = (token or "").split(".", 1)
		return int(ts), sig
	except ValueError:
		return None, None


def valid(mobile, token):
	ts, sig = parse(token)
	return bool(mobile and ts) and hmac.compare_digest(_sig(mobile, ts), sig or "")


def expired(token):
	import time
	ts, _s = parse(token)
	return not ts or time.time() - ts > LINK_HOURS * 3600


def link(mobile):
	m = digits10(mobile)
	return f"{frappe.utils.get_url()}/enquiry/new?m={m}&t={sign(m)}"


def already_used(token):
	return frappe.db.exists("Student Enquiry", {"invite_token": token})


@frappe.whitelist(allow_guest=True)
def enquiry_invite_state(m, t):
	"""Public form: is this personal link valid, and is it still open?"""
	if not valid(m, t):
		return {"valid": False}
	if expired(t):
		return {"valid": True, "closed": _("This link has expired. Please ask the institute for a new link.")}
	if already_used(t):
		return {"valid": True, "closed": _("This enquiry link has already been used. If you want to enquire again, please call the institute.")}
	return {"valid": True, "mobile": digits10(m)}


def guard(doc):
	"""Student Enquiry validate: a form submitted through a personal link must carry
	that link's mobile, and each link creates one enquiry."""
	if not doc.is_new():
		return
	if not doc.invite_token:
		if frappe.session.user == "Guest":
			frappe.throw(_("Please use the personal enquiry link sent to you by the institute."), frappe.PermissionError)
		return
	if not valid(doc.mobile, doc.invite_token):
		frappe.throw(_("This enquiry link was sent to a different mobile number. Please use the number the link was sent to, or ask the institute for your own link."), frappe.PermissionError)
	if expired(doc.invite_token):
		frappe.throw(_("This link has expired. Please ask the institute for a new link."), frappe.PermissionError)
	if already_used(doc.invite_token):
		frappe.throw(_("This enquiry link has already been used."), frappe.DuplicateEntryError)
	# the counsellor who sent this link owns the enquiry
	if not doc.counsellor or doc.counsellor == "Guest":
		sender = frappe.db.get_value("WhatsApp Message Log", {"reference_doctype": "Web Form", "reference_name": "enquiry", "mobile": digits10(doc.mobile)}, "owner", order_by="creation desc")
		if sender and sender != "Guest" and frappe.db.exists("User", sender):
			doc.counsellor = sender


@frappe.whitelist(allow_guest=True)
def web_form_sources():
	"""Sources a student may pick on the public enquiry form."""
	return frappe.get_all("Enquiry Source", filters={"show_on_web_form": 1, "disabled": 0}, pluck="name", order_by="idx asc, name asc")
