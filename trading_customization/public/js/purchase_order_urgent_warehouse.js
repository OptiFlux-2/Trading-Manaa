function toggle_set_warehouse_read_only(frm) {
	frm.set_df_property("set_warehouse", "read_only", frm.doc.custom_is_urgent_ ? 1 : 0);
	frm.refresh_field("set_warehouse");
}

function apply_urgent_warehouse(frm) {
	if (!frm.doc.custom_is_urgent_) {
		toggle_set_warehouse_read_only(frm);
		return;
	}

	frappe.db.get_single_value("Trading Setting", "urgent_warehouse").then((urgent_warehouse) => {
		if (!urgent_warehouse) {
			frappe.msgprint(__("Set 'Urgent Warehouse' in Trading Setting first."));
			frm.set_value("custom_is_urgent_", 0);
			return;
		}
		// Setting set_warehouse also triggers ERPNext's own "set_warehouse"
		// handler, which autofills the warehouse on every item row.
		frm.set_value("set_warehouse", urgent_warehouse).then(() => {
			toggle_set_warehouse_read_only(frm);
		});
	});
}

frappe.ui.form.on("Purchase Order", {
	custom_is_urgent_(frm) {
		apply_urgent_warehouse(frm);
	},
	refresh(frm) {
		toggle_set_warehouse_read_only(frm);
	},
});
