"""Thin Microsoft Graph REST client with throttling retries."""
from __future__ import annotations

import time
from typing import Any, Callable
from urllib.parse import quote

import requests

from .config import GRAPH_BASE


class GraphError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message

    @property
    def friendly(self) -> str:
        if self.status == 403 or self.code in ("Authorization_RequestDenied", "Forbidden"):
            return ("Access denied. Your account needs the right admin role "
                    "(User Administrator / Authentication Administrator, or higher for admin users) "
                    f"and the app needs consent. Details: {self.message}")
        if self.status == 404:
            return f"Not found. Details: {self.message}"
        return f"{self.code}: {self.message}"


class GraphClient:
    """Calls Graph with a bearer token supplied by `token_provider`."""

    def __init__(self, token_provider: Callable[[], str], session: requests.Session | None = None,
                 max_retries: int = 4):
        self._token = token_provider
        self._session = session or requests.Session()
        self._max_retries = max_retries

    def request(self, method: str, path: str, *, json: Any = None,
                params: dict | None = None, headers: dict | None = None) -> Any:
        url = path if path.startswith("http") else f"{GRAPH_BASE}{path}"
        for attempt in range(self._max_retries + 1):
            hdrs = {"Authorization": f"Bearer {self._token()}", "Accept": "application/json"}
            if headers:
                hdrs.update(headers)
            resp = self._session.request(method, url, json=json, params=params, headers=hdrs, timeout=60)
            if resp.status_code in (429, 502, 503, 504) and attempt < self._max_retries:
                wait = float(resp.headers.get("Retry-After", 2 ** attempt))
                time.sleep(min(wait, 30))
                continue
            if resp.status_code >= 400:
                try:
                    err = resp.json().get("error", {})
                except ValueError:
                    err = {}
                raise GraphError(resp.status_code, err.get("code", "Error"),
                                 err.get("message", resp.text[:300]))
            if resp.status_code == 204 or not resp.content:
                return None
            return resp.json()
        raise GraphError(429, "TooManyRequests", "Gave up after repeated throttling")

    # Convenience wrappers ---------------------------------------------------
    def get(self, path: str, **kw) -> Any:
        return self.request("GET", path, **kw)

    def patch(self, path: str, body: dict) -> Any:
        return self.request("PATCH", path, json=body)

    def post(self, path: str, body: dict | None = None) -> Any:
        return self.request("POST", path, json=body or {})

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)

    # Domain helpers ---------------------------------------------------------
    USER_FIELDS = "id,displayName,userPrincipalName,mail,jobTitle,department,accountEnabled,assignedLicenses"

    def me(self) -> dict:
        return self.get("/me", params={"$select": "id,displayName,userPrincipalName"})

    def organization(self) -> dict:
        data = self.get("/organization", params={"$select": "id,displayName,verifiedDomains"})
        return (data.get("value") or [{}])[0]

    def search_users(self, text: str, top: int = 15) -> list[dict]:
        text = text.replace('"', "")
        data = self.get(
            "/users",
            params={"$search": f'"displayName:{text}" OR "userPrincipalName:{text}" OR "mail:{text}"',
                    "$select": self.USER_FIELDS, "$top": str(top), "$orderby": "displayName"},
            headers={"ConsistencyLevel": "eventual"},
        )
        return data.get("value", [])

    def get_user(self, user_id: str) -> dict:
        return self.get(f"/users/{quote(user_id)}", params={"$select": self.USER_FIELDS})

    def list_auth_methods(self, user_id: str) -> list[dict]:
        return self.get(f"/users/{quote(user_id)}/authentication/methods").get("value", [])
