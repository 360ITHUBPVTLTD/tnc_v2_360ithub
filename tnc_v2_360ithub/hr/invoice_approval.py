# Copyright (c) 2026, 360ITHub and contributors
"""Purchase Invoice approval (SOW: approvals in the app for accounts entries).

A bill entered by hand is saved, sent for approval, and only an approver (TNC Settings >
Purchase Invoice approvers, or Administrator) can approve it; approving submits it. Teacher
payout invoices created from approved timesheets (custom_teacher set) skip this: their
timesheets were already approved. With no approvers listed, approval is off and invoices
submit as before. Same functions serve the desk and the mobile app.
"""
import frappe
from frappe import _
from frappe.utils import flt, now_datetime


def approvers():
	return [r.user for r in (frappe.get_cached_doc("TNC Settings").get("invoice_approvers") or []) if r.user]


def is_approver(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or user in approvers()


def requires_approval(doc):
	return bool(approvers()) and not doc.get("custom_teacher")


def before_submit(doc, method=None):
	"""Block a plain Submit on a bill that needs approval; an approver submitting counts as approving."""
	if not requires_approval(doc) or doc.get("custom_approval_status") == "Approved":
		return
	if is_approver():
		doc.custom_approval_status = "Approved"
		doc.custom_approved_by = frappe.session.user
		doc.custom_approved_on = now_datetime()
		doc.custom_approval_comment = doc.custom_approval_comment or _("Approved on submit")
		return
	frappe.throw(_("This bill needs approval before it can be submitted. It goes to the approver automatically when you save it. You will be notified once it is approved."), title=_("Approval required"))


def on_update(doc, method=None):
	"""Save = send. A non-approver saving a hand-entered draft puts it in front of the approvers;
	nothing to remember. Saving again while it waits changes nothing (no second notification).
	A rejected bill that is corrected and saved goes back for approval. Approvers are not
	auto-sent: their Submit counts as approval."""
	if doc.docstatus != 0 or not requires_approval(doc) or is_approver():
		return
	if doc.get("custom_approval_status") in ("Pending Approval", "Approved"):
		return
	_send(doc)


def _send(doc):
	from tnc_v2_360ithub import notifications
	doc.db_set({"custom_approval_status": "Pending Approval", "custom_sent_for_approval_by": frappe.session.user,
		"custom_approved_by": None, "custom_approved_on": None, "custom_approval_comment": None}, update_modified=False)
	note = (doc.get("custom_note_to_approver") or "").strip()
	doc.add_comment("Comment", _("Sent for approval") + (f": {frappe.utils.escape_html(note)}" if note else ""))
	who = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
	notifications.notify_users(approvers(), doc, _("{0} sent bill {1} ({2}, ₹{3}) for approval").format(who, doc.name, doc.supplier_name or doc.supplier, flt(doc.grand_total)), title=_("Purchase Invoice: approval needed"))


@frappe.whitelist()
def send_for_approval(name, note=None):
	from tnc_v2_360ithub import notifications
	doc = frappe.get_doc("Purchase Invoice", name)
	doc.check_permission("write")
	if doc.docstatus != 0:
		frappe.throw(_("Only a draft bill can be sent for approval."))
	if not requires_approval(doc):
		frappe.throw(_("This bill does not need approval; submit it directly."))
	if doc.custom_approval_status == "Pending Approval":
		frappe.throw(_("Already waiting for approval."))
	if note is not None:
		doc.db_set("custom_note_to_approver", (note or "").strip(), update_modified=False)
		doc.custom_note_to_approver = (note or "").strip()
	_send(doc)
	return {"status": "Pending Approval"}


@frappe.whitelist()
def decide(name, action, comment=None):
	"""Approver: Approved submits the bill, Rejected sends it back to the creator."""
	from tnc_v2_360ithub import notifications
	doc = frappe.get_doc("Purchase Invoice", name)
	if not is_approver():
		frappe.throw(_("You are not an approver for bills. Please ask an approver to decide this bill."), frappe.PermissionError)
	if doc.docstatus != 0 or doc.custom_approval_status != "Pending Approval":
		frappe.throw(_("This bill is not waiting for approval."))
	if action not in ("Approved", "Rejected"):
		frappe.throw(_("Unknown action."))
	comment = (comment or "").strip()
	if not comment:
		frappe.throw(_("Please write a short comment."))
	doc.custom_approval_status = action
	doc.custom_approved_by = frappe.session.user
	doc.custom_approved_on = now_datetime()
	doc.custom_approval_comment = comment
	doc.flags.ignore_permissions = True
	if action == "Approved":
		doc.submit()
	else:
		doc.save()
	doc.add_comment("Comment", _("{0}: {1}").format(_(action), frappe.utils.escape_html(comment)))
	who = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
	to = [u for u in {doc.custom_sent_for_approval_by, doc.owner} if u and u != frappe.session.user]
	notifications.notify_users(to, doc, _("Bill {0} ({1}, ₹{2}) was {3} by {4}: {5}").format(doc.name, doc.supplier_name or doc.supplier, flt(doc.grand_total), action.lower(), who, comment),
		title=_("Purchase Invoice {0}").format(action.lower()))
	return {"status": action}


@frappe.whitelist()
def my_rights():
	return {"approver": is_approver(), "approval_on": bool(approvers())}


SECTIONS = {
	"Pending": {"docstatus": 0, "custom_approval_status": "Pending Approval"},
	"Approved": {"docstatus": 1, "custom_approval_status": "Approved"},
	"Rejected": {"docstatus": 0, "custom_approval_status": "Rejected"},
}


@frappe.whitelist()
def bill_counts():
	"""App chips: how many bills sit in each section."""
	if not is_approver():
		return {}
	return {k: frappe.db.count("Purchase Invoice", f) for k, f in SECTIONS.items()}


@frappe.whitelist()
def pending(status="Pending"):
	"""For the app: bills in one section (Pending / Approved / Rejected), newest first, with items,
	attachments and, for decided bills, who decided, when and why."""
	if not is_approver():
		return []
	filters = SECTIONS.get(status) or SECTIONS["Pending"]
	rows = frappe.get_all("Purchase Invoice", filters=filters,
		fields=["name", "supplier", "supplier_name", "posting_date", "due_date", "bill_no", "bill_date", "net_total", "total_taxes_and_charges", "grand_total",
			"custom_expense_for", "custom_note_to_approver", "custom_sent_for_approval_by", "custom_approval_status", "custom_approved_by", "custom_approved_on", "custom_approval_comment", "remarks", "modified"],
		order_by="modified desc", limit=100)
	for r in rows:
		items = frappe.get_all("Purchase Invoice Item", filters={"parent": r.name}, fields=["item_name", "description", "qty", "uom", "rate", "amount"], order_by="idx asc")
		r["items"] = items
		r["item_summary"] = ", ".join(i.item_name for i in items[:4]) + (" …" if len(items) > 4 else "")
		r["sent_by_name"] = frappe.db.get_value("User", r.custom_sent_for_approval_by, "full_name") if r.custom_sent_for_approval_by else None
		r["decided_by_name"] = frappe.db.get_value("User", r.custom_approved_by, "full_name") if r.custom_approved_by else None
		r["attachments"] = frappe.get_all("File", filters={"attached_to_doctype": "Purchase Invoice", "attached_to_name": r.name}, pluck="file_url")
	return rows


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def supplier_query(doctype, txt, searchfield, start, page_len, filters):
	"""Supplier picker on a hand-entered bill: real suppliers only. Teachers are suppliers too, but
	their invoices come from approved timesheets (Create Invoice on the Teacher form), never by hand."""
	teacher_suppliers = [s for s in frappe.get_all("Teacher", pluck="supplier_id") if s]
	return frappe.db.sql("""
		select name, supplier_name, supplier_group from `tabSupplier`
		where disabled = 0 and (name like %(txt)s or supplier_name like %(txt)s)
		{exclude}
		order by if(locate(%(raw)s, name), locate(%(raw)s, name), 99999), name
		limit %(start)s, %(page_len)s""".format(exclude="and name not in %(teachers)s" if teacher_suppliers else ""),
		{"txt": f"%{txt}%", "raw": txt, "teachers": tuple(teacher_suppliers), "start": start, "page_len": page_len})
