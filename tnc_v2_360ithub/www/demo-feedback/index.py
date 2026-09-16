import frappe

no_cache = 1


def get_context(context):
	context.no_breadcrumbs = True
	context.show_sidebar = False
	context.title = "Rate your demo class"
	return context
