import json
from datetime import UTC, datetime

import frappe
import google.auth.transport.requests
import requests
from frappe.utils import cstr
from google.oauth2 import service_account

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FCM_SEND_URL = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
ACCESS_TOKEN_CACHE_KEY = "pwa_push_fcm_access_token"
ACCESS_TOKEN_REFRESH_MARGIN_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 10


def queue_delivery(tokens: list[str], title: str, body: str, data: str | None) -> None:
	if not tokens:
		return
	frappe.enqueue(
		"frappe_pwa_push.relay.fcm.deliver",
		queue="short",
		enqueue_after_commit=True,
		tokens=tokens,
		payload=build_payload(title, body, data),
	)


def build_payload(title: str, body: str, data: str | None) -> dict[str, str]:
	"""FCM data message; the service worker reads title/body/click_action from `data`.

	FCM only accepts string values in `data`, so nested values are JSON-encoded.
	"""
	extra = json.loads(data) if data else {}
	payload = {**extra, "title": cstr(title), "body": cstr(body)}
	return {key: value if isinstance(value, str) else json.dumps(value) for key, value in payload.items()}


def deliver(tokens: list[str], payload: dict[str, str]) -> None:
	project_id, access_token = get_fcm_access()
	url = FCM_SEND_URL.format(project_id=project_id)
	stale_tokens = []

	with requests.Session() as session:
		session.headers["Authorization"] = f"Bearer {access_token}"
		for token in tokens:
			response = session.post(url, json=build_message(token, payload), timeout=REQUEST_TIMEOUT_SECONDS)
			if response.ok:
				continue
			if is_stale_token_error(response):
				stale_tokens.append(token)
			else:
				frappe.log_error("PWA Push delivery failed", f"{response.status_code}: {response.text}")

	if stale_tokens:
		frappe.db.delete("PWA Push Token", {"fcm_token": ["in", stale_tokens]})


def build_message(token: str, payload: dict[str, str]) -> dict:
	return {"message": {"token": token, "data": payload, "webpush": {"headers": {"Urgency": "high"}}}}


def is_stale_token_error(response: requests.Response) -> bool:
	"""True when FCM says the token itself is dead (uninstalled app, cleared site data)."""
	try:
		error = response.json().get("error", {})
	except ValueError:
		return False

	error_codes = {detail.get("errorCode") for detail in error.get("details", [])}
	if "UNREGISTERED" in error_codes:
		return True
	return "INVALID_ARGUMENT" in error_codes and "registration token" in cstr(error.get("message")).lower()


def get_fcm_access() -> tuple[str, str]:
	settings = frappe.get_single("PWA Push Settings")
	cached_token = frappe.cache.get_value(ACCESS_TOKEN_CACHE_KEY)
	if cached_token:
		return settings.firebase_project_id, cached_token

	credentials = service_account.Credentials.from_service_account_info(
		json.loads(settings.get_password("service_account_json")), scopes=[FCM_SCOPE]
	)
	credentials.refresh(google.auth.transport.requests.Request())

	# google-auth reports expiry as a naive UTC datetime.
	lifetime = (credentials.expiry - datetime.now(UTC).replace(tzinfo=None)).total_seconds()
	frappe.cache.set_value(
		ACCESS_TOKEN_CACHE_KEY,
		credentials.token,
		expires_in_sec=max(int(lifetime) - ACCESS_TOKEN_REFRESH_MARGIN_SECONDS, 1),
	)
	return settings.firebase_project_id, credentials.token


def clear_cached_access_token() -> None:
	frappe.cache.delete_value(ACCESS_TOKEN_CACHE_KEY)
