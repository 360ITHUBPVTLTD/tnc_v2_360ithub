// Copyright (c) 2026, Administrator and contributors
// For license information, please see license.txt

frappe.ui.form.on('Recurring Task', {
	refresh: function (frm) {
		frm.trigger('setup_buttons');
		frm.trigger('toggle_config_fields');
		frm.trigger('update_client_summary');
	},

	toggle_config_fields: function (frm) {
		const is_editable = (frm.doc.status === 'Draft' || frm.doc.status === 'Paused');
		const config_fields = [
			"frequency", "day_of_week", "repeat_by", "day_of_month", 
			"repeat_every", "unit", "start_date", "ends", "end_date", 
			"number_of_occurrences"
		];
		config_fields.forEach(field => {
			frm.toggle_enable(field, is_editable);
		});
	},

	setup_buttons: function (frm) {
		// Clear existing custom buttons to avoid duplication
		frm.clear_custom_buttons();

		if (frm.doc.docstatus === 0) {
			if (frm.doc.status === 'Active') {
				frm.add_custom_button(__('Pause Recurrence'), function () {
					frappe.confirm(
						'Are you sure you want to pause this recurrence?',
						function () {
							frm.call({
								doc: frm.doc,
								method: 'pause_recurrence',
								callback: function (r) {
									frm.reload_doc();
								}
							});
						}
					);
				}).addClass('btn-warning');

				frm.add_custom_button(__('Stop Recurrence'), function () {
					frappe.confirm(__('Are you sure you want to stop this recurrence permanently?'), function () {
						frm.call({
							doc: frm.doc,
							method: 'stop_recurrence',
							callback: function (r) {
								frm.reload_doc();
							}
						});
					});
				}).addClass('btn-danger');
			}
			else if (frm.doc.status === 'Paused' || frm.doc.status === 'Draft') {
				frm.add_custom_button(__('Resume/Start Recurrence'), function () {
					frappe.confirm(__('Are you sure you want to resume this recurrence?'), function () {
						frm.call({
							doc: frm.doc,
							method: 'resume_recurrence',
							callback: function (r) {
								frm.reload_doc();
							}
						});
					})
				}).addClass('btn-primary');
			}
			else if (frm.doc.status === 'Stopped') {
				// Stopped is permanent, so we don't show Resume. But we can show a message or allow manual restart if requested.
				// By user feedback "Stopped schedules should never resume automatically, use action buttons to control status."
				// If they want to resume, we can allow resume button as well, or keep it hidden.
				// Let's allow Resume from Stopped if the user explicitly clicks it.
				frm.add_custom_button(__('Restart Recurrence'), function () {
					frm.call({
						doc: frm.doc,
						method: 'resume_recurrence',
						callback: function (r) {
							frm.reload_doc();
						}
					});
				}).addClass('btn-primary');
			}
		}
	},

	frequency: function (frm) {
		const f = frm.doc.frequency;
		if (f !== 'Weekly') {
			frm.set_value('day_of_week', '');
		}
		if (f !== 'Monthly') {
			frm.set_value('repeat_by', '');
			frm.set_value('day_of_month', '');
		}
		if (f !== 'Custom') {
			frm.set_value('repeat_every', 1);
			frm.set_value('unit', '');
		}
		frm.trigger('update_client_summary');
	},

	day_of_week: function (frm) {
		frm.trigger('update_client_summary');
	},

	repeat_by: function (frm) {
		if (frm.doc.repeat_by !== 'Day of Month') {
			frm.set_value('day_of_month', '');
		}
		frm.trigger('update_client_summary');
	},

	day_of_month: function (frm) {
		frm.trigger('update_client_summary');
	},

	repeat_every: function (frm) {
		frm.trigger('update_client_summary');
	},

	unit: function (frm) {
		frm.trigger('update_client_summary');
	},

	start_date: function (frm) {
		frm.trigger('update_client_summary');
	},

	ends: function (frm) {
		if (frm.doc.ends !== 'On Date') {
			frm.set_value('end_date', '');
		}
		if (frm.doc.ends !== 'After Occurrences') {
			frm.set_value('number_of_occurrences', '');
		}
		frm.trigger('update_client_summary');
	},

	end_date: function (frm) {
		frm.trigger('update_client_summary');
	},

	number_of_occurrences: function (frm) {
		frm.trigger('update_client_summary');
	},

	update_client_summary: function (frm) {
		let summary = '';
		const f = frm.doc.frequency;

		if (f === 'Daily') {
			summary = 'Repeats every day.';
		} else if (f === 'Weekly') {
			summary = `Repeats every ${frm.doc.day_of_week || 'Monday'}.`;
		} else if (f === 'Monthly') {
			if (frm.doc.repeat_by === 'Day of Month') {
				let day = frm.doc.day_of_month || '1st';
				let suffix = 'th';
				if (day == '1' || day == '21' || day == '31') suffix = 'st';
				else if (day == '2' || day == '22') suffix = 'nd';
				else if (day == '3' || day == '23') suffix = 'rd';
				summary = `Repeats on the ${day}${suffix} of every month.`;
			} else if (frm.doc.repeat_by === 'Last Day of Month') {
				summary = 'Repeats on the last day of every month.';
			} else {
				summary = 'Repeats every month.';
			}
		} else if (f === 'Custom') {
			let every = frm.doc.repeat_every || 1;
			let unit = (frm.doc.unit || 'Days').toLowerCase();
			if (every === 1) {
				unit = unit.slice(0, -1); // singular
			}
			summary = `Repeats every ${every} ${unit}.`;
		}

		if (summary) {
			if (frm.doc.ends === 'On Date' && frm.doc.end_date) {
				summary += ` until ${frappe.datetime.str_to_user(frm.doc.end_date)}.`;
			} else if (frm.doc.ends === 'After Occurrences' && frm.doc.number_of_occurrences) {
				summary += ` for ${frm.doc.number_of_occurrences} occurrences.`;
			}
		}
		frm.set_value('recurrence_summary', summary);
	}
});
