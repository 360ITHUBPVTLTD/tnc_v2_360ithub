"""Guard for files uploaded by Guest (public Admission Form photo).

Frappe's web form uploads the file before the document exists and without a doctype, so the
core "allowed doctypes for guest uploads" list cannot be used. This hook allows a guest to
upload only small photos or PDFs, and to attach them only to an Admission Form.
"""

import frappe
from frappe import _

ALLOWED_EXT = {"jpg", "jpeg", "png", "pdf"}
MAX_BYTES = 5 * 1024 * 1024
ALLOWED_DOCTYPES = {"Admission Form"}


def validate(doc, method=None):
	if frappe.session.user != "Guest":
		return
	ext = (doc.file_name or "").rsplit(".", 1)[-1].lower() if "." in (doc.file_name or "") else ""
	if ext not in ALLOWED_EXT:
		frappe.throw(_("Only JPG, PNG or PDF files can be uploaded."), frappe.PermissionError)
	if doc.attached_to_doctype and doc.attached_to_doctype not in ALLOWED_DOCTYPES:
		frappe.throw(_("Guests cannot attach files to {0}.").format(doc.attached_to_doctype), frappe.PermissionError)
	if (doc.file_size or 0) > MAX_BYTES:
		frappe.throw(_("File is larger than 5 MB."), frappe.PermissionError)
