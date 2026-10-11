import frappe
from frappe import _
from frappe.utils import now_datetime

from frappe_pwa_push.relay.common import get_client_site, is_project_enabled, project_not_configured, result


@frappe.whitelist(methods=["POST"])
def add(user_id: str, fcm_token: str, project_name: str, site_name: str) -> dict:
	client_site = get_client_site(site_name)
	if not is_project_enabled(project_name):
		return project_not_configured(project_name)

	values = {"client_site": client_site, "user_id": user_id, "last_seen_on": now_datetime()}
	# A browser token belongs to whoever registered it last (shared phone, re-login).
	existing = frappe.db.get_value(
		"PWA Push Token", {"project": project_name, "fcm_token": fcm_token}, "name"
	)
	if existing:
		frappe.db.set_value("PWA Push Token", existing, values)
	else:
		frappe.get_doc(
			{"doctype": "PWA Push Token", "project": project_name, "fcm_token": fcm_token, **values}
		).insert(ignore_permissions=True)
	return result(True, _("Device registered for push notifications"))


@frappe.whitelist(methods=["POST"])
def remove(user_id: str, fcm_token: str, project_name: str, site_name: str) -> dict:
	client_site = get_client_site(site_name)
	frappe.db.delete(
		"PWA Push Token",
		{"project": project_name, "client_site": client_site, "user_id": user_id, "fcm_token": fcm_token},
	)
	return result(True, _("Device unregistered from push notifications"))
