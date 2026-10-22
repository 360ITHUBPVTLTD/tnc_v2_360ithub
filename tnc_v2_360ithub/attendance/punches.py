"""Student punches from the attendance machine.

The eSSL machines push every punch to clarity's `essl_login` endpoint. Clarity matches the
code to an Employee; when nothing matches it calls the `essl_unmatched_punch` hook, and we
record the punch here against the Student whose Biometric ID is that code. A code that is
neither an employee nor a student is refused, so the machine log never holds anonymous rows.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime


def _direction(punch):
	d = str(punch.get("Direction") or punch.get("DeviceDirection") or punch.get("direction") or "").strip().upper()
	return "IN" if d in ("IN", "0", "ENTRY") else "OUT" if d in ("OUT", "1", "EXIT") else ""


def _code(punch):
	for k in ("EmployeeCode", "UserId", "employee_code", "badgenumber", "enroll_id"):
		if punch.get(k) not in (None, ""):
			return str(punch[k]).strip()
	return ""


def record_punch(punch, integration_request=None):
	"""Store one raw punch dict (eSSL shape). Returns the Student Punch Log name, or None when
	the code is not a student's Biometric ID, the punch has no time, or it is already recorded."""
	code = _code(punch)
	when = punch.get("LogDate") or punch.get("LogDateTime") or punch.get("log_datetime")
	if not code or not when:
		return None
	student = frappe.db.get_value("Student", {"biometric_id": code}, "name")
	if not student:
		return None
	device = str(punch.get("SerialNumber") or punch.get("device_id") or "").strip()
	# same code at the same second is the same punch, whichever path delivered it: the live push
	# reports the device serial, the nightly eSSL sync reports the device name
	if frappe.db.exists("Student Punch Log", {"biometric_id": code, "punch_time": get_datetime(when)}):
		return None
	doc = frappe.get_doc({
		"doctype": "Student Punch Log",
		"biometric_id": code,
		"student": student,
		"punch_time": get_datetime(when),
		"direction": _direction(punch),
		"device_id": device,
		"device_name": str(punch.get("DeviceName") or "").strip(),
		"integration_request": integration_request,
	})
	doc.insert(ignore_permissions=True)
	return doc.name


def on_unmatched_punch(punch, integration_request=None, **kwargs):
	"""Hook target (clarity `essl_unmatched_punch`). Returns True when the punch was recorded,
	so clarity does not count it as a failure."""
	try:
		return bool(record_punch(punch, integration_request))
	except Exception:
		frappe.log_error(title="Student punch not recorded", message=frappe.get_traceback())
		return False


@frappe.whitelist()
def add_manual(student, punch_time, direction="IN"):
	"""Office / admin: record a punch by hand (testing, or a machine that missed one). Stored
	with device "MANUAL" and the user's name, so it is never confused with a machine punch.
	Goes through record_punch, so the dedupe rule and today's attendance refresh apply."""
	frappe.only_for(("System Manager", "TNC Super Admin", "TNC Manager"))
	code = frappe.db.get_value("Student", student, "biometric_id")
	if not code:
		frappe.throw(_("{0} has no Biometric ID. Enter it on the Student first.").format(student))
	if get_datetime(punch_time) > now_datetime():
		frappe.throw(_("The punch time cannot be in the future."))
	name = record_punch({"EmployeeCode": code, "LogDate": str(get_datetime(punch_time)), "Direction": direction, "SerialNumber": "MANUAL", "DeviceName": _("Entered by {0}").format(frappe.session.user)})
	if not name:
		frappe.throw(_("A punch for this student at this time already exists."))
	return name
