"""Import the online student master (Excel from the TNC template): one row per student with
Student Name, Mobile, Gmail, Batch, Parent Mobile, Alternate Mobile.

	System Console:  frappe.call("tnc_v2_360ithub.admissions.import_online_students.run", path="/path/file.xlsx", dry_run=1)

Matches an existing Student by Google Meet Email; otherwise creates one. A row whose mobile already
belongs to another student is skipped and reported (never merged). Enrols everyone in their batch as fees-outside-system
(admissions.enrol_existing). dry_run=1 only reports. Batches must exist with that exact name;
rows with an unknown batch, no mobile or no Gmail are reported and skipped, never guessed.
"""
import re

import frappe
from frappe import _
from frappe.utils import cint, nowdate

EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$")
KNOWN_DOMAINS = {"gmail.com", "yahoo.com", "yahoo.in", "outlook.com", "hotmail.com", "rediffmail.com", "icloud.com", "live.com", "ymail.com", "protonmail.com"}


def _edits(a, b):
	"""Levenshtein distance: how many single-character edits turn a into b."""
	prev = list(range(len(b) + 1))
	for i, ca in enumerate(a, 1):
		cur = [i]
		for j, cb in enumerate(b, 1):
			cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
		prev = cur
	return prev[-1]


def clean_email(email):
	"""(cleaned email, what was fixed or None). Spaces and capitals are removed; a domain within two
	typing errors of gmail.com (gamil.com, gmail.vom, gmai.com, gmail.comm ...) becomes gmail.com.
	Other domains are left as typed."""
	e = re.sub(r"\s+", "", str(email or "")).lower().strip(".")
	if "@" not in e:
		return e, None
	local, _, dom = e.rpartition("@")
	fixed = "spaces/capitals" if e != str(email or "").strip() else None
	if dom != "gmail.com" and dom not in KNOWN_DOMAINS and (_edits(dom, "gmail.com") <= 2 or re.fullmatch(r"[0-9]*gmail[0-9]*\.com", dom)):
		e, fixed = f"{local}@gmail.com", "gmail spelling"
	return e, fixed


def email_problem(email):
	"""Why a cleaned email cannot be used, or None."""
	if "@" not in email:
		return "Gmail missing"
	if not EMAIL_RE.match(email):
		return "Gmail not valid"
	dom = email.rpartition("@")[2]
	if re.fullmatch(r"[0-9.]+\.[a-z]+", dom) or (dom not in KNOWN_DOMAINS and _edits(dom, "gmail.com") <= 4):
		return "Gmail not valid"  # a number domain, or a gmail typo too far gone to be sure
	return None


def is_gmail_typo(email):
	dom = email.rpartition("@")[2]
	return dom != "gmail.com" and dom not in KNOWN_DOMAINS and _edits(dom, "gmail.com") <= 2
HEADERS = {"student_name": "student name", "mobile": "mobile", "meet_email": "gmail", "batch": "batch", "parent_mobile": "parent mobile", "alt_mobile": "alternate mobile"}


def _digits(v):
	return re.sub(r"\D", "", str(v or ""))


def _read(path):
	from openpyxl import load_workbook
	wb = load_workbook(path, read_only=True, data_only=True)
	ws = wb["Online Students"] if "Online Students" in wb.sheetnames else wb.worksheets[0]
	rows = list(ws.iter_rows(values_only=True))
	if not rows:
		return []
	head = [str(h or "").strip().lower() for h in rows[0]]
	col = {}
	for key, label in HEADERS.items():
		col[key] = next((i for i, h in enumerate(head) if h.startswith(label)), None)
	missing = [HEADERS[k] for k, i in col.items() if i is None and k in ("student_name", "mobile", "meet_email", "batch")]
	if missing:
		frappe.throw(_("Columns not found in the sheet: {0}").format(", ".join(missing)))
	out = []
	for r in rows[1:]:
		get = lambda k: (r[col[k]] if col[k] is not None and col[k] < len(r) else None)
		name = re.sub(r"\s+", " ", str(get("student_name") or "")).strip()
		if not name or name.lower().startswith("example"):
			continue
		out.append({"student_name": name, "mobile": _digits(get("mobile")), "meet_email": clean_email(get("meet_email"))[0],
			"batch": str(get("batch") or "").strip(), "parent_mobile": _digits(get("parent_mobile")), "alt_mobile": _digits(get("alt_mobile"))})
	return out


@frappe.whitelist()
def run(path, dry_run=1, enrollment_date=None, same_person_mobiles=None, left_other_batches=0):
	"""same_person_mobiles: mobiles (comma-separated) the office has confirmed belong to the existing student with
	that number; those rows set the Gmail on that student and enrol them instead of being skipped.
	left_other_batches=1: for those students, mark their other Active/On Hold enrolments Left (moved to online)."""
	frappe.only_for(("System Manager", "TNC Super Admin"))
	dry_run = cint(dry_run)
	confirmed = {_digits(m) for m in str(same_person_mobiles or "").replace(";", ",").split(",") if _digits(m)}
	rows = _read(path)
	out = frappe._dict(rows=len(rows), matched_by_email=[], matched_by_mobile=[], created=[], email_set=[], skipped=[], enrolled=[], already_enrolled=[], left=[], errors=[])
	batches = {b: frappe.db.exists("Student Batch", b) for b in {r["batch"] for r in rows}}
	seen_email, seen_mobile = set(), set()
	to_enrol = {}
	for r in rows:
		name, mob, email, batch = r["student_name"], r["mobile"], r["meet_email"], r["batch"]
		why = None
		if not batches.get(batch):
			why = f"batch not found: {batch!r}"
		elif not mob or len(mob) < 10:
			why = "no mobile"
		elif email_problem(email):
			why = f"{email_problem(email)}: {email or '-'}"
		elif email in seen_email:
			why = f"duplicate gmail in sheet: {email}"
		if why:
			out.skipped.append((name, why))
			continue
		seen_email.add(email)
		try:
			st = frappe.db.get_value("Student", {"meet_email": email}, ["name", "student_name"], as_dict=True)
			if st:
				out.matched_by_email.append((email, st.name, st.student_name))
			else:
				st = frappe.db.sql("""select name, student_name from `tabStudent` where mobile = %s and ifnull(meet_email, '') = '' order by creation limit 1""", mob, as_dict=True)
				st = st[0] if st else None
				same_batch = st and frappe.db.exists("Student Batch Enrollment", {"student": st.name, "batch": batch, "docstatus": 1, "status": ["in", ["Active", "On Hold"]]})
				if st and (same_batch or mob in confirmed):
					# already in this batch from an earlier run, or the office confirmed it is the same student
					out.matched_by_mobile.append((mob, st.name, st.student_name))
					if not dry_run:
						frappe.db.set_value("Student", st.name, "meet_email", email)
					if mob in confirmed and cint(left_other_batches):
						for e in frappe.get_all("Student Batch Enrollment", filters={"student": st.name, "docstatus": 1, "batch": ["!=", batch], "status": ["in", ["Active", "On Hold"]]}, fields=["name", "batch"]):
							out.left.append((st.student_name, e.batch))
							if not dry_run:
								frappe.db.set_value("Student Batch Enrollment", e.name, "status", "Left")
				elif st:
					# same mobile as a student of another batch (offline list, sibling, or a wrong number): never
					# merged by us. The office checks and either corrects the sheet or adds the Gmail on that student.
					out.skipped.append((name, f"mobile {mob} already belongs to {st.student_name} ({st.name}): check"))
					continue
				elif dry_run:
					out.created.append((name, email))
					st = frappe._dict(name=f"(new) {email}")
				else:
					doc = frappe.get_doc({"doctype": "Student", "student_name": name, "mobile": mob, "alt_mobile": r["alt_mobile"] or None,
						"meet_email": email, "father_mobile_no": r["parent_mobile"] or None, "status": "Active", "batch_interested": batch,
						"notes": _("Imported from the online student list.")})
					doc.flags.ignore_permissions = True
					doc.insert()
					st = doc
					out.created.append((name, st.name))
			to_enrol.setdefault(batch, []).append(st.name)
		except Exception as ex:
			out.errors.append((name, email, str(ex)[:150]))
	if dry_run:
		for batch, names in to_enrol.items():
			for s in names:
				if frappe.db.exists("Student Batch Enrollment", {"batch": batch, "student": s, "docstatus": 1, "status": ["in", ["Active", "On Hold"]]}):
					out.already_enrolled.append(s)
				else:
					out.enrolled.append((batch, s))
		frappe.db.rollback()
	else:
		from tnc_v2_360ithub.admissions.enrol_existing import enrol
		for batch, names in to_enrol.items():
			res = enrol(batch, names, enrollment_date or nowdate())
			out.enrolled += [(batch, s) for s in res["made"]]
			out.already_enrolled += [s for s, why in res["skipped"] if "already" in why]
			out.errors += [(s, "", why) for s, why in res["skipped"] if "already" not in why]
		frappe.db.commit()
	return _summary(out, dry_run)


def _summary(o, dry_run):
	lines = [f"{'DRY RUN' if dry_run else 'DONE'}: {o.rows} rows in file"]
	lines.append(f"matched by gmail: {len(o.matched_by_email)}")
	lines.append(f"gmail set on existing students (matched by mobile): {len(o.matched_by_mobile)} {o.matched_by_mobile[:10]}")
	if o.left:
		lines.append(f"marked Left in other batches: {len(o.left)} {o.left}")
	lines.append(f"created: {len(o.created)} {o.created[:10] if len(o.created) <= 10 else ''}")
	lines.append(f"enrolled: {len(o.enrolled)}; already enrolled: {len(o.already_enrolled)}")
	for k in ("skipped", "errors"):
		if o[k]:
			lines.append(f"{k} ({len(o[k])}): {o[k]}")
	return "\n".join(lines)
