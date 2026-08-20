import frappe


def execute():
	frappe.delete_doc(
		"Custom Field",
		"Item-custom_category",
		ignore_missing=True,
		force=True,
	)

	if frappe.db.has_column("Item", "custom_category"):
		frappe.db.sql("ALTER TABLE `tabItem` DROP COLUMN `custom_category`")
