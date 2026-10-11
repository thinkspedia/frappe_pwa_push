import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from frappe_pwa_push.relay import auth, config, fcm, send_notification, token, topic

CLIENT_SITE = "client.example.test"
PROJECT = "test-pwa"
WEBHOOK_ROUTE = "/api/method/frappe.push_notification.auth_webhook?secret=abc"
REGISTRATION_TOKEN = "registration-token"
SERVICE_ACCOUNT = {
	"type": "service_account",
	"project_id": "demo-project",
	"private_key": "-----BEGIN PRIVATE KEY-----\nkey\n-----END PRIVATE KEY-----\n",
	"client_email": "relay@demo-project.iam.gserviceaccount.com",
}
WEB_CONFIG = {"apiKey": "key", "projectId": "demo-project", "messagingSenderId": "1", "appId": "1:1:web:1"}


def fcm_response(ok=True, status_code=200, error_code=None, message=""):
	error = {"message": message, "details": [{"errorCode": error_code}] if error_code else []}
	return MagicMock(ok=ok, status_code=status_code, text=message, json=lambda: {"error": error})


class TestRelay(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		settings = frappe.get_single("PWA Push Settings")
		settings.service_account_json = json.dumps(SERVICE_ACCOUNT)
		settings.enabled = 1
		settings.set("allowed_sites", [{"site_name": CLIENT_SITE.upper()}])
		settings.save()
		if not frappe.db.exists("PWA Push Project", PROJECT):
			frappe.get_doc(
				{
					"doctype": "PWA Push Project",
					"project_name": PROJECT,
					"vapid_public_key": "vapid-public-key",
					"firebase_config": json.dumps(WEB_CONFIG),
				}
			).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def register(self, site=CLIENT_SITE, webhook_text=REGISTRATION_TOKEN, webhook_route=WEBHOOK_ROUTE):
		frappe.set_user("Guest")
		with patch(
			"frappe_pwa_push.relay.auth.requests.get",
			return_value=MagicMock(status_code=200, text=webhook_text),
		) as webhook:
			response = auth.get_credential(
				endpoint=site,
				protocol="https",
				port="",
				token=REGISTRATION_TOKEN,
				webhook_route=webhook_route,
			)
		frappe.set_user("Administrator")
		self.webhook = webhook
		return response

	def act_as_client(self):
		credentials = self.register()["credentials"]
		frappe.set_user(frappe.db.get_value("User", {"api_key": credentials["api_key"]}))

	def test_registration_issues_credentials_to_allowed_site(self):
		response = self.register()

		self.assertTrue(response["success"])
		self.assertEqual(set(response["credentials"]), {"api_key", "api_secret"})
		client_user = frappe.db.get_value("PWA Push Client Site", CLIENT_SITE, "user")
		self.assertIn("PWA Push Client", frappe.get_roles(client_user))
		self.webhook.assert_called_once_with(f"https://{CLIENT_SITE}{WEBHOOK_ROUTE}", timeout=10)

	def test_registration_rejects_site_outside_allowlist(self):
		response = self.register(site="other.example.test")

		self.assertFalse(response["success"])
		self.assertFalse(frappe.db.exists("PWA Push Client Site", "other.example.test"))

	def test_registration_rejects_unconfirmed_token(self):
		self.assertFalse(self.register(webhook_text="something-else")["success"])

	def test_registration_never_calls_foreign_routes(self):
		response = self.register(webhook_route="/api/method/some.other.endpoint")

		self.assertFalse(response["success"])
		self.webhook.assert_not_called()

	def test_token_belongs_to_last_registering_user(self):
		self.act_as_client()

		self.assertTrue(token.add("first@example.test", "token-1", PROJECT, CLIENT_SITE)["success"])
		token.add("second@example.test", "token-1", PROJECT, CLIENT_SITE)
		self.assertEqual(
			frappe.get_all("PWA Push Token", filters={"fcm_token": "token-1"}, pluck="user_id"),
			["second@example.test"],
		)

		token.remove("second@example.test", "token-1", PROJECT, CLIENT_SITE)
		self.assertFalse(frappe.db.exists("PWA Push Token", {"fcm_token": "token-1"}))

	def test_token_add_fails_for_unknown_project(self):
		self.act_as_client()

		self.assertFalse(token.add("user@example.test", "token-1", "missing-project", CLIENT_SITE)["success"])

	def test_client_cannot_act_for_another_site(self):
		self.act_as_client()

		with self.assertRaises(frappe.PermissionError):
			token.add("user@example.test", "token-1", PROJECT, "other.example.test")

	def test_send_to_user_queues_that_users_tokens(self):
		self.act_as_client()
		token.add("user@example.test", "token-1", PROJECT, CLIENT_SITE)
		token.add("other@example.test", "token-2", PROJECT, CLIENT_SITE)

		with patch("frappe_pwa_push.relay.fcm.frappe.enqueue") as enqueue:
			response = send_notification.user(
				user_id="user@example.test",
				project_name=PROJECT,
				site_name=CLIENT_SITE,
				title="Leave approved",
				body="Body",
				data=json.dumps({"click_action": "/hrms"}),
			)

		self.assertTrue(response["success"])
		kwargs = enqueue.call_args.kwargs
		self.assertEqual(kwargs["tokens"], ["token-1"])
		self.assertEqual(
			kwargs["payload"], {"click_action": "/hrms", "title": "Leave approved", "body": "Body"}
		)

	def test_send_without_title_still_queues(self):
		self.act_as_client()
		token.add("user@example.test", "token-1", PROJECT, CLIENT_SITE)

		with patch("frappe_pwa_push.relay.fcm.frappe.enqueue") as enqueue:
			response = send_notification.user(
				user_id="user@example.test", project_name=PROJECT, site_name=CLIENT_SITE, body="Body"
			)

		self.assertTrue(response["success"])
		self.assertEqual(enqueue.call_args.kwargs["payload"], {"title": "", "body": "Body"})

	def test_send_to_topic_reaches_only_subscribers(self):
		self.act_as_client()
		token.add("subscriber@example.test", "token-1", PROJECT, CLIENT_SITE)
		token.add("outsider@example.test", "token-2", PROJECT, CLIENT_SITE)
		topic.add("announcements", PROJECT, CLIENT_SITE)
		self.assertTrue(
			topic.subscribe("subscriber@example.test", "announcements", PROJECT, CLIENT_SITE)["success"]
		)

		with patch("frappe_pwa_push.relay.fcm.frappe.enqueue") as enqueue:
			send_notification.topic(
				topic_name="announcements",
				project_name=PROJECT,
				site_name=CLIENT_SITE,
				title="Title",
				body="Body",
			)

		self.assertEqual(enqueue.call_args.kwargs["tokens"], ["token-1"])

	def test_delivery_prunes_dead_tokens_only(self):
		self.act_as_client()
		token.add("user@example.test", "dead-token", PROJECT, CLIENT_SITE)
		token.add("user@example.test", "live-token", PROJECT, CLIENT_SITE)
		frappe.set_user("Administrator")

		def fake_post(url, json, timeout):
			if json["message"]["token"] == "dead-token":
				return fcm_response(ok=False, status_code=404, error_code="UNREGISTERED")
			return fcm_response()

		with (
			patch("frappe_pwa_push.relay.fcm.get_fcm_access", return_value=("demo-project", "access-token")),
			patch("frappe_pwa_push.relay.fcm.requests.Session.post", side_effect=fake_post),
		):
			fcm.deliver(["dead-token", "live-token"], {"title": "Title", "body": "Body"})

		remaining = frappe.get_all(
			"PWA Push Token", filters={"fcm_token": ["in", ["dead-token", "live-token"]]}, pluck="fcm_token"
		)
		self.assertEqual(remaining, ["live-token"])

	def test_payload_values_are_strings(self):
		payload = fcm.build_payload("Title", "Body", json.dumps({"count": 3, "click_action": "/hrms"}))

		self.assertEqual(payload, {"count": "3", "click_action": "/hrms", "title": "Title", "body": "Body"})

	def test_get_config_answers_at_top_level(self):
		config.get_config(PROJECT)

		self.assertEqual(frappe.response["config"], WEB_CONFIG)
		self.assertEqual(frappe.response["vapid_public_key"], "vapid-public-key")

	def test_settings_accept_hostnames_only(self):
		settings = frappe.get_single("PWA Push Settings")
		settings.set("allowed_sites", [{"site_name": "erp.example.test:8000"}])

		with self.assertRaises(frappe.ValidationError):
			settings.save()

	def test_settings_reject_non_service_account_json(self):
		settings = frappe.get_single("PWA Push Settings")
		settings.service_account_json = json.dumps(WEB_CONFIG)

		with self.assertRaises(frappe.ValidationError):
			settings.save()
