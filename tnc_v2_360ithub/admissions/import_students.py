"""One-off import of existing students from an office list (CSV: biometric_id, student_name, mobile, alt_mobile).

	bench --site <site> execute tnc_v2_360ithub.admissions.import_students.run --kwargs "{'path': '/abs/file.csv', 'batch': 'Achievers Offline Class', 'dry_run': 1}"

Matches an existing Student by Biometric ID first, then by mobile; otherwise creates one. Sets the
Biometric ID where missing, then enrols everyone in the batch as fees-outside-system (see
admissions.enrol_existing). dry_run=1 only reports what would happen. Nothing is hardcoded: the
list is the CSV, the batch is an argument, misses are reported, never guessed.
"""
import csv
import re

import frappe
from frappe import _
from frappe.utils import cint, nowdate


def _digits(v):
	return re.sub(r"\D", "", v or "")


def _read(path):
	with open(path, newline="", encoding="utf-8-sig") as f:
		rows = [r for r in csv.DictReader(f) if (r.get("biometric_id") or "").strip()]
	for r in rows:
		r["biometric_id"] = r["biometric_id"].strip()
		r["student_name"] = re.sub(r"\s+", " ", r.get("student_name") or "").strip()
		r["mobile"] = _digits(r.get("mobile"))
		r["alt_mobile"] = _digits(r.get("alt_mobile"))
	return rows


def _by_mobile_without_id(mob):
	rows = frappe.db.sql("""select name, student_name from `tabStudent`
		where mobile = %s and ifnull(biometric_id, '') = '' order by creation limit 1""", mob, as_dict=True)
	return rows[0] if rows else None


def run(path, batch, dry_run=1, enrollment_date=None, enrol=1):
	"""enrol=0: create or update the students only, with no Biometric ID and no enrolment
	(students on the office list who are not yet active on the machine)."""
	dry_run, enrol = cint(dry_run), cint(enrol)
	if not frappe.db.exists("Student Batch", batch):
		frappe.throw(_("Batch {0} not found").format(batch))
	rows = _read(path)
	seen, dup_ids = set(), []
	for r in rows:
		if r["biometric_id"] in seen:
			dup_ids.append(r["biometric_id"])
		seen.add(r["biometric_id"])
	out = frappe._dict(rows=len(rows), matched_by_id=[], matched_by_mobile=[], created=[], id_set=[], no_mobile=[], enrolled=[], already_enrolled=[], errors=[], duplicate_ids=dup_ids)
	to_enrol = []
	for r in rows:
		bid, name, mob = r["biometric_id"], r["student_name"], r["mobile"]
		try:
			st = frappe.db.get_value("Student", {"biometric_id": bid}, ["name", "student_name", "biometric_id"], as_dict=True)
			if st:
				out.matched_by_id.append((bid, st.name, st.student_name))
			elif mob and (st := _by_mobile_without_id(mob)):
				# same mobile and no id yet: the same person. A student who already has a different id
				# (siblings sharing a phone) is left alone and a new record is created below.
				out.matched_by_mobile.append((bid, st.name, st.student_name))
				if not dry_run and enrol:
					frappe.db.set_value("Student", st.name, "biometric_id", bid)
				if enrol:
					out.id_set.append(st.name)
			else:
				if not mob:
					out.no_mobile.append((bid, name))  # mobile is mandatory on Student: ask the office, skip for now
					continue
				if dry_run:
					out.created.append((bid, name))
					st = frappe._dict(name=f"(new) {bid}")
				else:
					doc = frappe.get_doc({"doctype": "Student", "student_name": name, "mobile": mob, "alt_mobile": r["alt_mobile"] or None,
						"biometric_id": bid if enrol else None, "status": "Active", "batch_interested": batch, "notes": _("Imported from the office admission list.")})
					doc.flags.ignore_permissions = True
					doc.insert()
					st = doc
					out.created.append((bid, st.name))
			to_enrol.append(st.name)
		except Exception as ex:
			out.errors.append((bid, name, str(ex)[:150]))
	if not enrol:
		if dry_run:
			frappe.db.rollback()
		else:
			frappe.db.commit()
		out.enrolled = []
		return _summary(out, dry_run) + "\n(enrol=0: no Biometric ID set, no enrolment made)"
	if dry_run:
		already = {s for s in to_enrol if frappe.db.exists("Student Batch Enrollment", {"batch": batch, "student": s, "docstatus": 1, "status": ["in", ["Active", "On Hold"]]})}
		out.already_enrolled = sorted(already)
		out.enrolled = [s for s in to_enrol if s not in already]
		frappe.db.rollback()
	else:
		from tnc_v2_360ithub.admissions.enrol_existing import enrol
		res = enrol(batch, to_enrol, enrollment_date or nowdate())
		out.enrolled, out.already_enrolled = res["made"], [s for s, why in res["skipped"] if "already" in why]
		out.errors += [(s, "", why) for s, why in res["skipped"] if "already" not in why]
		frappe.db.commit()
	return _summary(out, dry_run)


def _summary(o, dry_run):
	lines = [f"{'DRY RUN' if dry_run else 'DONE'}: {o.rows} rows in file"]
	lines.append(f"matched by biometric id: {len(o.matched_by_id)}")
	lines.append(f"matched by mobile, id {'would be' if dry_run else ''} set: {len(o.matched_by_mobile)} {o.matched_by_mobile[:20]}")
	lines.append(f"created: {len(o.created)}")
	lines.append(f"enrolled: {len(o.enrolled)}; already enrolled: {len(o.already_enrolled)}")
	for k in ("no_mobile", "duplicate_ids", "errors"):
		if o[k]:
			lines.append(f"{k} ({len(o[k])}): {o[k]}")
	return "\n".join(lines)
