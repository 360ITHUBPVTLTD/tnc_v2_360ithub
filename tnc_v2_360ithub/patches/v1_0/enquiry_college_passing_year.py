"""Public enquiry form asks for college name and passing year (fields added to Student Enquiry)."""
import frappe

NEW = [("college_name", "Data", "College Name"), ("passing_year", "Data", "Passing Year")]


def execute():
	if not frappe.db.exists("Web Form", "enquiry"):
		return
	wf = frappe.get_doc("Web Form", "enquiry")
	have = {f.fieldname for f in wf.web_form_fields}
	if all(n in have for n, *_r in NEW):
		return
	rows = [f.as_dict() for f in wf.web_form_fields]
	at = next((i for i, f in enumerate(rows) if f["fieldname"] == "city"), len(rows) - 1) + 1
	for n, ft, label in reversed(NEW):
		if n not in have:
			rows.insert(at, {"fieldname": n, "fieldtype": ft, "label": label, "reqd": 0})
	wf.set("web_form_fields", [])
	for r in rows:
		wf.append("web_form_fields", {k: r.get(k) for k in ("fieldname", "fieldtype", "label", "reqd", "options", "default", "description", "read_only", "hidden", "max_length", "max_value", "depends_on", "mandatory_depends_on", "read_only_depends_on", "allow_read_on_all_link_options", "show_in_filter") if r.get(k) is not None})
	wf.flags.ignore_permissions = True
	wf.save(ignore_permissions=True)
	frappe.db.commit()
