import frappe

no_cache = 1
sitemap = 0


def get_context(context):
	"""Project guide: public, standalone page (full HTML document, no base template)."""
	context.no_cache = 1
	return context
