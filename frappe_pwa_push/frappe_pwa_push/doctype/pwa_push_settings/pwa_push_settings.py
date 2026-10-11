# Copyright (c) 2026, Thinkspedia and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document

from frappe_pwa_push.relay.fcm import clear_cached_access_token

REQUIRED_SERVICE_ACCOUNT_KEYS = ("project_id", "private_key", "client_email")


class PWAPushSettings(Document):
	def validate(self):
		self.normalize_allowed_sites()
		self.read_service_account()
		if self.enabled and not (self.firebase_project_id and self.service_account_json):
			frappe.throw(_("Set the Firebase Service Account JSON before enabling the relay"))

	def on_update(self):
		clear_cached_access_token()

	def get_allowed_sites(self) -> set[str]:
		return {row.site_name for row in self.allowed_sites}

	def normalize_allowed_sites(self):
		for row in self.allowed_sites:
			row.site_name = (row.site_name or "").strip().lower()
			if any(char in row.site_name for char in "/:"):
				frappe.throw(_("Row {0}: enter a hostname only, without protocol or port").format(row.idx))

	def read_service_account(self):
		# An unchanged Password field comes back masked; only a newly pasted value is parsed.
		if not self.service_account_json or set(self.service_account_json) == {"*"}:
			return
		try:
			service_account = json.loads(self.service_account_json)
		except ValueError:
			frappe.throw(_("Firebase Service Account JSON is not valid JSON"))

		if service_account.get("type") != "service_account" or not all(
			service_account.get(key) for key in REQUIRED_SERVICE_ACCOUNT_KEYS
		):
			frappe.throw(_("This is not a Firebase service account key file"))
		self.firebase_project_id = service_account["project_id"]
