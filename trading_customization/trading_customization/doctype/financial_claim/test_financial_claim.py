# Copyright (c) 2026, mnaa and contributors
# See license.txt

import frappe

from trading_customization.tests.utils import (
	TradingTestCase,
	make_branch,
	make_invoice,
	make_item,
	make_supplier,
)
from trading_customization.trading_customization.doctype.financial_claim.financial_claim import (
	create_financial_claim,
)


class TestFinancialClaim(TradingTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.supplier = make_supplier("_Test FC Supplier")
		cls.other_supplier = make_supplier("_Test FC Other Supplier")
		cls.branch = make_branch("_Test FC Branch")
		cls.other_branch = make_branch("_Test FC Other Branch")
		make_item("_Test Trading Item")

	def pi(self, posting_date="2026-06-10", supplier=None, **kwargs):
		kwargs.setdefault("branch", self.branch)
		return make_invoice(
			"Purchase Invoice",
			self.company,
			posting_date,
			supplier=supplier or self.supplier,
			**kwargs,
		)

	def claim(self, claim_number, **kwargs):
		doc = frappe.new_doc("Financial Claim")
		doc.update(
			{
				"claim_number": claim_number,
				"company": self.company,
				"supplier": self.supplier,
				"posting_date": "2026-06-30",
				"from_date": "2026-06-01",
				"to_date": "2026-06-30",
			}
		)
		doc.update(kwargs)
		return doc

	def test_get_invoices_fetches_only_matching_invoices(self):
		inside = self.pi(
			"2026-06-05", items=[{"item_code": "_Test Trading Item", "qty": 1, "rate": 3850}], taxes=577.5
		)
		self.pi("2026-07-01")  # outside period
		self.pi("2026-06-05", supplier=self.other_supplier)  # other supplier
		self.pi("2026-06-05", docstatus=0)  # draft
		self.pi("2026-06-05", docstatus=2)  # cancelled
		self.pi("2026-06-05", branch=self.other_branch)  # other branch

		doc = self.claim("_T-FC-FETCH", branch=self.branch)
		doc.get_invoices()

		self.assertEqual([row.purchase_invoice for row in doc.invoices], [inside.name])
		self.assertEqual(doc.total_invoices, 1)
		self.assertEqual(doc.net_total, 3850)
		self.assertEqual(doc.total_taxes, 577.5)
		self.assertEqual(doc.grand_total, 4427.5)

	def test_named_by_claim_number_and_number_is_unique(self):
		doc = self.claim("_T-FC/204")
		doc.append("invoices", {"purchase_invoice": self.pi().name})
		doc.insert()
		self.assertEqual(doc.name, "_T-FC/204")

		duplicate = self.claim("_T-FC/204")
		duplicate.append("invoices", {"purchase_invoice": self.pi().name})
		with self.assertRaises(frappe.DuplicateEntryError):
			duplicate.insert()

	def test_claim_number_is_required(self):
		doc = self.claim(None)
		doc.append("invoices", {"purchase_invoice": self.pi().name})
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_row_amounts_are_refreshed_from_invoice(self):
		invoice = self.pi(
			items=[{"item_code": "_Test Trading Item", "qty": 2, "rate": 50}], taxes=15, bill_no="SINV69"
		)
		doc = self.claim("_T-FC-REFRESH")
		doc.append("invoices", {"purchase_invoice": invoice.name, "grand_total": 999999})
		doc.insert()

		row = doc.invoices[0]
		self.assertEqual(row.grand_total, 115)
		self.assertEqual(row.net_total, 100)
		self.assertEqual(row.tax_amount, 15)
		self.assertEqual(row.bill_no, "SINV69")

	def test_invalid_invoices_are_blocked(self):
		cases = {
			"must be submitted": self.pi(docstatus=0),
			"is not linked to supplier": self.pi(supplier=self.other_supplier),
			"is outside the claim period": self.pi("2026-05-31"),
		}
		for message, invoice in cases.items():
			doc = self.claim(f"_T-FC-INVALID-{invoice.name}")
			doc.append("invoices", {"purchase_invoice": invoice.name})
			self.assertRaisesValidation(message, doc.insert)

	def test_branch_mismatch_is_blocked(self):
		doc = self.claim("_T-FC-BRANCH", branch=self.branch)
		doc.append("invoices", {"purchase_invoice": self.pi(branch=self.other_branch).name})
		self.assertRaisesValidation("does not belong to branch", doc.insert)

	def test_duplicate_row_is_blocked(self):
		invoice = self.pi()
		doc = self.claim("_T-FC-DUP-ROW")
		doc.append("invoices", {"purchase_invoice": invoice.name})
		doc.append("invoices", {"purchase_invoice": invoice.name})
		self.assertRaisesValidation("is added more than once", doc.insert)

	def test_invoice_cannot_be_in_two_claims_until_cancelled(self):
		invoice = self.pi()
		first = self.claim("_T-FC-FIRST")
		first.append("invoices", {"purchase_invoice": invoice.name})
		first.insert()

		second = self.claim("_T-FC-SECOND")
		second.append("invoices", {"purchase_invoice": invoice.name})
		self.assertRaisesValidation("is already included in Financial Claim", second.insert)

		first.submit()
		first.cancel()
		second.insert()
		self.assertTrue(second.name)

	def test_header_validations(self):
		invoice = self.pi()
		cases = {
			"To Date cannot be before From Date": {"from_date": "2026-06-30", "to_date": "2026-06-01"},
			"Authorization Date cannot be before Contract Date": {
				"contract_date": "2026-06-10",
				"authorization_date": "2026-06-01",
			},
			"Completion Percentage must be between 0 and 100": {"completion_percentage": 101},
			"Contract Value cannot be negative": {"contract_value": -1},
		}
		for message, values in cases.items():
			doc = self.claim("_T-FC-HEADER", **values)
			doc.append("invoices", {"purchase_invoice": invoice.name})
			self.assertRaisesValidation(message, doc.insert)

		empty = self.claim("_T-FC-EMPTY")
		self.assertRaisesValidation("Please add at least one Purchase Invoice", empty.insert)

	def test_cumulative_total_includes_previous_submitted_claims(self):
		first = self.claim("_T-FC-CUM-1", posting_date="2026-06-15")
		first.append(
			"invoices",
			{
				"purchase_invoice": self.pi(
					items=[{"item_code": "_Test Trading Item", "qty": 1, "rate": 1000}]
				).name
			},
		)
		first.insert().submit()

		draft = self.claim("_T-FC-CUM-DRAFT", posting_date="2026-06-16")
		draft.append(
			"invoices",
			{
				"purchase_invoice": self.pi(
					items=[{"item_code": "_Test Trading Item", "qty": 1, "rate": 5000}]
				).name
			},
		)
		draft.insert()  # drafts are not counted

		second = self.claim("_T-FC-CUM-2", posting_date="2026-06-30")
		second.append(
			"invoices",
			{
				"purchase_invoice": self.pi(
					items=[{"item_code": "_Test Trading Item", "qty": 1, "rate": 250}]
				).name
			},
		)
		second.insert()

		self.assertEqual(second.previous_claims_total, 1000)
		self.assertEqual(second.cumulative_total, 1250)

	def test_iban_is_fetched_from_supplier_bank_account(self):
		bank = frappe.get_doc({"doctype": "Bank", "bank_name": "_Test FC Bank"}).insert()
		frappe.get_doc(
			{
				"doctype": "Bank Account",
				"account_name": "_Test FC Supplier Account",
				"bank": bank.name,
				"party_type": "Supplier",
				"party": self.supplier,
				"iban": "GB82WEST12345698765432",
				"is_default": 1,
			}
		).insert()

		doc = self.claim("_T-FC-IBAN")
		doc.append("invoices", {"purchase_invoice": self.pi().name})
		doc.insert()
		self.assertEqual(doc.iban, "GB82WEST12345698765432")

	def test_create_from_list_button(self):
		invoice = self.pi("2026-06-20")
		self.assertRaisesValidation(
			"Claim Number is required",
			lambda: create_financial_claim(self.company, self.supplier, "2026-06-01", "2026-06-30"),
		)
		self.assertRaisesValidation(
			"To Date cannot be before From Date",
			lambda: create_financial_claim(
				self.company, self.supplier, "2026-06-30", "2026-06-01", claim_number="_T-X"
			),
		)

		name = create_financial_claim(
			self.company, self.supplier, "2026-06-01", "2026-06-30", claim_number="_T-FC-LIST"
		)
		doc = frappe.get_doc("Financial Claim", name)
		self.assertEqual(name, "_T-FC-LIST")
		self.assertIn(invoice.name, [row.purchase_invoice for row in doc.invoices])

		self.assertRaisesValidation(
			"No unclaimed submitted Purchase Invoices",
			lambda: create_financial_claim(
				self.company, self.supplier, "2026-06-01", "2026-06-30", claim_number="_T-FC-LIST-2"
			),
		)

	def test_print_format_renders(self):
		doc = self.claim(
			"_T-FC-PRINT",
			project_name="تأمين مواد الإعاشة",
			project_number="153-100-01",
			completion_percentage=100,
		)
		doc.append(
			"invoices",
			{
				"purchase_invoice": self.pi(
					items=[{"item_code": "_Test Trading Item", "qty": 1, "rate": 3850}],
					taxes=577.5,
					bill_no="SINV69",
				).name
			},
		)
		doc.insert()

		html = frappe.get_print("Financial Claim", doc.name, "Financial Claim", doc=doc, no_letterhead=1)
		for text in (
			"مطالبة مالية",
			"_T-FC-PRINT",
			"تأمين مواد الإعاشة",
			"153-100-01",
			"SINV69",
			"4,427.50",
			"مجموع فواتير المورد عدد (1)",
		):
			self.assertIn(text, html)
		self.assertNotIn("<img", html.split('class="fc"', 1)[-1])
