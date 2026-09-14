# Copyright (c) 2026, mnaa and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class FinancialClaim(Document):
	def validate(self):
		self.validate_dates()
		self.validate_percentages_and_values()
		self.set_iban()
		self.validate_invoices()
		self.calculate_totals()

	def validate_dates(self):
		if getdate(self.to_date) < getdate(self.from_date):
			frappe.throw(_("To Date cannot be before From Date"), title=_("Invalid Dates"))

		if (
			self.contract_date
			and self.authorization_date
			and getdate(self.authorization_date) < getdate(self.contract_date)
		):
			frappe.throw(_("Authorization Date cannot be before Contract Date"), title=_("Invalid Dates"))

	def validate_percentages_and_values(self):
		if not 0 <= flt(self.completion_percentage) <= 100:
			frappe.throw(_("Completion Percentage must be between 0 and 100"))

		if flt(self.contract_value) < 0:
			frappe.throw(_("Contract Value cannot be negative"))

	def set_iban(self):
		if self.iban or not self.supplier:
			return

		self.iban = frappe.db.get_value(
			"Bank Account",
			{"party_type": "Supplier", "party": self.supplier, "disabled": 0},
			"iban",
			order_by="is_default desc, modified desc",
		)

	def validate_invoices(self):
		if not self.invoices:
			frappe.throw(_("Please add at least one Purchase Invoice"))

		already_claimed = get_claimed_invoices(exclude_claim=self.name)
		seen = set()

		for row in self.invoices:
			if row.purchase_invoice in seen:
				frappe.throw(
					_("Row #{0}: Purchase Invoice {1} is added more than once").format(
						row.idx, row.purchase_invoice
					)
				)
			seen.add(row.purchase_invoice)

			if row.purchase_invoice in already_claimed:
				frappe.throw(
					_("Row #{0}: Purchase Invoice {1} is already included in Financial Claim {2}").format(
						row.idx, row.purchase_invoice, already_claimed[row.purchase_invoice]
					)
				)

			pi = frappe.db.get_value(
				"Purchase Invoice",
				row.purchase_invoice,
				[
					"docstatus",
					"company",
					"supplier",
					"posting_date",
					"bill_no",
					"branch",
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

			if pi.company != self.company:
				frappe.throw(
					_("Row #{0}: Purchase Invoice {1} belongs to company {2}").format(
						row.idx, row.purchase_invoice, pi.company
					)
				)

			if pi.supplier != self.supplier:
				frappe.throw(
					_("Row #{0}: Purchase Invoice {1} is not linked to supplier {2}").format(
						row.idx, row.purchase_invoice, self.supplier
					)
				)

			if not getdate(self.from_date) <= getdate(pi.posting_date) <= getdate(self.to_date):
				frappe.throw(
					_("Row #{0}: Purchase Invoice {1} posting date {2} is outside the claim period").format(
						row.idx, row.purchase_invoice, frappe.format(pi.posting_date, "Date")
					)
				)

			if self.branch and pi.branch != self.branch:
				frappe.throw(
					_("Row #{0}: Purchase Invoice {1} does not belong to branch {2}").format(
						row.idx, row.purchase_invoice, self.branch
					)
				)

			# Always refresh amounts from the invoice so they can't be edited by hand
			row.posting_date = pi.posting_date
			row.bill_no = pi.bill_no
			row.branch = pi.branch
			row.net_total = pi.base_net_total
			row.tax_amount = pi.base_total_taxes_and_charges
			row.grand_total = pi.base_grand_total

	def calculate_totals(self):
		self.total_invoices = len(self.invoices)
		self.net_total = sum(flt(row.net_total) for row in self.invoices)
		self.total_taxes = sum(flt(row.tax_amount) for row in self.invoices)
		self.grand_total = sum(flt(row.grand_total) for row in self.invoices)

		filters = {
			"docstatus": 1,
			"supplier": self.supplier,
			"company": self.company,
			"name": ["!=", self.name],
			"posting_date": ["<=", self.posting_date],
		}
		if self.project:
			filters["project"] = self.project

		self.previous_claims_total = flt(
			frappe.get_all("Financial Claim", filters=filters, fields=["sum(grand_total) as total"])[0].total
		)
		self.cumulative_total = flt(self.previous_claims_total) + flt(self.grand_total)

	@frappe.whitelist()
	def get_invoices(self):
		for field in ("company", "supplier", "from_date", "to_date"):
			if not self.get(field):
				frappe.throw(_("Please set {0} first").format(_(self.meta.get_label(field))))

		invoices = get_unclaimed_invoices(
			self.company, self.supplier, self.from_date, self.to_date, self.branch, exclude_claim=self.name
		)
		if not invoices:
			frappe.throw(_("No unclaimed submitted Purchase Invoices found for the selected filters"))

		self.set("invoices", [])
		for pi in invoices:
			self.append("invoices", {"purchase_invoice": pi})

		self.validate_invoices()
		self.calculate_totals()


def get_claimed_invoices(exclude_claim=None):
	"""Return {purchase_invoice: financial_claim} for invoices in draft or submitted claims."""
	filters = {"parenttype": "Financial Claim", "docstatus": ["<", 2]}
	if exclude_claim:
		filters["parent"] = ["!=", exclude_claim]

	return {
		row.purchase_invoice: row.parent
		for row in frappe.get_all(
			"Financial Claim Invoice", filters=filters, fields=["purchase_invoice", "parent"]
		)
	}


def get_unclaimed_invoices(company, supplier, from_date, to_date, branch=None, exclude_claim=None):
	filters = {
		"docstatus": 1,
		"company": company,
		"supplier": supplier,
		"posting_date": ["between", [from_date, to_date]],
	}
	if branch:
		filters["branch"] = branch

	claimed = get_claimed_invoices(exclude_claim)
	return [
		name
		for name in frappe.get_all(
			"Purchase Invoice", filters=filters, pluck="name", order_by="posting_date asc, name asc"
		)
		if name not in claimed
	]


@frappe.whitelist()
def create_financial_claim(
	company, supplier, from_date, to_date, claim_number=None, branch=None, project=None
):
	frappe.has_permission("Financial Claim", "create", throw=True)

	if not claim_number:
		frappe.throw(_("Claim Number is required"), title=_("Missing Value"))

	if getdate(to_date) < getdate(from_date):
		frappe.throw(_("To Date cannot be before From Date"), title=_("Invalid Dates"))

	claim = frappe.new_doc("Financial Claim")
	claim.update(
		{
			"claim_number": claim_number,
			"company": company,
			"supplier": supplier,
			"from_date": from_date,
			"to_date": to_date,
			"branch": branch,
			"project": project,
		}
	)
	claim.get_invoices()
	claim.insert()
	return claim.name
