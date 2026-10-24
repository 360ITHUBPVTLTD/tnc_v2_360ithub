# Copyright (c) 2026, 360ithub and contributors
from frappe.model.document import Document


class MeetClassSync(Document):
	"""One record per online class window pulled from the Google Meet audit log (see meet.py)."""
	pass
