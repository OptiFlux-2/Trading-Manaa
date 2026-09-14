# Copyright (c) 2026, mnaa and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class SupplyStatement(Document):
	def validate(self):
		self.validate_dates()
		self.validate_invoices()
		self.validate_items()
		self.calculate_totals()

	def validate_dates(self):
		if getdate(self.to_date) < getdate(self.from_date):
			frappe.throw(_("To Date cannot be before From Date"), title=_("Invalid Dates"))

	def validate_invoices(self):
		already_used = get_used_invoices(exclude=self.name)
		seen = set()

		for row in self.sales_invoices:
			if row.sales_invoice in seen:
				frappe.throw(_("Sales Invoice {0} is added more than once").format(row.sales_invoice))
			seen.add(row.sales_invoice)

			if row.sales_invoice in already_used:
				frappe.throw(
					_("Sales Invoice {0} is already included in Supply Statement {1}").format(
						row.sales_invoice, already_used[row.sales_invoice]
					)
				)

			si = frappe.db.get_value(
				"Sales Invoice",
				row.sales_invoice,
				["docstatus", "company", "posting_date", "branch", "base_net_total"],
				as_dict=True,
			)
			if not si or si.docstatus != 1:
				frappe.throw(_("Sales Invoice {0} must be submitted").format(row.sales_invoice))

			if si.company != self.company:
				frappe.throw(
					_("Sales Invoice {0} belongs to company {1}").format(row.sales_invoice, si.company)
				)

			if not getdate(self.from_date) <= getdate(si.posting_date) <= getdate(self.to_date):
				frappe.throw(
					_("Sales Invoice {0} posting date {1} is outside the selected period").format(
						row.sales_invoice, frappe.format(si.posting_date, "Date")
					)
				)

			if self.branch and si.branch != self.branch:
				frappe.throw(
					_("Sales Invoice {0} does not belong to branch {1}").format(
						row.sales_invoice, self.branch
					)
				)

			row.posting_date = si.posting_date
			row.branch = si.branch
			row.net_total = si.base_net_total

	def validate_items(self):
		if not self.items:
			frappe.throw(_("Please add at least one item"))

		for row in self.items:
			if not flt(row.qty):
				frappe.throw(
					_("Row #{0}: Quantity cannot be zero for item {1}").format(row.idx, row.item_code)
				)

			if flt(row.rate) < 0:
				frappe.throw(
					_("Row #{0}: Rate cannot be negative for item {1}").format(row.idx, row.item_code)
				)

			row.amount = flt(flt(row.qty) * flt(row.rate), row.precision("amount"))

	def calculate_totals(self):
		self.total_items = len(self.items)
		self.total_qty = sum(flt(row.qty) for row in self.items)
		self.total_amount = sum(flt(row.amount) for row in self.items)

	@frappe.whitelist()
	def get_items(self):
		for field in ("company", "from_date", "to_date"):
			if not self.get(field):
				frappe.throw(_("Please set {0} first").format(_(self.meta.get_label(field))))

		self.validate_dates()

		invoices = get_available_invoices(
			self.company, self.from_date, self.to_date, self.branch, exclude=self.name
		)
		if not invoices:
			frappe.throw(_("No unused submitted Sales Invoices found for the selected filters"))

		self.set("sales_invoices", [])
		for si in invoices:
			self.append("sales_invoices", {"sales_invoice": si})

		# One row per item, UOM and rate across all selected invoices
		items = frappe.db.sql(
			"""
			select
				sii.item_code,
				max(sii.item_name) as item_name,
				max(sii.item_group) as item_group,
				sii.uom,
				sii.base_net_rate as rate,
				sum(sii.qty) as qty
			from `tabSales Invoice Item` sii
			where sii.parenttype = 'Sales Invoice' and sii.parent in %(invoices)s
			group by sii.item_code, sii.uom, sii.base_net_rate
			having sum(sii.qty) != 0
			order by sii.item_code, sii.uom, sii.base_net_rate
			""",
			{"invoices": invoices},
			as_dict=True,
		)

		self.set("items", [])
		for row in items:
			self.append("items", row)

		self.validate_invoices()
		self.validate_items()
		self.calculate_totals()


def get_used_invoices(exclude=None):
	"""Return {sales_invoice: supply_statement} for invoices in draft or submitted statements."""
	filters = {"parenttype": "Supply Statement", "docstatus": ["<", 2]}
	if exclude:
		filters["parent"] = ["!=", exclude]

	return {
		row.sales_invoice: row.parent
		for row in frappe.get_all(
			"Supply Statement Invoice", filters=filters, fields=["sales_invoice", "parent"]
		)
	}


def get_available_invoices(company, from_date, to_date, branch=None, exclude=None):
	filters = {
		"docstatus": 1,
		"company": company,
		"posting_date": ["between", [from_date, to_date]],
	}
	if branch:
		filters["branch"] = branch

	used = get_used_invoices(exclude)
	return [
		name
		for name in frappe.get_all(
			"Sales Invoice", filters=filters, pluck="name", order_by="posting_date asc, name asc"
		)
		if name not in used
	]


@frappe.whitelist()
def create_supply_statement(company, from_date, to_date, branch=None):
	frappe.has_permission("Supply Statement", "create", throw=True)

	doc = frappe.new_doc("Supply Statement")
	doc.update({"company": company, "from_date": from_date, "to_date": to_date, "branch": branch})
	doc.get_items()
	doc.insert()
	return doc.name
