# Copyright (c) 2026, mnaa and Contributors
# See license.txt

import frappe

from trading_customization.tests.utils import TradingTestCase


def make_receipt(**kwargs):
	doc = frappe.new_doc("Manpower Receipt")
	doc.update({"posting_date": "2026-06-01", "from": "2026-06-01", "to": "2026-06-30"})
	doc.update(kwargs)
	doc.append(
		"receipts",
		{"designation": "مندوب مشتريات", "full_name": "فهد مساعد العتيبي", "id_number": "1000000001"},
	)
	doc.append("receipts", {"designation": "عامل نظافة للمطبخ", "full_name": "MD FARIDUL", "note": "-"})
	return doc


class TestManpowerReceipt(TradingTestCase):
	def test_valid_receipt_is_saved_and_submitted(self):
		doc = make_receipt().insert()
		doc.submit()
		self.assertEqual(doc.docstatus, 1)
		self.assertEqual(len(doc.receipts), 2)

	def test_to_date_before_from_date_is_blocked(self):
		doc = make_receipt(**{"from": "2026-06-30", "to": "2026-06-01"})
		self.assertRaisesValidation("To Date cannot be before From Date", doc.insert)

	def test_same_from_and_to_date_is_allowed(self):
		doc = make_receipt(**{"from": "2026-06-15", "to": "2026-06-15"}).insert()
		self.assertTrue(doc.name)

	def test_print_format_renders_period_and_rows(self):
		doc = make_receipt().insert()
		html = frappe.get_print("Manpower Receipt", doc.name, "Manpower Receipt", doc=doc, no_letterhead=1)

		self.assertIn("جدول استلام القوى العاملة", html)
		self.assertIn("2026/06/01", html)
		self.assertIn("2026/06/30", html)
		self.assertIn("فهد مساعد العتيبي", html)
		self.assertIn("MD FARIDUL", html)
