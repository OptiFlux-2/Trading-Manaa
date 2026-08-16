function use_supplier_code_search_for_item_code(frm) {
	if (!frm.fields_dict.items) return;

	const grid_field = frm.fields_dict.items.grid.get_field("item_code");
	if (!grid_field || grid_field.__supplier_code_search_applied) return;

	const original_get_query = grid_field.get_query;

	// Wrap (rather than replace) the query ERPNext already set in its own
	// setup() - this preserves its filters (is_sales_item/is_purchase_item,
	// customer/supplier, subcontracting, has_variants, etc.) exactly as-is,
	// we just point "query" at our own function which additionally matches
	// supplier_item_code / supplier_item_name from the Item's
	// "Item Supplier Pricing" child table.
	grid_field.get_query = function (doc, cdt, cdn) {
		const original = (original_get_query && original_get_query.apply(this, arguments)) || {};
		return Object.assign({}, original, {
			query: "trading_customization.api.item_code_query",
		});
	};

	grid_field.__supplier_code_search_applied = true;
}

frappe.ui.form.on("Purchase Order", {
	refresh(frm) {
		use_supplier_code_search_for_item_code(frm);
	},
});

frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		use_supplier_code_search_for_item_code(frm);
	},
});

frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		use_supplier_code_search_for_item_code(frm);
	},
});

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		use_supplier_code_search_for_item_code(frm);
	},
});
