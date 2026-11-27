"""Interactive Microsoft sign-in (delegated) with MSAL.

Tokens are kept in memory only: nothing is written to disk, so closing the
app signs the admin out.
"""
from __future__ import annotations

import msal

from .config import SCOPES


class AuthError(Exception):
    pass


# Common Entra sign-in errors, explained for the admin who set up the connection.
_HINTS = {
    "AADSTS700016": "The Application (client) ID was not found in this tenant. Check that you copied "
                    "the Application (client) ID of the app you registered, and that the tenant in the "
                    "connection is the tenant where you registered it.",
    "AADSTS90002": "Tenant not found. Check the Directory (tenant) ID or domain in the connection.",
    "AADSTS900023": "The tenant value is not valid. Use the Directory (tenant) ID or a verified domain.",
    "AADSTS50011": "Redirect URI mismatch. In the app registration go to Authentication → "
                   "Add a platform → Mobile and desktop applications, and add http://localhost.",
    "AADSTS7000218": "Public client flows are off. In the app registration go to Authentication → "
                     "Advanced settings → Allow public client flows → Yes, then Save.",
    "AADSTS65001": "The permissions have not been approved yet. In the app registration go to "
                   "API permissions → Grant admin consent for <your tenant> (needs a Global Administrator "
                   "or Privileged Role Administrator).",
    "AADSTS90094": "Admin approval is required. A Global Administrator must open the app registration → "
                   "API permissions → Grant admin consent.",
    "AADSTS50020": "This account is not a member of the tenant in the connection. Sign in with an admin "
                   "account of that tenant.",
    "AADSTS50105": "Your account is not assigned to this app. Ask a Global Administrator to assign you, "
                   "or turn off 'Assignment required' on the app's Enterprise application.",
}


def explain(error_text: str) -> str:
    for code, hint in _HINTS.items():
        if code in (error_text or ""):
            return f"{hint}\n\n(Microsoft error {code})"
    return error_text or "Sign-in failed"


class AuthSession:
    def __init__(self, client_id: str, authority: str):
        self._client_id = client_id
        self._authority = authority
        self._msal: msal.PublicClientApplication | None = None
        self._account: dict | None = None

    @property
    def _app(self) -> msal.PublicClientApplication:
        # Created lazily: MSAL contacts Microsoft on creation, so the app can start offline.
        if self._msal is None:
            self._msal = msal.PublicClientApplication(self._client_id, authority=self._authority)
        return self._msal

    @property
    def signed_in(self) -> bool:
        return self._account is not None

    @property
    def username(self) -> str:
        return (self._account or {}).get("username", "")

    @property
    def tenant_id(self) -> str:
        return ((self._account or {}).get("home_account_id", "").split(".") + ["", ""])[1]

    def sign_in(self) -> None:
        """Opens the system browser for Microsoft sign-in and consent."""
        try:
            app = self._app
        except Exception as e:  # MSAL validates the tenant on creation
            self._msal = None
            raise AuthError(explain(str(e)) if "AADSTS" in str(e) else
                            "Could not reach the tenant's sign-in page. Check the Directory (tenant) ID "
                            f"or domain in the connection, and your internet connection.\n\n({e})") from e
        result = app.acquire_token_interactive(SCOPES, prompt="select_account")
        if "access_token" not in result:
            raise AuthError(explain(result.get("error_description") or result.get("error") or ""))
        accounts = self._app.get_accounts()
        claims = result.get("id_token_claims", {})
        oid, tid = claims.get("oid"), claims.get("tid")
        self._account = next(
            (a for a in accounts if a.get("home_account_id", "").startswith(f"{oid}.{tid}")),
            accounts[0] if accounts else None,
        )
        if self._account is None:
            raise AuthError("Signed in, but no account was returned")

    def sign_out(self) -> None:
        if self._msal is not None:
            for acc in self._msal.get_accounts():
                self._msal.remove_account(acc)
        self._account = None

    def token(self) -> str:
        if not self._account:
            raise AuthError("Not signed in")
        result = self._app.acquire_token_silent(SCOPES, account=self._account)
        if not result or "access_token" not in result:
            raise AuthError("Session expired. Please sign in again.")
        return result["access_token"]
