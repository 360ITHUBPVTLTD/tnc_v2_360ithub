# Copyright (c) 2026, 360ITHub and contributors
"""Teacher Penalty: create -> submit -> approve / reject -> (cancel).

Two separate lists in TNC Settings (SOW: separate controls): Penalty imposers create and submit,
Penalty approvers decide; the same person cannot do both on one record. Administrator can always
do either. The same checks serve the desk and the mobile app. Nothing here touches the accounts;
the recovery figures are kept for the accounting step and stay 0 until then.
"""
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

def _settings_users(field):
	return [r.user for r in (frappe.get_cached_doc("TNC Settings").get(field) or []) if r.user]


def imposers():
	return _settings_users("penalty_imposers")


def approvers():
	return _settings_users("penalty_approvers")


def is_imposer(user=None):
	"""Listed in TNC Settings, or Administrator. With an empty list every TNC Manager may impose."""
	user = user or frappe.session.user
	listed = imposers()
	if user == "Administrator" or user in listed:
		return True
	return not listed and bool({"TNC Manager", "TNC Super Admin", "System Manager"} & set(frappe.get_roles(user)))


def is_approver(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or user in approvers()


def teacher_user(teacher):
	"""The teacher's login, when they have one (Teacher.email is the User id)."""
	email = frappe.db.get_value("Teacher", teacher, "email")
	return email if email and frappe.db.exists("User", email) else None


class TeacherPenalty(Document):
	def validate(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be more than zero."))
		if self.is_new() or not self.imposed_by:
			self.imposed_by = frappe.session.user
		if self.docstatus == 0:
			self.status = "Draft"
			self.recovered_amount = self.waived_amount = self.outstanding_amount = 0

	def before_submit(self):
		if not is_imposer():
			frappe.throw(_("You are not allowed to impose penalties. Please ask the office."), frappe.PermissionError)
		self.status = "Submitted"

	def on_submit(self):
		from tnc_v2_360ithub import notifications
		msg = _("Penalty on {0}: {1} ₹{2} needs your approval").format(self.teacher_name or self.teacher, self.penalty_type, frappe.format_value(self.amount, {"fieldtype": "Currency"}).replace("₹", "").strip())
		notifications.notify_users(approvers(), self, msg, title=_("Teacher penalty: approval needed"))

	def before_cancel(self):
		# Approval is final (client meeting 6 Oct): no waiver, no refund. Cancel exists only to
		# correct a mistake, before any money moved, by an approver, with a reason (cancel_penalty).
		if flt(self.recovered_amount) > 0:
			frappe.throw(_("₹{0} of this penalty has already been deducted from a payment, so it cannot be cancelled.").format(self.recovered_amount))
		if not self.flags.cancel_reason:
			frappe.throw(_("Use 'Cancel penalty' and give the reason."))
		self.status = "Cancelled"
		self.outstanding_amount = 0

	def on_cancel(self):
		from tnc_v2_360ithub import notifications
		self.add_comment("Info", _("Cancelled: {0}").format(frappe.utils.escape_html(self.flags.cancel_reason or "")))
		notifications.notify_users([u for u in (teacher_user(self.teacher), self.imposed_by, self.approved_by) if u and u != frappe.session.user], self,
			_("Penalty {0} on {1} was cancelled: {2}").format(self.name, self.teacher_name or self.teacher, self.flags.cancel_reason or ""), title=_("Teacher penalty cancelled"))


@frappe.whitelist()
def decide(name, action, comment=None):
	"""Approver's Approve / Reject on a submitted penalty. Comment is required for both."""
	from tnc_v2_360ithub import notifications
	doc = frappe.get_doc("Teacher Penalty", name)
	if not is_approver():
		frappe.throw(_("You are not an approver for penalties."), frappe.PermissionError)
	# four-eyes rule, unless TNC Settings lists this user as both imposer and approver (or Administrator)
	if doc.imposed_by == frappe.session.user and frappe.session.user != "Administrator" and frappe.session.user not in imposers():
		frappe.throw(_("You imposed this penalty; another person must approve or reject it."), frappe.PermissionError)
	if doc.docstatus != 1 or doc.status != "Submitted":
		frappe.throw(_("Only a submitted penalty that is awaiting decision can be approved or rejected."))
	if action not in ("Approved", "Rejected"):
		frappe.throw(_("Unknown action."))
	comment = (comment or "").strip()
	if not comment:
		frappe.throw(_("Please write a short comment for the {0}.").format(_("approval") if action == "Approved" else _("rejection")))
	doc.db_set({"status": action, "approved_by": frappe.session.user, "decided_on": now_datetime(), "approval_comment": comment,
		"outstanding_amount": doc.amount if action == "Approved" else 0})
	doc.add_comment("Comment", _("{0}: {1}").format(action, frappe.utils.escape_html(comment)))
	who = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
	msg = _("Penalty {0} ({1}, ₹{2}) was {3} by {4}: {5}").format(doc.name, doc.penalty_type, doc.amount, action.lower(), who, comment)
	notifications.notify_users([u for u in (teacher_user(doc.teacher), doc.imposed_by) if u], doc, msg, title=_("Teacher penalty {0}").format(action.lower()))
	return {"status": action}


@frappe.whitelist()
def my_rights():
	"""For the desk form and the app: can this user impose / approve penalties?"""
	user = frappe.session.user
	return {"imposer": is_imposer(), "approver": is_approver(), "can_self_approve": user == "Administrator" or (is_approver() and user in imposers())}


# ---- Accounting: recovery on payment, waiver, refund ---------------------------------------------
# Nothing is booked at approval. The penalty is deducted from the teacher's next Payment Entry as a
# deduction to the account set in TNC Settings, so the Purchase Invoice is never altered (SOW).

def penalty_account():
	acc = frappe.db.get_single_value("TNC Settings", "penalty_account")
	if not acc:
		frappe.throw(_("The penalty recovery account is not set up yet. Please contact the administrator."))
	return acc


def outstanding_for_teacher(teacher):
	"""Approved penalties with money still to recover, oldest first."""
	return frappe.get_all("Teacher Penalty", filters={"teacher": teacher, "docstatus": 1, "status": ["in", ["Approved", "Recovered"]], "outstanding_amount": [">", 0]},
		fields=["name", "penalty_type", "penalty_date", "amount", "outstanding_amount"], order_by="penalty_date asc, name asc")


def plan_deduction(teacher, amount):
	"""How much of `amount` goes to penalties and to which ones. -> (deduction, [{penalty, amount}])"""
	left, plan = flt(amount), []
	for p in outstanding_for_teacher(teacher):
		if left <= 0:
			break
		take = min(left, flt(p.outstanding_amount))
		plan.append({"penalty": p.name, "amount": take, "penalty_type": p.penalty_type, "penalty_date": str(p.penalty_date)})
		left -= take
	return flt(amount) - left, plan


def _refresh_status(doc):
	rec, waived, out = flt(doc.recovered_amount), flt(doc.waived_amount), flt(doc.outstanding_amount)
	if out <= 0.005:
		if rec <= 0 and waived > 0:
			status = "Waived"
		elif rec <= 0 and any(r.entry_type == "Refund" for r in doc.recoveries):
			status = "Refunded"
		else:
			status = "Recovered"
	else:
		status = "Approved"
	doc.db_set("status", status, update_modified=False)


def apply_entry(name, entry_type, amount, reference_doctype=None, reference_name=None, remarks=None):
	"""Append one line to the recovery history and move the three figures. Used by payments, waiver, refund."""
	doc = frappe.get_doc("Teacher Penalty", name)
	if doc.docstatus != 1 or doc.status not in ("Approved", "Recovered", "Waived", "Refunded"):
		frappe.throw(_("Penalty {0} is {1}; only an approved penalty can be recovered, waived or refunded.").format(name, doc.status))
	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("Amount must be more than zero."))
	if entry_type in ("Recovery", "Waiver") and amount > flt(doc.outstanding_amount) + 0.005:
		frappe.throw(_("Penalty {0}: only ₹{1} is outstanding.").format(name, doc.outstanding_amount))
	if entry_type == "Refund" and amount > flt(doc.recovered_amount) + 0.005:
		frappe.throw(_("Penalty {0}: only ₹{1} was recovered, so at most that can be refunded.").format(name, doc.recovered_amount))
	row = doc.append("recoveries", {"entry_date": frappe.utils.today(), "entry_type": entry_type, "amount": amount, "reference_doctype": reference_doctype,
		"reference_name": reference_name, "remarks": remarks, "entered_by": frappe.session.user})
	row.db_insert()
	if entry_type == "Recovery":
		doc.recovered_amount = flt(doc.recovered_amount) + amount; doc.outstanding_amount = flt(doc.outstanding_amount) - amount
	elif entry_type == "Waiver":
		doc.waived_amount = flt(doc.waived_amount) + amount; doc.outstanding_amount = flt(doc.outstanding_amount) - amount
	else:  # Refund: money given back; the penalty is withdrawn for that amount, not re-opened
		doc.recovered_amount = flt(doc.recovered_amount) - amount
	doc.db_set({"recovered_amount": doc.recovered_amount, "waived_amount": doc.waived_amount, "outstanding_amount": doc.outstanding_amount}, update_modified=False)
	doc.add_comment("Info", _("{0} of ₹{1}{2}").format(_(entry_type), amount, f" ({reference_name})" if reference_name else "") + (f": {frappe.utils.escape_html(remarks)}" if remarks else ""))
	_refresh_status(doc)
	return doc


def on_journal_entry_cancel(doc, method=None):
	undo_reference("Journal Entry", doc.name)


def before_payment_entry_cancel(doc, method=None):
	"""Refuse to cancel a payment whose penalty deduction was later partly refunded; the refund goes first."""
	for r in frappe.get_all("Teacher Penalty Recovery", filters={"reference_doctype": "Payment Entry", "reference_name": doc.name, "entry_type": "Recovery"}, fields=["parent", "idx"]):
		if frappe.db.exists("Teacher Penalty Recovery", {"parent": r.parent, "entry_type": "Refund", "idx": [">", r.idx]}):
			frappe.throw(_("Penalty {0}: a refund was made after this deduction. Cancel the refund Journal Entry first.").format(r.parent))


def undo_reference(reference_doctype, reference_name):
	"""A Payment Entry or Journal Entry was cancelled: take its lines back out of every penalty."""
	rows = frappe.get_all("Teacher Penalty Recovery", filters={"reference_doctype": reference_doctype, "reference_name": reference_name}, fields=["name", "parent", "entry_type", "amount", "idx"])
	for r in rows:
		doc = frappe.get_doc("Teacher Penalty", r.parent)
		if r.entry_type == "Recovery":
			doc.recovered_amount = flt(doc.recovered_amount) - flt(r.amount); doc.outstanding_amount = flt(doc.outstanding_amount) + flt(r.amount)
		elif r.entry_type == "Waiver":
			doc.waived_amount = flt(doc.waived_amount) - flt(r.amount); doc.outstanding_amount = flt(doc.outstanding_amount) + flt(r.amount)
		else:
			doc.recovered_amount = flt(doc.recovered_amount) + flt(r.amount)
		frappe.delete_doc("Teacher Penalty Recovery", r.name, force=1, ignore_permissions=True)
		doc.db_set({"recovered_amount": doc.recovered_amount, "waived_amount": doc.waived_amount, "outstanding_amount": doc.outstanding_amount}, update_modified=False)
		doc.add_comment("Info", _("{0} cancelled: {1} of ₹{2} reversed").format(reference_name, _(r.entry_type), r.amount))
		doc.reload(); _refresh_status(doc)


@frappe.whitelist()
def cancel_penalty(name, reason):
	"""Correct a mistake (wrong teacher, wrong amount, duplicate) before anything is deducted.
	Approvers may cancel; the person who raised it may withdraw it while it still waits for approval."""
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Please give the reason for cancelling."))
	doc = frappe.get_doc("Teacher Penalty", name)
	if doc.docstatus != 1:
		frappe.throw(_("Only a submitted penalty can be cancelled."))
	own_waiting = doc.status == "Submitted" and doc.imposed_by == frappe.session.user
	if not (is_approver() or own_waiting):
		frappe.throw(_("Only a penalty approver can cancel a penalty."), frappe.PermissionError)
	doc.flags.cancel_reason = reason
	doc.flags.ignore_permissions = True
	doc.cancel()
	return {"status": "Cancelled"}


@frappe.whitelist()
def waive(name, amount=None, reason=None):
	"""Removed (client meeting 6 Oct): an approved penalty is final. Kept so an older app gets a clear answer."""
	frappe.throw(_("An approved penalty is final and cannot be waived."))


@frappe.whitelist()
def refund(name, amount=None, reason=None):
	"""Removed (client meeting 6 Oct): money deducted is not returned. Kept so an older app gets a clear answer."""
	frappe.throw(_("A penalty that has been deducted cannot be refunded."))


def get_permission_query_conditions(user=None):
	"""Teachers see only their own penalties; everyone else follows role permissions."""
	user = user or frappe.session.user
	roles = frappe.get_roles(user)
	if user == "Administrator" or user in imposers() or user in approvers() or {"System Manager", "TNC Super Admin", "TNC Manager"} & set(roles):
		return None
	if "TNC Teachers" in roles:
		teacher = frappe.db.get_value("Teacher", {"email": user}, "name")
		return f"`tabTeacher Penalty`.teacher = {frappe.db.escape(teacher)}" if teacher else "1=0"
	return None


def has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	roles = frappe.get_roles(user)
	if user == "Administrator" or user in imposers() or user in approvers() or {"System Manager", "TNC Super Admin", "TNC Manager"} & set(roles):
		return True
	if "TNC Teachers" in roles:
		return doc.teacher == frappe.db.get_value("Teacher", {"email": user}, "name")
	return False
