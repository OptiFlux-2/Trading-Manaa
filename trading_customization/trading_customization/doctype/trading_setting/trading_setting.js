// Copyright (c) 2026, mnaa and contributors
// For license information, please see license.txt

frappe.ui.form.on("Trading Setting", {
	setup(frm) {
		frm.set_query("urgent_warehouse", () => {
			return {
				filters: {
					is_group: 0,
				},
			};
		});
	},
});
