function show_supplier_price_dialog(cdt, cdn, item_code, prices) {
	const rows_html = prices
		.map((p, idx) => {
			const rate_display = format_currency(p.price_list_rate, p.currency);
			return `
				<tr class="supplier-price-row" data-rate="${p.price_list_rate}" style="cursor:pointer;">
					<td>${idx === 0 ? `<b>${frappe.utils.escape_html(p.supplier)}</b>` : frappe.utils.escape_html(p.supplier)}</td>
					<td>${frappe.utils.escape_html(p.price_list || "")}</td>
					<td>${idx === 0 ? `<b class="text-success">${rate_display}</b>` : rate_display}</td>
					<td>${frappe.utils.escape_html(p.uom || "")}</td>
					<td>${p.valid_upto ? frappe.datetime.str_to_user(p.valid_upto) : ""}</td>
				</tr>
			`;
		})
		.join("");

	const html = `
		<table class="table table-bordered table-hover">
			<thead>
				<tr>
					<th>${__("Supplier")}</th>
					<th>${__("Price List")}</th>
					<th>${__("Rate")}</th>
					<th>${__("UOM")}</th>
					<th>${__("Valid Upto")}</th>
				</tr>
			</thead>
			<tbody>${rows_html}</tbody>
		</table>
		<p class="text-muted small">${__("Click a row to use that supplier's rate for this item.")}</p>
	`;

	const dialog = new frappe.ui.Dialog({
		title: __("Supplier Prices for {0}", [item_code]),
		fields: [{ fieldtype: "HTML", fieldname: "price_html", options: html }],
	});

	dialog.$wrapper.find(".supplier-price-row").on("click", function () {
		const rate = flt($(this).data("rate"));
		frappe.model.set_value(cdt, cdn, "rate", rate);
		dialog.hide();
	});

	dialog.show();
}

function fetch_and_show_supplier_prices(cdt, cdn, item_code, { require_multiple = false } = {}) {
	frappe.call({
		method: "trading_customization.api.get_supplier_prices",
		args: { item_code },
		callback(r) {
			const prices = r.message || [];
			if (!prices.length) {
				if (!require_multiple) {
					frappe.msgprint(__("No supplier prices found for this item."));
				}
				return;
			}
			if (require_multiple && prices.length < 2) return;
			show_supplier_price_dialog(cdt, cdn, item_code, prices);
		},
	});
}

frappe.ui.form.on("Purchase Order Item", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code) return;
		fetch_and_show_supplier_prices(cdt, cdn, row.item_code, { require_multiple: true });
	},
});

function pick_item_row_then(frm, callback) {
	// Prefer whichever row the user currently has expanded, if any.
	const open_row = frm.open_grid_row();
	if (open_row && open_row.doc && open_row.doc.item_code) {
		callback(open_row.doc);
		return;
	}

	const rows = (frm.doc.items || []).filter((d) => d.item_code);
	if (!rows.length) {
		frappe.msgprint(__("Add an item to the table first."));
		return;
	}
	if (rows.length === 1) {
		callback(rows[0]);
		return;
	}

	const row_by_label = {};
	rows.forEach((d) => {
		const item_label = d.item_name && d.item_name !== d.item_code ? `${d.item_code} - ${d.item_name}` : d.item_code;
		row_by_label[__("Row {0}: {1}", [d.idx, item_label])] = d;
	});

	frappe.prompt(
		{
			fieldtype: "Select",
			fieldname: "row_label",
			label: __("Select Item Row"),
			options: Object.keys(row_by_label),
			reqd: 1,
		},
		(values) => callback(row_by_label[values.row_label]),
		__("Select Item Row")
	);
}

frappe.ui.form.on("Purchase Order", {
	refresh(frm) {
		if (!frm.fields_dict.items) return;

		frm.fields_dict.items.grid.add_custom_button(__("Compare Supplier Prices"), function () {
			pick_item_row_then(frm, (row) => {
				fetch_and_show_supplier_prices(row.doctype, row.name, row.item_code);
			});
		});
	},
});
