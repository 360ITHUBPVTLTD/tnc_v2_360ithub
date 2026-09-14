# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class TimesheetApprover(Document):
	"""Row of TNC Settings.teacher_timesheet_approval: users who may approve or
	reject Teachers Timesheets and see the Create Invoice / Payment buttons.
	Replaces v1's 'Institute Management Admin Settings' + 'Multiselect User'."""

	pass
