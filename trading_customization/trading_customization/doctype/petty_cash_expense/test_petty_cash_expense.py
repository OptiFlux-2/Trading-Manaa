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
from trading_customization.trading_customization.doctype.petty_cash_expense.petty_cash_expense import (
	create_petty_cash_expense,
)


class TestPettyCashExpense(TradingTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.supplier = make_supplier("_Test PCE Supplier")
		cls.other_supplier = make_supplier("_Test PCE Other Supplier")
		cls.branch = make_branch("_Test PCE Branch")
		cls.other_branch = make_branch("_Test PCE Other Branch")
		make_item("_Test Trading Item")

	def pi(self, posting_date="2026-06-12", flagged=1, supplier=None, rate=100, taxes=15, **kwargs):
		kwargs.setdefault("branch", self.branch)
		return make_invoice(
			"Purchase Invoice",
			self.company,
			posting_date,
			items=[{"item_code": "_Test Trading Item", "qty": 1, "rate": rate}],
			taxes=taxes,
			supplier=supplier or self.supplier,
			supplier_name=supplier or self.supplier,
			custom_non_recoverable_tax=flagged,
			**kwargs,
		)

	def expense(self, form_number, **kwargs):
		doc = frappe.new_doc("Petty Cash Expense")
		doc.update(
			{
				"form_number": form_number,
				"company": self.company,
				"custody_account": "153-04",
				"posting_date": "2026-06-30",
				"from_date": "2026-06-01",
				"to_date": "2026-06-30",
			}
		)
		doc.update(kwargs)
		return doc

	def test_purchase_invoice_has_non_recoverable_tax_field(self):
		field = frappe.get_meta("Purchase Invoice").get_field("custom_non_recoverable_tax")
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Check")
		self.assertEqual(field.label, "Non-Recoverable Tax")

	def test_get_invoices_fetches_only_flagged_matching_invoices(self):
		first = self.pi("2026-06-12", rate=75, taxes=11.25)
		second = self.pi("2026-06-13", supplier=self.other_supplier, rate=236.52, taxes=35.48)
		self.pi(flagged=0)  # not flagged
		self.pi("2026-07-01")  # outside period
		self.pi(docstatus=0)  # draft
		self.pi(branch=self.other_branch)  # other branch

		doc = self.expense("_T-PCE-FETCH", branch=self.branch)
		doc.get_invoices()

		self.assertEqual({row.purchase_invoice for row in doc.invoices}, {first.name, second.name})
		self.assertEqual(doc.total_invoices, 2)
		self.assertAlmostEqual(doc.net_total, 311.52)
		self.assertAlmostEqual(doc.total_taxes, 46.73)
		self.assertAlmostEqual(doc.grand_total, 358.25)

	def test_supplier_filter_is_optional(self):
		mine = self.pi()
		self.pi(supplier=self.other_supplier)

		doc = self.expense("_T-PCE-SUPPLIER", supplier=self.supplier)
		doc.get_invoices()
		self.assertEqual([row.purchase_invoice for row in doc.invoices], [mine.name])

		other = self.expense("_T-PCE-OTHER", supplier=self.other_supplier)
		other.append("invoices", {"purchase_invoice": mine.name})
		self.assertRaisesValidation("is not for supplier", other.insert)

	def test_row_values_come_from_invoice(self):
		with_bill_date = self.pi(bill_no="H191-P110009701", bill_date="2026-06-11")
		without_bill_date = self.pi("2026-06-14", bill_no="114495037")

		doc = self.expense("_T-PCE-ROWS")
		doc.append("invoices", {"purchase_invoice": with_bill_date.name, "grand_total": 1})
		doc.append("invoices", {"purchase_invoice": without_bill_date.name})
		doc.insert()

		self.assertEqual(doc.invoices[0].bill_no, "H191-P110009701")
		self.assertEqual(str(doc.invoices[0].invoice_date), "2026-06-11")
		self.assertEqual(doc.invoices[0].grand_total, 115)
		self.assertEqual(doc.invoices[0].supplier, self.supplier)
		self.assertEqual(str(doc.invoices[1].invoice_date), "2026-06-14")

	def test_named_by_form_number_and_number_is_unique(self):
		doc = self.expense("_T-JUNE_16")
		doc.append("invoices", {"purchase_invoice": self.pi().name})
		doc.insert()
		self.assertEqual(doc.name, "_T-JUNE_16")

		duplicate = self.expense("_T-JUNE_16")
		duplicate.append("invoices", {"purchase_invoice": self.pi().name})
		with self.assertRaises(frappe.DuplicateEntryError):
			duplicate.insert()

	def test_invalid_invoices_are_blocked(self):
		cases = {
			"is not marked as Non-Recoverable Tax": self.pi(flagged=0),
			"must be submitted": self.pi(docstatus=0),
			"is outside the selected period": self.pi("2026-05-31"),
		}
		for message, invoice in cases.items():
			doc = self.expense(f"_T-PCE-INVALID-{invoice.name}")
			doc.append("invoices", {"purchase_invoice": invoice.name})
			self.assertRaisesValidation(message, doc.insert)

		doc = self.expense("_T-PCE-BRANCH", branch=self.branch)
		doc.append("invoices", {"purchase_invoice": self.pi(branch=self.other_branch).name})
		self.assertRaisesValidation("does not belong to branch", doc.insert)

	def test_header_validations(self):
		doc = self.expense("_T-PCE-DATES", from_date="2026-06-30", to_date="2026-06-01")
		doc.append("invoices", {"purchase_invoice": self.pi().name})
		self.assertRaisesValidation("To Date cannot be before From Date", doc.insert)

		self.assertRaisesValidation(
			"Please add at least one Purchase Invoice", self.expense("_T-PCE-EMPTY").insert
		)

		invoice = self.pi()
		dup = self.expense("_T-PCE-DUP")
		dup.append("invoices", {"purchase_invoice": invoice.name})
		dup.append("invoices", {"purchase_invoice": invoice.name})
		self.assertRaisesValidation("is added more than once", dup.insert)

	def test_invoice_cannot_be_used_twice_until_cancelled(self):
		invoice = self.pi()
		first = self.expense("_T-PCE-FIRST")
		first.append("invoices", {"purchase_invoice": invoice.name})
		first.insert()

		second = self.expense("_T-PCE-SECOND")
		second.append("invoices", {"purchase_invoice": invoice.name})
		self.assertRaisesValidation("is already included in Petty Cash Expense", second.insert)

		first.submit()
		first.cancel()
		second.insert()
		self.assertTrue(second.name)

	def test_create_from_list_button(self):
		invoice = self.pi("2026-06-20")
		self.assertRaisesValidation(
			"Form Number is required",
			lambda: create_petty_cash_expense(self.company, "2026-06-01", "2026-06-30"),
		)
		self.assertRaisesValidation(
			"To Date cannot be before From Date",
			lambda: create_petty_cash_expense(self.company, "2026-06-30", "2026-06-01", form_number="_T-X"),
		)

		name = create_petty_cash_expense(
			self.company, "2026-06-01", "2026-06-30", form_number="_T-PCE-LIST", custody_account="153-04"
		)
		doc = frappe.get_doc("Petty Cash Expense", name)
		self.assertEqual(doc.custody_account, "153-04")
		self.assertIn(invoice.name, [row.purchase_invoice for row in doc.invoices])

		self.assertRaisesValidation(
			"No unused submitted Purchase Invoices with Non-Recoverable Tax",
			lambda: create_petty_cash_expense(
				self.company, "2026-06-01", "2026-06-30", form_number="_T-PCE-LIST-2"
			),
		)

	def test_print_format_renders(self):
		doc = self.expense("_T-PCE-PRINT")
		doc.append(
			"invoices", {"purchase_invoice": self.pi(rate=75, taxes=11.25, bill_no="H191-P110009701").name}
		)
		doc.insert()

		html = frappe.get_print(
			"Petty Cash Expense", doc.name, "Petty Cash Expense", doc=doc, no_letterhead=1
		)
		for text in (
			"PETTY CASH EXPENSES FORM",
			"العهدة - العاجلة ضريبة غير مستردة",
			"_T-PCE-PRINT",
			"153-04",
			"H191-P110009701",
			"86.25",
			"Requested By:",
			"Finance Manager:",
			"Payment Method :",
		):
			self.assertIn(text, html)
