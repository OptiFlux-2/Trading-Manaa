# Copyright (c) 2026, mnaa and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class PettyCashExpense(Document):
	def validate(self):
		self.validate_dates()
		self.validate_invoices()
		self.calculate_totals()

	def validate_dates(self):
		if getdate(self.to_date) < getdate(self.from_date):
			frappe.throw(_("To Date cannot be before From Date"), title=_("Invalid Dates"))

	def validate_invoices(self):
		if not self.invoices:
			frappe.throw(_("Please add at least one Purchase Invoice"))

		already_added = get_used_invoices(exclude=self.name)
		seen = set()

		for row in self.invoices:
			if row.purchase_invoice in seen:
				frappe.throw(
					_("Row #{0}: Purchase Invoice {1} is added more than once").format(
						row.idx, row.purchase_invoice
					)
				)
			seen.add(row.purchase_invoice)

			if row.purchase_invoice in already_added:
				frappe.throw(
					_("Row #{0}: Purchase Invoice {1} is already included in Petty Cash Expense {2}").format(
						row.idx, row.purchase_invoice, already_added[row.purchase_invoice]
					)
				)

			pi = frappe.db.get_value(
				"Purchase Invoice",
				row.purchase_invoice,
				[
					"docstatus",
					"company",
					"supplier",
					"supplier_name",
					"posting_date",
					"bill_no",
					"bill_date",
					"branch",
					"custom_non_recoverable_tax",
					"base_net_total",
					"base_total_taxes_and_charges",
					"base_grand_total",
				],
				as_dict=True,
			)
			if not pi:
				frappe.throw(
					_("Row #{0}: Purchase Invoice {1} does not exist").format(row.idx, row.purchase_invoice)
				)

			if pi.docstatus != 1:
				frappe.throw(
					_("Row #{0}: Purchase Invoice {1} must be submitted").format(
						row.idx, row.purchase_invoice
					)
				)

			if not pi.custom_non_recoverable_tax:
				frappe.throw(
					_("Row #{0}: Purchase Invoice {1} is not marked as Non-Recoverable Tax").format(
						row.idx, row.purchase_invoice
					)
				)

			if pi.company != self.company:
				frappe.throw(
					_("Row #{0}: Purchase Invoice {1} belongs to company {2}").format(
						row.idx, row.purchase_invoice, pi.company
					)
				)

			if not getdate(self.from_date) <= getdate(pi.posting_date) <= getdate(self.to_date):
				frappe.throw(
					_(
						"Row #{0}: Purchase Invoice {1} posting date {2} is outside the selected period"
					).format(row.idx, row.purchase_invoice, frappe.format(pi.posting_date, "Date"))
				)

			if self.branch and pi.branch != self.branch:
				frappe.throw(
					_("Row #{0}: Purchase Invoice {1} does not belong to branch {2}").format(
						row.idx, row.purchase_invoice, self.branch
					)
				)

			if self.supplier and pi.supplier != self.supplier:
				frappe.throw(
					_("Row #{0}: Purchase Invoice {1} is not for supplier {2}").format(
						row.idx, row.purchase_invoice, self.supplier
					)
				)

			# Always refresh values from the invoice so they can't be edited by hand
			row.supplier = pi.supplier
			row.supplier_name = pi.supplier_name
			row.bill_no = pi.bill_no
			row.invoice_date = pi.bill_date or pi.posting_date
			row.branch = pi.branch
			row.net_total = pi.base_net_total
			row.tax_amount = pi.base_total_taxes_and_charges
			row.grand_total = pi.base_grand_total

	def calculate_totals(self):
		self.total_invoices = len(self.invoices)
		self.net_total = sum(flt(row.net_total) for row in self.invoices)
		self.total_taxes = sum(flt(row.tax_amount) for row in self.invoices)
		self.grand_total = sum(flt(row.grand_total) for row in self.invoices)

	@frappe.whitelist()
	def get_invoices(self):
		for field in ("company", "from_date", "to_date"):
			if not self.get(field):
				frappe.throw(_("Please set {0} first").format(_(self.meta.get_label(field))))

		invoices = get_available_invoices(
			self.company, self.from_date, self.to_date, self.branch, self.supplier, exclude=self.name
		)
		if not invoices:
			frappe.throw(
				_(
					"No unused submitted Purchase Invoices with Non-Recoverable Tax found for the selected filters"
				)
			)

		self.set("invoices", [])
		for pi in invoices:
			self.append("invoices", {"purchase_invoice": pi})

		self.validate_invoices()
		self.calculate_totals()


def get_used_invoices(exclude=None):
	"""Return {purchase_invoice: petty_cash_expense} for invoices in draft or submitted forms."""
	filters = {"parenttype": "Petty Cash Expense", "docstatus": ["<", 2]}
	if exclude:
		filters["parent"] = ["!=", exclude]

	return {
		row.purchase_invoice: row.parent
		for row in frappe.get_all(
			"Petty Cash Expense Invoice", filters=filters, fields=["purchase_invoice", "parent"]
		)
	}


def get_available_invoices(company, from_date, to_date, branch=None, supplier=None, exclude=None):
	filters = {
		"docstatus": 1,
		"company": company,
		"custom_non_recoverable_tax": 1,
		"posting_date": ["between", [from_date, to_date]],
	}
	if branch:
		filters["branch"] = branch
	if supplier:
		filters["supplier"] = supplier

	used = get_used_invoices(exclude)
	return [
		name
		for name in frappe.get_all(
			"Purchase Invoice", filters=filters, pluck="name", order_by="posting_date asc, name asc"
		)
		if name not in used
	]


@frappe.whitelist()
def create_petty_cash_expense(
	company, from_date, to_date, form_number=None, custody_account=None, branch=None, supplier=None
):
	frappe.has_permission("Petty Cash Expense", "create", throw=True)

	if not form_number:
		frappe.throw(_("Form Number is required"), title=_("Missing Value"))

	if getdate(to_date) < getdate(from_date):
		frappe.throw(_("To Date cannot be before From Date"), title=_("Invalid Dates"))

	doc = frappe.new_doc("Petty Cash Expense")
	doc.update(
		{
			"form_number": form_number,
			"company": company,
			"custody_account": custody_account,
			"from_date": from_date,
			"to_date": to_date,
			"branch": branch,
			"supplier": supplier,
		}
	)
	doc.get_invoices()
	doc.insert()
	return doc.name
