import frappe
# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class TNCSettings(Document):
	pass

	def validate(self):
		# the penalty recovery account must be a real (non-group) income account
		if self.get("penalty_account"):
			acc = frappe.db.get_value("Account", self.penalty_account, ["is_group", "root_type"], as_dict=True)
			if not acc or acc.is_group:
				frappe.throw(frappe._("Penalty recovery account: '{0}' is a group heading. Pick an actual account under it (for example an Indirect Income account for recovered penalties).").format(self.penalty_account))
			if acc.root_type != "Income":
				frappe.throw(frappe._("Penalty recovery account must be an Income account; '{0}' is {1}.").format(self.penalty_account, acc.root_type))
