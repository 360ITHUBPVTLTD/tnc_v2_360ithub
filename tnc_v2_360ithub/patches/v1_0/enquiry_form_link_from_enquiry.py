"""Share Forms page retired: the personal enquiry-form link now goes out when the enquiry is
saved, and the public form fills that enquiry instead of creating a second one.

The public form's client script lives on the Web Form record, so it is rewritten here:
the personal-link submit replaces the standard save (returning false from validate would
show Frappe's "Couldn't save" message even though the data was stored)."""
import re

import frappe

MARK = "// personal link: the submission fills the enquiry the counsellor saved"
OVERRIDE = MARK + """
if (inv_m && inv_t) {
	frappe.web_form.save = function () {
		if (this.validate && !this.validate()) return false;
		const values = this.get_values(false);
		if (!values) return false;
		frappe.call({ method: "tnc_v2_360ithub.admissions.invites.submit_personal_form", args: { m: inv_m, t: inv_t, values }, freeze: true }).then((r) => {
			const v = r.message || {};
			if (v.closed) { tnc_notice(v.closed); return; }
			if (v.ok) tnc_notice(`<b>${__("Thank you!")}</b><br>${__("Our counsellor will call you within one working day.")}<br>धन्यवाद! हमारे काउंसलर एक कार्यदिवस में आपसे संपर्क करेंगे।`);
		});
		return false;
	};
}
"""
OLD_INSIDE_VALIDATE = re.compile(r"\tif \(inv_m && inv_t\) \{\n\t\tfrappe\.call\(\{ method: \"tnc_v2_360ithub\.admissions\.invites\.submit_personal_form\".*?\n\t\treturn false;\n\t\}\n", re.S)


def execute():
	if frappe.db.exists("Page", "share-forms"):
		frappe.delete_doc("Page", "share-forms", force=1, ignore_permissions=True)
	if frappe.db.exists("Web Form", "enquiry"):
		wf = frappe.get_doc("Web Form", "enquiry")
		script = wf.client_script or ""
		if MARK in script:
			script = script[: script.index(MARK)]
		script = OLD_INSIDE_VALIDATE.sub("", script).rstrip()
		if "submit_personal_form" not in script and "tnc_notice" in script:
			wf.client_script = script + "\n" + OVERRIDE
			wf.flags.ignore_permissions = True
			wf.save(ignore_permissions=True)
	frappe.db.commit()
