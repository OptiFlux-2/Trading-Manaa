"""Shared helpers for trading_customization tests.

Invoices are written straight to the database (``db_insert``) with the fields
our doctypes read. This keeps the tests fast and independent of the chart of
accounts, stock settings and GL posting, and avoids any side effects of a real
submit. Each test is rolled back to a savepoint, and the whole class is
rolled back by ``FrappeTestCase``; committing during a test fails it.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, now_datetime


class TradingTestCase(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")

		# Tests must never commit: all data is rolled back at the end.
		frappe.db.before_commit.add(_fail_on_commit)
		cls.addClassCleanup(frappe.db.before_commit.reset)

		cls.company = get_company()
		cls.currency = frappe.get_cached_value("Company", cls.company, "default_currency")

	def setUp(self):
		frappe.set_user("Administrator")

		# Undo each test's data so invoices from one test never leak into another.
		frappe.db.savepoint("trading_test")
		self.addCleanup(frappe.db.rollback, save_point="trading_test")

	def assertRaisesValidation(self, message, fn):
		"""Assert ``fn`` raises a ValidationError whose text contains ``message``."""
		with self.assertRaises(frappe.ValidationError) as ctx:
			fn()
		self.assertIn(message, frappe.utils.strip_html(str(ctx.exception)))
		frappe.clear_messages()


def _fail_on_commit():
	raise AssertionError("A test tried to commit to the database")


def get_company():
	company = frappe.db.get_value("Company", {}, "name", order_by="creation asc")
	if not company:
		raise AssertionError("These tests need at least one Company on the site")
	return company


def make_supplier(name):
	if not frappe.db.exists("Supplier", name):
		frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": name,
				"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0})
				or "All Supplier Groups",
			}
		).insert()
	return frappe.db.get_value("Supplier", {"supplier_name": name})


def make_branch(name):
	if not frappe.db.exists("Branch", name):
		frappe.get_doc({"doctype": "Branch", "branch": name}).insert()
	return name


def make_item(item_code, item_group=None, uom="Nos"):
	if not frappe.db.exists("Item", item_code):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": f"{item_code} name",
				# Required by this app's Item customization; also becomes item_name.
				"custom_description_c": f"{item_code} name",
				"item_group": item_group
				or frappe.db.get_value("Item Group", {"is_group": 0})
				or "All Item Groups",
				"stock_uom": uom,
				"is_stock_item": 0,
			}
		).insert()
	return item_code


def make_invoice(doctype, company, posting_date, items=None, docstatus=1, taxes=0, **fields):
	"""Insert a minimal Sales/Purchase Invoice row with the given docstatus.

	``items`` is a list of dicts with item_code, qty, rate and optionally uom.
	"""
	prefix = "_T-SINV-" if doctype == "Sales Invoice" else "_T-PINV-"
	doc = frappe.new_doc(doctype)
	doc.name = frappe.model.naming.make_autoname(prefix + ".#####", doctype)
	doc.update(
		{
			"company": company,
			"posting_date": posting_date,
			"currency": frappe.get_cached_value("Company", company, "default_currency"),
			"docstatus": docstatus,
			"owner": "Administrator",
			"modified_by": "Administrator",
			"creation": now_datetime(),
			"modified": now_datetime(),
		}
	)
	doc.update(fields)

	net_total = 0
	for row in items or [{"item_code": make_item("_Test Trading Item"), "qty": 1, "rate": 100}]:
		amount = flt(row["qty"]) * flt(row["rate"])
		net_total += amount
		item_code = row["item_code"]
		doc.append(
			"items",
			{
				"item_code": item_code,
				"item_name": frappe.get_cached_value("Item", item_code, "item_name"),
				"item_group": frappe.get_cached_value("Item", item_code, "item_group"),
				"uom": row.get("uom", "Nos"),
				"qty": row["qty"],
				"base_net_rate": row["rate"],
				"base_net_amount": amount,
				"docstatus": docstatus,
			},
		)

	doc.base_net_total = net_total
	doc.base_total_taxes_and_charges = taxes
	doc.base_grand_total = net_total + taxes

	doc.db_insert()
	for row in doc.items:
		row.parent = doc.name
		row.owner = row.modified_by = "Administrator"
		row.creation = row.modified = doc.creation
		row.db_insert()

	return doc
