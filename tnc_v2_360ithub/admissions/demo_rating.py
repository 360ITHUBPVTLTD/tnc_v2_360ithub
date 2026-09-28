"""Demo class rating.

The student gets a personal WhatsApp link and gives two ratings out of 5, each with an optional
comment: one for the demo class and one for the counsellor who handled them. The page is
/demo-feedback and both land on the same Demo Class. Links are per demo, single use, and expire
after 7 days. Nothing is rated from the office side.
"""

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, get_url, now_datetime

LINK_DAYS = 7


def _link(demo):
	if not demo.rating_token:
		demo.db_set({"rating_token": frappe.generate_hash(length=20), "rating_sent_on": now_datetime()}, update_modified=False)
	from tnc_v2_360ithub.admissions.invites import site_url
	return f"{site_url()}/demo-feedback?d={demo.name}&t={demo.rating_token}"


def _state(demo, t):
	"""None when the link is good, else a message for the page."""
	if not demo or not t or demo.rating_token != t:
		return _("This link is not valid. Please call the institute.")
	if demo.rated_on:
		return _("Thank you, your rating for this demo class is already recorded.")
	if demo.rating_sent_on and (now_datetime() - get_datetime(demo.rating_sent_on)).days >= LINK_DAYS:
		return _("This link has expired. Please call the institute.")
	return None


@frappe.whitelist()
def send_rating_link(demo, mobile=None):
	"""WhatsApp the student a personal link to rate this demo. Returns Sent / Failed with reason."""
	from tnc_v2_360ithub import notifications
	doc = frappe.get_doc("Demo Class", demo)
	doc.check_permission("write")
	if doc.result != "Attended":
		frappe.throw(_("The rating link can be sent only after the demo is marked Attended."))
	digits = "".join(ch for ch in (mobile or doc.mobile or "") if ch.isdigit())
	if len(digits) < 10:
		frappe.throw(_("Please enter a valid 10-digit mobile number."))
	to = digits[-10:]
	link = _link(doc)
	msg = _("Namaste {0}, thank you for attending the demo class at Team Nursing Classes. Please take 30 seconds to rate the demo class and your counsellor (1 to 5 stars each):").format(doc.student_name or "") + "\n\n" + link
	result = notifications.send_whatsapp_to_mobile(to, msg, ref_doctype="Demo Class", ref_name=doc.name)
	ok = bool(result.get("status")) if isinstance(result, dict) else bool(result)
	reason = (result.get("msg") or result.get("message") or result.get("error")) if isinstance(result, dict) else None
	if ok:
		doc.add_comment("Info", _("Rating link sent to {0}").format(to))
	return {"status": "Sent" if ok else "Failed", "reason": reason, "link": link, "message": msg, "mobile": to}


@frappe.whitelist(allow_guest=True)
def page_state(d, t):
	demo = frappe.db.get_value("Demo Class", d, ["name", "student_name", "demo_date", "batch", "enquiry", "rating_token", "rated_on", "rating_sent_on"], as_dict=True)
	closed = _state(demo, t)
	if closed:
		return {"closed": closed}
	return {"student_name": demo.student_name, "demo_date": frappe.format_value(demo.demo_date, {"fieldtype": "Date"}), "batch": demo.batch, "counsellor_name": _counsellor_name(demo.enquiry)}


def _counsellor_name(enquiry):
	"""First name of the counsellor on the enquiry, for the page; empty when nobody is set."""
	user = frappe.db.get_value("Student Enquiry", enquiry, "counsellor") if enquiry else None
	full = frappe.db.get_value("User", user, "full_name") if user else None
	return (full or "").split(" ")[0]


@frappe.whitelist(allow_guest=True)
def submit(d, t, rating, feedback=None, counsellor_rating=None, counsellor_feedback=None):
	"""Both ratings are required; the two comments are optional."""
	frappe.rate_limit = None
	demo = frappe.get_doc("Demo Class", d) if frappe.db.exists("Demo Class", d) else None
	closed = _state(demo, t)
	if closed:
		frappe.throw(closed, frappe.PermissionError)
	stars = int(rating or 0)
	cstars = int(counsellor_rating or 0)
	if stars < 1 or stars > 5:
		frappe.throw(_("Please choose 1 to 5 stars for the demo class."))
	if cstars < 1 or cstars > 5:
		frappe.throw(_("Please choose 1 to 5 stars for the counsellor."))
	fb = (feedback or "").strip()[:1000]
	cfb = (counsellor_feedback or "").strip()[:1000]
	demo.db_set({"student_rating": stars / 5.0, "student_feedback": fb, "student_counsellor_rating": cstars / 5.0, "student_counsellor_feedback": cfb, "rated_on": now_datetime()}, update_modified=False)
	esc = frappe.utils.escape_html
	demo.add_comment("Info", _("Student rated the demo {0}/5").format(stars) + (f": {esc(fb[:200])}" if fb else "") + "<br>" + _("Student rated the counsellor {0}/5").format(cstars) + (f": {esc(cfb[:200])}" if cfb else ""))
	if demo.enquiry:
		frappe.get_doc("Student Enquiry", demo.enquiry).add_comment("Info", _("Demo {0}: student rated the demo {1}/5 and the counsellor {2}/5").format(demo.name, stars, cstars))
	return {"ok": True}
