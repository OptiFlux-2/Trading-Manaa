// Copyright (c) 2026, mnaa and contributors
// For license information, please see license.txt

frappe.ui.form.on("Financial Claim", {
	setup(frm) {
		frm.set_query("purchase_invoice", "invoices", () => {
			const filters = {
				docstatus: 1,
				company: frm.doc.company,
				supplier: frm.doc.supplier,
			};
			if (frm.doc.from_date && frm.doc.to_date) {
				filters.posting_date = ["between", [frm.doc.from_date, frm.doc.to_date]];
			}
			if (frm.doc.branch) {
				filters.branch = frm.doc.branch;
			}
			return { filters };
		});

		frm.set_query("project", () => ({
			filters: frm.doc.company ? { company: frm.doc.company } : {},
		}));
	},

	from_date(frm) {
		validate_claim_dates(frm, "from_date");
	},

	to_date(frm) {
		validate_claim_dates(frm, "to_date");
	},

	supplier(frm) {
		frm.set_value("iban", "");
	},

	get_invoices(frm) {
		if (frm.doc.docstatus !== 0) return;
		frm.call({
			doc: frm.doc,
			method: "get_invoices",
			freeze: true,
			freeze_message: __("Fetching Purchase Invoices..."),
			callback: () => frm.dirty(),
		});
	},
});

frappe.ui.form.on("Financial Claim Invoice", {
	invoices_remove(frm) {
		calculate_claim_totals(frm);
	},
});

function validate_claim_dates(frm, changed_field) {
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

function calculate_claim_totals(frm) {
	const rows = frm.doc.invoices || [];
	const sum = (field) => rows.reduce((total, row) => total + flt(row[field]), 0);

	frm.set_value("total_invoices", rows.length);
	frm.set_value("net_total", sum("net_total"));
	frm.set_value("total_taxes", sum("tax_amount"));
	frm.set_value("grand_total", sum("grand_total"));
	frm.set_value("cumulative_total", flt(frm.doc.previous_claims_total) + sum("grand_total"));
}
