// Extends ERPNext's Purchase Invoice list settings (loaded before this file)
// with "Create > Financial Claim" and "Create > Petty Cash Expense" buttons.
(() => {
	const settings = (frappe.listview_settings["Purchase Invoice"] ||= {});
	const original_onload = settings.onload;

	settings.onload = function (listview) {
		original_onload && original_onload.apply(this, arguments);

		if (frappe.model.can_create("Financial Claim")) {
			listview.page.add_inner_button(
				__("Financial Claim"),
				() => open_financial_claim_dialog(listview),
				__("Create")
			);
		}

		if (frappe.model.can_create("Petty Cash Expense")) {
			listview.page.add_inner_button(
				__("Petty Cash Expense"),
				() => open_petty_cash_expense_dialog(listview),
				__("Create")
			);
		}
	};

	const list_filter = (listview, field) =>
		(listview.filter_area.get().find((f) => f[1] === field && f[2] === "=") || [])[3];

	const company_field = () => ({
		fieldname: "company",
		fieldtype: "Link",
		label: __("Company"),
		options: "Company",
		reqd: 1,
		default: frappe.defaults.get_user_default("Company"),
	});

	const date_fields = () => [
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
	];

	function open_create_dialog({ doctype, method, fields }) {
		const dialog = new frappe.ui.Dialog({
			title: __("Create {0}", [__(doctype)]),
			fields,
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
					method,
					args: values,
					freeze: true,
					freeze_message: __("Creating {0}...", [__(doctype)]),
					callback(r) {
						if (!r.message) return;
						dialog.hide();
						frappe.set_route("Form", doctype, r.message);
					},
				});
			},
		});

		dialog.show();
	}

	function open_financial_claim_dialog(listview) {
		open_create_dialog({
			doctype: "Financial Claim",
			method: "trading_customization.trading_customization.doctype.financial_claim.financial_claim.create_financial_claim",
			fields: [
				{ fieldname: "claim_number", fieldtype: "Data", label: __("Claim Number"), reqd: 1 },
				company_field(),
				{
					fieldname: "supplier",
					fieldtype: "Link",
					label: __("Supplier"),
					options: "Supplier",
					reqd: 1,
					default: list_filter(listview, "supplier"),
				},
				{ fieldtype: "Column Break" },
				...date_fields(),
				{ fieldtype: "Section Break", label: __("Optional") },
				{
					fieldname: "branch",
					fieldtype: "Link",
					label: __("Branch"),
					options: "Branch",
					default: list_filter(listview, "branch"),
				},
				{ fieldtype: "Column Break" },
				{ fieldname: "project", fieldtype: "Link", label: __("Project"), options: "Project" },
			],
		});
	}

	function open_petty_cash_expense_dialog(listview) {
		open_create_dialog({
			doctype: "Petty Cash Expense",
			method: "trading_customization.trading_customization.doctype.petty_cash_expense.petty_cash_expense.create_petty_cash_expense",
			fields: [
				{ fieldname: "form_number", fieldtype: "Data", label: __("Form Number"), reqd: 1 },
				company_field(),
				{ fieldname: "custody_account", fieldtype: "Data", label: __("Custody Account (CA)") },
				{ fieldtype: "Column Break" },
				...date_fields(),
				{ fieldtype: "Section Break", label: __("Optional") },
				{
					fieldname: "branch",
					fieldtype: "Link",
					label: __("Branch"),
					options: "Branch",
					default: list_filter(listview, "branch"),
				},
				{ fieldtype: "Column Break" },
				{
					fieldname: "supplier",
					fieldtype: "Link",
					label: __("Supplier"),
					options: "Supplier",
					default: list_filter(listview, "supplier"),
				},
			],
		});
	}
})();
