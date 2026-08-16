function set_item_uom_query(frm) {
	frm.set_query("uom", "items", function (doc, cdt, cdn) {
		const row = locals[cdt][cdn];
		return {
			query: "trading_customization.api.item_uom_query",
			filters: { item_code: row.item_code },
		};
	});
}

// Registered on refresh (not setup) so this runs AFTER ERPNext's own
// TransactionController.setup(), which unconditionally calls
// frm.set_query("uom", "items", ...) pointing at its own
// erpnext.controllers.queries.get_item_uom_query. refresh fires later in the
// form lifecycle and every time the form re-renders, so ours always wins.
frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		set_item_uom_query(frm);
	},
});

frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		set_item_uom_query(frm);
	},
});
