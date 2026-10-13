import json

import frappe
from frappe import _

from frappe_pwa_push.relay.common import is_relay_enabled


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_config(project_name: str | None = None) -> None:
	"""Public Firebase web config for a PWA.

	frappe-push-notification.js reads `config` and `vapid_public_key` from the top level of
	the response body, not from `message`, so both are set on frappe.response directly.
	"""
	if not project_name:
		# WHY: a public endpoint; a call without the argument is a client error, not a
		#      server error worth an Error Log entry.
		frappe.throw(_("project_name is required"), frappe.ValidationError)

	project = frappe.db.get_value(
		"PWA Push Project",
		{"name": project_name, "enabled": 1},
		["firebase_config", "vapid_public_key"],
		as_dict=True,
	)
	if not is_relay_enabled() or not project:
		frappe.throw(_("Push project {0} is not configured").format(project_name), frappe.DoesNotExistError)

	frappe.response["config"] = json.loads(project.firebase_config)
	frappe.response["vapid_public_key"] = project.vapid_public_key
