# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt

"""Outbound notification service.

Every message this app sends to a person goes through here: in-app bell
notifications, FCM push, and WhatsApp. This is deliberate difference #2 in the
parity checklist: v1 called the WhatsApp provider from several places and only
the Error Log knew what happened. Here every WhatsApp and FCM attempt writes a
WhatsApp Message Log row first and records the outcome on it.

Providers are optional apps on the bench. When one is missing or disabled in
TNC Settings, the send is recorded as Skipped and nothing raises.

Behaviour carried over from v1 (tnc_frappe_custom_app.custom_task):
- The WhatsApp number comes from User.phone, falling back to User.mobile_no.
  Employee.cell_number is deliberately not consulted.
- Disabled User accounts are never messaged.
- FCM goes to the Employee linked to the user via Employee.custom_fcm_token.
"""

import frappe
from frappe.utils import now_datetime

WEBTOOLEX_SEND = (
	"webtoolex_whatsapp.webtoolex_whatsapp.doctype.whatsapp_instance.whatsapp_instance.send_custom_whatsapp_message"
)
WEBTOOLEX_VALIDATE = (
	"webtoolex_whatsapp.webtoolex_whatsapp.doctype.whatsapp_instance.whatsapp_instance.validate_whatsapp_instance"
)
FCM_SEND = "fcm_360ithub.fcm_functions.send_fcm_notification"


def settings():
	return frappe.get_cached_doc("TNC Settings")


def app_installed(app_name):
	return app_name in frappe.get_installed_apps()


# ---------------------------------------------------------------------------
# number / recipient resolution
# ---------------------------------------------------------------------------


def get_whatsapp_number_for_user(user_id):
	"""User.phone preferred, User.mobile_no fallback, None when neither is set."""
	if not user_id:
		return None
	row = frappe.db.get_value("User", user_id, ["phone", "mobile_no"], as_dict=True)
	if not row:
		return None
	return (row.phone or "").strip() or (row.mobile_no or "").strip() or None


def is_enabled_user(user_id):
	return bool(user_id and frappe.db.get_value("User", user_id, "enabled"))


# ---------------------------------------------------------------------------
# log
# ---------------------------------------------------------------------------


def _log(channel, status, user=None, mobile=None, message=None, ref_doctype=None, ref_name=None, provider=None, response=None, error=None):
	try:
		doc = frappe.get_doc(
			{
				"doctype": "WhatsApp Message Log",
				"channel": channel,
				"status": status,
				"provider": provider,
				"recipient_user": user,
				"mobile": mobile,
				"sent_on": now_datetime() if status == "Sent" else None,
				"reference_doctype": ref_doctype,
				"reference_name": ref_name,
				"message": message,
				"response": (str(response)[:2000] if response is not None else None),
				"error": (str(error)[:2000] if error else None),
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name
	except Exception:
		# The log must never break the business action that triggered it.
		frappe.log_error(title="WhatsApp Message Log write failed", message=frappe.get_traceback())
		return None


# ---------------------------------------------------------------------------
# WhatsApp
# ---------------------------------------------------------------------------


def whatsapp_available():
	"""(ok, reason). ok is True only when a provider is configured, installed and usable."""
	s = settings()
	if s.whatsapp_provider != "Webtoolex":
		return False, "WhatsApp provider is Disabled in TNC Settings"
	if not app_installed("webtoolex_whatsapp"):
		return False, "webtoolex_whatsapp app is not installed on this bench"
	try:
		check = frappe.get_attr(WEBTOOLEX_VALIDATE)(s.whatsapp_instance or None)
	except Exception as e:
		return False, f"validate_whatsapp_instance raised: {e}"
	if isinstance(check, dict) and not check.get("status"):
		return False, f"WhatsApp instance not usable: {check.get('msg')}"
	return True, ""


def send_whatsapp(user, message, ref_doctype=None, ref_name=None):
	"""Send one WhatsApp message to a User. Always writes a log row.

	Returns the log status: "Sent", "Failed" or "Skipped".
	"""
	if not is_enabled_user(user):
		_log("WhatsApp", "Skipped", user=user, message=message, ref_doctype=ref_doctype, ref_name=ref_name, error="User disabled or missing")
		return "Skipped"

	mobile = get_whatsapp_number_for_user(user)
	if not mobile:
		_log("WhatsApp", "Skipped", user=user, message=message, ref_doctype=ref_doctype, ref_name=ref_name, error="No phone / mobile_no on User")
		return "Skipped"

	ok, reason = whatsapp_available()
	if not ok:
		_log("WhatsApp", "Skipped", user=user, mobile=mobile, message=message, ref_doctype=ref_doctype, ref_name=ref_name, error=reason)
		return "Skipped"

	s = settings()
	try:
		resp = frappe.get_attr(WEBTOOLEX_SEND)(mobile, message, s.whatsapp_instance or None)
		sent = bool(resp and (resp.get("status") if isinstance(resp, dict) else True))
		_log(
			"WhatsApp",
			"Sent" if sent else "Failed",
			user=user,
			mobile=mobile,
			message=message,
			ref_doctype=ref_doctype,
			ref_name=ref_name,
			provider="Webtoolex",
			response=resp,
			error=None if sent else "Provider reported failure",
		)
		return "Sent" if sent else "Failed"
	except Exception as e:
		_log("WhatsApp", "Failed", user=user, mobile=mobile, message=message, ref_doctype=ref_doctype, ref_name=ref_name, provider="Webtoolex", error=e)
		return "Failed"


def queue_whatsapp(user, message, ref_doctype=None, ref_name=None):
	"""Enqueue send_whatsapp after the current transaction commits."""
	frappe.enqueue(
		"tnc_v2_360ithub.notifications.send_whatsapp",
		queue="short",
		enqueue_after_commit=True,
		user=user,
		message=message,
		ref_doctype=ref_doctype,
		ref_name=ref_name,
	)


# ---------------------------------------------------------------------------
# FCM push
# ---------------------------------------------------------------------------


def send_fcm(user, title, body, ref_doctype=None, ref_name=None):
	"""Push to the Employee linked to `user`. Always writes a log row."""
	s = settings()
	if not s.fcm_enabled:
		_log("FCM", "Skipped", user=user, message=body, ref_doctype=ref_doctype, ref_name=ref_name, error="FCM disabled in TNC Settings")
		return "Skipped"
	if not app_installed("fcm_360ithub"):
		_log("FCM", "Skipped", user=user, message=body, ref_doctype=ref_doctype, ref_name=ref_name, error="fcm_360ithub app is not installed on this bench")
		return "Skipped"

	emp = frappe.db.get_value("Employee", {"user_id": user}, ["name", "custom_fcm_token"], as_dict=True)
	if not emp:
		_log("FCM", "Skipped", user=user, message=body, ref_doctype=ref_doctype, ref_name=ref_name, error="No Employee linked to user")
		return "Skipped"
	if not emp.custom_fcm_token:
		_log("FCM", "Skipped", user=user, message=body, ref_doctype=ref_doctype, ref_name=ref_name, error=f"Employee {emp.name} has no FCM token")
		return "Skipped"

	try:
		frappe.get_attr(FCM_SEND)(
			token=emp.custom_fcm_token,
			title=title,
			body=body,
			doctype=ref_doctype,
			task_id=ref_name,
			user_doctype="Employee",
			user=user,
			notification_type="Task Notification",
		)
		_log("FCM", "Sent", user=user, message=body, ref_doctype=ref_doctype, ref_name=ref_name, provider="fcm_360ithub")
		return "Sent"
	except Exception as e:
		_log("FCM", "Failed", user=user, message=body, ref_doctype=ref_doctype, ref_name=ref_name, provider="fcm_360ithub", error=e)
		return "Failed"


# ---------------------------------------------------------------------------
# in-app + push, the combination v1 used everywhere
# ---------------------------------------------------------------------------


def notify_users(users, doc, message, title=None):
	"""Bell notification plus FCM push to each user except the acting user."""
	s = settings()
	sender = frappe.session.user
	for user in users:
		if not user or user == sender:
			continue
		if s.in_app_notifications_enabled:
			try:
				frappe.get_doc(
					{
						"doctype": "Notification Log",
						"for_user": user,
						"from_user": sender,
						"subject": message,
						"type": "Alert",
						"document_type": doc.doctype,
						"document_name": doc.name,
						"email_content": message,
					}
				).insert(ignore_permissions=True)
			except Exception:
				frappe.log_error(title="System Notification Error", message=frappe.get_traceback())
		send_fcm(user, title or f"{doc.doctype}: {doc.get('subject') or doc.name}", message, doc.doctype, doc.name)
