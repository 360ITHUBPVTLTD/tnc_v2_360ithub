# Copyright (c) 2026, 360ITHub and contributors
# For license information, please see license.txt
"""Make `custom/<doctype>.json` the single source of truth for Custom Fields.

`bench migrate` calls `sync_customizations`, whose Custom Field branch only inserts
what is missing and updates what is already there - it never deletes a field that
was removed from the JSON. (`Custom DocPerm`, a few lines below in the same frappe
function, *is* deleted and reinserted, so the asymmetry is deliberate.) The effect
was that removing a field in Customize Form, exporting and merging changed nothing
on any other site: the deploy ran, migrate ran, and the field stayed.

This closes that gap. It is registered as the *last* `after_migrate` hook, which
frappe runs after `sync_customizations` (see `SiteMigration.post_schema_updates`),
so a leftover can be removed without being re-added in the same run.

WHAT IT DELETES: any Custom Field on a doctype we ship a `custom/*.json` for, with
`is_system_generated = 0`, whose fieldname is absent from that file. That includes
a field an admin created directly on a site through Customize Form and never
exported. If you add a field on a live site, export it to the repo, or this will
remove it.

Deleting a Custom Field drops its column, so it destroys data. That is why a site
REPORTS ONLY until it is armed: every migrate prints exactly what would go, and
nothing is touched. Read that list, then arm the site once:

    bench --site <site> set-config -g reconcile_custom_fields 1 --parse

From then on it enforces on every migrate, with no further steps. Set it back to 0
on any site where admins are allowed to add fields through Customize Form without
exporting them.

WHAT IT NEVER DELETES: fields with `is_system_generated = 1` - the ones apps create
programmatically, such as india_compliance's GST fields. `export_customizations`
writes those into our JSON too (it exports every Custom Field on the doctype), and
`admissions.custom_fields.ensure_custom_fields` flips the flag to 0 for fields
whose module is "TNC v2" so Customize Form will edit them. That is exactly why this
hook has to run after it.

NOT HANDLED: Property Setters have the same root cause, but unlike Custom Field
they carry no `is_system_generated` flag, so there is no safe way to tell ours from
another app's. Removing a property setter still needs an explicit patch.
"""

import json
import os

import frappe
from frappe.custom.doctype.custom_field.custom_field import delete_custom_fields

APP = "tnc_v2_360ithub"

# A deliberate removal is one or two fields. A number much larger than that almost
# always means the JSON was exported from a bench that was missing an app, so the
# file under-declares reality. Refuse and let a human look rather than delete the lot.
# Raise it per site with:
#   bench --site <site> set-config -g reconcile_custom_fields_max_deletions 20 --parse
DEFAULT_MAX_DELETIONS_PER_DOCTYPE = 5


def declared_fields_by_doctype() -> dict[str, set[str]]:
	"""Fieldnames each of our custom/*.json files declares, keyed by doctype.

	Mirrors frappe's own traversal in `sync_customizations`, including the
	`sync_on_migrate` gate: a file frappe will not sync must not be treated as
	authoritative here either.
	"""
	declared: dict[str, set[str]] = {}

	for module_name in frappe.local.app_modules.get(APP) or []:
		folder = frappe.get_app_path(APP, module_name, "custom")
		if not os.path.exists(folder):
			continue

		for fname in sorted(os.listdir(folder)):
			if not fname.endswith(".json"):
				continue

			with open(os.path.join(folder, fname)) as f:
				data = json.load(f)

			if not data.get("sync_on_migrate"):
				continue

			doctype = data.get("doctype")
			if not doctype:
				continue

			# Keep every fieldname the file mentions, whatever its
			# is_system_generated value - the keep-set should be as wide as possible.
			keep = declared.setdefault(doctype, set())
			for row in data.get("custom_fields") or []:
				if row.get("fieldname"):
					keep.add(row["fieldname"])

	return declared


def reconcile_custom_fields(dry_run: bool = False):
	"""Delete Custom Fields our custom/*.json no longer declares.

	Preview it on any site before trusting it:

	    bench --site <site> execute \\
	        tnc_v2_360ithub.customizations.reconcile_custom_fields \\
	        --kwargs "{'dry_run': True}"
	"""
	# Report-only until the site is armed. Deleting a Custom Field drops its column,
	# so the first run on any site must be reviewable rather than destructive.
	armed = bool(frappe.conf.get("reconcile_custom_fields"))
	if not armed:
		dry_run = True

	max_deletions = int(frappe.conf.get("reconcile_custom_fields_max_deletions") or DEFAULT_MAX_DELETIONS_PER_DOCTYPE)

	to_delete: dict[str, list[str]] = {}

	for doctype, keep in declared_fields_by_doctype().items():
		if not frappe.db.exists("DocType", doctype):
			continue

		existing = frappe.get_all(
			"Custom Field",
			filters={"dt": doctype, "is_system_generated": 0},
			pluck="fieldname",
		)
		orphans = sorted(set(existing) - keep)
		if not orphans:
			continue

		if len(orphans) > max_deletions:
			print(
				f"reconcile_custom_fields: REFUSING to delete {len(orphans)} fields from "
				f"{doctype} (limit {max_deletions}). Either the export is missing "
				f"another app's fields, or this is a bulk change that wants an explicit "
				f"patch. Fields left in place: {orphans}"
			)
			continue

		to_delete[doctype] = orphans

	if not to_delete:
		return

	total = sum(len(v) for v in to_delete.values())
	for doctype, fieldnames in to_delete.items():
		print(f"reconcile_custom_fields: {doctype}: {'would delete' if dry_run else 'deleting'} {fieldnames}")

	if dry_run:
		if not armed:
			print(
				f"reconcile_custom_fields: REPORT ONLY - {total} field(s) left in place. "
				f"Review the list above, then arm this site with: "
				f"bench --site {frappe.local.site} set-config -g reconcile_custom_fields 1 --parse"
			)
		return

	# delete_custom_fields goes through delete_doc, so Custom Field.on_trash runs:
	# it drops the column, deletes Property Setter rows for the field, prunes
	# DocType Layout references and clears the doctype cache.
	delete_custom_fields(to_delete)
	frappe.db.commit()
