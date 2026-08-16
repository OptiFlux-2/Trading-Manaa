function make_uom_default_exclusive(frm, cdt, cdn, fieldname) {
	const row = locals[cdt][cdn];
	if (!row[fieldname]) return;

	(frm.doc.uoms || []).forEach((d) => {
		if (d.name !== row.name && d[fieldname]) {
			frappe.model.set_value(d.doctype, d.name, fieldname, 0);
		}
	});
	frm.refresh_field("uoms");
}

frappe.ui.form.on("UOM Conversion Detail", {
	custom_default_for_sales(frm, cdt, cdn) {
		make_uom_default_exclusive(frm, cdt, cdn, "custom_default_for_sales");
	},
	custom_default_for_purchase(frm, cdt, cdn) {
		make_uom_default_exclusive(frm, cdt, cdn, "custom_default_for_purchase");
	},
});
