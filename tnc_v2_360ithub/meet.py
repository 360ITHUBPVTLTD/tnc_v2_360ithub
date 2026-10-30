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
CAL_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
# reports: who was in a meeting; calendar.events: create the batch meetings with the student guest list
MEET_SPACES_URL = "https://meet.googleapis.com/v2/spaces"
# reports: who was in a meeting; calendar.events: create the batch meetings with the student guest
# list; meetings.space.settings: lock a meeting to invited guests only (TNC Settings "Online class entry")
SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/admin.reports.audit.readonly",
	"https://www.googleapis.com/auth/calendar.events", "https://www.googleapis.com/auth/meetings.space.settings"]
STRICT_ENTRY = "Only registered students can join"
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


def _reports_get(headers, params, tries=3):
	"""GET the audit log; Google's 5xx replies are retried with a short pause before giving up."""
	import time
	for i in range(tries):
		r = requests.get(REPORTS_URL, headers=headers, params=params, timeout=60)
		if r.status_code < 500 or i == tries - 1:
			return r
		time.sleep(2 * (i + 1))
	return r


def meet_sessions(code, start_dt, end_dt):
	"""Participant sessions of one meeting code that ended between start and end (site time):
	[{email, name, start, end, minutes, device}] in site time. Anonymous (guest) participants
	have no email, only the name they typed.
	The meeting-code filter is asked of Google first; when Google keeps failing on it (500 backendError),
	the window is pulled unfiltered and the code is matched here instead."""
	code = code.upper()
	headers = {"Authorization": f"Bearer {access_token()}"}
	base = {"eventName": "call_ended", "startTime": _rfc3339(start_dt), "endTime": _rfc3339(end_dt), "maxResults": 1000}
	for filtered in (True, False):
		out, token = [], None
		while True:
			params = dict(base, filters=f"meeting_code=={code}") if filtered else dict(base)
			if token:
				params["pageToken"] = token
			r = _reports_get(headers, params)
			if r.status_code >= 500 and filtered:
				break  # try once more without the filter
			if r.status_code != 200:
				frappe.throw(_("Google audit log error {0}: {1}").format(r.status_code, r.text[:300]))
			data = r.json()
			for item in data.get("items", []):
				for ev in item.get("events", []):
					p = {x["name"]: (x.get("value") or x.get("intValue") or x.get("boolValue")) for x in ev.get("parameters", [])}
					if not p.get("start_timestamp_seconds") or (p.get("meeting_code") or "").upper() != code:
						continue
					start = _local(p["start_timestamp_seconds"])
					secs = cint(p.get("duration_seconds"))
					out.append({"email": (p.get("identifier") or "").strip().lower(), "name": p.get("display_name") or "", "device": p.get("device_type") or "",
						"start": start, "end": start + timedelta(seconds=secs), "minutes": secs // 60})
			token = data.get("nextPageToken")
			if not token:
				return out
	return out


# ---------- sync ----------

def online_classes(date):
	"""Online batches with a Meet link and class windows on the date."""
	from tnc_v2_360ithub.attendance.daily import batches_with_class
	out = []
	for b in batches_with_class(date):
		if b.get("mode") != "Online":
			continue
		code = code_for(b.name, date)
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


# ---------- batch meetings (Google Calendar) ----------
#
# The system creates the batch's meeting as a Calendar event on the TNC account with the enrolled
# students as guests. Google then lets an invited Gmail into the Meet directly and holds everyone
# else at "ask to join" (Workspace default for invited vs uninvited), so one link can be shared
# with the whole group and still only admit registered students. Each link is kept as a Batch Meet
# Link with the dates it covers; attendance looks up the link that was current on the class day,
# so a batch may keep one link for its whole life or take a fresh one for a day.

DAYS = ("day_mon", "day_tue", "day_wed", "day_thu", "day_fri", "day_sat", "day_sun")
RRULE_DAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")


def code_for(batch, date):
	"""Meeting code of the link that was current for the batch on the date: the newest system link
	whose dates cover it, else whatever is typed on the batch."""
	date = getdate(date)
	rows = frappe.get_all("Batch Meet Link", filters={"batch": batch, "valid_from": ["<=", date]},
		fields=["meeting_code", "valid_to"], order_by="valid_from desc, created_on desc")
	for r in rows:
		if not r.valid_to or getdate(r.valid_to) >= date:
			return r.meeting_code
	return meeting_code(frappe.db.get_value("Student Batch", batch, "meet_link"))


def batch_guests(batch):
	"""Emails Google should let in without asking: students enrolled in the batch (Active / On Hold)
	with a Meet email, and the teachers with one (they host)."""
	students = frappe.db.sql("""select distinct lower(trim(s.meet_email)) from `tabStudent Batch Enrollment` e
		join `tabStudent` s on s.name = e.student
		where e.batch = %s and e.docstatus = 1 and e.status in ('Active', 'On Hold') and ifnull(s.meet_email, '') != ''""", batch)
	teachers = frappe.get_all("Teacher", filters={"meet_email": ["!=", ""], "status": ["!=", "Inactive"]}, pluck="meet_email")
	host = (_settings().meet_account or "").strip().lower()
	return sorted({e[0] for e in students} | {t.strip().lower() for t in teachers if t} - {host, ""})


def _event_body(b, valid_from, valid_to, guests, kind):
	# Google needs a time on the event; the Meet link works at any hour and attendance follows the
	# timesheet, so the time only decides where the meeting shows in the TNC calendar
	start_t, end_t = str(b.start_time or "18:00:00")[:8], str(b.end_time or "20:00:00")[:8]
	if end_t <= start_t:
		start_t, end_t = "18:00:00", "20:00:00"
	body = {
		"summary": f"{b.batch_name or b.name} · online class",
		"description": _("Team Nursing Classes · {0}. Join only through this link, signed in to the Gmail you gave the institute: attendance is marked from it.").format(b.batch_name or b.name),
		"start": {"dateTime": f"{valid_from}T{start_t}", "timeZone": "Asia/Kolkata"},
		"end": {"dateTime": f"{valid_from}T{end_t}", "timeZone": "Asia/Kolkata"},
		"attendees": [{"email": e} for e in guests],
		"guestsCanInviteOthers": False, "guestsCanSeeOtherGuests": False, "guestsCanModify": False,
		"reminders": {"useDefault": False},
		"conferenceData": {"createRequest": {"requestId": frappe.generate_hash(length=20), "conferenceSolutionKey": {"type": "hangoutsMeet"}}},
	}
	if kind == "Whole batch":
		days = [RRULE_DAYS[i] for i, f in enumerate(DAYS) if b.get(f)] or list(RRULE_DAYS[:6])  # no ticks: Mon-Sat
		until = getdate(valid_to).strftime("%Y%m%dT235959Z")
		body["recurrence"] = [f"RRULE:FREQ=WEEKLY;BYDAY={','.join(days)};UNTIL={until}"]
	return body


def _calendar(method, url, **kw):
	headers = {"Authorization": f"Bearer {access_token()}", "Content-Type": "application/json"}
	r = requests.request(method, url, headers=headers, timeout=60, **kw)
	if r.status_code == 403 and "insufficient" in r.text.lower():
		frappe.throw(_("Google has not allowed calendar access yet. Open TNC Settings, click Reconnect Google and approve, then try again."))
	if r.status_code >= 300:
		try:
			msg = r.json()["error"]["message"]
		except Exception:
			msg = r.text[:300]
		frappe.throw(_("Google Calendar error {0}: {1}").format(r.status_code, msg))
	return r.json() if r.text else {}


@frappe.whitelist()
def create_batch_link(batch, for_date=None):
	"""Manager action on the batch. `for_date` empty: one meeting for the whole batch (recurring on
	the batch's class days, start to end date). `for_date` given: a meeting for that one day only.
	The new link becomes the batch's current link; earlier ones stay for the days they covered."""
	frappe.only_for(MANAGERS)
	b = frappe.get_doc("Student Batch", batch)
	if b.mode == "Offline":
		frappe.throw(_("{0} is an offline batch.").format(b.name))
	if not b.starting_date or not b.actual_ending_date:
		frappe.throw(_("Set the batch start and end dates first."))
	kind = "One day" if for_date else "Whole batch"
	valid_from = getdate(for_date) if for_date else getdate(max(getdate(b.starting_date), getdate(nowdate())))
	valid_to = getdate(for_date) if for_date else getdate(b.actual_ending_date)
	if valid_to < getdate(nowdate()):
		frappe.throw(_("That date is over.") if for_date else _("The batch end date ({0}) is in the past. Correct the batch dates first.").format(frappe.format_value(valid_to, {"fieldtype": "Date"})))
	guests = batch_guests(batch)
	ev = _calendar("POST", CAL_EVENTS_URL, params={"conferenceDataVersion": 1, "sendUpdates": "none"}, json=_event_body(b, valid_from, valid_to, guests, kind))
	link = ev.get("hangoutLink") or next((p["uri"] for p in ev.get("conferenceData", {}).get("entryPoints", []) if p.get("entryPointType") == "video"), None)
	if not link:
		frappe.throw(_("Google created the event but gave no Meet link. Check that Google Meet is enabled for the TNC account."))
	entry_note = set_entry_rule(link)
	# a whole-batch link replaces the batch's link; a one-day link is used for that day only and
	# leaves the batch link in place (code_for prefers the newest link whose dates cover the day)
	if kind == "Whole batch":
		frappe.db.sql("update `tabBatch Meet Link` set current = 0 where batch = %s", batch)
	doc = frappe.get_doc({"doctype": "Batch Meet Link", "batch": batch, "kind": kind, "meet_link": link, "meeting_code": meeting_code(link), "current": 1 if kind == "Whole batch" else 0,
		"valid_from": valid_from, "valid_to": valid_to, "event_id": ev.get("id"), "created_on": now_datetime(), "guests": len(guests), "guests_synced_on": now_datetime()})
	doc.flags.ignore_permissions = True
	doc.insert()
	if kind == "Whole batch":
		b.db_set("meet_link", link)
	b.add_comment("Info", _("Google Meet link created for {0}: {1} ({2} guests)").format(_("the whole batch") if kind == "Whole batch" else frappe.format_value(valid_from, {"fieldtype": "Date"}), link, len(guests)))
	return {"link": link, "guests": len(guests), "kind": kind, "valid_from": str(valid_from), "valid_to": str(valid_to), "entry": entry_note}


def set_entry_rule(link):
	"""Apply TNC Settings "Online class entry" to a meeting. Google's default for a Workspace meeting
	is TRUSTED: invited guests join directly, others knock. RESTRICTED: only invited can join at all.
	Returns a short note for the user; a failure here is reported, not fatal (the link still works)."""
	strict = (_settings().get("meet_entry") or "") == STRICT_ENTRY
	# the Meet API names a space by the dashed meeting code from the link ("abc-defg-hij"), not the
	# squashed form the audit log uses
	m = re.search(r"([a-z]{3}-[a-z]{4}-[a-z]{3})", (link or "").lower())
	if not m:
		return _("Entry rule not applied (no meeting code in the link); Google's default applies: registered students join directly, others must ask.")
	want = "RESTRICTED" if strict else "TRUSTED"
	try:
		headers = {"Authorization": f"Bearer {access_token()}", "Content-Type": "application/json"}
		r = requests.patch(f"{MEET_SPACES_URL}/{m.group(1)}", headers=headers, params={"updateMask": "config.access_type"}, json={"config": {"accessType": want}}, timeout=60)
		if r.status_code >= 300:
			raise Exception(r.text[:300])
		return _("Only registered students can join; others are refused.") if strict else _("Registered students join directly; others must ask to join.")
	except Exception as ex:
		frappe.log_error(title="Meet entry rule not applied", message=f"{link}\n{ex}")
		return _("Entry rule not applied ({0}); Google's default applies: registered students join directly, others must ask.").format(str(ex)[:120])


def apply_entry_rule_all():
	"""Background, after TNC Settings "Online class entry" is saved: every current system-made batch
	link gets the rule, and the result is noted on the Batch Meet Link."""
	done = []
	for l in frappe.get_all("Batch Meet Link", filters={"current": 1, "event_id": ["!=", ""]}, fields=["name", "meet_link"]):
		note = set_entry_rule(l.meet_link)
		frappe.db.set_value("Batch Meet Link", l.name, "error", None if "not applied" not in note else note, update_modified=False)
		done.append((l.name, note))
	frappe.db.commit()
	return done


def sync_guests(batch):
	"""Push the batch's guest list to its current system-made meeting (and to a one-day link that is
	still ahead). Runs in the background after enrolments or a student's Meet email change."""
	today = getdate(nowdate())
	links = [l for l in frappe.get_all("Batch Meet Link", filters={"batch": batch, "event_id": ["!=", ""]}, fields=["name", "event_id", "valid_to", "current"])
		if l.current or (l.valid_to and getdate(l.valid_to) >= today)]
	if not links:
		return {"skipped": "no system link"}
	guests = batch_guests(batch)
	out = []
	for l in links:
		try:
			_calendar("PATCH", f"{CAL_EVENTS_URL}/{l.event_id}", params={"sendUpdates": "none"}, json={"attendees": [{"email": e} for e in guests]})
			frappe.db.set_value("Batch Meet Link", l.name, {"guests": len(guests), "guests_synced_on": now_datetime(), "error": None}, update_modified=False)
			out.append(l.name)
		except Exception as ex:
			frappe.db.set_value("Batch Meet Link", l.name, "error", str(ex)[:1000], update_modified=False)
			frappe.log_error(title="Meet guest list not updated", message=frappe.get_traceback())
	frappe.db.commit()
	return {"updated": out, "guests": len(guests)}


def queue_guest_sync(batch):
	"""Hook helper: refresh the guest list soon, once, however many enrolments were saved together."""
	if not batch or not frappe.db.exists("Batch Meet Link", {"batch": batch, "current": 1, "event_id": ["!=", ""]}):
		return
	frappe.enqueue("tnc_v2_360ithub.meet.sync_guests", queue="short", job_id=f"meet-guests:{batch}", deduplicate=True, enqueue_after_commit=True, batch=batch)


def on_enrolment_change(doc, method=None):
	queue_guest_sync(doc.batch)


def on_student_change(doc, method=None):
	"""Student saved with a different Meet email: every batch they are in gets the new address."""
	if doc.is_new() or not doc.has_value_changed("meet_email"):
		return
	for b in frappe.get_all("Student Batch Enrollment", filters={"student": doc.name, "docstatus": 1, "status": ["in", ["Active", "On Hold"]]}, pluck="batch", distinct=True):
		queue_guest_sync(b)


@frappe.whitelist()
def update_guests_now(batch):
	frappe.only_for(MANAGERS)
	return sync_guests(batch)


@frappe.whitelist()
def batch_links(batch):
	return frappe.get_all("Batch Meet Link", filters={"batch": batch}, fields=["name", "kind", "meet_link", "current", "valid_from", "valid_to", "guests", "guests_synced_on", "error"],
		order_by="created_on desc", limit=10)
