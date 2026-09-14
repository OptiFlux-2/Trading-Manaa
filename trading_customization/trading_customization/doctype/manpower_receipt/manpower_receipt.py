# Copyright (c) 2026, mnaa and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class ManpowerReceipt(Document):
	def validate(self):
		self.validate_dates()

	def validate_dates(self):
		if self.get("from") and self.get("to") and getdate(self.get("to")) < getdate(self.get("from")):
			frappe.throw(_("To Date cannot be before From Date"), title=_("Invalid Dates"))
