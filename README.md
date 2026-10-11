# Frappe PWA Push

Self-hosted Web Push relay (Firebase Cloud Messaging) for **any** Progressive Web App built on Frappe Framework — not tied to HRMS or any specific product.

## Why

Frappe's push notifications (`frappe.push_notification.PushNotification`) talk to a relay server under the `notification_relay.api.*` API. Frappe's own relay app is not published, and its hosted relay sends your notifications through Frappe's Firebase project.

This app **is** that relay, installable on your own bench and backed by **your own Firebase project**. It serves the same API through `override_whitelisted_methods`, so Frappe core and existing PWA clients (such as the Frappe HR PWA) work unchanged.

## Features

- **Relay-compatible API** — `auth.get_credential`, `token.add/remove`, `topic.add/remove/subscribe/unsubscribe`, `send_notification.user/topic` and `get_config`.
- **PWA Push Settings** — Firebase service account stored encrypted, plus an allowlist of sites that may register.
- **PWA Push Project** — one per PWA (`project_name`, e.g. `hrms`): Firebase web config + VAPID public key.
- **Per-site API keys** — each registered site gets its own API user (role `PWA Push Client`, no Desk access) and can only touch its own tokens.
- **Delivery** — FCM HTTP v1 in a background job; tokens FCM reports as dead are removed automatically. No extra Python dependencies (`google-auth` ships with Frappe).

## Requirements

- Frappe Framework v16
- Python 3.14+
- A Firebase project with Cloud Messaging API (V1) enabled
- HTTPS (or `localhost`) — browsers only allow push on secure origins

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/thinkspedia/frappe_pwa_push --branch main
bench --site your-site.example install-app frappe_pwa_push
```

## Configuration

On the relay site (it can be the same site as your PWA):

1. Firebase Console → Project settings → **Service accounts** → Generate new private key. Paste the JSON into **PWA Push Settings → Firebase Service Account JSON**.
2. Add each client site's hostname to **Allowed Sites**, then tick **Enabled**.
3. Create a **PWA Push Project** per PWA: Project settings → **General** → your Web app config, and **Cloud Messaging** → Web Push certificates → public key.

On each client site:

1. `bench --site your-site.example set-config push_relay_server_url https://relay.example`
2. **Push Notification Settings** → Enable Push Notification Relay. The site registers itself with the relay on first use.

Never commit the service account JSON or any key file to git.

## Usage

Use Frappe's own API — nothing app-specific:

```python
from frappe.push_notification import PushNotification

PushNotification("hrms").send_notification_to_user(
	"employee@example.com", "Leave approved", "Your leave for 12-10 was approved.", link="/hrms/leave-applications"
)
```

Frappe HR's PWA already registers devices and creates push notifications for its PWA Notifications. Other PWAs need a client that requests notification permission, registers the Firebase service worker and calls `frappe.push_notification.subscribe`.

## Security

- The service account lives only in PWA Push Settings, encrypted.
- Only allowlisted sites can register; the relay confirms each registration through the site's own webhook.
- Each site's API key is scoped to that site's tokens and topics.
- See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## Contributing

This app uses `pre-commit` for code formatting and linting (ruff, eslint, prettier, pyupgrade):

```bash
cd apps/frappe_pwa_push
pre-commit install
```

## CI

- **CI** — installs the app and runs unit tests on every push to `main`.
- **Linters** — runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.

## License

MIT — see [license.txt](license.txt).
