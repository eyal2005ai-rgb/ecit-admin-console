"""Saved tenant connections.

Each admin registers the app in their OWN Microsoft Entra tenant and enters its
details here once. Nothing depends on an ECIT-owned app registration.

A connection is:  {"name": str, "tenant": str, "client_id": str}
  - tenant: the Directory (tenant) ID (GUID) or a verified domain (contoso.com
    or contoso.onmicrosoft.com)
  - client_id: the Application (client) ID of the admin's own app registration
MSPs can save one connection per customer tenant.
"""
from __future__ import annotations

import re

from . import settings

_GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_DOMAIN = re.compile(r"^(?=.{4,253}$)([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$")

REDIRECT_URI = "http://localhost"


def is_guid(value: str) -> bool:
    return bool(_GUID.match((value or "").strip()))


def normalize(conn: dict) -> dict:
    return {
        "name": (conn.get("name") or "").strip(),
        "tenant": (conn.get("tenant") or "").strip().lower(),
        "client_id": (conn.get("client_id") or "").strip().lower(),
    }


def validate(conn: dict) -> list[str]:
    """Returns a list of problems; empty list means the connection is usable."""
    c = normalize(conn)
    problems = []
    if not c["name"]:
        problems.append("Give the connection a name (for example the customer's name).")
    if not c["tenant"]:
        problems.append("Enter the Directory (tenant) ID or the tenant's domain.")
    elif not (is_guid(c["tenant"]) or _DOMAIN.match(c["tenant"])):
        problems.append("Tenant must be a Directory (tenant) ID like 1234abcd-... "
                        "or a domain like contoso.onmicrosoft.com.")
    elif c["tenant"] in ("common", "organizations", "consumers"):
        problems.append("Use your own tenant ID or domain, not 'common' or 'organizations'.")
    if not c["client_id"]:
        problems.append("Enter the Application (client) ID of your app registration.")
    elif not is_guid(c["client_id"]):
        problems.append("Application (client) ID must look like 1234abcd-12ab-34cd-56ef-1234567890ab.")
    elif c["client_id"] == "00000000-0000-0000-0000-000000000000":
        problems.append("Application (client) ID can't be all zeros.")
    return problems


def authority(conn: dict) -> str:
    return f"https://login.microsoftonline.com/{normalize(conn)['tenant']}"


# ------------------------------------------------------------------ storage
def load_all() -> list[dict]:
    items = settings.load().get("connections") or []
    return [normalize(c) for c in items if isinstance(c, dict)]


def save_all(items: list[dict]) -> None:
    data = settings.load()
    data["connections"] = [normalize(c) for c in items]
    settings.save(data)


def upsert(conn: dict, old_name: str | None = None) -> list[dict]:
    """Adds or replaces a connection (matched by name). Returns the new list."""
    conn = normalize(conn)
    items = [c for c in load_all() if c["name"].lower() not in {conn["name"].lower(), (old_name or "").lower()}]
    items.append(conn)
    items.sort(key=lambda c: c["name"].lower())
    save_all(items)
    set_last(conn["name"])
    return items


def remove(name: str) -> list[dict]:
    items = [c for c in load_all() if c["name"].lower() != name.lower()]
    save_all(items)
    return items


def last_used() -> str:
    return settings.load().get("last_connection", "")


def set_last(name: str) -> None:
    data = settings.load()
    data["last_connection"] = name
    settings.save(data)
