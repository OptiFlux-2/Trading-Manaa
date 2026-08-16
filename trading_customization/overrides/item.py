import frappe
from frappe import _


def validate_item_name(doc, method=None):
	parts = [
		(doc.custom_category or "").strip(),
		(doc.custom_description_c or "").strip(),
		(doc.custom_size or "").strip(),
		(doc.custom_brand_c or "").strip(),
	]

	if not any(parts):
		return

	# Override item_name here (instead of just validating it) because ERPNext's
	# own Item form/controller defaults item_name to item_code before this hook
	# runs, which would otherwise fail an equality check on every insert.
	doc.item_name = " ".join(filter(None, parts))


def _sync_single_default(rows, fieldname):
	flagged = [d for d in rows if d.get(fieldname)]

	# Safety net for API/import writes that bypass the grid's client-side
	# exclusivity check: keep only the last flagged row.
	if len(flagged) > 1:
		for d in flagged[:-1]:
			d.set(fieldname, 0)
		flagged = flagged[-1:]

	return flagged[0].uom if flagged else None


def sync_default_uoms(doc, method=None):
	rows = doc.uoms or []

	# ERPNext's get_item_details() already prefers Item.sales_uom /
	# Item.purchase_uom for Sales/Purchase Order & Invoice rows, so syncing
	# these two checkboxes into those standard fields is enough to make the
	# default automatic there - no need to touch the transaction doctypes.
	doc.sales_uom = _sync_single_default(rows, "custom_default_for_sales")
	doc.purchase_uom = _sync_single_default(rows, "custom_default_for_purchase")
