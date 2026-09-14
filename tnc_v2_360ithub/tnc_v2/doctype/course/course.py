# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document

from tnc_v2_360ithub.admissions.setup import ensure_fee_item


class Course(Document):
	def validate(self):
		if self.default_fee is not None and self.default_fee < 0:
			frappe.throw("Default Fee cannot be negative")

	def on_update(self):
		# one service Item per course, used as the line on every enrolment Sales Order
		item = ensure_fee_item(self)
		if item != self.fee_item:
			self.db_set("fee_item", item, update_modified=False)
