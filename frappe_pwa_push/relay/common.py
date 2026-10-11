import frappe
from frappe import _

from frappe_pwa_push.setup.install import CLIENT_ROLE


def result(success: bool, message: str = "") -> dict:
	return {"success": success, "message": message}


def is_relay_enabled() -> bool:
	return bool(frappe.db.get_single_value("PWA Push Settings", "enabled"))


def get_client_site(site_name: str) -> str:
	"""Return the client site owned by the authenticated API user.

	Clients post their own site_name with every call; it must match the site the API key
	was issued to, so one registered site can never touch another site's tokens.
	"""
	if not is_relay_enabled():
		frappe.throw(_("Push relay is disabled"), frappe.PermissionError)
	if CLIENT_ROLE not in frappe.get_roles():
		frappe.throw(_("Not a registered push client"), frappe.PermissionError)

	client_site = frappe.db.get_value("PWA Push Client Site", {"user": frappe.session.user}, "name")
	if not client_site or client_site != site_name:
		frappe.throw(
			_("Site {0} is not registered with this relay").format(site_name), frappe.PermissionError
		)
	return client_site


def is_project_enabled(project_name: str) -> bool:
	return bool(frappe.db.get_value("PWA Push Project", project_name, "enabled"))


def project_not_configured(project_name: str) -> dict:
	return result(False, _("Push project {0} is not configured on the relay").format(project_name))
