// Copyright (c) 2026, mnaa and contributors
// For license information, please see license.txt

frappe.ui.form.on("Manpower Receipt", {
	from(frm) {
		validate_dates(frm, "from");
	},
	to(frm) {
		validate_dates(frm, "to");
	},
});

function validate_dates(frm, changed_field) {
	const from_date = frm.doc.from;
	const to_date = frm.doc.to;
	if (from_date && to_date && frappe.datetime.get_diff(to_date, from_date) < 0) {
		frappe.msgprint({
			title: __("Invalid Dates"),
			message: __("To Date cannot be before From Date"),
			indicator: "red",
		});
		frm.set_value(changed_field, null);
	}
}
