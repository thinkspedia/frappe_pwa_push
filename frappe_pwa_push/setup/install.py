import frappe

CLIENT_ROLE = "PWA Push Client"


def after_install() -> None:
	ensure_client_role()


def ensure_client_role() -> None:
	"""API users of registered sites hold only this role, with no Desk access."""
	if frappe.db.exists("Role", CLIENT_ROLE):
		return
	frappe.get_doc({"doctype": "Role", "role_name": CLIENT_ROLE, "desk_access": 0}).insert(
		ignore_permissions=True
	)
