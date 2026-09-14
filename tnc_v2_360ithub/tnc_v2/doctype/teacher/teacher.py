# Copyright (c) 2024, pankaj@360ithub.com and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe

class Teacher(Document):

    def validate(self):
        # Call the duplicate validation method before saving
        self.validate_duplicate_pricing()

    def validate_duplicate_pricing(self):
        # List to hold all activity names from the child table
        activity_names =[]
        duplicate_activities = set()

        # Loop through the child table 'teachers_activity_type'
        for row in self.teachers_activity_type:
            if row.activity_name:
                # Check if we've already seen this activity name
                if row.activity_name in activity_names:
                    duplicate_activities.add(row.activity_name)

                activity_names.append(row.activity_name)

        # If any duplicates are found, throw an error mentioning the exact activity
        if duplicate_activities:
            duplicates_str = ", ".join(duplicate_activities)
            frappe.throw((
                "Duplicate pricing found for activities: <b>{0}</b>. "
                "Please ensure each activity has only one pricing entry per Teacher."
            ).format(duplicates_str))

    # def after_insert(self):
    #     """Automatically create or update a Supplier and create a User when a Teacher is inserted."""

    #     # === Supplier Creation or Update ===
    #     # Check if a Supplier with the same full name already exists
    #     existing_supplier = frappe.db.get_value(
    #         "Supplier", {"supplier_name": self.full_name}, "name"
    #     )

    #     if existing_supplier:
    #         # Update existing Supplier
    #         supplier = frappe.get_doc("Supplier", existing_supplier)
    #         supplier.supplier_name = self.full_name
    #         supplier.email_id = self.email
    #         supplier.save()
    #         frappe.msgprint(f"Supplier '{supplier.supplier_name}' updated successfully.")
    #     else:
    #         # Create a new Supplier
    #         supplier = frappe.get_doc({
    #             "doctype": "Supplier",
    #             "supplier_name": self.full_name,
    #             "email_id": self.email,
    #             # "supplier_primary_contact": self.mobile_no,  # Uncomment if needed
    #         })
    #         supplier.insert()
    #         frappe.msgprint(f"Supplier '{supplier.supplier_name}' created successfully.")

    #     # === User Creation ===
    #     # Check if a User with the same email already exists
    #     existing_user = frappe.db.exists("User", self.email)
    #     if existing_user:
    #         frappe.msgprint(f"User with email '{self.email}' already exists.")
    #         return  # Exit the method to prevent duplicate User creation

    #     # Create a new User
    #     user = frappe.get_doc({
    #         "doctype": "User",
    #         "email": self.email,
    #         "first_name": self.full_name,
    #         "mobile_no": self.mobile_no,
    #         # "internal_employee": 1,        # Set to 1 (checked) for True
    #         "enabled": 1,                   # Enable the user by default
    #         "user_type": "System User",     # Set appropriate user type
    #         # "new_password": frappe.generate_hash(length=12),  # Optionally generate a random password
    #         "roles": [{"role": "TNC Teachers"}],
    #         "module_profile": "No Module"
    #     })

    #     try:
    #         user.insert(ignore_permissions=True)
    #         frappe.msgprint(f"User '{user.email}' created successfully.")
    #     except frappe.exceptions.DuplicateEntryError:
    #         frappe.msgprint(f"User with email '{user.email}' already exists.")
    #     except Exception as e:
    #         frappe.msgprint(f"Failed to create User: {e}")


    # def after_insert(self):
    #     """Automatically create or update a Supplier and create a User when a Teacher is inserted."""

    #     # === Supplier Creation or Update ===
    #     # Check if a Supplier with the same full name already exists
    #     existing_supplier = frappe.db.get_value(
    #         "Supplier", {"supplier_name": self.full_name}, "name"
    #     )

    #     supplier_name_id = None

    #     if existing_supplier:
    #         # Update existing Supplier
    #         supplier = frappe.get_doc("Supplier", existing_supplier)
    #         supplier.supplier_name = self.full_name
    #         supplier.email_id = self.email
    #         supplier.save()
    #         supplier_name_id = supplier.name # Get the ID
    #         frappe.msgprint(f"Supplier '{supplier.supplier_name}' updated successfully.")
    #     else:
    #         # Create a new Supplier
    #         supplier = frappe.get_doc({
    #             "doctype": "Supplier",
    #             "supplier_name": self.full_name,
    #             "email_id": self.email,
    #             "supplier_group": "All Supplier Groups", # Ensure mandatory fields are filled
    #         })
    #         supplier.insert()
    #         supplier_name_id = supplier.name # Get the ID
    #         frappe.msgprint(f"Supplier '{supplier.supplier_name}' created successfully.")

    #     # === Update the Teacher Doc with the Supplier ID ===
    #     if supplier_name_id:
    #         # db_set updates the DB directly and updates the current object's value
    #         self.db_set('supplier_id', supplier_name_id)

    #     # === User Creation ===
    #     existing_user = frappe.db.exists("User", self.email)
    #     if existing_user:
    #         frappe.msgprint(f"User with email '{self.email}' already exists.")
    #     else:
    #         user = frappe.get_doc({
    #             "doctype": "User",
    #             "email": self.email,
    #             "first_name": self.full_name,
    #             "mobile_no": self.mobile_no,
    #             "enabled": 1,
    #             "user_type": "System User",
    #             "roles": [{"role": "TNC Teachers"}],
    #             "module_profile": "No Module"
    #         })

    #         try:
    #             user.insert(ignore_permissions=True)
    #             frappe.msgprint(f"User '{user.email}' created successfully.")
    #         except frappe.exceptions.DuplicateEntryError:
    #             pass 
    #         except Exception as e:
    #             frappe.msgprint(f"Failed to create User: {e}")

    def after_insert(self):
        """Automatically create/update Supplier and handle User roles when a Teacher is inserted."""

        # === 1. Supplier Logic (Keep your existing logic here) ===
        existing_supplier = frappe.db.get_value("Supplier", {"supplier_name": self.full_name}, "name")
        supplier_name_id = None

        if existing_supplier:
            supplier = frappe.get_doc("Supplier", existing_supplier)
            supplier.email_id = self.email
            supplier.save()
            supplier_name_id = supplier.name
        else:
            supplier = frappe.get_doc({
                "doctype": "Supplier",
                "supplier_name": self.full_name,
                "email_id": self.email,
                "supplier_group": "All Supplier Groups",
            })
            supplier.insert()
            supplier_name_id = supplier.name

        if supplier_name_id:
            self.db_set('supplier_id', supplier_name_id)

        # === 2. User & Role Assignment Logic ===
        target_role = "TNC Teachers"
        
        if frappe.db.exists("User", self.email):
            # User exists: Update roles if necessary
            user = frappe.get_doc("User", self.email)
            
            # Check if user already has the role
            has_role = any(r.role == target_role for r in user.roles)
            
            if not has_role:
                user.append("roles", {
                    "role": target_role
                })
                # Also ensure the user is enabled
                user.enabled = 1
                user.save(ignore_permissions=True)
                frappe.msgprint(f"Role '{target_role}' assigned to existing user {self.email}.")
            else:
                frappe.msgprint(f"User {self.email} already has the required role.")
                
        else:
            # User does not exist: Create new User
            user = frappe.get_doc({
                "doctype": "User",
                "email": self.email,
                "first_name": self.full_name,
                "mobile_no": self.mobile_no,
                "enabled": 1,
                "user_type": "System User",
                "roles": [{"role": target_role}],
                "module_profile": "No Module"
            })
            user.insert(ignore_permissions=True)
            frappe.msgprint(f"New User '{user.email}' created with role '{target_role}'.")

################################## Selected Timesheets to make the payment for the teachers ########################################
import frappe
from frappe.utils import flt, getdate
import json

# SAC for "Commercial training and coaching services". India Compliance requires an
# HSN/SAC on every Item (v1 predates that check), so activity items carry this code.
TEACHER_SERVICE_SAC = "999293"


def ensure_teacher_service_sac():
    """Create the GST HSN Code master row for TEACHER_SERVICE_SAC if missing."""
    if not frappe.db.exists("GST HSN Code", TEACHER_SERVICE_SAC):
        frappe.get_doc({
            "doctype": "GST HSN Code",
            "hsn_code": TEACHER_SERVICE_SAC,
            "description": "Commercial training and coaching services",
        }).insert(ignore_permissions=True)


def ensure_item_exists(item_code, uom="Nos"):
    """Creates an Item if it doesn't already exist."""
    if not frappe.db.exists("Item", item_code):
        ensure_teacher_service_sac()
        item = frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": item_code,
            "item_group": "Services",
            "gst_hsn_code": TEACHER_SERVICE_SAC,
            "stock_uom": uom,
            "is_stock_item": 0,
            "is_purchase_item": 1,
            "is_sales_item": 1,
            "description": f"Automatically created for activity: {item_code}"
        })
        item.insert(ignore_permissions=True)
        frappe.logger().info(f"Created missing Item: {item_code}")

@frappe.whitelist()
def create_purchase_order_for_selected_timesheets(teacher_name, name_of_the_teacher, start_date, end_date, timesheets):
    # print("RRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRR",type(timesheets))
    if isinstance(timesheets, str):
        try:
            timesheets = json.loads(timesheets)  # Convert JSON string to list
        except json.JSONDecodeError:
            timesheets = timesheets.split(",")  # Fallback: Split by comma

    if not teacher_name or not start_date or not end_date or not timesheets:
        frappe.throw("Teacher Name, Start Date, End Date, and at least one Timesheet are required.")

    start_date = getdate(start_date)
    end_date = getdate(end_date)

    if start_date > end_date:
        frappe.throw("Start Date cannot be after End Date.")

    teacher = frappe.get_doc("Teacher", teacher_name)
    if not teacher:
        frappe.throw(f"Teacher {teacher_name} not found.")

    # Get rates and UOMs for each activity from teacher settings
    activity_configs = {
        activity.activity_name: {"rate": activity.rate, "uom": activity.uom}
        for activity in teacher.teachers_activity_type
    }

    # Fetch selected Teachers Timesheets that are "Submitted" and don't have a Purchase Order
    timesheets_id = frappe.get_all(
        "Teachers Timesheet",
        filters={
            "teacher_id": teacher_name,
            "name": ["in", timesheets],
            "status": "Submitted",
            "purchase_order_id": ["is", "not set"]  # ✅ Correct filter
        },
        fields=["name"]
    )

    # print("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",timesheets_id)
    frappe.logger().info(f"Selected Timesheets without PO: {timesheets_id}")

    if not timesheets_id:
        frappe.msgprint("All selected timesheets already have a Purchase Order. No new PO was created.")
        return None  # Stop execution

    # Aggregate activity values
    activity_aggregates = {}
    for ts in timesheets_id:
        timesheet = frappe.get_doc("Teachers Timesheet", ts["name"])
        for row in timesheet.activity_type:
            if row.activity_name not in activity_aggregates:
                activity_aggregates[row.activity_name] = 0

            activity_aggregates[row.activity_name] += flt(row.qty)

    items = []
    for activity_name, total_qty in activity_aggregates.items():
        config = activity_configs.get(activity_name, {"rate": 0, "uom": "Hour"})
        rate = config["rate"]
        uom = config["uom"]

        if uom == "Hour":
            qty = total_qty / 60
            description = f"Payment for {activity_name} activities ({total_qty} minutes)"
        else:
            qty = total_qty
            description = f"Payment for {activity_name} activities ({total_qty} Nos)"

        # Ensure item exists before adding to items list
        ensure_item_exists(activity_name, uom)

        items.append({
            "item_code": activity_name,
            "qty": qty,
            "rate": rate,
            "description": description,
            "expense_account": "Services Rendered - IND"
        })

    if not items:
        frappe.msgprint("No activities found for selected timesheets.")
        return None

    timesheet_ids = ", ".join([ts["name"] for ts in timesheets_id])

    # Create Purchase Order
    purchase_order = frappe.get_doc({
        "doctype": "Purchase Order",
        "custom_starting_date": start_date,
        "custom_ending_date": end_date,
        "supplier": name_of_the_teacher,
        "transaction_date": frappe.utils.today(),
        "schedule_date": frappe.utils.today(),
        "custom_teacher_timesheets": timesheet_ids,
        "items": items,
    })
    purchase_order.insert()
    purchase_order.submit()
    frappe.db.commit()

    frappe.logger().info(f"Created Purchase Order: {purchase_order.name}")

    # Link items to PO for the Purchase Invoice
    pi_items = []
    for item in items:
        pi_item = item.copy()
        pi_item["purchase_order"] = purchase_order.name
        pi_items.append(pi_item)

    # Create Purchase Invoice
    purchase_invoice = frappe.get_doc({
        "doctype": "Purchase Invoice",
        "supplier": name_of_the_teacher,
        "transaction_date": frappe.utils.today(),
        "allocate_advances_automatically": 1,
        "due_date": frappe.utils.today(),
        "items": pi_items,
        "credit_to": "TNC Teachers Salary Paid A/c - IND"
    })
    purchase_invoice.insert()
    purchase_invoice.submit()
    frappe.db.commit()

    frappe.logger().info(f"Created Purchase Invoice: {purchase_invoice.name}")

    # invoice_outstanding = frappe.db.get_value("Purchase Invoice", purchase_invoice.name, "outstanding_amount")
    # frappe.logger().info(f"Purchase Invoice: {purchase_invoice.name}, Outstanding Amount: {invoice_outstanding}, Paid Amount: {paid_amount}")

    # Create Payment Entry
    paid_amount = sum([item["qty"] * item["rate"] for item in items])
    payment_entry = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Pay",
        "mode_of_payment": "Online",
        "party_type": "Supplier",
        "party": name_of_the_teacher,
        "paid_from": "BOI TNC A/c - Bank of india - IND",
        "paid_to": "TNC Teachers Salary Paid A/c - IND",
        "paid_amount": paid_amount,
        "received_amount": paid_amount,
        "reference_date": frappe.utils.today(),
        "reference_no": purchase_order.name,
        "references": [
            {
                "reference_doctype": "Purchase Invoice",
                "reference_name": purchase_invoice.name,
                "allocated_amount": paid_amount
            }
        ]
    })
    # payment_entry.insert(ignore_permissions=True)
    # payment_entry.submit()
    # frappe.db.commit()

    frappe.logger().info(f"Created Payment Entry: {payment_entry.name}")

    # Update purchase_order_id in related timesheets
    for ts in timesheets_id:
        timesheet_doc = frappe.get_doc("Teachers Timesheet", ts["name"])
        timesheet_doc.purchase_order_id = purchase_order.name
        timesheet_doc.db_update()
    frappe.db.commit()

    return purchase_order.name



################################################################################################

############################### Creating a Purchase order for the timesheeets #####################################
import frappe
from frappe.utils import flt, getdate

@frappe.whitelist()
def create_purchase_order(teacher_name, name_of_the_teacher, start_date, end_date):
    # print(teacher_name, name_of_the_teacher, start_date, end_date)
    # print("SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSs")
    # Validate inputs
    if not teacher_name or not start_date or not end_date:
        frappe.throw("Teacher Name, Start Date, and End Date are required.")

    # Ensure valid date range
    start_date = getdate(start_date)
    end_date = getdate(end_date)
    if start_date > end_date:
        frappe.throw("Start Date cannot be after End Date.")

    # Fetch Teacher document
    teacher = frappe.get_doc("Teacher", teacher_name)
    if not teacher:
        frappe.throw(f"Teacher {teacher_name} not found.")

    # Get rates and UOMs for each activity
    activity_configs = {
        activity.activity_name: {"rate": activity.rate, "uom": activity.uom}
        for activity in teacher.teachers_activity_type
    }

    # Fetch all Teachers Timesheet entries for the selected date range
    timesheets = frappe.get_all(
        "Teachers Timesheet",
        filters={
            "teacher_id": teacher_name,
            "status": "Submitted",
            "date": ["between", [start_date, end_date]]
        },
        fields=["name", "purchase_order_id"]
    )
    # print("FunCctionnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn",timesheets)
    # Check for timesheets with existing purchase_order_id
    timesheets_with_po = [ts for ts in timesheets if ts.get("purchase_order_id")]
    if timesheets_with_po:
        existing_po_ids = [ts.get("purchase_order_id") for ts in timesheets_with_po]
        frappe.throw(
            f"Purchase Order(s) already exist for some timesheets: {', '.join(existing_po_ids)}"
        )

    # Check if there are any valid timesheets left
    if not timesheets:
        frappe.throw(f"No submitted timesheets found for {teacher_name} between {start_date} and {end_date}.")

    # Aggregate activity values
    activity_aggregates = {}
    for ts in timesheets:
        timesheet = frappe.get_doc("Teachers Timesheet", ts["name"])
        for row in timesheet.activity_type:
            if row.activity_name not in activity_aggregates:
                activity_aggregates[row.activity_name] = 0

            activity_aggregates[row.activity_name] += flt(row.qty)

    # Prepare Purchase Order items
    items = []
    for activity_name, total_qty in activity_aggregates.items():
        config = activity_configs.get(activity_name, {"rate": 0, "uom": "Hour"})
        rate = config["rate"]
        uom = config["uom"]

        if uom == "Hour":
            qty = total_qty / 60
            description = f"Payment for {activity_name} activities ({total_qty} minutes)"
        else:
            qty = total_qty
            description = f"Payment for {activity_name} activities ({total_qty} Nos)"

        # Ensure item exists before adding to items list
        ensure_item_exists(activity_name, uom)

        items.append({
            "item_code": activity_name,
            "qty": qty,
            "rate": rate,
            "description": description,
            "expense_account": "Services Rendered - IND"  # Ensure this is a valid account
        })
    # print("ITemsssssssssssssssssItttttttttttttttttttttttt", items)
    # Create Purchase Orderqa1

    # Create a comma-separated string of timesheet names
    timesheet_ids = ", ".join([ts["name"] for ts in timesheets])
    purchase_order = frappe.get_doc({
        "doctype": "Purchase Order",
        "custom_starting_date": start_date,
        "custom_ending_date": end_date,
        "supplier": name_of_the_teacher,  # Assuming teacher acts as a supplier
        "transaction_date": frappe.utils.today(),
        "schedule_date": frappe.utils.today(),
        "custom_teacher_timesheets" : timesheet_ids,
        "items": items,
    })
    purchase_order.insert()
    purchase_order.submit()
    frappe.db.commit()
    # print("purchase_orderPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP", purchase_order.name)
    # Create Purchase Invoice linked to the Purchase Order
    # purchase_invoice = frappe.get_doc({
    #     "doctype": "Purchase Invoice",
    #     "supplier": name_of_the_teacher,
    #     "transaction_date": frappe.utils.today(),
    #     "allocate_advances_automatically": 1,  # Automatically allocate advances
    #     "due_date": frappe.utils.today(),  # Adjust due date as necessary
    #     "items": items,
    #     "credit_to" : "TNC Teachers Salary Paid A/c - IND"
    # })
    # purchase_invoice.insert()
    # purchase_invoice.submit()  # Submit the Purchase Invoice here
    # frappe.db.commit()

    # purchase_invoice.reload()
    # actual_outstanding = purchase_invoice.outstanding_amount

    # # Create Payment Entry (explicitly linking it to the Purchase Invoice)
    # paid_amount = sum([item["qty"] * item["rate"] for item in items])  # Total amount from PO items
    # if actual_outstanding > 0:
    #     payment_entry = frappe.get_doc({
    #         "doctype": "Payment Entry",
    #         "payment_type": "Pay",
    #         "mode_of_payment": "Online",  # Adjust the mode of payment
    #         "party_type": "Supplier",
    #         "party": name_of_the_teacher,  # Link to teacher as supplier
    #         "paid_from": "BOI TNC A/c - Bank of india - IND",  # Bank account from where payment is made
    #         "paid_to": "TNC Teachers Salary Paid A/c - IND",  # Bank account where payment is made
    #         "paid_amount": actual_outstanding,
    #         "received_amount": actual_outstanding,
    #         "reference_date": frappe.utils.today(),
    #         "reference_no": purchase_order.name,  # You can use PO name as reference
    #         "references": [
    #             {
    #                 "reference_doctype": "Purchase Invoice",
    #                 "reference_name": purchase_invoice.name,
    #                 "allocated_amount": actual_outstanding
    #             }
    #         ]
    #     })
        # payment_entry.insert(ignore_permissions=True)
        # payment_entry.submit()
        # frappe.db.commit()

    # Update purchase_order_id in related timesheets
    for ts in timesheets:
        timesheet_doc = frappe.get_doc("Teachers Timesheet", ts["name"])
        timesheet_doc.purchase_order_id = purchase_order.name
        timesheet_doc.db_update()
    frappe.db.commit()

    # return purchase_order.name
    return  purchase_order.name

################################################
@frappe.whitelist()
def get_unpaid_timesheets(teacher_name, start_date, end_date):
    """
    Fetches ONLY Approved Teachers Timesheets for Invoicing.
    """
    from frappe.utils import getdate
    
    # Only fetch "Approved" status
    timesheets = frappe.get_all(
        "Teachers Timesheet",
        filters={
            "teacher_id": teacher_name,
            "status": "Approved", # Changed from Submitted to Approved
            "date": ["between", [getdate(start_date), getdate(end_date)]]
        },
        fields=["name", "date", "grand_total"]
    )

    final_list = []
    for ts in timesheets:
        unpaid_activities = frappe.get_all(
            "Activities",
            filters={
                "parent": ts["name"],
                "purchase_invoice_id": ["is", "not set"] 
            },
            fields=["name", "activity_name", "qty", "uom"]
        )

        if unpaid_activities:
            ts["activities"] = unpaid_activities
            final_list.append(ts)

    return final_list

###################################################################

####################################### Below code is the scheduler to make the Payment for teachers everyday ########################################
import frappe
from frappe.utils import flt, getdate, nowdate, get_last_day, get_first_day

@frappe.whitelist()
def schedule_bulk_teachers_payment():
    # Get the start and end dates of the current month
    today = nowdate()
    current_month_start_date = get_first_day(today)
    current_month_end_date = get_last_day(today)

    # print("current_month_start_date", current_month_start_date)
    # print("current_month_end_date", current_month_end_date)

    # Log the start of the bulk payment process
    # frappe.log_error(f"Start Date: {current_month_start_date}, End Date: {current_month_end_date}", "Bulk Teachers Payment Scheduler")

    # Fetch all active teachers
    teachers = frappe.get_all("Teacher", filters={"status": "Active"}, fields=["name", "full_name"])

    if not teachers:
        frappe.log_error("No active teachers found.", "Bulk Teachers Payment Scheduler")
        return

    for teacher in teachers:
        try:
            # Fetch all submitted timesheets for the teacher in the date range
            timesheets = frappe.get_all(
                "Teachers Timesheet",
                filters={
                    "teacher_id": teacher["name"],
                    "status": "Approved",
                    "date": ["between", [current_month_start_date, current_month_end_date]]
                },
                fields=["name", "purchase_order_id"]
            )

            # Filter timesheets that do not have a purchase order assigned
            valid_timesheets = [ts for ts in timesheets if not ts.get("purchase_order_id")]

            # print("RRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRR", valid_timesheets)
            frappe.log_error(f"Valid Timesheets for {teacher['full_name']} ({teacher['name']}): {valid_timesheets}", "Bulk Teachers Payment Scheduler")

            if not valid_timesheets:
                frappe.log_error(
                    title=f"No valid timesheets for {teacher['full_name']} ({teacher['name']})",
                    message=f"All timesheets already have Purchase Orders or none are submitted."
                )
                continue  # Skip to the next teacher

            # Loop through valid timesheets
            for timesheet in valid_timesheets:
                # Fetch full timesheet details
                timesheet_doc = frappe.get_doc("Teachers Timesheet", timesheet["name"])

                # Extract teacher_id and teacher_name dynamically
                teacher_id = timesheet_doc.teacher_id
                teacher_name = timesheet_doc.teacher_name

                # print(f"Processing Timesheet: {timesheet['name']} | Teacher: {teacher_id} - {teacher_name}")
                # frappe.log_error(f"Processing Timesheet: {timesheet['name']} | Teacher: {teacher_id} - {teacher_name}", "Bulk Teachers Payment Scheduler")

                # Create Purchase Order
                create_purchase_order(
                    teacher_name=teacher_id,
                    name_of_the_teacher=teacher_name,
                    start_date=current_month_start_date,
                    end_date=current_month_end_date
                )

        except Exception as e:
            # Log any errors encountered
            frappe.log_error(
                title=f"Failed to create purchase order for {teacher['full_name']} ({teacher['name']})",
                message=frappe.get_traceback()
            )

########################################################################################################################################################



###################### Sending Bulk whatsapp messages to teachers fill the timesheet ########################################


import frappe
from tnc_v2_360ithub.notifications import send_whatsapp_to_mobile as send_custom_whatsapp_message  # provider-agnostic, logged
@frappe.whitelist()
def send_remainders():
    # frappe.log_error("Executing follow_up_payment_installments scheduler")
    """
    Server-side method to send remainders via WhatsApp to all active teachers.
    """
    try:
        # Fetch all active teachers with their mobile numbers and full names
        teachers = frappe.get_all(
            "Teacher",
            filters={"status": "Active"},
            fields=["full_name", "mobile_no"]
        )

        if not teachers:
            frappe.throw("No active teachers found to send remainders.")

        failed_sends = []

        for teacher in teachers:
            mobile_number = teacher.mobile_no
            full_name = teacher.full_name
            print("Mobile Number:", mobile_number)
            if mobile_number:
                # Dynamically generate the URL
                base_url = frappe.utils.get_url()  # Get the base URL of the Frappe application
                timesheet_url = f"{base_url}/app/teachers-timesheet/new-teachers-timesheet-pbjqbziuhr"

                # Prepare the message with the clickable link
                message = (
                    f"Hello {full_name}, this is a reminder to submit your timesheet.\n"
                    f"Please fill your timesheet here: {timesheet_url}"
                )
                try:
                    # Send the WhatsApp message
                    send_custom_whatsapp_message(mobile_number, message)
                    frappe.logger().info(f"Sent remainder to {full_name} ({mobile_number})")
                except Exception as send_error:
                    failed_sends.append({
                        "teacher": full_name,
                        "mobile_no": mobile_number,
                        "error": str(send_error)
                    })
                    frappe.log_error(
                        message=str(send_error),
                        title=f"Failed to send remainder to {full_name}"
                    )
            else:
                frappe.logger().warning(f"No mobile number for teacher {full_name}. Skipping.")

        if failed_sends:
            error_messages = [
                f"{item['teacher']} ({item['mobile_no']}): {item['error']}"
                for item in failed_sends
            ]
            frappe.throw(
                f"Failed to send remainders to the following teachers:\n" + "\n".join(error_messages)
            )

        return "Remainders have been successfully sent to all active teachers."

    except Exception as e:
        frappe.log_error(message=str(e), title="Error Sending Remainders")
        frappe.throw(f"An error occurred while sending remainders: {str(e)}")


##################### HTML Table in the custom script to show the teacher payments ########################################

import frappe
import frappe

# @frappe.whitelist()
# def get_teacher_payments(teacher_id):
#     if not teacher_id:
#         return {"error": "Teacher ID is required"}

#     # Fetch all records where purchase_order_id is not empty
#     records = frappe.get_all(
#         "Teachers Timesheet",
#         filters={"teacher_id": teacher_id, "purchase_order_id": ["is", "set"]},
#         fields=["purchase_order_id", "date", "teacher_id", "teacher_name", "status"],
#         order_by="date desc"
#     )

#     # Use a set to keep track of unique purchase_order_id
#     unique_records = []
#     seen_purchase_orders = set()

#     for record in records:
#         po_id = record["purchase_order_id"]
#         if po_id not in seen_purchase_orders:
#             seen_purchase_orders.add(po_id)

#             # Fetch PO details
#             po_data = frappe.db.get_value("Purchase Order", po_id, ["grand_total", "status"], as_dict=True) or {}
#             record["total_amount"] = po_data.get("grand_total")
#             record["po_status"] = po_data.get("status")

#             # Try to find linked PI
#             # In ERPNext, Purchase Invoice Item has 'purchase_order' field
#             pi_id = frappe.db.get_value("Purchase Invoice Item", {"purchase_order": po_id}, "parent")
#             if pi_id:
#                 pi_data = frappe.db.get_value("Purchase Invoice", pi_id, ["status", "outstanding_amount"], as_dict=True) or {}
#                 record["payment_status"] = pi_data.get("status")
#                 record["outstanding"] = pi_data.get("outstanding_amount")
#             else:
#                 # Fallback: if no PI linked, use PO status or mark as N/A
#                 record["payment_status"] = "N/A"
#                 record["outstanding"] = record["total_amount"]

#             unique_records.append(record)

#     return unique_records


@frappe.whitelist()
def get_teacher_payments(teacher_id):
    """
    Fetches unique Purchase Invoices generated from this Teacher's Timesheets
    to show Payment and Outstanding status in the Teacher Form.
    """
    if not teacher_id:
        return []

    # 1. Find all Timesheets for this teacher that have a linked Purchase Invoice
    # IMPORTANT: If your field name in 'Teachers Timesheet' is still 'purchase_order_id' 
    # but it contains PI numbers, change 'purchase_invoice_id' to 'purchase_order_id' below.
    records = frappe.get_all(
        "Teachers Timesheet",
        filters={
            "teacher_id": teacher_id, 
            "purchase_invoice_id": ["is", "set"] # Use the name of your link field
        },
        fields=["purchase_invoice_id"],
        order_by="date desc"
    )

    if not records:
        return []

    # 2. Get a unique list of Invoice IDs (sets remove duplicates)
    unique_invoice_ids = list(set(r.purchase_invoice_id for r in records))

    payment_data = []

    # 3. Fetch current status details from the Purchase Invoice Doctype
    for inv_id in unique_invoice_ids:
        # Check if the Invoice still exists
        inv_details = frappe.db.get_value(
            "Purchase Invoice", 
            inv_id, 
            ["name", "posting_date", "status", "grand_total", "outstanding_amount"], 
            as_dict=True
        )

        if inv_details:
            payment_data.append({
                "purchase_order_id": inv_details.name, # Key kept as 'purchase_order_id' for JS compatibility
                "date": inv_details.posting_date,
                "total_amount": inv_details.grand_total,
                "payment_status": inv_details.status, # ERPNext gives 'Unpaid', 'Paid', 'Partly Paid', 'Overdue'
                "outstanding": inv_details.outstanding_amount
            })

    # 4. Sort the list by date (most recent first)
    payment_data.sort(key=lambda x: x['date'], reverse=True)

    return payment_data



# @frappe.whitelist()
# def get_teacher_timesheets_for_portal(teacher_id, start_date, end_date, status="All"):
#     if not teacher_id or not start_date or not end_date:
#         return {"timesheets": [], "summary": {"draft": 0, "to_be_paid": 0, "paid": 0}}

#     # Base filters for the date range
#     base_filters = {
#         "teacher_id": teacher_id,
#         "date": ["between", [start_date, end_date]]
#     }

#     # Calculate summary data for the entire date range
#     all_ts = frappe.get_all(
#         "Teachers Timesheet",
#         filters=base_filters,
#         fields=["status", "grand_total", "purchase_order_id"]
#     )

#     summary = {"draft": 0, "to_be_paid": 0, "paid": 0}
#     for ts in all_ts:
#         if ts.status == "Draft":
#             summary["draft"] += flt(ts.grand_total)
#         elif ts.status == "Submitted":
#             if ts.purchase_order_id:
#                 summary["paid"] += flt(ts.grand_total)
#             else:
#                 summary["to_be_paid"] += flt(ts.grand_total)

#     # Apply status filter for the list view
#     list_filters = base_filters.copy()
#     if status == "Draft":
#         list_filters["status"] = "Draft"
#     elif status == "Approved":
#         list_filters["status"] = "Submitted"
#         list_filters["purchase_order_id"] = ["is", "not set"]
#     elif status == "Paid":
#         list_filters["status"] = "Submitted"
#         list_filters["purchase_order_id"] = ["is", "set"]

#     timesheets = frappe.get_all(
#         "Teachers Timesheet",
#         filters=list_filters,
#         fields=["name", "date", "grand_total", "purchase_order_id", "status"],
#         order_by="date desc"
#     )

#     for ts in timesheets:
#         ts["activities"] = frappe.get_all(
#             "Activities",
#             filters={"parent": ts["name"], "parenttype": "Teachers Timesheet"},
#             fields=["activity_name", "qty", "uom"]
#         )

#     return {
#         "timesheets": timesheets,
#         "summary": summary
#     }




##       Mohan script



import frappe
from frappe.utils import flt, getdate, today
import json
# @frappe.whitelist()
# def create_invoice_from_timesheets(teacher_name, timesheets, start_date, end_date):
#     if isinstance(timesheets, str):
#         timesheets = json.loads(timesheets)

#     teacher = frappe.get_doc("Teacher", teacher_name)
    
#     # 1. Aggregate activities
#     activity_aggregates = {}
#     activity_configs = {row.activity_name: {"rate": row.rate, "uom": row.uom} for row in teacher.teachers_activity_type}

#     for ts_name in timesheets:
#         # Get only the rows that haven't been invoiced
#         unpaid_rows = frappe.get_all("Activities", 
#             filters={"parent": ts_name, "purchase_invoice_id": ["is", "not set"]}, 
#             fields=["activity_name", "qty"])
        
#         for row in unpaid_rows:
#             if row.activity_name not in activity_aggregates:
#                 activity_aggregates[row.activity_name] = 0
#             activity_aggregates[row.activity_name] += flt(row.qty)

#     # 2. Create Items list for Purchase Invoice
#     items = []
#     for activity_name, total_qty in activity_aggregates.items():
#         config = activity_configs.get(activity_name, {"rate": 0, "uom": "Hour"})
#         qty = total_qty / 60 if config["uom"] == "Hour" else total_qty
        
#         items.append({
#             "item_code": activity_name,
#             "qty": qty,
#             "rate": config["rate"],
#             "expense_account": "Services Rendered - IND",
#             "description": f"Activities from {start_date} to {end_date}"
#         })

#     # 3. Generate and Submit Purchase Invoice
#     invoice = frappe.get_doc({
#         "doctype": "Purchase Invoice",
#         "supplier": teacher.full_name,
#         "posting_date": today(),
#         "due_date": today(),
#         "items": items,
#         "credit_to": "TNC Teachers Salary Paid A/c - IND"
#     })
#     invoice.insert()
#     invoice.submit()

#     # 4. Update the Parent and the Child Rows in Teachers Timesheet
#     for ts_name in timesheets:
#         # Update Parent
#         frappe.db.set_value("Teachers Timesheet", ts_name, "purchase_invoice_id", invoice.name)
        
#         # Update ALL child rows belonging to this timesheet that were just invoiced
#         frappe.db.sql("""
#             UPDATE `tabActivities` 
#             SET purchase_invoice_id = %s 
#             WHERE parent = %s AND (purchase_invoice_id IS NULL OR purchase_invoice_id = '')
#         """, (invoice.name, ts_name))

#     frappe.db.commit()
#     return invoice.name



# import frappe
# from frappe.utils import flt, today, nowdate
# import json

# @frappe.whitelist()
# def create_invoice_from_timesheets(teacher_name, timesheets, start_date, end_date):
#     if isinstance(timesheets, str):
#         timesheets = json.loads(timesheets)

#     teacher = frappe.get_doc("Teacher", teacher_name)
    
#     # 1. Aggregate activities from child tables
#     activity_aggregates = {}
    
#     # Map activity configuration from the Teacher Master
#     activity_configs = {
#         row.activity_name: {"rate": row.rate, "uom": row.uom} 
#         for row in teacher.teachers_activity_type
#     }

#     for ts_name in timesheets:
#         # Get only the child rows that haven't been linked to an invoice yet
#         unpaid_rows = frappe.get_all("Activities", 
#             filters={
#                 "parent": ts_name, 
#                 "purchase_invoice_id": ["is", "not set"]
#             }, 
#             fields=["activity_name", "qty"])
        
#         for row in unpaid_rows:
#             name = row.activity_name
#             if name not in activity_aggregates:
#                 activity_aggregates[name] = 0
            
#             # Since Qty in Timesheet is already in Hours (e.g. 1.5 for 90 mins), 
#             # we add it directly without dividing by 60
#             activity_aggregates[name] += flt(row.qty)

#     # 2. Build the Items list for Purchase Invoice
#     items = []
#     for activity_name, total_qty in activity_aggregates.items():
#         # Fallback to empty config if activity not found in Teacher settings
#         config = activity_configs.get(activity_name, {"rate": 0, "uom": "Nos"})
        
#         # LOGIC CORRECTED: Amount is simply consolidated Qty * Rate
#         # We no longer divide by 60 here.
#         qty = flt(total_qty)
#         rate = flt(config["rate"])
        
#         items.append({
#             "item_code": activity_name,
#             "qty": qty,
#             "rate": rate,
#             "uom": config["uom"],
#             "expense_account": "Services Rendered - IND",
#             "description": f"Service Period: {start_date} to {end_date}. Consolidated {qty} {config['uom']}."
#         })

#     if not items:
#         frappe.throw("No unpaid activities found in the selected timesheets.")

#     # 3. Generate and Submit Purchase Invoice
#     invoice = frappe.get_doc({
#         "doctype": "Purchase Invoice",
#         "supplier": teacher.full_name,
#         "posting_date": today(),
#         "due_date": today(),
#         "items": items,
#         "credit_to": "TNC Teachers Salary Paid A/c - IND"
#     })
    
#     invoice.insert()
#     invoice.submit()

#     # 4. Link Parent Timesheets and Child Activity rows to this Invoice
#     for ts_name in timesheets:
#         # Link the parent Teachers Timesheet
#         frappe.db.set_value("Teachers Timesheet", ts_name, {
#             "purchase_invoice_id": invoice.name,
#             "payment_status": "Unpaid" # Set initial status on submit
#         })
        
#         # Link only the child rows belonging to this timesheet that were part of this aggregation
#         frappe.db.sql("""
#             UPDATE `tabActivities` 
#             SET purchase_invoice_id = %s 
#             WHERE parent = %s AND (purchase_invoice_id IS NULL OR purchase_invoice_id = '')
#         """, (invoice.name, ts_name))

#     frappe.db.commit()
    
#     # Optional: Sync the Teacher Form specific payment ledger immediately
#     from tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher import sync_timesheet_payment_status_from_pi
#     sync_timesheet_payment_status_from_pi(invoice.name)

#     return invoice.name



import frappe
from frappe.utils import flt, today, getdate
import json

@frappe.whitelist()
def create_invoice_from_timesheets(teacher_name, timesheets, start_date, end_date):
    if isinstance(timesheets, str):
        timesheets = json.loads(timesheets)

    teacher = frappe.get_doc("Teacher", teacher_name)
    
    # 1. Prepare Individual rows (Not aggregated)
    items = []

    for ts_name in timesheets:
        # Fetch individual child rows from the current timesheet that haven't been invoiced
        unpaid_rows = frappe.get_all("Activities", 
            filters={
                "parent": ts_name, 
                "purchase_invoice_id": ["is", "not set"]
            }, 
            fields=["activity_name", "qty", "uom", "activity_fee", "description"])
        
        for row in unpaid_rows:
            # We fetch everything directly from the 'row' which represents the timesheet child data
            qty = flt(row.qty)
            rate = flt(row.activity_fee) # Based on the Timesheet value, not Teacher master

            ensure_item_exists(row.activity_name, row.uom)

            # 2. Append individual row with Timesheet ID in the description
            items.append({
                "item_code": row.activity_name,
                "qty": qty,
                "rate": rate,
                "uom": row.uom,
                "expense_account": "Services Rendered - IND",
                "description": f"Timesheet: {ts_name} | Activity: {row.activity_name} | {row.description or ''}"
            })

    if not items:
        frappe.throw("No unpaid activities found in the selected timesheets.")

    # 3. Generate and Submit Purchase Invoice
    invoice = frappe.get_doc({
        "doctype": "Purchase Invoice",
        "supplier": teacher.supplier_id,
        "posting_date": today(),
        "due_date": today(),
        "items": items,
        "credit_to": "TNC Teachers Salary Paid A/c - IND"
    })
    
    invoice.insert()
    invoice.submit()

    # 4. Link Parent Timesheets and Child Activity rows to this Invoice
    for ts_name in timesheets:
        # Link the parent Teachers Timesheet
        frappe.db.set_value("Teachers Timesheet", ts_name, {
            "purchase_invoice_id": invoice.name,
            "payment_status": "Unpaid" 
        })
        
        # Link specifically the child rows for this parent
        frappe.db.sql("""
            UPDATE `tabActivities` 
            SET purchase_invoice_id = %s 
            WHERE parent = %s AND (purchase_invoice_id IS NULL OR purchase_invoice_id = '')
        """, (invoice.name, ts_name))

    frappe.db.commit()
    
    # Trigger payment ledger sync
    try:
        from tnc_v2_360ithub.tnc_v2.doctype.teacher.teacher import sync_timesheet_payment_status_from_pi
        sync_timesheet_payment_status_from_pi(invoice.name)
    except Exception:
        pass

    return invoice.name

@frappe.whitelist()
def get_outstanding_invoices(supplier_name):
    return frappe.get_all("Purchase Invoice", 
        filters={
            "supplier": supplier_name, 
            "docstatus": 1, 
            "status": ["in", ["Unpaid", "Partly Paid"]]
        }, 
        fields=["name", "posting_date", "outstanding_amount as outstanding", "grand_total"])

# @frappe.whitelist()
# def create_payment_for_invoices(teacher_id, supplier_name, invoices):
#     if isinstance(invoices, str):
#         invoices = json.loads(invoices)

#     total_payment = sum([flt(i['outstanding']) for i in invoices])
    
#     payment_entry = frappe.get_doc({
#         "doctype": "Payment Entry",
#         "payment_type": "Pay",
#         "party_type": "Supplier",
#         "party": supplier_name,
#         "paid_from": "BOI TNC A/c - Bank of india - IND",
#         "paid_to": "TNC Teachers Salary Paid A/c - IND",
#         "paid_amount": total_payment,
#         "received_amount": total_payment,
#         "reference_no": f"Batch Payment - {today()}",
#         "reference_date": today(),
#         "references": []
#     })

#     for inv in invoices:
#         payment_entry.append("references", {
#             "reference_doctype": "Purchase Invoice",
#             "reference_name": inv['name'],
#             "allocated_amount": flt(inv['outstanding'])
#         })

#     payment_entry.insert()
#     # Note: Keeping as Draft so User can verify and Submit
#     return payment_entry.name


@frappe.whitelist()
def create_payment_for_invoices_v2(teacher_id, supplier_name, total_paid, references):
    """
    Creates a Payment Entry with explicit row-level allocations (Full or Partial).
    'references' is expected to be a list of dictionaries with name and allocated_amount.
    """
    if isinstance(references, str):
        references = json.loads(references)

    paid_amount = flt(total_paid)

    # 1. Initialize Payment Entry
    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = "Pay"
    pe.party_type = "Supplier"
    pe.party = supplier_name
    pe.posting_date = frappe.utils.today()
    
    # Banking details (Same as your configuration)
    pe.paid_from = "BOI TNC A/c - Bank of india - IND"
    pe.paid_to = "TNC Teachers Salary Paid A/c - IND"
    pe.paid_amount = paid_amount
    pe.received_amount = paid_amount
    
    # Reference Number for Audit
    pe.reference_no = f"Self Service Allocation"
    pe.reference_date = frappe.utils.today()

    # 2. Add allocated references (Handle partial logic here)
    for ref in references:
        pe.append("references", {
            "reference_doctype": "Purchase Invoice",
            "reference_name": ref.get("reference_name"),
            "total_amount": flt(ref.get("total_amount")),
            "outstanding_amount": flt(ref.get("outstanding_amount")),
            "allocated_amount": flt(ref.get("allocated_amount"))
        })

    pe.insert(ignore_permissions=True)
    
    # We leave it as Draft so the Accounts head can review/Submit
    return pe.name


import frappe
from frappe.utils import flt, getdate
import json

def sync_timesheet_payment_status_from_pi(invoice_name):
    """
    Checks the financial status of a Purchase Invoice and updates
    all linked Teachers Timesheets.
    """
    if not invoice_name:
        return

    # Fetch PI info including financial balances
    inv = frappe.db.get_value("Purchase Invoice", invoice_name, 
        ["status", "docstatus", "outstanding_amount", "grand_total"], as_dict=True)
    
    if not inv or inv.docstatus == 2:
        # If canceled or missing, revert to Unpaid
        target_status = "Unpaid"
    else:
        out = flt(inv.outstanding_amount)
        tot = flt(inv.grand_total)

        # Logic for "payment_status" in Teachers Timesheet
        if out <= 0:
            target_status = "Paid"
        elif out >= tot:
            target_status = "Unpaid"
        else:
            target_status = "Partially Paid"
    # frappe.log_error(f"Target status: {target_status}")
    # Update Parent
    frappe.db.sql("""
        UPDATE `tabTeachers Timesheet`
        SET payment_status = %s
        WHERE purchase_invoice_id = %s
    """, (target_status, invoice_name))
    
    frappe.db.commit()
# --- Hook Function: When Payment Entry is Submitted or Canceled ---
@frappe.whitelist()
def on_payment_entry_update(doc, method=None):
    # frappe.log_error("Paymesssssssssssssssssssssssssssssssssssssssssssssssssssssnt Entry Update")
    """
    Triggered on Payment Entry submit/cancel.
    Identifies linked Invoices to recalculate Teacher status.
    """
    # Look for Purchase Invoices in the 'references' table of the Payment Entry
    pi_list = []
    if hasattr(doc, "references"):
        for ref in doc.references:
            if ref.reference_doctype == "Purchase Invoice":
                pi_list.append(ref.reference_name)
    
    # Process each unique invoice found
    for invoice_id in set(pi_list):
        # print("Invoicessssssssssssssssssssssssss ID:", invoice_id)
        sync_timesheet_payment_status_from_pi(invoice_id)
# --- Hook Function: When Purchase Invoice is Canceled ---
@frappe.whitelist()
def on_purchase_invoice_cancel(doc, method=None):
    """
    Triggered on PI cancel. 
    Removes ID reference and sets status back to Unpaid.
    """
    frappe.db.sql("""
        UPDATE `tabTeachers Timesheet` 
        SET purchase_invoice_id = NULL, payment_status = 'Unpaid' 
        WHERE purchase_invoice_id = %s
    """, (doc.name,))
    
    frappe.db.sql("""
        UPDATE `tabActivities` 
        SET purchase_invoice_id = NULL 
        WHERE purchase_invoice_id = %s
    """, (doc.name,))
    
    frappe.db.commit()

# --- Hook Function: When Purchase Invoice is Submitted ---
@frappe.whitelist()
def on_purchase_invoice_submit(doc, method=None):
    """Triggered on PI submit."""
    sync_timesheet_payment_status_from_pi(doc.name)


@frappe.whitelist()
def unlink_timesheets_on_invoice_cancel(doc, method=None):
    """
    Called on 'on_cancel' of Purchase Invoice via hooks.py
    This will clear the reference to this Invoice in all Teachers Timesheets and Activities.
    """
    invoice_id = doc.name

    # 1. Clear 'purchase_invoice_id' in the Parent Doctype: Teachers Timesheet
    frappe.db.sql("""
        UPDATE `tabTeachers Timesheet` 
        SET purchase_invoice_id = NULL 
        WHERE purchase_invoice_id = %s
    """, (invoice_id,))

    # 2. Clear 'purchase_invoice_id' in the Child Table Doctype: Activities
    # Note: Using %s prevents SQL injection. 
    frappe.db.sql("""
        UPDATE `tabActivities` 
        SET purchase_invoice_id = NULL 
        WHERE purchase_invoice_id = %s
    """, (invoice_id,))

    # 3. Inform the user
    frappe.msgprint(f"Activities from Invoice <b>{invoice_id}</b> have been unlinked and can be invoiced again.")


@frappe.whitelist()
def get_outstanding_invoices_with_items(supplier_name):
    """
    Fetches outstanding Purchase Invoices along with their child item rows
    for a detailed preview in the Create Payment dialog.
    """
    invoices = frappe.get_all("Purchase Invoice", 
        filters={
            "supplier": supplier_name, 
            "docstatus": 1, 
            "status": ["in", ["Unpaid", "Partly Paid"]]
        }, 
        fields=["name", "posting_date", "outstanding_amount as outstanding", "grand_total"],
        order_by="posting_date asc"
    )

    for inv in invoices:
        # Fetch item details (activities) for this specific invoice
        inv["items"] = frappe.get_all("Purchase Invoice Item",
            filters={"parent": inv.name},
            fields=["item_code", "qty", "uom", "rate", "amount"]
        )

    return invoices



# @frappe.whitelist()
# def get_teacher_timesheets_for_portal(teacher_id, start_date, end_date, ts_status="All", inv_status="All", payment_status="All"):
#     from frappe.utils import flt
    
#     filters = {"teacher_id": teacher_id, "date": ["between", [start_date, end_date]]}
#     if ts_status != "All":
#         if ts_status == "Pending": filters["status"] = ["in", ["Draft", "Submitted", "Pending"]]
#         else: filters["status"] = ts_status

#     timesheets = frappe.get_all(
#         "Teachers Timesheet", filters=filters,
#         fields=["name", "date", "grand_total", "purchase_invoice_id", "status"],
#         order_by="date desc"
#     )

#     summary = {"total_unpaid": 0, "total_paid": 0, "total_partial": 0, "total_pending": 0}
#     final_list = []
#     pi_cache = {}

#     for ts in timesheets:
#         amt = flt(ts.grand_total)
#         ts["status"] = "Pending" if ts.status in ["Draft", "Submitted"] else ts.status

#         # Financial Calculations
#         current_pay_status = "Unpaid"
#         if ts["status"] == "Pending":
#             summary["total_pending"] += amt
#         elif ts["status"] == "Approved":
#             if not ts.purchase_invoice_id:
#                 summary["total_unpaid"] += amt
#             else:
#                 if ts.purchase_invoice_id not in pi_cache:
#                     pi_cache[ts.purchase_invoice_id] = frappe.db.get_value("Purchase Invoice", ts.purchase_invoice_id, ["status", "outstanding_amount", "grand_total"], as_dict=True)
                
#                 inv = pi_cache[ts.purchase_invoice_id]
#                 if inv and flt(inv.grand_total) > 0:
#                     ratio = amt / flt(inv.grand_total)
#                     outstanding_part = flt(inv.outstanding_amount) * ratio
#                     paid_part = amt - outstanding_part
#                     summary["total_paid"] += paid_part
#                     if inv.status == "Paid": current_pay_status = "Paid"
#                     elif inv.status == "Partly Paid": 
#                         current_pay_status = "Partially Paid"
#                         summary["total_partial"] += outstanding_part
#                     else: 
#                         current_pay_status = "Unpaid"
#                         summary["total_unpaid"] += outstanding_part

#         ts_invoiced = True if ts.purchase_invoice_id else False
#         match_inv = (inv_status == "All") or (inv_status == "Invoiced" and ts_invoiced) or (inv_status == "Not Invoiced" and not ts_invoiced)
#         match_pay = (payment_status == "All") or (payment_status == current_pay_status)

#         if match_inv and match_pay:
#             # Fetch Activity and concatenate descriptions from child rows
#             acts = frappe.get_all("Activities", filters={"parent": ts.name}, fields=["activity_name", "qty", "uom", "description"])
#             ts["activity_desc"] = ", ".join([f"{a.activity_name} ({a.qty} {a.uom})" for a in acts])
#             # Join non-empty child descriptions to show in table
#             ts["row_description"] = " | ".join([a.description for a in acts if a.description])
#             ts["payment_status"] = current_pay_status
#             final_list.append(ts)

#     return {"timesheets": final_list, "summary": summary}





@frappe.whitelist()
def get_teacher_timesheets_for_portal(teacher_id, start_date, end_date, ts_status="All", inv_status="All", payment_status="All"):
    from frappe.utils import flt
    
    filters = {"teacher_id": teacher_id, "date": ["between", [start_date, end_date]]}
    if ts_status != "All":
        if ts_status == "Pending": filters["status"] = ["in", ["Draft", "Submitted", "Pending"]]
        else: filters["status"] = ts_status

    timesheets = frappe.get_all(
        "Teachers Timesheet", filters=filters,
        fields=["name", "date", "grand_total", "purchase_invoice_id", "status"],
        order_by="date desc"
    )

    # Updated summary dictionary to include counts
    summary = {
        "total_unpaid": 0, "count_unpaid": 0, "unpaid_minutes": 0,
        "total_paid": 0, "count_paid": 0,
        "total_partial": 0, "count_partial": 0,
        "total_pending": 0, "count_pending": 0
    }
    final_list = []
    pi_cache = {}

    for ts in timesheets:
        amt = flt(ts.grand_total)
        ts["status"] = "Pending" if ts.status in ["Draft", "Submitted"] else ts.status

        # Child table logic - fetched upfront so duration is available for every row
        acts = frappe.get_all("Activities", filters={"parent": ts.name}, fields=["activity_name", "qty", "uom", "description"])
        duration_minutes = 0
        for a in acts:
            uom = (a.uom or "").strip().lower()
            if uom == "hour":
                duration_minutes += flt(a.qty) * 60
            elif uom == "minute":
                duration_minutes += flt(a.qty)
        ts["duration_minutes"] = duration_minutes
        ts["duration_formatted"] = format_duration(duration_minutes)
        ts["activity_desc"] = ", ".join([a.activity_name for a in acts])
        ts["row_description"] = " | ".join([a.description for a in acts if a.description])

        current_pay_status = "Unpaid"

        if ts["status"] == "Pending":
            summary["total_pending"] += amt
            summary["count_pending"] += 1
        elif ts["status"] == "Approved":
            if not ts.purchase_invoice_id:
                summary["total_unpaid"] += amt
                summary["count_unpaid"] += 1
                summary["unpaid_minutes"] += duration_minutes
            else:
                if ts.purchase_invoice_id not in pi_cache:
                    pi_cache[ts.purchase_invoice_id] = frappe.db.get_value("Purchase Invoice", ts.purchase_invoice_id, ["status", "outstanding_amount", "grand_total"], as_dict=True)

                inv = pi_cache[ts.purchase_invoice_id]
                if inv and flt(inv.grand_total) > 0:
                    ratio = amt / flt(inv.grand_total)
                    outstanding_part = flt(inv.outstanding_amount) * ratio
                    paid_part = amt - outstanding_part

                    if inv.status == "Paid":
                        current_pay_status = "Paid"
                        summary["total_paid"] += amt
                        summary["count_paid"] += 1
                    elif inv.status == "Partly Paid":
                        current_pay_status = "Partially Paid"
                        summary["total_partial"] += amt # Full amount of this TS is in 'Partial' bucket
                        summary["count_partial"] += 1
                    else:
                        current_pay_status = "Unpaid"
                        summary["total_unpaid"] += amt
                        summary["count_unpaid"] += 1
                        summary["unpaid_minutes"] += duration_minutes

        ts_invoiced = True if ts.purchase_invoice_id else False
        match_inv = (inv_status == "All") or (inv_status == "Invoiced" and ts_invoiced) or (inv_status == "Not Invoiced" and not ts_invoiced)
        match_pay = (payment_status == "All") or (payment_status == current_pay_status)

        if match_inv and match_pay:
            ts["payment_status"] = current_pay_status
            final_list.append(ts)

    summary["unpaid_duration_formatted"] = format_duration(summary["unpaid_minutes"])

    return {"timesheets": final_list, "summary": summary}


def format_duration(minutes):
    minutes = int(flt(minutes))
    if not minutes:
        return "0m"
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"



import frappe
from frappe import _
from frappe.utils import now_datetime

@frappe.whitelist()
def update_timesheet_status(name, target_status, reason=None):
    # 1. Fetch the Timesheet
    ts = frappe.get_doc("Teachers Timesheet", name)
    
    if target_status == "Approved":
        # 2. VALIDATION: Check Activities against Teacher's authorized list
        teacher = frappe.get_doc("Teacher", ts.teacher_id)
        
        # Create a dictionary of authorized activities for easy lookup
        # key: (activity_name, uom), value: rate
        auth_activities = {
            (d.activity_name, d.uom): flt(d.rate) 
            for d in teacher.teachers_activity_type 
        }

        # Validate every row in the timesheet
        for row in ts.activity_type:
            key = (row.activity_name, row.uom)
            
            if key not in auth_activities:
                frappe.throw(_("Row #{0}: Activity '{1}' with UOM '{2}' is not authorized for this Teacher.")
                             .format(row.idx, row.activity_name, row.uom))
            
            if auth_activities[key] <= 0:
                frappe.throw(_("Row #{0}: No valid rate found for '{1}' in Teacher's Master.")
                             .format(row.idx, row.activity_name))

        # 3. SET APPROVAL METADATA
        ts.status = "Approved"
        ts.approved_by = frappe.session.user
        ts.approved_on = now_datetime()
        ts.rejected_by = None # Clear rejection info if approved later
        ts.rejected_on = None
        ts.rejected_reason = None

    elif target_status == "Rejected":
        if not reason:
            frappe.throw(_("Please provide a reason for rejection."))
            
        # 4. SET REJECTION METADATA
        ts.status = "Rejected"
        ts.rejected_by = frappe.session.user
        ts.rejected_on = now_datetime()
        ts.rejected_reason = reason
        ts.approved_by = None # Clear approval info
        ts.approved_on = None

    ts.save(ignore_permissions=True)
    return True





import frappe
import json

@frappe.whitelist()
def create_teacher_from_employee(employee_id, activities):
    # Load Employee
    emp = frappe.get_doc("Employee", employee_id)
    
    if not emp.personal_email:
        frappe.throw(f"Personal Email is mandatory for Employee {emp.name} to create a Teacher.")

    # 1. Create the Teacher Doc
    # (The after_insert hook you shared will trigger automatically after teacher.insert())
    teacher = frappe.get_doc({
        "doctype": "Teacher",
        "full_name": emp.employee_name,
        "email": emp.personal_email,
        "mobile_no":emp.cell_number,
        "status": "Active",
    })

    # Add the child table rows from the prompt
    activities_list = json.loads(activities)
    for row in activities_list:
        teacher.append("teachers_activity_type", {
            "activity_name": row.get("activity_name"),
            "uom": row.get("uom"),
            "rate": row.get("rate")
        })

    teacher.insert()

    # 2. Update the Employee Record
    emp.db_set("custom_teacher", teacher.name)
    emp.db_set("user_id", emp.personal_email)
    emp.db_set("create_user_permission", 1)

    # 3. Create User Permission
    # Logic: User = Email, Allow = Teacher, For Value = Teacher Name
    if not frappe.db.exists("User Permission", {"user": emp.personal_email, "allow": "Teacher", "for_value": teacher.name}):
        user_permission = frappe.get_doc({
            "doctype": "User Permission",
            "user": emp.personal_email,
            "allow": "Teacher",
            "for_value": teacher.name,
            "is_default": 1
        })
        user_permission.insert(ignore_permissions=True)

    return teacher.name






