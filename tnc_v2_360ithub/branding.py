"""Institute branding shared by the dashboard pages."""
import mimetypes
import frappe

DEFAULT_LOGO = "/assets/tnc_v2_360ithub/images/tnc_logo.png"


def _chosen_logo():
	"""The navbar logo (Navbar Settings › App Logo), else the TNC logo shipped with the app."""
	return frappe.db.get_single_value("Navbar Settings", "app_logo") or DEFAULT_LOGO


def institute_logo():
	"""URL the dashboard pages can show to every logged-in user. A private file is served through
	`logo` below, since only privileged users may read /private/files directly."""
	url = _chosen_logo()
	if url.startswith("/private/"):
		return "/api/method/tnc_v2_360ithub.branding.logo"
	return url


@frappe.whitelist()
def logo():
	"""Stream the institute logo to any logged-in user, whatever file it is stored in."""
	url = _chosen_logo()
	if url.startswith("/assets/"):
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = url
		return
	f = frappe.get_doc("File", {"file_url": url})
	frappe.local.response.filename = f.file_name or "logo"
	frappe.local.response.filecontent = f.get_content()
	frappe.local.response.type = "binary"
	frappe.local.response.display_content_type = mimetypes.guess_type(f.file_name or url)[0] or "image/png"
