# Frappe PWA Push

Generic Web Push notifications (Firebase Cloud Messaging) for **any** Progressive Web App built on Frappe Framework — not tied to HRMS or any specific product.

> **Status:** early development (v0.x). APIs below are the planned v0.1 surface and may change.

## Why

Frappe ships a built-in push relay that routes through a third-party relay server. This app instead talks directly to **your own Firebase project**, so you control the credentials, delivery, and data — and any number of Frappe PWAs on the same site can share one push engine.

## Features (planned v0.1)

- **Push Settings** — Firebase web config + service-account credentials stored encrypted (Password field), never in code.
- **Push Subscription** — one row per user × device × app (`app_name`, token, user agent, last seen).
- **Server API** — `frappe_pwa_push.api.send(user, title, body, url=None, app_name=None)`, queued via `frappe.enqueue`; tokens rejected by FCM are pruned automatically.
- **JS client** — permission prompt, service-worker registration and token sync, usable from any Vue/frappe-ui or plain-JS PWA.
- **Notification Log bridge** (optional) — every new Frappe Notification Log is also delivered as a push, so existing notifications work without extra code.

## Requirements

- Frappe Framework v16
- Python 3.14+
- A Firebase project with Cloud Messaging enabled
- HTTPS site (browsers only allow push on secure origins)

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/thinkspedia/frappe_pwa_push --branch main
bench --site your-site.example install-app frappe_pwa_push
```

## Configuration

1. Firebase Console → Project settings → **General**: copy the Web app config.
2. **Cloud Messaging** → Web Push certificates: generate / copy the VAPID key pair.
3. **Service accounts** → Generate new private key (JSON).
4. In Desk, open **Push Settings** and paste the values. Do not commit any of these files to git.

## Usage (planned)

Server side:

```python
from frappe_pwa_push.api import send

send(
	user="employee@example.com",
	title="Leave approved",
	body="Your leave for 12-10 was approved.",
	url="/hrms/leave-applications",
	app_name="hrms",
)
```

Client side (inside your PWA):

```js
import { registerPush } from "/assets/frappe_pwa_push/js/client.js"

await registerPush({ appName: "hrms" })
```

Other apps should treat this app as an **optional** dependency — check `"frappe_pwa_push" in frappe.get_installed_apps()` before calling it.

## Security

- Credentials live only in Push Settings (encrypted) or `site_config.json`.
- Tokens are scoped per user; users can only manage their own subscriptions.
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
