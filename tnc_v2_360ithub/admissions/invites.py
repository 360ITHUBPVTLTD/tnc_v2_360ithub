"""Personal enquiry-form links.

When a counsellor saves a new Student Enquiry, the student gets a WhatsApp with a personal
link to the public enquiry form (student_enquiry._send_enquiry_link; "Send Enquiry Form"
resends it). The link carries the mobile and a signature, so the form is locked to that
number and can be submitted once. The submitted form fills the enquiry the counsellor saved
(submit_personal_form); it only creates a new enquiry when none exists for that number.
"""

import hashlib, hmac

import frappe
from frappe import _


def _key():
	return (frappe.local.conf.get("encryption_key") or frappe.local.conf.get("secret") or frappe.local.site).encode()


def site_url():
	"""Base address for links we send out. Nothing is fixed here: the address the staff member's
	browser used to reach the server wins, whatever the site's domain is today or later, so a stale
	host_name in the site config can never leak a wrong address or a port into a WhatsApp message.
	Bare IP addresses are not used because WhatsApp does not make them clickable; then, and outside
	a request (scheduled jobs), Frappe's configured host_name applies."""
	import re
	req = getattr(frappe.local, "request", None)
	if req is not None:
		proto = (req.headers.get("X-Forwarded-Proto") or req.scheme or "http").split(",")[0].strip()
		host = (req.headers.get("X-Forwarded-Host") or req.host or "").split(",")[0].strip()
		# WhatsApp does not make bare IP addresses clickable; on the office LAN keep the configured
		# host name (the nip.io address) and use the browser's host only when it is a real domain
		if host and not re.match(r"^(\d{1,3}\.){3}\d{1,3}(:\d+)?$", host) and not host.startswith("localhost"):
			return f"{proto}://{host}"
	return frappe.utils.get_url()


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
	return f"{site_url()}/enquiry/new?m={m}&t={sign(m)}"


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


FORM_FIELDS = ("student_name", "email", "gender", "batch_interested", "city", "college_name", "passing_year", "source", "referrer_name", "referrer_teacher_name", "notes")


def open_enquiry_for(mobile):
	"""The newest open enquiry a counsellor saved for this mobile that no personal link has filled yet."""
	m = digits10(mobile)
	for row in frappe.get_all("Student Enquiry", filters={"status": ["not in", ["Converted", "Lost"]], "mobile": ["like", f"%{m}"]},
			fields=["name", "mobile", "invite_token"], order_by="creation desc"):
		if digits10(row.mobile) == m and not row.invite_token:
			return row.name
	return None


@frappe.whitelist(allow_guest=True)
def submit_personal_form(m, t, values=None):
	"""Public enquiry form, submitted through a personal link: fill the enquiry the counsellor
	already saved for this number; create one only when there is none. The link is then used."""
	from frappe.utils import now_datetime
	state = enquiry_invite_state(m, t)
	if not state.get("valid"):
		frappe.throw(_("This link is not valid. Please call the institute for your link."), frappe.PermissionError)
	if state.get("closed"):
		return {"closed": state["closed"]}
	values = frappe.parse_json(values or {}) or {}
	data = {k: values.get(k) for k in FORM_FIELDS if values.get(k) not in (None, "")}
	name = open_enquiry_for(m)
	if name:
		enq = frappe.get_doc("Student Enquiry", name)
		enq.update(data)
		enq.invite_token = t
		enq.enquiry_form_filled_on = now_datetime()
		enq.save(ignore_permissions=True)
		enq.add_comment("Info", _("Enquiry form filled by the student through the personal link"))
		return {"ok": True, "name": enq.name, "updated": True}
	doc = frappe.get_doc({"doctype": "Student Enquiry", "mobile": digits10(m), "invite_token": t, "enquiry_form_filled_on": now_datetime(), **data})
	doc.insert(ignore_permissions=True)
	return {"ok": True, "name": doc.name, "updated": False}
