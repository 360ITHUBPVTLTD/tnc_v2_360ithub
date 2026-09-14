"""Read-only export of the live v1 schema for the doctypes v2 keeps.

Writes JSON under <app>/v1_schema_export/. Token from env TNC_TOKEN only.
Volatile fields (timestamps, owners, idx-less noise) are stripped so files diff cleanly.
"""
import json, os, sys, urllib.parse, urllib.request

B = "https://tnc.360ithub.com"
TOK = os.environ["TNC_TOKEN"]
OUT = sys.argv[1]
STRIP = {"modified", "modified_by", "owner", "creation", "docstatus", "_user_tags", "_comments", "_assign", "_liked_by", "__last_sync_on", "__onload", "__unsaved"}


def get(path, **params):
    q = urllib.parse.urlencode({k: json.dumps(v) if not isinstance(v, str) else v for k, v in params.items()})
    req = urllib.request.Request(f"{B}{urllib.parse.quote(path)}?{q}", headers={"Authorization": f"token {TOK}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def clean(d):
    if isinstance(d, dict):
        return {k: clean(v) for k, v in d.items() if k not in STRIP}
    if isinstance(d, list):
        return [clean(x) for x in d]
    return d


def write(rel, data):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(clean(data), open(p, "w"), indent=1, sort_keys=True, ensure_ascii=False)
    print("  wrote", rel, file=sys.stderr)


def doc(doctype, name):
    return get(f"/api/resource/{doctype}/{name}")["data"]


def lst(doctype, filters, fields=None, limit=2000):
    return get(f"/api/resource/{doctype}", filters=filters, fields=fields or ["name"], limit_page_length=limit)["data"]


# 1. Custom doctypes we port (full definitions, incl. child tables)
CUSTOM_DOCTYPES = [
    "Recurring Task", "Recurring Task Owner",
    "Teacher", "Teachers Timesheet", "Activities", "Activity", "Teachers Activity Type",
    "User Multiselect Clarity",
    "Institute Management Admin Settings",
]
for dt in CUSTOM_DOCTYPES:
    try:
        write(f"doctype/{dt.replace(' ', '_').lower()}.json", doc("DocType", dt))
    except Exception as e:
        print("  SKIP doctype", dt, str(e)[:80], file=sys.stderr)

# 2. Custom Fields + Property Setters on kept standard/custom doctypes
KEPT = ["Task", "Employee", "Employee Checkin", "User", "Expense Claim", "Leave Application", "Attendance",
        "Attendance Request", "Shift Type", "Recurring Task", "Teachers Timesheet", "Teacher", "Department", "Designation",
        "Supplier", "Purchase Invoice", "Payment Entry", "Holiday List"]
cf = lst("Custom Field", [["dt", "in", KEPT]], ["name"])
write("custom_field/all.json", [doc("Custom Field", r["name"]) for r in cf])
ps = lst("Property Setter", [["doc_type", "in", KEPT]], ["name"])
write("property_setter/all.json", [doc("Property Setter", r["name"]) for r in ps])

# 3. Roles, role profiles, permissions
roles = lst("Role", [["name", "like", "TNC%"]], ["name"]) + lst("Role", [["name", "in", ["Employee Self Service", "super Admin"]]], ["name"])
write("role/all.json", [doc("Role", r["name"]) for r in roles])
rps = lst("Role Profile", [["name", "like", "TNC%"]], ["name"]) + lst("Role Profile", [["name", "=", "super Admin"]], ["name"])
write("role_profile/all.json", [doc("Role Profile", r["name"]) for r in rps])
perms = lst("Custom DocPerm", [["parent", "in", KEPT + CUSTOM_DOCTYPES]], ["name"])
write("custom_docperm/all.json", [doc("Custom DocPerm", r["name"]) for r in perms])

# 4. Workspace, number cards, page, reports
for ws in ["TNC Task", "Teacher Management", "Employee Workspace", "HR Workspace", "TNC Employee", "TNC Admin"]:
    try:
        write(f"workspace/{ws.replace(' ', '_').lower()}.json", doc("Workspace", ws))
    except Exception as e:
        print("  SKIP workspace", ws, str(e)[:80], file=sys.stderr)
cards = lst("Number Card", [["document_type", "in", ["Task", "Recurring Task", "Teachers Timesheet"]]], ["name"])
write("number_card/all.json", [doc("Number Card", r["name"]) for r in cards])
write("page/task_dashboard.json", doc("Page", "task-dashboard"))
REPORTS = ["Teachers Timesheet Report", "Teachers Payable Report", "Monthly Teacher Task Summary Report", "Recurring task report",
           "Employee Attendance Report", "Monthly Attendance Report"]
for rp in REPORTS:
    try:
        write(f"report/{rp.replace(' ', '_').lower()}.json", doc("Report", rp))
    except Exception as e:
        print("  SKIP report", rp, str(e)[:80], file=sys.stderr)

# 5. Scheduler + notification config actually live
jobs = lst("Scheduled Job Type", [["method", "not like", "frappe.%"], ["method", "not like", "erpnext.%"], ["method", "not like", "hrms.%"], ["method", "not like", "india_compliance.%"]],
           ["name", "method", "frequency", "cron_format", "stopped"])
write("scheduled_job_type/custom_apps.json", jobs)
write("client_script/all.json", [doc("Client Script", r["name"]) for r in lst("Client Script", [], ["name"])])

# 6. Small live reference data worth carrying as-is
for dt in ["Activity", "Teachers Activity Type", "Holiday List", "Department", "Designation", "Expense Claim Type", "Leave Type"]:
    try:
        rows = lst(dt, [], ["name"], 500)
        write(f"data/{dt.replace(' ', '_').lower()}.json", [doc(dt, r["name"]) for r in rows])
    except Exception as e:
        print("  SKIP data", dt, str(e)[:80], file=sys.stderr)

print("done", file=sys.stderr)
