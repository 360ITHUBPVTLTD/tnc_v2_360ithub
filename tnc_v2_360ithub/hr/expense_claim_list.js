// Expense Claim list (client ask): open with Expense For = All and Approval Status = Draft ("Open"),
// the same defaults as the mobile app. Buttons switch the status filter and carry live counts.
frappe.listview_settings["Expense Claim"] = Object.assign(frappe.listview_settings["Expense Claim"] || {}, {
	onload(listview) {
		// Always open on "Open" (Draft), whatever filter was used last time; a link that brings its
		// own status filter (route options) is the only exception. Runs after the list has finished
		// its own setup, and uses the normal add() so the list refreshes with the filter applied.
		const from_route = frappe.route_options && (frappe.route_options.approval_status || frappe.route_options.status);
		if (!from_route) {
			setTimeout(() => {
				const has_draft = (listview.filter_area.get() || []).some((f) => f[1] === "approval_status" && f[2] === "=" && f[3] === "Draft");
				if (has_draft) return;
				listview.filter_area.remove("approval_status");
				listview.filter_area.remove("status");
				listview.filter_area.add([["Expense Claim", "approval_status", "=", "Draft"]]);
			}, 300);
		}

		const set_status = (value) => {
			listview.filter_area.remove("approval_status");
			listview.filter_area.remove("status");
			if (value) listview.filter_area.add([["Expense Claim", "approval_status", "=", value]]);
		};
		const buttons = [["Open", "Draft"], ["Approved", "Approved"], ["Rejected", "Rejected"], ["All", null]];
		const $btn = {};
		buttons.forEach(([label, value]) => { $btn[label] = listview.page.add_inner_button(__(label), () => set_status(value)); });

		// counts: one call, refreshed whenever the list reloads (approve/reject/new claim)
		const refresh_counts = () => frappe.call({
			method: "frappe.client.get_list",
			args: { doctype: "Expense Claim", fields: ["approval_status", "count(name) as n"], group_by: "approval_status", limit_page_length: 0 },
		}).then((r) => {
			const by = {}; let total = 0;
			(r.message || []).forEach((row) => { by[row.approval_status] = row.n; total += row.n; });
			buttons.forEach(([label, value]) => {
				const n = value ? (by[value] || 0) : total;
				$btn[label].text(`${__(label)} (${n})`);
			});
		});
		refresh_counts();
		listview.page.wrapper.on("refresh-list", refresh_counts);
		const orig = listview.refresh.bind(listview);
		listview.refresh = (...a) => { const p = orig(...a); refresh_counts(); return p; };
	},
});
