# Copyright (c) 2024, pankaj@360ithub.com and Contributors
# See license.txt

# import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase


# On IntegrationTestCase, the doctype test records and all
# link-field test record depdendencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class TestTeachersTimesheet(UnitTestCase):
	"""
	Unit tests for TeachersTimesheet.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestTeachersTimesheet(IntegrationTestCase):
	"""
	Integration tests for TeachersTimesheet.
	Use this class for testing interactions between multiple components.
	"""

	pass
