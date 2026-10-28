# Copyright (c) 2026, 360ITHub and contributors
from frappe.model.document import Document


class BatchMeetLink(Document):
	"""One Google Meet link created by the system for a batch (see tnc_v2_360ithub.meet). Every link
	ever created is kept with the dates it was meant for, so attendance of a past class still finds
	the meeting that class ran on after the batch has moved to a newer link."""
	pass
