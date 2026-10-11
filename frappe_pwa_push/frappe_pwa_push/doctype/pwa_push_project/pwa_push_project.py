# Copyright (c) 2026, Thinkspedia and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document

REQUIRED_WEB_CONFIG_KEYS = ("apiKey", "projectId", "messagingSenderId", "appId")


class PWAPushProject(Document):
	def validate(self):
		self.vapid_public_key = (self.vapid_public_key or "").strip()
		try:
			web_config = json.loads(self.firebase_config)
		except ValueError:
			frappe.throw(_("Firebase Web Config is not valid JSON"))
		if not isinstance(web_config, dict):
			frappe.throw(_("Firebase Web Config must be a JSON object"))

		missing = [key for key in REQUIRED_WEB_CONFIG_KEYS if not web_config.get(key)]
		if missing:
			frappe.throw(_("Firebase Web Config is missing: {0}").format(", ".join(missing)))
