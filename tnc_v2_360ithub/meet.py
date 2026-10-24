"""Google Meet attendance for online batches.

One-time: a manager clicks Connect in TNC Settings, Google shows the Allow page for the TNC
Workspace account, and the refresh token is kept on TNC Settings. From then on `sync` (every 15
minutes) reads, for every online class that has ended, who was in the batch's Meet and for how
long, from the Workspace audit log (Admin SDK Reports API, Meet `call_ended` events: one event per
participant session with the participant's email, start and duration). Each session becomes an
IN and an OUT punch in Student Punch Log, device "MEET:<code>", and the ordinary attendance engine
marks the day: time in the meeting against the "Present From" threshold.

Students are matched on Student.meet_email. Emails nobody owns are kept on the Meet Class Sync
record so the office can fix the student's email and re-run.
"""
import json
import re
from datetime import datetime, timedelta, timezone

import frappe
import requests
from frappe import _
from frappe.utils import add_days, cint, get_datetime, get_url, getdate, now_datetime, nowdate

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
REPORTS_URL = "https://admin.googleapis.com/admin/reports/v1/activity/users/all/applications/meet"
SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/admin.reports.audit.readonly"]
MANAGERS = ("System Manager", "TNC Super Admin", "TNC Manager")
IST = timezone(timedelta(hours=5, minutes=30))


def _settings():
	return frappe.get_cached_doc("TNC Settings")


def redirect_uri():
	"""Where Google sends the browser back: the address this page was opened with (live:
	https://tnc.360ithub.com; local test: http://localhost:8000), as registered on the OAuth client."""
	if getattr(frappe.local, "request", None):
		host = frappe.request.host
		# behind the live reverse proxy the request arrives as http; Google only accepts the https address
		scheme = "http" if host.split(":")[0] in ("localhost", "127.0.0.1") else "https"
		base = f"{scheme}://{host}"
	else:
		base = get_url().rstrip("/")
	return base + "/api/method/tnc_v2_360ithub.meet.oauth_callback"


def meeting_code(link):
	"""'https://meet.google.com/abc-defg-hij' -> 'abcdefghij' (the audit log's meeting_code)."""
	m = re.search(r"([a-z]{3})-?([a-z]{4})-?([a-z]{3})", (link or "").strip().lower())
	return "".join(m.groups()) if m else ""


# ---------- OAuth ----------

@frappe.whitelist()
def connect_url():
	"""The Google Allow page for the TNC account. Manager only; the state ties the callback to this user."""
	frappe.only_for(MANAGERS)
	s = _settings()
	if not s.meet_client_id or not s.get_password("meet_client_secret", raise_exception=False):
		frappe.throw(_("Fill Client ID and Client Secret first, then save."))
	state = frappe.generate_hash(length=24)
	frappe.cache().set_value(f"meet_oauth_state:{state}", frappe.session.user, expires_in_sec=600)
	from urllib.parse import urlencode
	return AUTH_URL + "?" + urlencode({
		"client_id": s.meet_client_id, "redirect_uri": redirect_uri(), "response_type": "code", "scope": " ".join(SCOPES),
		"access_type": "offline", "prompt": "consent", "include_granted_scopes": "true", "state": state})


@frappe.whitelist(allow_guest=True)
def oauth_callback(code=None, state=None, error=None, **kwargs):
	"""Google sends the browser here after Allow. Swap the code for a refresh token and keep it."""
	user = frappe.cache().get_value(f"meet_oauth_state:{state}") if state else None
	if error or not code or not user:
		return _page(_("Google Meet not connected"), _("Google said: {0}").format(error or _("missing code or expired link")) + " " + _("Open TNC Settings and click Connect again."))
	frappe.cache().delete_value(f"meet_oauth_state:{state}")
	s = frappe.get_doc("TNC Settings")
	r = requests.post(TOKEN_URL, data={"code": code, "client_id": s.meet_client_id, "client_secret": s.get_password("meet_client_secret"),
		"redirect_uri": redirect_uri(), "grant_type": "authorization_code"}, timeout=30)
	tok = r.json()
	if r.status_code != 200 or not tok.get("refresh_token"):
		frappe.log_error(title="Meet OAuth token exchange failed", message=r.text[:2000])
		return _page(_("Google Meet not connected"), _("Token exchange failed: {0}").format(tok.get("error_description") or tok.get("error") or r.status_code))
	email = ""
	try:
		email = requests.get(USERINFO_URL, headers={"Authorization": f"Bearer {tok['access_token']}"}, timeout=30).json().get("email") or ""
	except Exception:
		pass
	s.meet_refresh_token = tok["refresh_token"]
	s.meet_account = email
	s.meet_connected_on = now_datetime()
	s.meet_last_error = None
	s.flags.ignore_permissions = True
	s.save()
	frappe.cache().set_value("meet_access_token", tok["access_token"], expires_in_sec=max(60, cint(tok.get("expires_in", 3600)) - 120))
	frappe.db.commit()
	return _page(_("Google Meet connected"), _("Connected as {0}. You can close this tab.").format(email or _("the TNC account")))


def _page(title, msg):
	frappe.respond_as_web_page(title, f"<p style='font-size:16px'>{frappe.utils.escape_html(msg)}</p>", indicator_color="green" if "connected" in title.lower() and "not" not in title.lower() else "red")


def access_token():
	tok = frappe.cache().get_value("meet_access_token")
	if tok:
		return tok
	s = _settings()
	refresh = s.get_password("meet_refresh_token", raise_exception=False)
	if not refresh:
		frappe.throw(_("Google Meet is not connected. Open TNC Settings and click Connect."))
	r = requests.post(TOKEN_URL, data={"client_id": s.meet_client_id, "client_secret": s.get_password("meet_client_secret"),
		"refresh_token": refresh, "grant_type": "refresh_token"}, timeout=30)
	tok = r.json()
	if r.status_code != 200 or not tok.get("access_token"):
		frappe.throw(_("Google refused to refresh the Meet connection ({0}). Open TNC Settings and click Connect again.").format(tok.get("error_description") or tok.get("error") or r.status_code))
	frappe.cache().set_value("meet_access_token", tok["access_token"], expires_in_sec=max(60, cint(tok.get("expires_in", 3600)) - 120))
	return tok["access_token"]


# ---------- audit log ----------

def _rfc3339(dt):
	"""Site time (IST) -> RFC 3339 UTC, as the Reports API wants."""
	return get_datetime(dt).replace(tzinfo=IST).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _local(ts):
	"""Epoch seconds -> naive site time (IST)."""
	return datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(IST).replace(tzinfo=None)


def meet_sessions(code, start_dt, end_dt):
	"""Participant sessions of one meeting code that ended between start and end (site time):
	[{email, name, start, end, minutes, device}] in site time. Anonymous (guest) participants
	have no email, only the name they typed."""
	out, token = [], None
	headers = {"Authorization": f"Bearer {access_token()}"}
	while True:
		params = {"eventName": "call_ended", "startTime": _rfc3339(start_dt), "endTime": _rfc3339(end_dt), "maxResults": 1000,
			"filters": f"meeting_code=={code.upper()}"}
		if token:
			params["pageToken"] = token
		r = requests.get(REPORTS_URL, headers=headers, params=params, timeout=60)
		if r.status_code != 200:
			frappe.throw(_("Google audit log error {0}: {1}").format(r.status_code, r.text[:300]))
		data = r.json()
		for item in data.get("items", []):
			for ev in item.get("events", []):
				p = {x["name"]: (x.get("value") or x.get("intValue") or x.get("boolValue")) for x in ev.get("parameters", [])}
				if not p.get("start_timestamp_seconds"):
					continue
				start = _local(p["start_timestamp_seconds"])
				secs = cint(p.get("duration_seconds"))
				out.append({"email": (p.get("identifier") or "").strip().lower(), "name": p.get("display_name") or "", "device": p.get("device_type") or "",
					"start": start, "end": start + timedelta(seconds=secs), "minutes": secs // 60})
		token = data.get("nextPageToken")
		if not token:
			break
	return out


# ---------- sync ----------

def online_classes(date):
	"""Online batches with a Meet link and class windows on the date."""
	from tnc_v2_360ithub.attendance.daily import batches_with_class
	out = []
	for b in batches_with_class(date):
		if b.get("mode") != "Online":
			continue
		link = frappe.db.get_value("Student Batch", b.name, "meet_link")
		code = meeting_code(link)
		if code:
			b.meeting_code = code
			out.append(b)
	return out


def _write_punches(student, sessions, code):
	"""One IN and one OUT per session, skipping ones already there (same student, same second)."""
	made = 0
	for ses in sessions:
		for when, d in ((ses["start"], "IN"), (ses["end"], "OUT")):
			if frappe.db.exists("Student Punch Log", {"student": student, "punch_time": when}):
				continue
			frappe.get_doc({"doctype": "Student Punch Log", "student": student, "biometric_id": frappe.db.get_value("Student", student, "biometric_id") or "",
				"punch_time": when, "direction": d, "device_id": f"MEET:{code}", "device_name": _("Google Meet · {0}").format(ses.get("device") or "")}).insert(ignore_permissions=True)
			made += 1
	return made


def sync_class(batch, date, window, code, now=None):
	"""Pull the sessions of one class window and turn them into punches. Returns the Meet Class Sync name."""
	now = now or now_datetime()
	start = get_datetime(f"{date} {window.from_time}") - timedelta(minutes=30)
	end = min(get_datetime(f"{date} {window.to_time}") + timedelta(hours=2), now)
	name = frappe.db.get_value("Meet Class Sync", {"timesheet_row": window.timesheet_row})
	doc = frappe.get_doc("Meet Class Sync", name) if name else frappe.get_doc({"doctype": "Meet Class Sync", "batch": batch, "date": date, "timesheet": window.timesheet,
		"timesheet_row": window.timesheet_row, "subject": window.subject, "from_time": window.from_time, "to_time": window.to_time, "meeting_code": code})
	try:
		sessions = meet_sessions(code, start, end)
	except Exception as ex:
		doc.update({"status": "Error", "error": str(ex)[:1000], "synced_on": now})
		doc.flags.ignore_permissions = True
		doc.save()
		return doc.name
	host = (_settings().meet_account or "").strip().lower()
	teacher_emails = {e.lower() for e in frappe.get_all("Teacher", filters={"meet_email": ["!=", ""]}, pluck="meet_email") if e}
	by_email = {}
	for s in sessions:
		if s["email"] and (s["email"] == host or s["email"] in teacher_emails):
			continue  # the TNC account and teachers are hosts, not students
		by_email.setdefault(s["email"] or f"guest:{s['name']}", []).append(s)
	students = {}
	for e in by_email:
		if e.startswith("guest:"):
			continue
		st = frappe.db.get_value("Student", {"meet_email": e}, "name")
		if st:
			students[e] = st
	matched, unmatched, punches = 0, [], 0
	for e, ses in by_email.items():
		if e in students:
			matched += 1
			punches += _write_punches(students[e], ses, code)
		else:
			unmatched.append({"email": "" if e.startswith("guest:") else e, "name": ses[0]["name"], "minutes": sum(x["minutes"] for x in ses)})
	doc.update({"status": "Synced" if sessions else "No data", "sessions": len(sessions), "participants": len(by_email), "matched": matched,
		"punches": punches, "unmatched": json.dumps(unmatched, indent=1) if unmatched else None, "error": None, "synced_on": now})
	doc.flags.ignore_permissions = True
	doc.save()
	return doc.name


def sync(date=None, lookback_days=2):
	"""Scheduled every 15 minutes. Every online class that ended at least 10 minutes ago in the last
	`lookback_days` days is (re)pulled: the audit log can lag, and a re-pull only adds what is new."""
	s = _settings()
	if not s.get_password("meet_refresh_token", raise_exception=False):
		return {"skipped": "not connected"}
	from tnc_v2_360ithub.attendance.daily import build_day
	now = now_datetime()
	dates = [getdate(date)] if date else [getdate(add_days(nowdate(), -i)) for i in range(lookback_days + 1)]
	done, errors = [], []
	for d in dates:
		for b in online_classes(d):
			touched = False
			for w in b.windows:
				if get_datetime(f"{d} {w.to_time}") + timedelta(minutes=10) > now:
					continue
				try:
					done.append(sync_class(b.name, d, w, b.meeting_code, now))
					touched = True
				except Exception as ex:
					errors.append(f"{b.name} {d} {w.subject}: {ex}")
					frappe.log_error(title="Meet sync failed", message=frappe.get_traceback())
			if touched:
				build_day(d, batch=b.name, notify=False)
	frappe.db.set_single_value("TNC Settings", {"meet_last_sync": now, "meet_last_error": "\n".join(errors)[:1000] or None})
	frappe.db.commit()
	return {"synced": done, "errors": errors}


@frappe.whitelist()
def test_connection(days=7):
	"""Manager check from TNC Settings: can we read the audit log, and how many Meet sessions were there lately?"""
	frappe.only_for(MANAGERS)
	start, end = get_datetime(add_days(nowdate(), -cint(days))), now_datetime()
	headers = {"Authorization": f"Bearer {access_token()}"}
	r = requests.get(REPORTS_URL, headers=headers, params={"eventName": "call_ended", "startTime": _rfc3339(start), "endTime": _rfc3339(end), "maxResults": 1000}, timeout=60)
	if r.status_code != 200:
		frappe.throw(_("Google audit log error {0}: {1}").format(r.status_code, r.text[:300]))
	items = r.json().get("items", [])
	codes = {}
	for item in items:
		for ev in item.get("events", []):
			p = {x["name"]: (x.get("value") or x.get("intValue")) for x in ev.get("parameters", [])}
			if p.get("meeting_code"):
				codes[p["meeting_code"]] = codes.get(p["meeting_code"], 0) + 1
	return {"account": _settings().meet_account, "sessions": sum(codes.values()), "meetings": codes}


@frappe.whitelist()
def sync_now(date=None):
	frappe.only_for(MANAGERS)
	return sync(date)
