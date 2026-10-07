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
from frappe.utils import cint, flt, getdate, today

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
        self.validate_enabled_activities()
        self.resolve_chapters()

    def resolve_chapters(self):
        """Syllabus tracking: a row that names a subject and chapter must use a chapter of that
        subject; its number is stored so the Syllabus Progress report can count and order it."""
        for row in self.activity_type:
            row.chapter = (row.chapter or "").strip()
            if not row.subject and row.chapter:
                frappe.throw(_("Row {0}: choose the Subject before the Chapter.").format(row.idx))
            if not row.subject or not row.chapter:
                row.chapter_seq = None
                row.chapter_completed = 0
                row.chapter_status = None
                continue
            # Chapter Status (In progress / Completed) is what people pick; chapter_completed is
            # the flag the report reads. An older app sends only the flag, so either one counts.
            done = row.chapter_status == "Completed" or cint(row.chapter_completed)
            row.chapter_status = "Completed" if done else "In progress"
            row.chapter_completed = 1 if done else 0
            seq = frappe.db.get_value("Subject Chapter", {"parent": row.subject, "chapter_name": row.chapter}, "seq")
            if not seq:
                frappe.throw(_("Row {0}: '{1}' is not a chapter of {2}. Pick one from the list or add it to the subject first.").format(row.idx, row.chapter, row.subject))
            row.chapter_seq = seq

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

    def validate_enabled_activities(self):
        """A switched-off activity cannot be picked on a new line (the app may still offer it until
        it refreshes); timesheets saved before it was switched off keep it."""
        for row in self.activity_type:
            if not row.activity_name or not row.is_new() and frappe.db.get_value("Activities", row.name, "activity_name") == row.activity_name:
                continue
            if not frappe.db.get_value("Activity", row.activity_name, "enable"):
                frappe.throw(_("'{0}' is no longer used. Please pick another activity.").format(row.activity_name))

    def get_rate_helper(self, teacher_id, activity_name):
        """Helper to get rate if not set by client script"""
        from tnc_v2_360ithub.tnc_v2.doctype.teachers_timesheet.teachers_timesheet import get_rate_for_activity
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
#         from tnc_v2_360ithub.tnc_v2.doctype.teachers_timesheet.teachers_timesheet import get_rate_for_activity
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


@frappe.whitelist()
def get_chapters(subject):
    """Chapter names of a subject, in teaching order, for the timesheet picker (web and app)."""
    return [r.chapter_name for r in frappe.get_all("Subject Chapter", filters={"parent": subject}, fields=["chapter_name"], order_by="seq asc")]


def my_teacher(user=None):
    """The Teacher record behind the logged-in user, tried in order: the User Permission on Teacher
    (how v1 ties a login to a teacher), Teacher.email, then the Employee's Teacher field."""
    user = user or frappe.session.user
    return (frappe.db.get_value("User Permission", {"user": user, "allow": "Teacher"}, "for_value")
        or frappe.db.get_value("Teacher", {"email": user}, "name")
        or frappe.db.get_value("Employee", {"user_id": user, "custom_teacher": ["is", "set"]}, "custom_teacher"))


@frappe.whitelist()
def my_teacher_id():
    """App: which Teacher is the logged-in user. Works for teachers with or without an Employee record."""
    t = my_teacher()
    return {"teacher": t, "teacher_name": frappe.db.get_value("Teacher", t, "full_name") if t else None}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def subject_query(doctype, txt, searchfield, start, page_len, filters):
    """Subject picker: the logged-in teacher's own subjects first, then every other active subject.
    Works for the desk link field and for the app (same ordering)."""
    teacher = my_teacher()
    return frappe.db.sql("""
        select name, teacher_name from `tabSubject`
        where disabled = 0 and (name like %(txt)s or ifnull(teacher_name, '') like %(txt)s)
        order by if(teacher = %(teacher)s, 0, 1), sort_order, name
        limit %(start)s, %(page_len)s""", {"txt": f"%{txt}%", "teacher": teacher or "", "start": start, "page_len": page_len})


@frappe.whitelist()
def subjects_for_me():
    """App: active subjects with the logged-in teacher's own first; `mine` marks them."""
    teacher = my_teacher()
    rows = frappe.get_all("Subject", filters={"disabled": 0}, fields=["name", "teacher", "teacher_name"], order_by="sort_order asc, name asc")
    return sorted(({"name": r.name, "teacher_name": r.teacher_name, "mine": int(r.teacher == teacher)} for r in rows), key=lambda x: -x["mine"])
