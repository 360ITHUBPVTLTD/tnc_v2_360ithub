frappe.pages["task-dashboard"].on_page_load = function (wrapper) {
	new TaskDashboard(wrapper);
};

class TaskDashboard {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: "",
			single_column: true
		});
		this.wrapper.find('.page-head').hide();
		this.wrapper.closest('.standard-filter-section').hide(); // Hide standard filters if any
		this.wrapper.css('overflow-x', 'hidden');

		this.filters = {
			status: ["Open", "Working", "Pending Review", "Overdue"]
		};
		this.start = 0;
		this.page_length = 20;
		this.sort_field = "creation";
		this.sort_order = "desc";
		this.leaderboard_sort_field = "completed_count";
		this.leaderboard_sort_order = "asc";

		this.make();
		this.bind_events();
		this.load();
	}

	make() {
		$(this.page.main).html(`
			<div class="task-dashboard-page">
				<div class="task-dashboard-header-card">
					<div class="header-left" style="display: flex; align-items: center; gap: 24px; flex-wrap: wrap;">
						<div class="header-copy">
							<h1 class="dashboard-title">Task Dashboard</h1>
						</div>
						<div class="small-kpis" id="task-kpis" style="display: flex; gap: 12px; flex-wrap: wrap;"></div>
					</div>
					<div class="header-actions">
						<button class="btn btn-light" id="go-dashboard"><i class="fa fa-home"></i> Go to Dashboard</button>
						<button class="btn btn-light" id="go-task"><i class="fa fa-tasks"></i> Create Task </button>
						<button class="btn btn-success" id="export-tasks"><i class="fa fa-file-excel-o"></i> Export Excel</button>
					</div>
				</div>

				<div class="dashboard-tabs">
					<button class="dashboard-tab active" data-tab="task-list">Task List</button>
					<button class="dashboard-tab" data-tab="leaderboard">Performance Leaderboard</button>
				</div>

				<div id="task-list-tab" class="tab-content active">

				<div class="task-filter-card">
<div class="task-filter-row compact">
	<div class="filter-group search-group">
		<label>Search</label>
		<input type="text" class="form-control" id="search-task" placeholder="Search by Task ID or Subject">
	</div>

	<div class="filter-group custom-multiselect" id="ms-owner" data-filter="Owner">
		<label>Owner</label>
		<div class="multiselect-header">
			<span class="multiselect-selected-text">All Owners</span>
			<i class="fa fa-chevron-down"></i>
		</div>
		<div class="multiselect-dropdown" style="display: none;">
			<div class="multiselect-search">
				<input type="text" class="form-control" placeholder="Search...">
			</div>
			<div class="multiselect-options" id="filter-owner-options"></div>
		</div>
	</div>

	<div class="filter-group custom-multiselect" id="ms-status" data-filter="Status">
		<label>Status</label>
		<div class="multiselect-header">
			<span class="multiselect-selected-text">All Statuses</span>
			<i class="fa fa-chevron-down"></i>
		</div>
		<div class="multiselect-dropdown" style="display: none;">
			<div class="multiselect-search">
				<input type="text" class="form-control" placeholder="Search...">
			</div>
			<div class="multiselect-options" id="filter-status-options"></div>
		</div>
	</div>

	<div class="filter-group custom-multiselect" id="ms-priority" data-filter="Priority">
		<label>Priority</label>
		<div class="multiselect-header">
			<span class="multiselect-selected-text">All Priorities</span>
			<i class="fa fa-chevron-down"></i>
		</div>
		<div class="multiselect-dropdown" style="display: none;">
			<div class="multiselect-search">
				<input type="text" class="form-control" placeholder="Search...">
			</div>
			<div class="multiselect-options" id="filter-priority-options"></div>
		</div>
	</div>

	<div class="filter-group date-range-group">
		<label>Expected End Date</label>
		<div class="date-inputs unified-range" id="filter-date-range-container"></div>
	</div>

	<div class="filter-group button-group">
		<label>&nbsp;</label>
		<button class="btn btn-secondary" id="clear-filters">Clear</button>
	</div>
</div>

<div class="active-filters" id="active-filters"></div>
</div>
<div class="task-table-card">
					<div class="table-responsive">
						<table class="table table-bordered task-table">
							<thead>
								<tr>
									<th>S.No</th>
									<th>Subject</th>
									<th class="sortable" data-sort="task_owner_name" title="Click to sort" style="cursor: pointer; user-select: none;">Task Owner <i class="fa fa-sort" style="margin-left: 5px;"></i></th>
									<th class="sortable" data-sort="task_reporter_name" title="Click to sort" style="cursor: pointer; user-select: none;">Task Reporter <i class="fa fa-sort" style="margin-left: 5px;"></i></th>
									<th class="sortable" data-sort="exp_start_date" title="Click to sort" style="cursor: pointer; user-select: none;">Expected Start Date <i class="fa fa-sort" style="margin-left: 5px;"></i></th>
									<th class="sortable" data-sort="exp_end_date" title="Click to sort" style="cursor: pointer; user-select: none;">Expected End Date <i class="fa fa-sort" style="margin-left: 5px;"></i></th>
									<th class="sortable" data-sort="status" title="Click to sort" style="cursor: pointer; user-select: none;">Status <i class="fa fa-sort" style="margin-left: 5px;"></i></th>
									<th class="sortable" data-sort="priority" title="Click to sort" style="cursor: pointer; user-select: none;">Priority <i class="fa fa-sort" style="margin-left: 5px;"></i></th>
									<th>Overdue</th>
									<th>Latest Comment</th>
									<th>Actions</th>
								</tr>
							</thead>
							<tbody id="task-table-body"></tbody>
						</table>
					</div>

					<div class="task-pagination">
						<button class="btn btn-light" id="load-more">Load More</button>
					</div>
				</div>
				</div>

				<div id="leaderboard-tab" class="tab-content" style="display: none;"></div>

			</div>
		`);

		this.date_range_field = frappe.ui.form.make_control({
			df: {
				fieldtype: "DateRange",
				fieldname: "date_range",
				placeholder: "Select Date Range",
				onchange: () => {
					this.start = 0;
					this.set_filters();
					this.load();
					if ($("#leaderboard-tab").is(":visible")) {
						this.load_leaderboard();
					}
				}
			},
			parent: this.wrapper.find("#filter-date-range-container"),
			render_input: true
		});
		if (this.date_range_field && this.date_range_field.$input) {
			this.date_range_field.$input.addClass("form-control");
		}

		if (this.date_range_field) {
			this.date_range_field.refresh();
		}

		this.load_filter_options();
	}

	bind_events() {
		const me = this;

		let search_timeout;
		this.wrapper.on("input", "#search-task", function () {
			clearTimeout(search_timeout);
			search_timeout = setTimeout(() => {
				me.start = 0;
				me.set_filters();
				me.load();
				if ($("#leaderboard-tab").is(":visible")) {
					me.load_leaderboard();
				}
			}, 500);
		});

		this.wrapper.on("click", ".dashboard-tab", function () {
			$(".dashboard-tab").removeClass("active");
			$(this).addClass("active");

			const tab = $(this).data("tab");
			$(".tab-content").hide();
			$(`#${tab}-tab`).show();

			if (tab === "leaderboard") {
				me.load_leaderboard();
			}
		});

		this.wrapper.on("click", "th.sortable", function () {
			const field = $(this).data("sort");
			const is_leaderboard = $(this).closest("#leaderboard-tab").length > 0;

			if (is_leaderboard) {
				if (me.leaderboard_sort_field === field) {
					me.leaderboard_sort_order = me.leaderboard_sort_order === "asc" ? "desc" : "asc";
				} else {
					me.leaderboard_sort_field = field;
					me.leaderboard_sort_order = "asc";
				}
				me.load_leaderboard();
			} else {
				if (me.sort_field === field) {
					me.sort_order = me.sort_order === "asc" ? "desc" : "asc";
				} else {
					me.sort_field = field;
					me.sort_order = "asc";
				}
				me.start = 0;
				me.load();
			}

			me.update_sort_icons();
		});

		this.wrapper.on("click", "#clear-filters", function () {
			me.start = 0;
			me.clear_filters();
			me.load();
		});

		this.wrapper.on("click", "#load-more", function () {
			me.start += me.page_length;
			me.load(true);
		});

		this.wrapper.on("click", "#export-tasks", function () {
			me.export_tasks();
		});

		this.wrapper.on("click", "#go-dashboard", function () {
			frappe.set_route("desk");
		});
		this.wrapper.on("click", "#go-task", function () {
			frappe.set_route("Form", "Task", "new-task");
		});

		this.wrapper.on("click", ".open-task", function () {
			const task = $(this).data("name");
			frappe.set_route("Form", "Task", task);
		});

		this.wrapper.on("click", ".add-comment", function () {
			const task = $(this).data("name");
			me.open_comment_dialog(task);
		});

		this.wrapper.on("click", ".small-kpi-card", function () {
			const filter = $(this).data("filter");

			if (me.filters.card_filter === filter) {
				delete me.filters.card_filter;
				$(this).removeClass("active");
			} else {
				me.filters.card_filter = filter;
				$(".small-kpi-card").removeClass("active");
				$(this).addClass("active");
			}

			me.start = 0;
			me.load();
		});
		this.setup_multiselect();
	}

	setup_multiselect() {
		const me = this;

		this.wrapper.on("click", ".custom-multiselect .multiselect-header", function (e) {
			e.stopPropagation();
			const $dropdown = $(this).siblings(".multiselect-dropdown");
			const isVisible = $dropdown.is(":visible");
			$(".multiselect-dropdown").hide();
			if (!isVisible) {
				$dropdown.show();
				$dropdown.find("input").focus();
			}
		});

		this.wrapper.on("keyup", ".custom-multiselect .multiselect-search input", function () {
			const text = $(this).val().toLowerCase();
			const $options = $(this).closest(".multiselect-dropdown").find(".multiselect-option");
			$options.each(function () {
				const val = $(this).text().toLowerCase();
				if (val.includes(text)) {
					$(this).show();
				} else {
					$(this).hide();
				}
			});
		});

		this.wrapper.on("change", ".custom-multiselect input[type='checkbox']", function () {
			const $ms = $(this).closest(".custom-multiselect");
			const checked = $ms.find("input[type='checkbox']:checked");
			let text = "All " + $ms.data("filter") + "s";
			if (checked.length === 1) {
				text = checked.closest("label").find(".option-text").text().trim();
			} else if (checked.length > 1) {
				text = checked.length + " selected";
			}
			$ms.find(".multiselect-selected-text").text(text);

			me.start = 0;
			me.set_filters();
			me.load();
			if ($("#leaderboard-tab").is(":visible")) {
				me.load_leaderboard();
			}
		});

		$(document).on("click", function (e) {
			if (!$(e.target).closest(".custom-multiselect").length) {
				$(".multiselect-dropdown").hide();
			}
		});
	}

	get_multiselect_values(id) {
		const checked = this.wrapper.find(`#${id} input[type='checkbox']:checked`);
		return checked.map(function () { return $(this).val(); }).get();
	}

	set_filters() {
		const current_card_filter = this.filters.card_filter;
		let dates = this.date_range_field ? this.date_range_field.get_value() : null;
		let from_date = "", to_date = "";
		if (dates && dates.length === 2) {
			from_date = dates[0];
			to_date = dates[1];
		}

		this.filters = {
			search: $("#search-task").val(),
			status: this.get_multiselect_values("ms-status"),
			priority: this.get_multiselect_values("ms-priority"),
			task_owner: this.get_multiselect_values("ms-owner"),
			from_date: from_date,
			to_date: to_date
		};
		if (current_card_filter) {
			this.filters.card_filter = current_card_filter;
		}
	}

	clear_filters() {
		this.filters = {
			status: ["Open", "Working", "Pending Review", "Overdue"]
		};
		$("#search-task").val("");
		if (this.date_range_field) {
			this.date_range_field.set_value(null);
		}
		$(".custom-multiselect input[type='checkbox']").prop("checked", false);

		$("#filter-status-options input[type='checkbox']").each(function () {
			const val = $(this).val();
			if (val !== "Completed" && val !== "Cancelled") {
				$(this).prop("checked", true);
			}
		});

		$(".custom-multiselect").each(function () {
			const $ms = $(this);
			const checked = $ms.find("input[type='checkbox']:checked");
			if (checked.length > 0) {
				$ms.find(".multiselect-selected-text").text(checked.length + " selected");
			} else {
				$ms.find(".multiselect-selected-text").text("All " + $ms.data("filter") + "s");
			}
		});
		$(".small-kpi-card").removeClass("active");
	}

	async load_filter_options() {
		const r = await frappe.call({
			method: "tnc_v2_360ithub.tasks.page.task_dashboard.task_dashboard.get_filter_options"
		});

		const data = r.message || {};

		(data.statuses || []).forEach(v => {
			let is_default = (v !== "Completed" && v !== "Cancelled");
			$("#filter-status-options").append(`<label class="multiselect-option"><input type="checkbox" value="${v}" ${is_default ? 'checked' : ''}> <span class="checkmark"></span> <span class="option-text">${v}</span></label>`);
		});

		const $ms = $("#ms-status");
		const checked_status = $ms.find("input[type='checkbox']:checked");
		if (checked_status.length > 0) {
			$ms.find(".multiselect-selected-text").text(checked_status.length + " selected");
		}

		(data.priorities || []).forEach(v => {
			$("#filter-priority-options").append(`<label class="multiselect-option"><input type="checkbox" value="${v}"> <span class="checkmark"></span> <span class="option-text">${v}</span></label>`);
		});
		(data.owners || []).forEach(v => {
			$("#filter-owner-options").append(`<label class="multiselect-option"><input type="checkbox" value="${v.name}"> <span class="checkmark"></span> <span class="option-text">${v.full_name || v.name}</span></label>`);
		});
	}

	async load(append = false) {
		frappe.dom.freeze("Loading Task Dashboard...");

		const r = await frappe.call({
			method: "tnc_v2_360ithub.tasks.page.task_dashboard.task_dashboard.get_dashboard_data",
			args: {
				filters: this.filters,
				start: this.start,
				page_length: this.page_length,
				sort_field: this.sort_field,
				sort_order: this.sort_order
			}
		});

		frappe.dom.unfreeze();

		const data = r.message || {};
		this.render_kpis(data.kpis || {});
		this.render_table(data.tasks || [], append);
		this.render_active_filters();
		this.render_task_count(data.total_count || 0);
		this.toggle_load_more(data.tasks || [], data.total_count || 0);
		this.update_sort_icons();
	}

	async load_leaderboard() {
		const $container = this.wrapper.find("#leaderboard-tab");
		if (!$container.find("table").length) {
			$container.html(`<div class="text-center text-muted" style="padding: 40px;">Loading Leaderboard...</div>`);
		}

		const r = await frappe.call({
			method: "tnc_v2_360ithub.tasks.page.task_dashboard.task_dashboard.get_leaderboard_data",
			args: {
				filters: this.filters,
				sort_field: this.leaderboard_sort_field,
				sort_order: this.leaderboard_sort_order
			}
		});

		const data = r.message || { leaderboard: [] };
		this.render_leaderboard(data);
	}

	render_leaderboard(data) {
		const render_list = (performers) => {
			if (!performers.length) return `<tr><td colspan="5" class="text-center text-muted">No data available</td></tr>`;

			return performers.map((p, i) => {
				// Calculate segments for the Stacked Bar
				const compWidth = (p.completed_count / p.total_count) * 100;
				const overWidth = (p.overdue_count / p.total_count) * 100;
				const openWidth = (p.open_count / p.total_count) * 100;

				return `
                <tr>
                    <td class="text-center">${i + 1}</td>
                    <td>
                        <div style="font-weight: 600; color: #1e293b;">${p.task_owner_name}</div>
                        <small class="text-muted">${p.total_count} Total Tasks</small>
                    </td>
                    <td style="vertical-align: middle; width: 250px;">
                        <div class="progress-stacked" style="display: flex; height: 12px; background: #f1f5f9; border-radius: 6px; overflow: hidden; margin-bottom: 4px;">
                            <div class="progress-bar bg-success" style="width: ${compWidth}%" title="Completed"></div>
                            <div class="progress-bar bg-warning" style="width: ${openWidth}%" title="Open/Working"></div>
                            <div class="progress-bar bg-danger" style="width: ${overWidth}%" title="Overdue"></div>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 10px; font-weight: 700;">
                            <span class="text-success">${p.completed_count} Done</span>
                            <span class="text-danger">${p.overdue_count} Overdue</span>
                        </div>
                    </td>
                    <td class="text-center">
                        <div style="font-size: 16px; font-weight: 800; color: #2563eb;">${p.completion_rate}%</div>
                    </td>
                    <td class="text-center">
                        <span class="badge ${p.critical_count > 0 ? 'badge-danger' : 'badge-light'}" 
                              style="font-size: 12px; padding: 6px 12px; border-radius: 8px;">
                            ${p.critical_count} High/Urgent
                        </span>
                    </td>
                </tr>
            `;
			}).join("");
		};

		const get_icon = (field) => {
			if (this.leaderboard_sort_field !== field) return "fa-sort";
			return this.leaderboard_sort_order === "asc" ? "fa-sort-asc sort-active" : "fa-sort-desc sort-active";
		};

		const html = `
        <div class="leaderboard-container">
            <div class="leaderboard-card task-table-card">
                <div class="table-responsive">
                    <table class="table task-table mb-0">
                        <thead>
                            <tr>
                                <th style="width: 60px;">Rank</th>
                                <th>Task Owner</th>
                                <th style="width: 250px;">Workload Mix (Ratio)</th>
                                <th class="text-center sortable" data-sort="completion_rate">Success Rate <i class="fa ${get_icon('completion_rate')}"></i></th>
                                <th class="text-center sortable" data-sort="critical_count">Critical Pending <i class="fa ${get_icon('critical_count')}"></i></th>
                            </tr>
                        </thead>
                        <tbody>
                            ${render_list(data.leaderboard || [])}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;

		this.wrapper.find("#leaderboard-tab").html(html);
	}

	update_sort_icons() {
		const me = this;

		// Update Task List icons
		const $task_thead = this.wrapper.find(".task-table:not(#leaderboard-tab *) thead");
		$task_thead.find("th.sortable").each(function () {
			const field = $(this).data("sort");
			const $i = $(this).find("i");
			$i.removeClass("fa-sort-asc fa-sort-desc sort-active").addClass("fa-sort");

			if (me.sort_field === field) {
				$i.removeClass("fa-sort").addClass(
					me.sort_order === "asc" ? "fa-sort-asc sort-active" : "fa-sort-desc sort-active"
				);
			}
		});

		// Update Leaderboard icons
		const $leaderboard_thead = this.wrapper.find("#leaderboard-tab thead");
		$leaderboard_thead.find("th.sortable").each(function () {
			const field = $(this).data("sort");
			const $i = $(this).find("i");
			$i.removeClass("fa-sort-asc fa-sort-desc sort-active").addClass("fa-sort");

			if (me.leaderboard_sort_field === field) {
				$i.removeClass("fa-sort").addClass(
					me.leaderboard_sort_order === "asc" ? "fa-sort-asc sort-active" : "fa-sort-desc sort-active"
				);
			}
		});
	}

	// render_kpis(kpis) {
	// 	$("#task-kpis").html(`
	// 		<div class="task-kpi overdue"><div class="num">${kpis.overdue || 0}</div><div class="label">Overdue Tasks</div></div>
	// 		<div class="task-kpi open"><div class="num">${kpis.open || 0}</div><div class="label">Open Tasks</div></div>
	// 		<div class="task-kpi pending"><div class="num">${kpis.pending || 0}</div><div class="label">Pending Tasks</div></div>
	// 		<div class="task-kpi completed"><div class="num">${kpis.completed || 0}</div><div class="label">Completed Tasks</div></div>
	// 	`);
	// }
	render_kpis(kpis) {
		const active_filter = this.filters.card_filter;
		$("#task-kpis").html(`
			<div class="small-kpi-card ${active_filter === 'Overdue' ? 'active' : ''}" data-filter="Overdue">
				<span class="kpi-num overdue-text" data-target="${kpis.overdue || 0}">0</span>
				<span class="kpi-label">Overdue</span>
			</div>
			<div class="small-kpi-card ${active_filter === 'Today' ? 'active' : ''}" data-filter="Today">
				<span class="kpi-num today-text" data-target="${kpis.today || 0}">0</span>
				<span class="kpi-label">Today task</span>
			</div>
			<div class="small-kpi-card ${active_filter === 'Future' ? 'active' : ''}" data-filter="Future">
				<span class="kpi-num future-text" data-target="${kpis.future || 0}">0</span>
				<span class="kpi-label">Future task</span>
			</div>
			<div class="small-kpi-card ${active_filter === 'Pending Review' ? 'active' : ''}" data-filter="Pending Review">
				<span class="kpi-num pending-text" data-target="${kpis.pending_review || 0}">0</span>
				<span class="kpi-label">pending for review</span>
			</div>
		`);

		this.animate_kpis();
	}

	animate_kpis() {
		$(".small-kpi-card .kpi-num").each(function () {
			const $el = $(this);
			const target = parseInt($el.attr("data-target")) || 0;
			const duration = 600;
			const stepTime = 20;
			const steps = Math.max(1, Math.floor(duration / stepTime));
			const increment = target / steps;

			let current = 0;

			const timer = setInterval(() => {
				current += increment;

				if (current >= target) {
					$el.text(target);
					clearInterval(timer);
				} else {
					$el.text(Math.floor(current));
				}
			}, stepTime);
		});
	}

	render_table(tasks, append = false) {
		let html = "";

		tasks.forEach((t, i) => {
			html += `
				<tr>
					<td class="text-center">${this.start + i + 1}</td>
					<td class="subject-cell"><a href="/app/task/${t.name}" target="_blank">${t.subject || "-"}</a></td>
					<td>${t.task_owner_name || t.task_owner || "-"}</td>
					<td>${t.task_reporter_name || t.task_reporter || "-"}</td>
					<td class="text-nowrap">${t.exp_start_date ? frappe.datetime.str_to_user(t.exp_start_date) : "-"}</td>
					<td class="text-nowrap">${t.exp_end_date ? frappe.datetime.str_to_user(t.exp_end_date) : "-"}</td>
					<td><span class="badge badge-${this.get_status_color(t.status)}">${t.status || "-"}</span></td>
					<td>${t.priority || "-"}</td>
					<td class="text-center">${t.overdue_days > 0 ? `<span class="overdue-pill">${t.overdue_days} day(s)</span>` : "-"}</td>
					<td class="comment-cell">
						<div>${t.latest_comment || "-"}</div>
						${t.latest_comment_on ? `<small>${frappe.utils.escape_html(t.latest_comment_by || "")} &bull; ${frappe.datetime.str_to_user(t.latest_comment_on)}</small>` : ""}
					</td>
					<td class="action-cell">
						<div class="action-buttons">
							<button class="btn btn-icon btn-outline-primary open-task" data-name="${t.name}" title="View Task"><i class="fa fa-eye"></i></button>
							<button class="btn btn-icon btn-outline-secondary add-comment" data-name="${t.name}" title="Add Comment"><i class="fa fa-comment"></i></button>
						</div>
					</td>
				</tr>
			`;
		});

		if (append) {
			$("#task-table-body").append(html);
		} else {
			$("#task-table-body").html(html || `<tr><td colspan="12" class="text-center">No Tasks Found</td></tr>`);
		}
	}

	toggle_load_more(rows, total_count) {
		if ((this.start + rows.length) >= total_count) {
			$("#load-more").hide();
		} else {
			$("#load-more").show();
		}
	}

	get_status_color(status) {
		const map = {
			"Open": "warning",
			"Working": "info",
			"Pending Review": "primary",
			"Completed": "success",
			"Cancelled": "secondary"
		};
		return map[status] || "secondary";
	}

	render_active_filters() {
		const parts = [];

		// Helper function to format date string YYYY-MM-DD to DD-MM-YYYY
		const formatDate = (date_str) => {
			return date_str ? moment(date_str).format("DD-MM-YYYY") : "";
		};

		if (this.filters.card_filter) parts.push(`Filter: ${this.filters.card_filter}`);
		if (this.filters.search) parts.push(`Search: ${this.filters.search}`);
		if (this.filters.status && this.filters.status.length) parts.push(`Status: ${this.filters.status.join(', ')}`);
		if (this.filters.priority && this.filters.priority.length) parts.push(`Priority: ${this.filters.priority.join(', ')}`);
		if (this.filters.task_owner && this.filters.task_owner.length) parts.push(`Owner: ${this.filters.task_owner.join(', ')}`);

		// Combined Date Logic with DD-MM-YYYY format
		if (this.filters.from_date || this.filters.to_date) {
			let date_label = "";
			if (this.filters.from_date && this.filters.to_date) {
				date_label = `Date: ${formatDate(this.filters.from_date)} to ${formatDate(this.filters.to_date)}`;
			} else if (this.filters.from_date) {
				date_label = `From: ${formatDate(this.filters.from_date)}`;
			} else if (this.filters.to_date) {
				date_label = `To: ${formatDate(this.filters.to_date)}`;
			}
			parts.push(date_label);
		}

		let html = "";
		if (parts.length) {
			html = parts.map(part => `<span class="filter-pill">${part}</span>`).join("");
		}

		$("#active-filters").html(html);
	}

	render_task_count(total) {
		$("#task-count").text(`Total Tasks: ${total}`);
	}

	async open_comment_dialog(task_name) {
		const r = await frappe.call({
			method: "tnc_v2_360ithub.tasks.page.task_dashboard.task_dashboard.get_task_comments",
			args: { task_name }
		});

		const { comments, task_subject, task_description } = r.message || { comments: [], task_subject: "", task_description: "" };
		let comment_html = `<div class="task-comment-history">`;

		if (comments.length) {
			comments.forEach(c => {
				comment_html += `
					<div class="comment-box">
						<div class="comment-meta">${c.owner} • ${frappe.datetime.str_to_user(c.creation)}</div>
						<div>${c.content}</div>
					</div>
				`;
			});
		} else {
			comment_html += `<div class="text-muted">No comments found</div>`;
		}

		comment_html += `</div>`;

		let d = new frappe.ui.Dialog({
			title: `Comments - ${task_name}`,
			fields: [
				{ fieldtype: "HTML", fieldname: "task_info_html" },
				{ fieldtype: "HTML", fieldname: "comments_html" },
				{ fieldtype: "Small Text", fieldname: "new_comment", label: "Add Comment", reqd: 0 }
			],
			primary_action_label: "Add Comment",
			primary_action: async () => {
				const comment = d.get_value("new_comment");
				if (!comment) return;

				await frappe.call({
					method: "tnc_v2_360ithub.tasks.page.task_dashboard.task_dashboard.add_task_comment",
					args: { task_name, comment }
				});

				d.set_value("new_comment", "");
				d.hide();
				this.load();
			}
		});

		// Display task info (subject and description)
		const task_info_html = `
			<div style="background-color: #f8f9fa; padding: 12px; border-radius: 4px; margin-bottom: 12px;">
				<strong>Subject:</strong> ${task_subject}<br><br>
				${task_description ? `<strong>Description:</strong> ${task_description}` : ""}
			</div>
		`;

		d.fields_dict.task_info_html.$wrapper.html(task_info_html);
		d.fields_dict.comments_html.$wrapper.html(comment_html);
		d.show();
		d.set_value("new_comment", "");
	}

	export_tasks() {
		const filters = JSON.stringify(this.filters);
		frappe.call({
			method: "tnc_v2_360ithub.tasks.page.task_dashboard.task_dashboard.export_tasks",
			args: { filters },
			callback: function (r) {
				if (r.message && r.message.file_url) {
					window.open(r.message.file_url, "_blank");
				} else {
					frappe.show_alert({ message: "Unable to export tasks", indicator: "danger" });
				}
			}
		});
	}
}
