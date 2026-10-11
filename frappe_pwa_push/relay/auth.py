import frappe
import requests
from frappe import _
from frappe.utils import now_datetime

from frappe_pwa_push.relay.common import CLIENT_ROLE, result
from frappe_pwa_push.setup.install import ensure_client_role

# The only callback route Frappe's client ever asks us to call; anything else is refused
# so registration can't be used to make this server fetch arbitrary URLs.
WEBHOOK_ROUTE_PREFIX = "/api/method/frappe.push_notification.auth_webhook?"
WEBHOOK_TIMEOUT_SECONDS = 10


@frappe.whitelist(allow_guest=True, methods=["POST"])
def get_credential(endpoint: str, protocol: str, port: str, token: str, webhook_route: str) -> dict:
	"""Register a site (frappe.push_notification.PushNotification._get_credential) and issue API keys."""
	settings = frappe.get_single("PWA Push Settings")
	site_name = (endpoint or "").strip().lower()

	if not settings.enabled:
		return result(False, _("Push relay is disabled"))
	if site_name not in settings.get_allowed_sites():
		return result(False, _("Site {0} is not allowed to use this relay").format(site_name))
	if protocol not in ("http", "https") or not webhook_route.startswith(WEBHOOK_ROUTE_PREFIX):
		return result(False, _("Invalid registration request"))
	if not _webhook_confirms_token(protocol, site_name, port, webhook_route, token):
		return result(False, _("Site {0} could not confirm the registration token").format(site_name))

	return {
		"success": True,
		"message": _("Site registered"),
		"credentials": _issue_credentials(site_name, protocol, port),
	}


def _webhook_confirms_token(protocol: str, site_name: str, port: str, webhook_route: str, token: str) -> bool:
	host = f"{site_name}:{port}" if port else site_name
	try:
		response = requests.get(f"{protocol}://{host}{webhook_route}", timeout=WEBHOOK_TIMEOUT_SECONDS)
	except requests.RequestException:
		return False
	return response.status_code == 200 and response.text.strip() == token


def _issue_credentials(site_name: str, protocol: str, port: str) -> dict:
	email = f"pwa-push-client@{site_name}"
	api_key = frappe.db.get_value("User", email, "api_key") or frappe.generate_hash(length=15)
	api_secret = frappe.generate_hash(length=15)
	_save_client_user(email, site_name, api_key, api_secret)

	_upsert_client_site(site_name, protocol, port, email)
	return {"api_key": api_key, "api_secret": api_secret}


def _save_client_user(email: str, site_name: str, api_key: str, api_secret: str) -> None:
	# Exactly one save per registration: every User save queues a create_contact job, and
	# two of them racing for the same new user deadlock on tabContact.
	keys = {"api_key": api_key, "api_secret": api_secret}
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
		user.update(keys)
		user.save(ignore_permissions=True)
		return

	ensure_client_role()
	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": "PWA Push Client",
			"last_name": site_name,
			"user_type": "Website User",
			"send_welcome_email": 0,
			"roles": [{"role": CLIENT_ROLE}],
			**keys,
		}
	).insert(ignore_permissions=True)


def _upsert_client_site(site_name: str, protocol: str, port: str, user: str) -> None:
	values = {"protocol": protocol, "port": port, "user": user, "last_registered_on": now_datetime()}
	if frappe.db.exists("PWA Push Client Site", site_name):
		frappe.db.set_value("PWA Push Client Site", site_name, values)
		return
	frappe.get_doc({"doctype": "PWA Push Client Site", "site_name": site_name, **values}).insert(
		ignore_permissions=True
	)
