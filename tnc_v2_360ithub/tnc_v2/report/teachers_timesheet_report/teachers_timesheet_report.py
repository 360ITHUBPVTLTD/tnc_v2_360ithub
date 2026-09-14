# Copyright (c) 2025, pankaj@360ithub.com and contributors
# For license information, please see license.txt

# import frappe
from frappe import _


# def execute(filters: dict | None = None):
# 	"""Return columns and data for the report.

# 	This is the main entry point for the report. It accepts the filters as a
# 	dictionary and should return columns and data. It is called by the framework
# 	every time the report is refreshed or a filter is updated.
# 	"""
# 	columns = get_columns()
# 	data = get_data()

# 	return columns, data


# def get_columns() -> list[dict]:
# 	"""Return columns for the report.

# 	One field definition per column, just like a DocType field definition.
# 	"""
# 	return [
# 		{
# 			"label": _("Column 1"),
# 			"fieldname": "column_1",
# 			"fieldtype": "Data",
# 		},
# 		{
# 			"label": _("Column 2"),
# 			"fieldname": "column_2",
# 			"fieldtype": "Int",
# 		},
# 	]


# def get_data() -> list[list]:
# 	"""Return data for the report.

# 	The report data is a list of rows, with each row being a list of cell values.
# 	"""
# 	return [
# 		["Row 1", 1],
# 		["Row 2", 2],
# 	]





# ---############################## Report Logic #########################################
import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}

    columns = [
        {
            "label": _("Teacher ID"),
            "fieldname": "teacher_id",
            "fieldtype": "Link",
            "options": "Teacher",
            "width": 150
        },
        {
            "label": _("Teacher Name"),
            "fieldname": "teacher_name",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Online Class"),
            "fieldname": "online_class",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Offline Class"),
            "fieldname": "offline_class",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("YouTube Class"),
            "fieldname": "youtube_class",
            "fieldtype": "Data",
            "width": 150
        },
        # {
        #     "label": _("Question Preparation"),
        #     "fieldname": "question_preparation",
        #     "fieldtype": "Data",
        #     "width": 150
        # },
    ]

    data = get_teachers_aggregated_activities(filters)
    return columns, data

def get_default_date_range():
    """Return the first and last day of the current month as ["YYYY-MM-DD", "YYYY-MM-DD"]."""
    today = frappe.utils.getdate()
    return [
        frappe.utils.get_first_day(today).strftime("%Y-%m-%d"),
        frappe.utils.get_last_day(today).strftime("%Y-%m-%d"),
    ]

def get_teachers_aggregated_activities(filters):
    teacher_id = filters.get("teacher_id")        # e.g. TCH-0001
    date_range = filters.get("date_range") or get_default_date_range()

    timesheet_filters = {"status": "Approved"}

    if teacher_id:
        timesheet_filters["teacher_id"] = teacher_id

    if len(date_range) == 2:
        timesheet_filters["date"] = ["between", date_range]

    timesheets = frappe.get_all(
        "Teachers Timesheet",
        filters=timesheet_filters,
        fields=["name", "teacher_id", "teacher_name"]
    )

    if not timesheets:
        return []

    aggregator = {}

    for t in timesheets:
        t_doc = frappe.get_doc("Teachers Timesheet", t["name"])
        t_id = t_doc.teacher_id

        if t_id not in aggregator:
            aggregator[t_id] = {
                "teacher_id": t_id,               # Updated field
                "teacher_name": t_doc.teacher_name,  # New field for full name
                "online_class": 0,
                "offline_class": 0,
                "youtube_class": 0,
                "question_preparation": 0,
            }

        for row in t_doc.activity_type:
            if row.activity_name == "Online Class":
                aggregator[t_id]["online_class"] += row.qty or 0
            elif row.activity_name == "Offline Class":
                aggregator[t_id]["offline_class"] += row.qty or 0
            elif row.activity_name == "Youtube Class":
                aggregator[t_id]["youtube_class"] += row.qty or 0
            elif row.activity_name == "Question Preparation":
                aggregator[t_id]["question_preparation"] += row.qty or 0

    for teacher_id, summary in aggregator.items():
        summary["online_class"] = format_duration(summary["online_class"])
        summary["offline_class"] = format_duration(summary["offline_class"])
        summary["youtube_class"] = format_duration(summary["youtube_class"])
        summary["question_preparation"] = format_duration(summary["question_preparation"])

    return list(aggregator.values())

def format_duration(minutes):
    if not minutes:
        return "0"
    minutes = int(minutes)
    hours = minutes // 60
    mins = minutes % 60
    if hours and mins:
        return f"{hours}h {mins}m"
    elif hours:
        return f"{hours}h"
    else:
        return f"{mins}m"

# ---############################## PDF Download Logic #########################################

### **PDF Download Logic**
# ```python


import json
from frappe.utils.pdf import get_pdf
from frappe.utils.file_manager import save_file
from datetime import datetime

@frappe.whitelist()
def download_pdf(filters=None):
    # Parse filters if provided
    if filters:
        if isinstance(filters, str):
            filters = json.loads(filters)
        filters = frappe._dict(filters)
    else:
        filters = frappe._dict()  # Initialize as an empty dictionary if no filters are provided

    # Handle date range; default to the current month, same as the report's data logic
    if filters.get("date_range"):
        if len(filters.date_range) != 2:
            frappe.throw("Date range should contain both start and end date.")
    else:
        filters["date_range"] = get_default_date_range()

    try:
        start_date = datetime.strptime(filters.date_range[0], "%Y-%m-%d").strftime("%d-%m-%Y")
        end_date = datetime.strptime(filters.date_range[1], "%Y-%m-%d").strftime("%d-%m-%Y")
        formatted_date_range = f"{start_date} to {end_date}"
    except Exception as e:
        frappe.throw(f"Error parsing date range: {str(e)}")

    # Fetch teacher details if teacher_id is provided
    teacher_name = "All Teachers"
    teacher_id = None
    if filters.get("teacher_id"):
        teacher_doc = frappe.get_doc("Teacher", filters.teacher_id)
        teacher_name = teacher_doc.full_name
        teacher_id = teacher_doc.name

    # Execute report logic to get columns and data
    columns, data = execute(filters)

    # Render HTML for the PDF
    html = frappe.render_template("tnc_v2_360ithub/templates/reports/teachers_timesheet_pdf.html", {
        "columns": columns,
        "data": data,
        "filters": filters,
        "teacher_name": teacher_name,
        "formatted_date_range": formatted_date_range,
        "teacher_id": teacher_id
    })

    # Generate PDF
    pdf = get_pdf(html)

    # Create a filename based on filters or default to "All Data"
    file_name = f"Teachers_Timesheet_{teacher_id or 'All'}_{filters.date_range[0] if filters.get('date_range') else 'All'}_to_{filters.date_range[1] if filters.get('date_range') else 'Dates'}.pdf"
    file_doc = save_file(file_name, pdf, "Teachers Timesheet", frappe.session.user, is_private=0)

    return file_doc.file_url
