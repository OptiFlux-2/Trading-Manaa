# Copyright (c) 2026, mnaa and contributors
# See license.txt

import frappe

from trading_customization.tests.utils import TradingTestCase, make_branch, make_invoice, make_item
from trading_customization.trading_customization.doctype.supply_statement.supply_statement import (
	create_supply_statement,
)


class TestSupplyStatement(TradingTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.branch = make_branch("_Test SS Branch")
		cls.other_branch = make_branch("_Test SS Other Branch")
		cls.rice = make_item("_Test SS Rice")
		cls.sugar = make_item("_Test SS Sugar")

	def si(self, items, posting_date="2026-06-10", **kwargs):
		kwargs.setdefault("branch", self.branch)
		return make_invoice("Sales Invoice", self.company, posting_date, items=items, **kwargs)

	def statement(self, **kwargs):
		doc = frappe.new_doc("Supply Statement")
		doc.update(
			{
				"company": self.company,
				"posting_date": "2026-06-30",
				"from_date": "2026-06-01",
				"to_date": "2026-06-30",
				"branch": self.branch,
			}
		)
		doc.update(kwargs)
		return doc

	def test_get_items_groups_by_item_uom_and_rate(self):
		first = self.si(
			[
				{"item_code": self.rice, "qty": 20, "rate": 253.10, "uom": "Nos"},
				{"item_code": self.sugar, "qty": 2, "rate": 130.70, "uom": "Nos"},
			]
		)
		second = self.si(
			[
				{
					"item_code": self.rice,
					"qty": 13,
					"rate": 253.10,
					"uom": "Nos",
				},  # same item/uom/rate -> merged
				{"item_code": self.rice, "qty": 1, "rate": 200, "uom": "Nos"},  # different rate -> own row
				{"item_code": self.rice, "qty": 1, "rate": 253.10, "uom": "Box"},  # different uom -> own row
			],
			posting_date="2026-06-20",
		)

		doc = self.statement()
		doc.get_items()

		rows = {(row.item_code, row.uom, row.rate): row.qty for row in doc.items}
		self.assertEqual(
			rows,
			{
				(self.rice, "Box", 253.10): 1,
				(self.rice, "Nos", 200): 1,
				(self.rice, "Nos", 253.10): 33,
				(self.sugar, "Nos", 130.70): 2,
			},
		)
		self.assertEqual({row.sales_invoice for row in doc.sales_invoices}, {first.name, second.name})
		self.assertEqual(doc.total_items, 4)
		self.assertEqual(doc.total_qty, 37)
		self.assertAlmostEqual(doc.total_amount, 33 * 253.10 + 200 + 253.10 + 2 * 130.70)

		rice_row = next(row for row in doc.items if row.uom == "Nos" and row.rate == 253.10)
		self.assertEqual(rice_row.item_name, "_Test SS Rice name")
		self.assertEqual(rice_row.item_group, frappe.db.get_value("Item", self.rice, "item_group"))

	def test_get_items_respects_period_branch_and_status(self):
		included = self.si([{"item_code": self.rice, "qty": 1, "rate": 10}])
		self.si([{"item_code": self.rice, "qty": 5, "rate": 10}], posting_date="2026-07-01")
		self.si([{"item_code": self.rice, "qty": 5, "rate": 10}], branch=self.other_branch)
		self.si([{"item_code": self.rice, "qty": 5, "rate": 10}], docstatus=0)
		self.si([{"item_code": self.rice, "qty": 5, "rate": 10}], docstatus=2)

		doc = self.statement()
		doc.get_items()
		self.assertEqual([row.sales_invoice for row in doc.sales_invoices], [included.name])
		self.assertEqual(doc.total_qty, 1)

		no_branch = self.statement(branch=None)
		no_branch.get_items()
		self.assertEqual(no_branch.total_qty, 6)

	def test_user_can_remove_and_edit_rows(self):
		self.si(
			[
				{"item_code": self.rice, "qty": 2, "rate": 100},
				{"item_code": self.sugar, "qty": 3, "rate": 10},
			]
		)
		doc = self.statement()
		doc.get_items()
		doc.insert()

		doc.items = [row for row in doc.items if row.item_code != self.sugar]
		doc.items[0].qty = 5
		doc.save()

		self.assertEqual(len(doc.items), 1)
		self.assertEqual(doc.items[0].amount, 500)
		self.assertEqual(doc.total_items, 1)
		self.assertEqual(doc.total_qty, 5)
		self.assertEqual(doc.total_amount, 500)

		doc.submit()
		self.assertEqual(doc.docstatus, 1)

	def test_manual_statement_without_invoices(self):
		doc = self.statement()
		doc.append("items", {"item_code": self.rice, "uom": "Nos", "qty": 4, "rate": 2.5})
		doc.insert()

		self.assertEqual(doc.items[0].item_name, "_Test SS Rice name")
		self.assertEqual(doc.items[0].amount, 10)
		self.assertEqual(doc.total_amount, 10)
		self.assertTrue(doc.name.startswith("SUP-"))

	def test_item_validations(self):
		cases = {
			"Quantity cannot be zero": {"qty": 0, "rate": 1},
			"Rate cannot be negative": {"qty": 1, "rate": -1},
		}
		for message, values in cases.items():
			doc = self.statement()
			doc.append("items", {"item_code": self.rice, "uom": "Nos", **values})
			self.assertRaisesValidation(message, doc.insert)

		self.assertRaisesValidation("Please add at least one item", self.statement().insert)

		dates = self.statement(from_date="2026-06-30", to_date="2026-06-01")
		dates.append("items", {"item_code": self.rice, "uom": "Nos", "qty": 1, "rate": 1})
		self.assertRaisesValidation("To Date cannot be before From Date", dates.insert)

	def test_invalid_source_invoices_are_blocked(self):
		cases = {
			"must be submitted": self.si([{"item_code": self.rice, "qty": 1, "rate": 1}], docstatus=0),
			"is outside the selected period": self.si(
				[{"item_code": self.rice, "qty": 1, "rate": 1}], posting_date="2026-05-31"
			),
			"does not belong to branch": self.si(
				[{"item_code": self.rice, "qty": 1, "rate": 1}], branch=self.other_branch
			),
		}
		for message, invoice in cases.items():
			doc = self.statement()
			doc.append("items", {"item_code": self.rice, "uom": "Nos", "qty": 1, "rate": 1})
			doc.append("sales_invoices", {"sales_invoice": invoice.name})
			self.assertRaisesValidation(message, doc.insert)

	def test_invoice_cannot_be_used_twice_until_cancelled(self):
		self.si([{"item_code": self.rice, "qty": 1, "rate": 10}])
		first = self.statement()
		first.get_items()
		first.insert()

		second = self.statement()
		self.assertRaisesValidation("No unused submitted Sales Invoices", second.get_items)

		second.append("items", {"item_code": self.rice, "uom": "Nos", "qty": 1, "rate": 10})
		second.append("sales_invoices", {"sales_invoice": first.sales_invoices[0].sales_invoice})
		self.assertRaisesValidation("is already included in Supply Statement", second.insert)

		first.submit()
		first.cancel()
		third = self.statement()
		third.get_items()
		self.assertEqual(len(third.sales_invoices), 1)

	def test_create_from_list_button(self):
		self.si([{"item_code": self.rice, "qty": 3, "rate": 7}])
		name = create_supply_statement(self.company, "2026-06-01", "2026-06-30", branch=self.branch)
		doc = frappe.get_doc("Supply Statement", name)
		self.assertEqual(doc.total_amount, 21)

		self.assertRaisesValidation(
			"To Date cannot be before From Date",
			lambda: create_supply_statement(self.company, "2026-06-30", "2026-06-01"),
		)

	def test_print_format_renders(self):
		self.si([{"item_code": self.rice, "qty": 33, "rate": 253.10}])
		doc = self.statement()
		doc.get_items()
		doc.insert()

		html = frappe.get_print("Supply Statement", doc.name, "Supply Statement", doc=doc, no_letterhead=1)
		for text in (
			"مستخلص توريد مواد الإعاشة",
			"2026/06/01",
			"2026/06/30",
			f"({self.branch})",
			self.rice,
			"_Test SS Rice name",
			"8,352.30",
		):
			self.assertIn(text, html)
