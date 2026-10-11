import frappe

from frappe_pwa_push.relay.common import get_client_site, is_project_enabled, project_not_configured, result


def get_topic(project_name: str, client_site: str, topic_name: str) -> str | None:
	return frappe.db.get_value(
		"PWA Push Topic",
		{"project": project_name, "client_site": client_site, "topic_name": topic_name},
		"name",
	)


@frappe.whitelist(methods=["POST"])
def add(topic_name: str, project_name: str, site_name: str) -> dict:
	client_site = get_client_site(site_name)
	if not is_project_enabled(project_name):
		return project_not_configured(project_name)
	if not get_topic(project_name, client_site, topic_name):
		frappe.get_doc(
			{
				"doctype": "PWA Push Topic",
				"project": project_name,
				"client_site": client_site,
				"topic_name": topic_name,
			}
		).insert(ignore_permissions=True)
	return result(True)


@frappe.whitelist(methods=["POST"])
def remove(topic_name: str, project_name: str, site_name: str) -> dict:
	topic = get_topic(project_name, get_client_site(site_name), topic_name)
	if topic:
		frappe.db.delete("PWA Push Topic Subscription", {"topic": topic})
		frappe.delete_doc("PWA Push Topic", topic, ignore_permissions=True)
	return result(True)


@frappe.whitelist(methods=["POST"])
def subscribe(user_id: str, topic_name: str, project_name: str, site_name: str) -> dict:
	topic = get_topic(project_name, get_client_site(site_name), topic_name)
	if not topic:
		return result(False)
	if not frappe.db.exists("PWA Push Topic Subscription", {"topic": topic, "user_id": user_id}):
		frappe.get_doc({"doctype": "PWA Push Topic Subscription", "topic": topic, "user_id": user_id}).insert(
			ignore_permissions=True
		)
	return result(True)


@frappe.whitelist(methods=["POST"])
def unsubscribe(user_id: str, topic_name: str, project_name: str, site_name: str) -> dict:
	topic = get_topic(project_name, get_client_site(site_name), topic_name)
	if topic:
		frappe.db.delete("PWA Push Topic Subscription", {"topic": topic, "user_id": user_id})
	return result(True)
