frappe.listview_settings["Teacher"] = {
	onload: function (listview) {
		listview.page.add_inner_button(__("Send Remainders"), function () {
			frappe.confirm(
				"Are you sure you want to send the remainders?",
				() => {
					// Make a Frappe call to the server
					frappe.call({
						method: "tnc_v2_360ithub.teachers.doctype.teacher.teacher.send_remainders",
						callback: function (response) {
							if (response.message) {
								// Display the server's success message
								frappe.msgprint(response.message);
							} else {
								// Handle unexpected responses
								frappe.msgprint("Failed to send remainder.");
							}
						},
						error: function () {
							// Handle server call errors
							frappe.msgprint("An error occurred while sending remainders.");
						},
					});
				},
				() => {
					// User clicked No, do nothing
				},
			);
		}); // Icon and label
	},
};
