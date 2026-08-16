import frappe
from frappe.utils import cint


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def item_uom_query(doctype, txt, searchfield, start, page_len, filters):
	item_code = filters.get("item_code") if filters else None

	item_uoms = (
		frappe.get_all(
			"UOM Conversion Detail",
			filters={"parent": item_code},
			pluck="uom",
			distinct=True,
		)
		if item_code
		else []
	)

	uom_filters = [["name", "like", f"%{txt}%"]]
	if item_uoms:
		uom_filters.append(["name", "in", item_uoms])

	return frappe.get_all(
		"UOM",
		filters=uom_filters,
		fields=["name"],
		start=start,
		page_length=page_len,
		as_list=True,
	)


@frappe.whitelist()
def get_supplier_prices(item_code):
	if not item_code:
		return []

	return frappe.get_all(
		"Item Price",
		filters={
			"item_code": item_code,
			"buying": 1,
			"supplier": ["is", "set"],
		},
		fields=["supplier", "price_list", "price_list_rate", "currency", "uom", "valid_upto"],
		order_by="price_list_rate asc",
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def item_code_query(doctype, txt, searchfield, start, page_len, filters):
	"""item_code search that also matches supplier_item_code / supplier_item_name
	in the Item's "Item Supplier Pricing" child table, on top of the normal
	item_code/item_name/description/etc. search.

	Delegates to ERPNext's own item_query for both passes so sales/purchase
	item flags, Party Specific Item restrictions, subcontracting rules, and
	permission conditions are respected exactly as they are for a plain
	search - we only translate supplier codes/names into item names first.
	"""
	from erpnext.controllers.queries import item_query as core_item_query

	filters = dict(filters) if filters else {}
	page_len = cint(page_len) or 10

	results = list(core_item_query(doctype, txt, searchfield, start, page_len, dict(filters)))

	matched_parents = frappe.get_all(
		"Item Supplier Pricing",
		filters={"parenttype": "Item", "parentfield": "custom_item_supplier_pricing"},
		or_filters=[
			["supplier_item_code", "like", f"%{txt}%"],
			["supplier_item_name", "like", f"%{txt}%"],
		],
		pluck="parent",
		distinct=True,
	)

	if matched_parents:
		supplier_match_filters = dict(filters)
		supplier_match_filters["name"] = ["in", matched_parents]
		results += list(core_item_query(doctype, "", searchfield, 0, page_len, supplier_match_filters))

	seen = set()
	deduped = []
	for row in results:
		item_code = row[0]
		if item_code in seen:
			continue
		seen.add(item_code)
		deduped.append(row)
		if len(deduped) >= page_len:
			break

	return deduped
