# Copyright (c) 2024, pankaj@360ithub.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today
from frappe import _

class TeachersTimesheet(Document):

    import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

class TeachersTimesheet(Document):
    def before_insert(self):
        # Validate that the date is not in the future
        if getdate(self.date) > getdate(today()):
            frappe.throw(_("You cannot create a timesheet for a future date."))

    def validate(self):
        # Perform all calculations and checks
        self.calculate_totals()
        self.validate_single_activity()
        self.validate_unique_activities()

    def calculate_totals(self):
        """Calculates row amount based on Hourly rate and total sum"""
        self.grand_total = 0
        for activity in self.activity_type:
            # Ensure the rate (activity_fee) is present
            if not activity.activity_fee:
                # Assuming get_rate_for_activity is an imported helper 
                # or defined within the same controller
                activity.activity_fee = self.get_rate_helper(self.teacher_id, activity.activity_name)

            qty = flt(activity.qty)
            fee = flt(activity.activity_fee)

            # UPDATED: Direct calculation (Amount = Quantity * Rate)
            # We removed (qty / 60) because we are now treating the Qty as decimal hours.
            activity.amount = qty * fee

            self.grand_total += activity.amount

    def validate_single_activity(self):
        """Throws an error if the user tries to add more than one row"""
        if len(self.activity_type) > 1:
            frappe.throw(_("Only one activity entry is allowed per Timesheet."))

    def validate_unique_activities(self):
        """Redundant if only 1 row is allowed, but kept for logical safety"""
        activity_names = [activity.activity_name for activity in self.activity_type]
        if len(activity_names) != len(set(activity_names)):
            frappe.throw(_("Duplicate Activity Names are not allowed in the Timesheet."))

    def get_rate_helper(self, teacher_id, activity_name):
        """Helper to get rate if not set by client script"""
        from tnc_v2_360ithub.teachers.doctype.teachers_timesheet.teachers_timesheet import get_rate_for_activity
        rate = get_rate_for_activity(teacher_id, activity_name)
        return flt(rate)


@frappe.whitelist()
def get_rate_for_activity(teacher_id, activity_name):
    """
    Return the 'rate' for a specific activity in a given Teacher doc.
    If the activity or rate is missing, throw a custom message.
    """
    if not teacher_id:
        frappe.throw(_("Teacher ID is required."))
    if not activity_name:
        frappe.throw(_("Activity Name is required."))

    # Fetch the teacher doc
    teacher_doc = frappe.get_doc("Teacher", teacher_id)
    teacher_name = teacher_doc.full_name

    # Search for the matching activity
    for row in teacher_doc.teachers_activity_type:
        if row.activity_name == activity_name:
            if row.rate:
                return row.rate
            else:
                frappe.throw(_(
                    "Please set the Rate for activity '{0}' in Teacher '{1}'."
                ).format(activity_name, teacher_name))

    # frappe.throw(_(
    #     "Teacher '{0}' is not authorized to perform the activity '{1}'."
    # ).format(teacher_name, activity_name))




# teachers_timesheet.py

# import frappe
# from frappe import _
# from frappe.model.document import Document
# from frappe.utils import flt, getdate, today

# class TeachersTimesheet(Document):
#     def before_insert(self):
#         if getdate(self.date) > getdate(today()):
#             frappe.throw(_("You cannot create a timesheet for a future date."))

#     def validate(self):
#         self.calculate_totals()
#         self.validate_single_activity()
#         self.validate_unique_activities()

#     def calculate_totals(self):
#         """Calculates row amount based on Hourly rate and UOM"""
#         self.grand_total = 0
        
#         # Note: Using 'activity_type' as per your provided class loop
#         for activity in self.activity_type:
#             if not activity.activity_fee:
#                 activity.activity_fee = self.get_rate_helper(self.teacher_id, activity.activity_name)

#             # Fetch UOM from Activity Master if not present in row
#             if not activity.uom:
#                 activity.uom = frappe.db.get_value("Activity", activity.activity_name, "uom")

#             qty = flt(activity.qty)
#             fee = flt(activity.activity_fee)

#             # Logic based on UOM
#             if activity.uom == "Hour":
#                 # If Qty is entered in hours (e.g., 1.5 hours)
#                 activity.amount = qty * fee
#             elif activity.uom == "Minute":
#                 # If Qty is entered in minutes (e.g., 90 minutes)
#                 activity.amount = (qty / 60) * fee
#             else:
#                 # Default calculation for other units
#                 activity.amount = qty * fee

#             self.grand_total += activity.amount

#     def validate_single_activity(self):
#         if len(self.activity_type) > 1:
#             frappe.throw(_("Only one activity entry is allowed per Timesheet."))

#     def validate_unique_activities(self):
#         activity_names = [activity.activity_name for activity in self.activity_type]
#         if len(activity_names) != len(set(activity_names)):
#             frappe.throw(_("Duplicate Activity Names are not allowed."))

#     def get_rate_helper(self, teacher_id, activity_name):
#         from tnc_v2_360ithub.teachers.doctype.teachers_timesheet.teachers_timesheet import get_rate_for_activity
#         rate = get_rate_for_activity(teacher_id, activity_name)
#         return flt(rate)

# @frappe.whitelist()
# def get_rate_for_activity(teacher_id, activity_name):
#     if not teacher_id or not activity_name:
#         return 0

#     # Fetch the teacher child table row to get the rate AND the current UOM
#     data = frappe.db.get_value("Teachers Activity Type", 
#         {"parent": teacher_id, "activity_name": activity_name}, 
#         ["rate", "uom"], as_dict=1)

#     if data:
#         return data
#     return {"rate": 0, "uom": ""}






import frappe

def update_uom_in_related_docs(doc, method):
    # Check if UOM was actually changed to avoid unnecessary database hits
    # _doc_before_save is available in on_update
    old_doc = doc.get_doc_before_save()
    if not old_doc or old_doc.uom == doc.uom:
        return

    # 1. Update Teacher Doctype (Child Table: teachers_activity_type)
    # We find all Teachers that have this activity in their child table
    teachers_to_update = frappe.get_all("Teachers Activity Type", 
        filters={"activity_name": doc.name}, 
        fields=["parent"]
    )
    
    teacher_parents = list(set([d.parent for d in teachers_to_update]))
    
    for parent in teacher_parents:
        frappe.db.sql("""
            UPDATE `tabTeachers Activity Type` 
            SET uom = %s 
            WHERE parent = %s AND activity_name = %s
        """, (doc.uom, parent, doc.name))

    # 2. Update Teachers Timesheet (Child Table: Activities, Status: Pending)
    # We find all Pending Timesheets that have this activity
    timesheets_to_update = frappe.get_all("Teachers Timesheet",
        filters={
            "status": "Pending",
            # "docstatus": 0 # Draft
        },
        fields=["name"]
    )
    
    ts_names = [ts.name for ts in timesheets_to_update]
    
    if ts_names:
        # Note: Ensure the child table name is correct. 
        # In your code it is 'activity_type', in your description you said 'Activities'
        frappe.db.sql("""
            UPDATE `tabActivities` 
            SET uom = %s 
            WHERE parent IN %s AND activity_name = %s
        """, (doc.uom, tuple(ts_names), doc.name))
        
    frappe.msgprint(f"Updated UOM to {doc.uom} in related Teachers and Pending Timesheets.")