# v1 schema export (source of truth for the parity port)

Read-only export from the live v1 site `tnc.360ithub.com`, taken **2026-09-11**
via the REST API with an Administrator key. Nothing on v1 was changed.

**Why this exists.** v1's shape lives in three places: app code on GitHub,
Custom Fields and Property Setters added on the site, and records such as
roles, workspaces and number cards. The code repos alone are incomplete, and the
deployed branches may differ from the repo defaults. The port therefore starts
from these files, not from notes or memory. The acceptance checklist in the
workspace repo (`docs/specs/tnc-v2/acceptance-checklist-v1-parity.md`) is checked
against v1 behaviour; this folder is checked against v1 **structure**.

**This is reference material, not installed fixtures.** Nothing here is loaded by
`hooks.py`. The build step turns the relevant parts into proper fixtures and
doctype folders under `tnc_v2_360ithub/`, and each file here is the thing to diff
against when asking "did we lose a field".

Volatile keys (`modified`, `owner`, `creation`, `docstatus`) were stripped so the
files diff cleanly. No passwords, keys or site config were exported; the only
match for a secret-looking word is the field name `custom_fcm_token`.

## Contents

| Folder | What | Count / notes |
|---|---|---|
| `doctype/` | Full DocType definitions of the custom doctypes v2 ports | Recurring Task, Recurring Task Owner, Teacher, Teachers Timesheet, Activities (child), Activity, Teachers Activity Type, User Multiselect Clarity (to be replaced by `Task Assignee`), Institute Management Admin Settings |
| `custom_field/all.json` | Custom Fields on kept doctypes | 96. Task 9, Employee 26, Employee Checkin 4, Department 8, Designation 3, Payment Entry 9, Purchase Invoice 28, Supplier 7, Attendance 1, Expense Claim 1. **43 belong to india_compliance** (module GST India / Income Tax India) and come with that app; **53 are site-level** and are the ones to port. |
| `property_setter/all.json` | Property Setters on kept doctypes | 71. Task 15, Employee 15, Purchase Invoice 21, Recurring Task 4, Teacher 5, Teachers Timesheet 5, Payment Entry 3, Supplier 3 |
| `role/all.json`, `role_profile/all.json` | TNC roles and role profiles | Roles: TNC Employee, TNC Employees, TNC Manager, TNC Super Admin, TNC Teachers, Employee Self Service. Profiles: TNC Employees, TNC Manager, TNC Super Admin, TNC Teacher, super Admin. Note the near-duplicate `TNC Employee` / `TNC Employees`; only the plural is used (46 users). |
| `custom_docperm/all.json` | Permission rows on kept doctypes | 112 |
| `workspace/` | Workspaces | TNC Task (the one people open), Teacher Management, Employee Workspace, HR Workspace, TNC Employee, TNC Admin |
| `number_card/all.json` | Task number cards | Completed, Overdue, Pending for Review, Pending |
| `page/task_dashboard.json` | The Page record for `task-dashboard` | Code is in `360ithub_institute_management`, not here |
| `report/` | Report records | Teachers Timesheet Report, Teachers Payable Report, Monthly Teacher Task Summary Report, Recurring task report, Employee Attendance Report, Monthly Attendance Report. Script report code is in the source repos. |
| `scheduled_job_type/custom_apps.json` | The six live custom scheduler jobs | 23:00 and 23:30 clarity attendance, 08:00 task WhatsApp digest, 07:30 recurring task run, daily overdue update, monthly teacher summary, plus the dead Team Task scheduler |
| `client_script/all.json` | Site client scripts | Employee form, RQ Job list |
| `data/` | Small reference data to carry as-is | Activity 9, Holiday List 2, Department 15, Designation 32, Expense Claim Type 5, Leave Type 6. Teachers Activity Type rows were not readable (403) and must be exported by an admin on v1. |

## Findings from the export that change the plan

- **No custom fields on User.** Confirmed in `custom_task.py`: the WhatsApp
  number for task notifications is `User.phone`, falling back to
  `User.mobile_no`; the Employee's `cell_number` is deliberately ignored.
  Checklist row A4 is resolved by that fact.
- **The Employee custom fields split two ways**: hrms and clarity own most of
  them (approvers, shift, geo-fencing, FCM token); only `custom_teacher` is
  TNC's. Port only that one into this app; the rest come from the shared apps.
- **Two TNC employee roles exist**, `TNC Employee` and `TNC Employees`. Carry
  the plural only, and map the singular to it at migration.

## Re-running

`export_v1_schema.py` in this folder; needs `TNC_TOKEN` (an Administrator API key:secret)
in the environment and a target directory. Re-run before cutover and diff, so a
v1 change made in the meantime is not missed.
