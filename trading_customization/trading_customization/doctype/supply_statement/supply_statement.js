// Copyright (c) 2026, mnaa and contributors
// For license information, please see license.txt

frappe.ui.form.on("Supply Statement", {
	from_date(frm) {
		validate_supply_statement_dates(frm, "from_date");
	},

	to_date(frm) {
		validate_supply_statement_dates(frm, "to_date");
	},

	get_items(frm) {
		if (frm.doc.docstatus !== 0) return;

		const fetch = () =>
			frm.call({
				doc: frm.doc,
				method: "get_items",
				freeze: true,
				freeze_message: __("Fetching Sales Invoice items..."),
				callback: () => frm.dirty(),
			});

		if ((frm.doc.items || []).length) {
			frappe.confirm(__("This will replace the current items. Continue?"), fetch);
		} else {
			fetch();
		}
	},
});

frappe.ui.form.on("Supply Statement Item", {
	qty(frm, cdt, cdn) {
		calculate_row_amount(frm, cdt, cdn);
	},

	rate(frm, cdt, cdn) {
		calculate_row_amount(frm, cdt, cdn);
	},

	items_remove(frm) {
		calculate_supply_statement_totals(frm);
	},
});

function calculate_row_amount(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "amount", flt(row.qty) * flt(row.rate));
	calculate_supply_statement_totals(frm);
}

function calculate_supply_statement_totals(frm) {
	const rows = frm.doc.items || [];
	frm.set_value("total_items", rows.length);
	frm.set_value("total_qty", rows.reduce((total, row) => total + flt(row.qty), 0));
	frm.set_value("total_amount", rows.reduce((total, row) => total + flt(row.qty) * flt(row.rate), 0));
}

function validate_supply_statement_dates(frm, changed_field) {
	const { from_date, to_date } = frm.doc;
	if (from_date && to_date && frappe.datetime.get_diff(to_date, from_date) < 0) {
		frappe.msgprint({
			title: __("Invalid Dates"),
			message: __("To Date cannot be before From Date"),
			indicator: "red",
		});
		frm.set_value(changed_field, null);
	}
}
