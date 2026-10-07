# Copyright (c) 2026, 360ITHub and contributors
"""Syllabus master import from TNC's spreadsheet.

Layout the institute uses: row 1 holds one subject per column (from column C on), each column
lists that subject's chapters top to bottom in teaching order, and column B carries
"<Subject> - <Teacher>" rows naming the usual teacher. Nothing about the file is fixed here:
subject names are taken from the headings as written, and the teacher is looked up in the
Teacher list by the name after the last dash. Whatever cannot be matched is reported so the
office fills it in on the Subject form.

Safe to run again with a newer file: existing subjects get their chapter list replaced; a
teacher already set on the form is kept.

Chapters split into parts on the sheet ("Female Pelvis part - I" … "part - IV", "Oxygen Therapy -II")
become one chapter ("Female Pelvis"), and the sheet's own serial number ("21.") is dropped, since
the list order already numbers them. A subject whose rows are only numbered parts of one name
("Psychology -1" … "-6") has no chapter names to merge into, so it is kept as it is and reported.
merge_existing() applies the same rule to subjects already imported and re-points logged classes.

Run:  bench --site <site> execute tnc_v2_360ithub.teachers.syllabus.import_master --kwargs "{'path': '/path/to/syllabus.xlsx'}"
"""
import io
import re

import frappe
from frappe import _


def _clean(s):
	return re.sub(r"\s+", " ", str(s or "")).replace("–", "-").strip()


def _split_label(label):
	"""'MSN – Renal - Arjun sir' -> ('msn - renal', 'arjun sir'); no dash -> (label, None)."""
	parts = [p.strip() for p in re.split(r"\s*-\s*", _clean(label).lower()) if p.strip()]
	if len(parts) < 2:
		return parts[0] if parts else "", None
	return " - ".join(parts[:-1]), parts[-1]


def _same_name(a, b):
	"""'avdesh' ~ 'avadhesh', 'sukhdev' ~ 'sukhi', 'hansraj' ~ 'hans': spelling on the sheet is loose."""
	from difflib import SequenceMatcher
	if a == b:
		return True
	if len(a) >= 4 and len(b) >= 4 and a[:4] == b[:4]:
		return True
	return SequenceMatcher(None, a, b).ratio() >= 0.8


def _find_teacher(nickname, teachers):
	"""Match the name after the dash ('arjun sir', 'divya mam') to exactly one Teacher."""
	skip = {"sir", "mam", "madam", "dr", "ji", "miss", "mr", "mrs"}
	words = [w for w in re.findall(r"[a-z]+", nickname or "") if w not in skip]
	for w in words:
		exact = [t.name for t in teachers if w in t.words]
		if len(exact) == 1:
			return exact[0]
		if exact:
			continue  # two teachers share this first name; the office picks on the form
		fuzzy = [t.name for t in teachers if any(_same_name(w, x) for x in t.words)]
		if len(fuzzy) == 1:
			return fuzzy[0]
	return None


_NOISE = {"msn", "topic", "name", "system", "theory", "and", "mcq", "the", "of"}


def _words(s):
	return {w for w in re.findall(r"[a-z]+", _clean(s).lower()) if w not in _NOISE}


def _subject_matches(label_subject, subject_name):
	"""Every word of the column-B label appears in the heading ('obg' -> 'Gynecology (OBG)')."""
	a, b = _words(label_subject), _words(subject_name)
	return bool(a) and bool(b) and a <= b


_LEAD_NO = re.compile(r"^\s*\d+\s*[.)]?\s*")
# A part marker at the end of a name: "Part - II", "(Part-2)", "- IV", "-3", or a bare roman "XII".
# Roman numerals on the sheet are often typed with 1 or l for I ("- 1l", "- 1ll"), so those count too.
_NUM = r"(?:[ivxl1]+|\d+)"
_PART = re.compile(r"[\s\-–]*(?:\(?\s*(?:part|pt)\.?\s*[-–.]?\s*" + _NUM + r"\s*\)?|[-–]\s*" + _NUM + r"|\s[ivx]{1,5})\s*$", re.I)


def _letters(s):
	return re.sub(r"[^a-z]", "", s.lower().replace("&", "and"))


def _one_slip(a, b):
	"""True when b is a with at most one typing slip: a letter wrong, missing, extra, or two swapped."""
	if a == b:
		return True
	if abs(len(a) - len(b)) > 1:
		return False
	d = [[i + j if i * j == 0 else 0 for j in range(len(b) + 1)] for i in range(len(a) + 1)]
	for i in range(1, len(a) + 1):
		for j in range(1, len(b) + 1):
			cost = a[i - 1] != b[j - 1]
			d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
			if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
				d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
	return d[-1][-1] <= 1


def _same_topic(a, b):
	"""Same chapter name apart from the sheet's lecture numbers, punctuation and one typing slip:
	'Fluid and ElectrolyteB' ~ 'Fluid and Electrolyte', 'Pharma - 10 Adrenergic Drugs' ~ 'Pharma -
	09 Adrenergic Drugs', 'Carnial Nerve' ~ 'Cranial Nerve'; but 'Hypothyroidism' is not 'Hyperthyroidism'."""
	a, b = _letters(a), _letters(b)
	# short names ('Vitamin C' / 'Vitamin D') differ by one letter on purpose: no typo allowance there
	return a == b or (min(len(a), len(b)) >= 10 and _one_slip(a, b))


def merge_parts(names):
	"""Chapter names in order -> (merged names, old position -> new position).

	Neighbouring rows of the same topic become one chapter: a row joins the chapter above when
	either of the two rows carries a part marker and the names without markers match (allowing a
	small typo, & = and), or when its name is exactly that chapter's name. The merged chapter takes the topic name most rows
	use. A lone row keeps its own name minus the sheet's serial number. If everything would fold
	into a single chapter, the rows are the only names there are, so they are returned unchanged."""
	from collections import Counter
	cleaned = [_LEAD_NO.sub("", n).strip() or n for n in names]
	marked = [bool(_PART.search(c)) for c in cleaned]
	bases = [_PART.sub("", c).strip(" -–") or c for c in cleaned]
	groups = []  # [first base, [positions]]
	for i, base in enumerate(bases):
		if groups:
			top = groups[-1][0]
			if base.lower() == top.lower() or ((marked[i] or marked[groups[-1][1][-1]]) and _same_topic(base, top)):
				groups[-1][1].append(i)
				continue
		groups.append([base, [i]])
	merged, index = [], [0] * len(names)
	for top, members in groups:
		if len(members) > 1:
			merged.append(Counter(bases[m] for m in members).most_common(1)[0][0])
		else:
			merged.append(cleaned[members[0]])
		for m in members:
			index[m] = len(merged) - 1
	if len(merged) <= 1 < len(names):
		return list(names), list(range(len(names)))
	return merged, index


def read_sheet(path=None, content=None):
	"""-> list of {name, order, chapters, teacher, teacher_label}. `content` is xlsx bytes."""
	import openpyxl
	wb = openpyxl.load_workbook(path or io.BytesIO(content), read_only=True, data_only=True)
	rows = list(wb.worksheets[0].iter_rows(values_only=True))
	if not rows:
		return []
	subjects = []
	for j, h in enumerate(rows[0]):
		if j < 2 or not _clean(h):
			continue
		chapters = merge_parts([_clean(r[j]) for r in rows[1:] if j < len(r) and _clean(r[j])])[0]
		subjects.append({"name": _clean(h), "order": len(subjects) + 1, "chapters": chapters, "teacher": None, "teacher_label": None})
	teachers = [frappe._dict(name=t.name, words=set(re.findall(r"[a-z]+", (t.full_name or "").lower())))
		for t in frappe.get_all("Teacher", fields=["name", "full_name"])]
	for r in rows[1:]:
		label = _clean(r[1]) if len(r) > 1 else ""
		if not label:
			continue
		subj, nick = _split_label(label)
		teacher = _find_teacher(nick, teachers) if nick else None
		for s in subjects:
			if not s["teacher"] and _subject_matches(subj, s["name"]):
				s["teacher"], s["teacher_label"] = teacher, nick
	return subjects


def import_master(path=None, content=None, dry_run=False):
	"""Create/refresh Subject records from the spreadsheet. Returns a summary dict."""
	subjects = read_sheet(path=path, content=content)
	created = updated = 0
	for s in subjects:
		if frappe.db.exists("Subject", s["name"]):
			doc = frappe.get_doc("Subject", s["name"])
			updated += 1
		else:
			doc = frappe.new_doc("Subject")
			doc.subject_name = s["name"]
			created += 1
		if s["teacher"] and not doc.teacher:
			doc.teacher = s["teacher"]
		doc.sort_order = s["order"]
		doc.set("chapters", [])
		for ch in s["chapters"]:
			doc.append("chapters", {"chapter_name": ch})
		if not dry_run:
			doc.flags.ignore_permissions = True
			doc.save()
	if not dry_run:
		frappe.db.commit()
	summary = {
		"subjects": len(subjects), "created": created, "updated": updated,
		"chapters": sum(len(s["chapters"]) for s in subjects),
		"teacher_not_found": {s["name"]: s["teacher_label"] for s in subjects if not s["teacher"]},
	}
	print(summary)
	return summary


@frappe.whitelist()
def import_from_file(file_url, dry_run=0):
	"""Desk: import an uploaded xlsx (File doc url). System Manager / TNC Super Admin only."""
	if not ({"System Manager", "TNC Super Admin"} & set(frappe.get_roles())):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	f = frappe.get_doc("File", {"file_url": file_url})
	return import_master(content=f.get_content(), dry_run=frappe.utils.cint(dry_run))


def merge_existing(dry_run=1):
	"""Apply merge_parts to every Subject already in the system and move logged classes (timesheet
	rows) to the merged chapter. Returns {subject: (before, after)}; dry_run only reports.

	Run: bench --site <site> execute tnc_v2_360ithub.teachers.syllabus.merge_existing --kwargs "{'dry_run': 0}"
	"""
	dry_run = frappe.utils.cint(dry_run)
	summary, kept = {}, []
	for name in frappe.get_all("Subject", pluck="name", order_by="sort_order asc"):
		doc = frappe.get_doc("Subject", name)
		old = [c.chapter_name for c in doc.chapters]
		new, index = merge_parts(old)
		if new == old:
			if len(old) > 1 and len({_PART.sub("", _LEAD_NO.sub("", n)).strip(" -–").lower() for n in old}) == 1:
				kept.append(name)
			continue
		summary[name] = (len(old), len(new))
		if dry_run:
			continue
		doc.set("chapters", [])
		for n in new:
			doc.append("chapters", {"chapter_name": n})
		doc.flags.ignore_permissions = True
		doc.save()
		for row in frappe.get_all("Activities", filters={"subject": name, "chapter_seq": [">", 0]}, fields=["name", "chapter_seq"]):
			if row.chapter_seq <= len(index):
				pos = index[row.chapter_seq - 1]
				frappe.db.set_value("Activities", row.name, {"chapter_seq": pos + 1, "chapter": new[pos]}, update_modified=False)
	if not dry_run:
		frappe.db.commit()
	result = {"changed": summary, "kept_as_is (no chapter names on the sheet)": kept,
		"chapters_before": sum(a for a, _ in summary.values()), "chapters_after": sum(b for _, b in summary.values())}
	print(result)
	return result
