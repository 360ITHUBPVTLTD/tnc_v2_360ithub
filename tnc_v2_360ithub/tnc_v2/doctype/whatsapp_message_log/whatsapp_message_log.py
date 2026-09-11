# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class WhatsAppMessageLog(Document):
	"""One row per outbound WhatsApp or FCM message. Written by
	tnc_v2_360ithub.notifications before the provider is called and updated
	with the result, so a failed or skipped send is visible without the Error Log."""

	pass
