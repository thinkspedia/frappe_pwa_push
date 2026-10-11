import frappe
from frappe import _

from frappe_pwa_push.relay.common import get_client_site, is_project_enabled, project_not_configured, result
from frappe_pwa_push.relay.fcm import queue_delivery
from frappe_pwa_push.relay.topic import get_topic


# title/body default to "": the client drops None-valued form fields (e.g. HRMS sends a PWA
# Notification's reference doctype as the title, which may be empty), and that must not fail.
@frappe.whitelist(methods=["POST"])
def user(
	user_id: str,
	project_name: str,
	site_name: str,
	title: str = "",
	body: str = "",
	data: str | None = None,
) -> dict:
	client_site = get_client_site(site_name)
	if not is_project_enabled(project_name):
		return project_not_configured(project_name)

	tokens = frappe.get_all(
		"PWA Push Token",
		filters={"project": project_name, "client_site": client_site, "user_id": user_id},
		pluck="fcm_token",
	)
	queue_delivery(tokens, title, body, data)
	return result(True, _("Queued for {0} device(s)").format(len(tokens)))


@frappe.whitelist(methods=["POST"])
def topic(
	topic_name: str,
	project_name: str,
	site_name: str,
	title: str = "",
	body: str = "",
	data: str | None = None,
) -> dict:
	client_site = get_client_site(site_name)
	if not is_project_enabled(project_name):
		return project_not_configured(project_name)

	topic_id = get_topic(project_name, client_site, topic_name)
	if not topic_id:
		return result(False, _("Topic {0} does not exist").format(topic_name))

	subscribers = frappe.get_all("PWA Push Topic Subscription", filters={"topic": topic_id}, pluck="user_id")
	tokens = frappe.get_all(
		"PWA Push Token",
		filters={"project": project_name, "client_site": client_site, "user_id": ["in", subscribers or [""]]},
		pluck="fcm_token",
	)
	queue_delivery(tokens, title, body, data)
	return result(True, _("Queued for {0} device(s)").format(len(tokens)))
