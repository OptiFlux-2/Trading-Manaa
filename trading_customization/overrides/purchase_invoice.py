import frappe
from frappe import _


def create_linked_sales_invoice(doc, method=None):
	customer = frappe.db.get_single_value("Trading Setting", "defualt_invoice_customer")
	if not customer:
		frappe.msgprint(
			_(
				"Could not auto-create a Sales Invoice: set 'Defualt Invoice Customer' in Trading Setting."
			),
			indicator="orange",
			alert=True,
		)
		return

	try:
		si = frappe.new_doc("Sales Invoice")
		si.customer = customer
		si.company = doc.company
		si.currency = doc.currency
		si.posting_date = doc.posting_date
		si.set_posting_time = 1
		si.update_stock = 0

		for row in doc.items:
			si.append(
				"items",
				{
					"item_code": row.item_code,
					"item_name": row.item_name,
					"description": row.description,
					"qty": row.qty,
					"uom": row.uom,
					"conversion_factor": row.conversion_factor,
					"rate": row.rate,
				},
			)

		si.insert(ignore_permissions=True)

		frappe.msgprint(
			_("Draft Sales Invoice {0} created for {1}").format(
				frappe.utils.get_link_to_form("Sales Invoice", si.name), customer
			),
			indicator="green",
			alert=True,
		)
	except Exception:
		frappe.log_error(
			frappe.get_traceback(), f"Failed to auto-create Sales Invoice from {doc.name}"
		)
		frappe.msgprint(
			_("Purchase Invoice {0} was submitted, but auto-creating the linked Sales Invoice failed. Check the Error Log.").format(
				doc.name
			),
			indicator="red",
			alert=True,
		)
