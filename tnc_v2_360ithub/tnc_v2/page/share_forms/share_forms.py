# Copyright (c) 2026, 360ITHub and contributors
import base64, io

import frappe
from frappe.utils import get_url


@frappe.whitelist()
def get_links():
	"""Public form links for this site and a QR code (PNG, base64) for the enquiry form."""
	import pyqrcode

	base = get_url()
	enquiry = f"{base}/enquiry"
	qr = pyqrcode.create(enquiry, error="M")
	buf = io.BytesIO()
	qr.png(buf, scale=8, module_color=(17, 24, 39, 255), background=(255, 255, 255, 255))
	return {"enquiry": enquiry, "admission": f"{base}/admission/new", "qr_png": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()}
