// Extends ERPNext's Sales Invoice list settings (loaded before this file)
// with a "Create > Supply Statement" button.
(() => {
	const settings = (frappe.listview_settings["Sales Invoice"] ||= {});
	const original_onload = settings.onload;

	settings.onload = function (listview) {
		original_onload && original_onload.apply(this, arguments);

		if (!frappe.model.can_create("Supply Statement")) return;

		listview.page.add_inner_button(
			__("Supply Statement"),
			() => open_supply_statement_dialog(listview),
			__("Create")
		);
	};

	function open_supply_statement_dialog(listview) {
		const branch_filter = (listview.filter_area.get().find((f) => f[1] === "branch" && f[2] === "=") || [])[3];

		const dialog = new frappe.ui.Dialog({
			title: __("Create Supply Statement"),
			fields: [
				{
					fieldname: "company",
					fieldtype: "Link",
					label: __("Company"),
					options: "Company",
					reqd: 1,
					default: frappe.defaults.get_user_default("Company"),
				},
				{
					fieldname: "branch",
					fieldtype: "Link",
					label: __("Branch"),
					options: "Branch",
					default: branch_filter,
				},
				{ fieldtype: "Column Break" },
				{
					fieldname: "from_date",
					fieldtype: "Date",
					label: __("From Date"),
					reqd: 1,
					default: frappe.datetime.month_start(),
				},
				{
					fieldname: "to_date",
					fieldtype: "Date",
					label: __("To Date"),
					reqd: 1,
					default: frappe.datetime.get_today(),
				},
			],
			primary_action_label: __("Create"),
			primary_action(values) {
				if (frappe.datetime.get_diff(values.to_date, values.from_date) < 0) {
					frappe.msgprint({
						title: __("Invalid Dates"),
						message: __("To Date cannot be before From Date"),
						indicator: "red",
					});
					return;
				}

				frappe.call({
					method: "trading_customization.trading_customization.doctype.supply_statement.supply_statement.create_supply_statement",
					args: values,
					freeze: true,
					freeze_message: __("Creating Supply Statement..."),
					callback(r) {
						if (!r.message) return;
						dialog.hide();
						frappe.set_route("Form", "Supply Statement", r.message);
					},
				});
			},
		});

		dialog.show();
	}
})();
