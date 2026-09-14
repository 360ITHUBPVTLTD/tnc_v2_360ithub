# Copyright (c) 2026, pankaj@360ithub.com and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, today

def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"label": _("Task ID"), "fieldname": "task_id", "fieldtype": "Link", "options": "Task", "width": 150},
        {"label": _("Subject"), "fieldname": "subject", "fieldtype": "Data", "width": 250},
        # {"label": _("Task Owner"), "fieldname": "task_owner", "fieldtype": "Link", "options": "User", "width": 150},
        {"label": _("Task Owner Name"), "fieldname": "task_owner_name", "fieldtype": "Data", "width": 150},
        # {"label": _("Task Reporter"), "fieldname": "task_reporter", "fieldtype": "Link", "options": "User", "width": 150},
        {"label": _("Task Reporter Name"), "fieldname": "task_reporter_name", "fieldtype": "Data", "width": 150},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
        {"label": _("Priority"), "fieldname": "priority", "fieldtype": "Data", "width": 100},
        {"label": _("Expected Start Date"), "fieldname": "exp_start_date", "fieldtype": "Date", "width": 120},
        {"label": _("Expected End Date"), "fieldname": "exp_end_date", "fieldtype": "Date", "width": 120},
        {"label": _("Overdue Days"), "fieldname": "overdue_days", "fieldtype": "Int", "width": 120},
    ]

def get_data(filters):
    conditions = []
    values = {}

    # 1. Check if the column actually exists in the database
    columns_in_db = frappe.db.get_table_columns("Task")
    has_reporter = "task_reporter" in columns_in_db
    # If you added it via Customize Form, it's likely "custom_task_reporter"
    if not has_reporter and "custom_task_reporter" in columns_in_db:
        has_reporter = True
        reporter_field = "custom_task_reporter"
    else:
        reporter_field = "task_reporter"

    if filters.get("date_range"):
        date_range = filters.get("date_range")
        if len(date_range) == 2:
            conditions.append("t.exp_start_date >= %(from_date)s")
            values["from_date"] = date_range[0]
            conditions.append("t.exp_start_date <= %(to_date)s")
            values["to_date"] = date_range[1]
    if filters.get("task_owner"):
        conditions.append("t.task_owner = %(task_owner)s")
        values["task_owner"] = filters.get("task_owner")
    if filters.get("department"):
        conditions.append("t.department = %(department)s")
        values["department"] = filters.get("department")
    if filters.get("priority"):
        conditions.append("t.priority = %(priority)s")
        values["priority"] = filters.get("priority")
    if filters.get("task_reporter"):
        conditions.append("t.task_reporter = %(task_reporter)s")
        values["task_reporter"] = filters.get("task_reporter")
    if filters.get("subject"):
        conditions.append("t.subject LIKE %(subject)s")
        values["subject"] = f"%{filters.get('subject')}%"

    status_filter = filters.get("status")
    if status_filter:
        if status_filter == "Overdue":
            conditions.append("t.status NOT IN ('Completed', 'Cancelled') AND t.exp_end_date IS NOT NULL AND t.exp_end_date < %(today)s")
            values["today"] = today()
        else:
            conditions.append("t.status = %(status)s")
            values["status"] = status_filter

    if has_reporter and filters.get("task_reporter"):
        conditions.append(f"t.{reporter_field} = %(task_reporter)s")
        values["task_reporter"] = filters.get("task_reporter")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    reporter_select = f"t.{reporter_field}" if has_reporter else "NULL AS task_reporter"
    reporter_name_select = "t.task_reporter_name" if "task_reporter_name" in columns_in_db else "NULL AS task_reporter_name"

    query = f"""
        SELECT
            t.name,
            t.subject,
            t.task_owner,
            t.task_owner_name,
            t.task_reporter,
            t.task_reporter_name,
            t.status,
            t.priority,
            t.exp_start_date,
            t.exp_end_date
        FROM `tabTask` t
        WHERE {where_clause}
    """
    
    tasks = frappe.db.sql(query, values, as_dict=True)
    
    today_date = getdate(today())
    
    data = []
    for t in tasks:
        overdue_days = 0
        if t.status not in ("Completed", "Cancelled") and t.exp_end_date:
            exp_date = getdate(t.exp_end_date)
            if today_date > exp_date:
                overdue_days = (today_date - exp_date).days
        
        data.append({
            "task_id": t.name,
            "subject": t.subject,
            "task_owner": t.task_owner,
            "task_owner_name": t.task_owner_name or t.task_owner,
            "task_reporter": t.task_reporter,
            "task_reporter_name": t.task_reporter_name or t.task_reporter,
            "status": t.status,
            "priority": t.priority,
            "exp_start_date": t.exp_start_date,
            "exp_end_date": t.exp_end_date,
            "overdue_days": overdue_days,
        })
        
    # Sort key function for default/custom sorting in python
    # Default Sorting: Overdue Days (Descending), Expected End Date (Ascending)
    sort_by = filters.get("sort_by") or "Overdue Days"
    sort_order = filters.get("sort_order") or "Descending"

    def sort_key(item):
        if sort_by == "Expected End Date":
            val = item.get("exp_end_date")
            return str(val) if val else "9999-12-31"
        elif sort_by == "Expected Start Date":
            val = item.get("exp_start_date")
            return str(val) if val else "9999-12-31"
        elif sort_by == "Overdue Days":
            return item.get("overdue_days", 0)
        elif sort_by == "Priority":
            prio = item.get("priority")
            prio_map = {"Urgent": 4, "High": 3, "Medium": 2, "Low": 1}
            return prio_map.get(prio, 0)
        elif sort_by == "Status":
            stat = item.get("status")
            stat_map = {"Open": 1, "Working": 2, "Pending Review": 3, "Overdue": 4, "Completed": 5, "Cancelled": 6}
            return stat_map.get(stat, 7)
        elif sort_by == "Task ID":
            return item.get("name") or ""
        elif sort_by == "Task Owner":
            return item.get("task_owner_name") or ""
        return item.get("overdue_days", 0)

    reverse = (sort_order == "Descending")
    # If sorting by Overdue Days, or Priority, or Status, descending is natural, otherwise handle appropriately.
    # But let's follow the standard python sort with reverse:
    if sort_by in ["Expected End Date", "Expected Start Date", "Task ID", "Task Owner"]:
        # For dates and strings, ascending order is standard. So if user asked for Descending, we reverse.
        data.sort(key=sort_key, reverse=reverse)
    else:
        # For numeric metrics like Overdue Days, Priority, default is descending (Highest to Lowest).
        # If user asked for Ascending, we reverse the standard descending sort.
        if sort_by == "Overdue Days":
            # Default sorting requirement: Overdue Days (Descending) then Expected End Date (Ascending)
            # Let's implement secondary sort key
            def default_sort_key(item):
                od = item.get("overdue_days", 0)
                eed = item.get("exp_end_date")
                eed_str = str(eed) if eed else "9999-12-31"
                # -od makes od descending when sorting ascending
                return (-od, eed_str)
            data.sort(key=default_sort_key)
            if sort_order == "Ascending":
                data.reverse()
        else:
            data.sort(key=sort_key, reverse=reverse)
    
    return data
