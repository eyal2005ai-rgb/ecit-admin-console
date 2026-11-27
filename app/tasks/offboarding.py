"""Offboarding task, v1: core account lock.

Steps run in this order:
  1. Block sign-in
  2. Reset password to a random value nobody knows
  3. Remove MFA / sign-in methods (all except the password itself)
  4. Revoke all sign-in sessions (last, so anything issued meanwhile is killed too)

`build_plan` only READS from Graph (dry run). `execute` makes the changes.
"""
from __future__ import annotations

import secrets
import string
from typing import Callable
from urllib.parse import quote

from ..graph import GraphClient, GraphError
from .base import PlannedStep, Status, StepResult

STEP_BLOCK = "block_signin"
STEP_PASSWORD = "reset_password"
STEP_MFA = "remove_mfa"
STEP_REVOKE = "revoke_sessions"

STEPS: list[tuple[str, str, str]] = [
    (STEP_BLOCK, "Block sign-in", "Disable the account so nobody can sign in with it."),
    (STEP_PASSWORD, "Reset password", "Set a long random password that is not shown or stored anywhere."),
    (STEP_MFA, "Remove MFA methods", "Delete Authenticator app, phone, FIDO2 keys, OATH tokens, email "
                                     "and other sign-in methods registered by the user."),
    (STEP_REVOKE, "Revoke all sessions", "Sign the user out of every app and device (Outlook, Teams, "
                                         "browsers, phones). Done last on purpose."),
]
STEP_TITLES = {sid: title for sid, title, _ in STEPS}

# Graph @odata.type -> URL segment under /users/{id}/authentication/
METHOD_SEGMENTS = {
    "#microsoft.graph.phoneAuthenticationMethod": "phoneMethods",
    "#microsoft.graph.microsoftAuthenticatorAuthenticationMethod": "microsoftAuthenticatorMethods",
    "#microsoft.graph.softwareOathAuthenticationMethod": "softwareOathMethods",
    "#microsoft.graph.fido2AuthenticationMethod": "fido2Methods",
    "#microsoft.graph.emailAuthenticationMethod": "emailMethods",
    "#microsoft.graph.windowsHelloForBusinessAuthenticationMethod": "windowsHelloForBusinessMethods",
    "#microsoft.graph.temporaryAccessPassAuthenticationMethod": "temporaryAccessPassMethods",
    "#microsoft.graph.platformCredentialAuthenticationMethod": "platformCredentialMethods",
}
PASSWORD_METHOD = "#microsoft.graph.passwordAuthenticationMethod"
MOBILE_PHONE_ID = "3179e48a-750b-4051-897c-87b9720928f7"  # must be deleted after alternateMobile


class TargetNotAllowed(Exception):
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _mask(value: str, keep: int = 3) -> str:
    if not value:
        return ""
    if "@" in value:
        name, _, domain = value.partition("@")
        return f"{name[:2]}***@{domain}"
    return "*" * max(len(value) - keep, 0) + value[-keep:]


def describe_method(m: dict) -> str:
    t = m.get("@odata.type", "")
    if t.endswith("phoneAuthenticationMethod"):
        return f"Phone ({m.get('phoneType', 'phone')}) {_mask(m.get('phoneNumber', ''))}"
    if t.endswith("microsoftAuthenticatorAuthenticationMethod"):
        return f"Microsoft Authenticator on {m.get('displayName') or m.get('deviceTag') or 'device'}"
    if t.endswith("fido2AuthenticationMethod"):
        return f"FIDO2 security key / passkey: {m.get('displayName') or m.get('model') or 'key'}"
    if t.endswith("softwareOathAuthenticationMethod"):
        return "Software OATH token (authenticator code app)"
    if t.endswith("emailAuthenticationMethod"):
        return f"Email for password reset: {_mask(m.get('emailAddress', ''))}"
    if t.endswith("windowsHelloForBusinessAuthenticationMethod"):
        return f"Windows Hello for Business: {m.get('displayName') or 'device'}"
    if t.endswith("temporaryAccessPassAuthenticationMethod"):
        return "Temporary Access Pass"
    if t.endswith("platformCredentialAuthenticationMethod"):
        return f"Platform credential (macOS): {m.get('displayName') or 'device'}"
    return t.replace("#microsoft.graph.", "") or "Unknown method"


def removable_methods(methods: list[dict]) -> list[dict]:
    """Methods we can delete, ordered so the mobile phone goes last."""
    out = [m for m in methods if m.get("@odata.type") in METHOD_SEGMENTS]
    return sorted(out, key=lambda m: m.get("id") == MOBILE_PHONE_ID)


def generate_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.islower() for c in pw) and any(c.isupper() for c in pw)
                and any(c.isdigit() for c in pw) and any(not c.isalnum() for c in pw)):
            return pw


def validate_target(user: dict, admin_upn: str) -> list[str]:
    """Raises TargetNotAllowed for hard stops; returns warnings otherwise."""
    upn = (user.get("userPrincipalName") or "").lower()
    if admin_upn and upn == admin_upn.lower():
        raise TargetNotAllowed("You can't offboard the account you are signed in with.")
    warnings = []
    if user.get("accountEnabled") is False:
        warnings.append("This account is already blocked from signing in.")
    if "#EXT#" in upn:
        warnings.append("This is a guest (external) account. Offboarding still works, but you may "
                        "prefer to simply delete the guest.")
    return warnings


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------
def build_plan(graph: GraphClient, user: dict, selected: list[str]) -> list[PlannedStep]:
    name = user.get("displayName") or user.get("userPrincipalName")
    plan: list[PlannedStep] = []
    for sid, title, _ in STEPS:
        if sid not in selected:
            continue
        if sid == STEP_BLOCK:
            if user.get("accountEnabled") is False:
                plan.append(PlannedStep(sid, title, ["Already blocked — will be confirmed again."], False))
            else:
                plan.append(PlannedStep(sid, title, [f"Set accountEnabled = false for {name}."]))
        elif sid == STEP_PASSWORD:
            plan.append(PlannedStep(sid, title, [
                "Set a random 24-character password (not displayed, not logged).",
                "Require password change at next sign-in.",
            ]))
        elif sid == STEP_MFA:
            try:
                methods = removable_methods(graph.list_auth_methods(user["id"]))
            except GraphError as e:
                plan.append(PlannedStep(sid, title, [f"Could not read methods: {e.friendly}"], False))
                continue
            if methods:
                plan.append(PlannedStep(sid, title, [f"Delete: {describe_method(m)}" for m in methods]))
            else:
                plan.append(PlannedStep(sid, title, ["No MFA methods registered — nothing to remove."], False))
        elif sid == STEP_REVOKE:
            plan.append(PlannedStep(sid, title, [
                "Invalidate all refresh tokens and session cookies (may take a few minutes to "
                "reach every app)."]))
    return plan


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------
ProgressFn = Callable[[str], None]


def _run_block(graph: GraphClient, uid: str) -> StepResult:
    graph.patch(f"/users/{quote(uid)}", {"accountEnabled": False})
    return StepResult(STEP_BLOCK, STEP_TITLES[STEP_BLOCK], Status.OK, "Sign-in blocked.")


def _run_password(graph: GraphClient, uid: str) -> StepResult:
    graph.patch(f"/users/{quote(uid)}", {"passwordProfile": {
        "password": generate_password(), "forceChangePasswordNextSignIn": True}})
    return StepResult(STEP_PASSWORD, STEP_TITLES[STEP_PASSWORD], Status.OK,
                      "Password reset to a random value (not recorded).")


def _run_mfa(graph: GraphClient, uid: str, progress: ProgressFn) -> StepResult:
    pending = removable_methods(graph.list_auth_methods(uid))
    title = STEP_TITLES[STEP_MFA]
    if not pending:
        return StepResult(STEP_MFA, title, Status.SKIPPED, "No MFA methods registered.")
    removed: list[str] = []
    errors: dict[str, str] = {}
    # Several passes: the user's default method can only be deleted once the others are gone.
    for _ in range(3):
        still: list[dict] = []
        for m in pending:
            label = describe_method(m)
            seg = METHOD_SEGMENTS[m["@odata.type"]]
            try:
                graph.delete(f"/users/{quote(uid)}/authentication/{seg}/{quote(m['id'])}")
                removed.append(label)
                errors.pop(label, None)
                progress(f"  removed {label}")
            except GraphError as e:
                errors[label] = e.friendly
                still.append(m)
        pending = still
        if not pending:
            break
    items = [f"Removed: {x}" for x in removed] + [f"NOT removed: {k} — {v}" for k, v in errors.items()]
    if not errors:
        return StepResult(STEP_MFA, title, Status.OK, f"{len(removed)} method(s) removed.", items)
    status = Status.PARTIAL if removed else Status.FAILED
    return StepResult(STEP_MFA, title, status,
                      f"{len(removed)} removed, {len(errors)} could not be removed.", items)


def _run_revoke(graph: GraphClient, uid: str) -> StepResult:
    graph.post(f"/users/{quote(uid)}/revokeSignInSessions")
    return StepResult(STEP_REVOKE, STEP_TITLES[STEP_REVOKE], Status.OK,
                      "All sessions revoked (apps may take a few minutes to notice).")


def execute(graph: GraphClient, user: dict, selected: list[str],
            progress: ProgressFn = lambda _msg: None) -> list[StepResult]:
    uid = user["id"]
    results: list[StepResult] = []
    for sid, title, _ in STEPS:
        if sid not in selected:
            results.append(StepResult(sid, title, Status.SKIPPED, "Not selected."))
            continue
        progress(f"{title}…")
        try:
            if sid == STEP_BLOCK:
                res = _run_block(graph, uid)
            elif sid == STEP_PASSWORD:
                res = _run_password(graph, uid)
            elif sid == STEP_MFA:
                res = _run_mfa(graph, uid, progress)
            else:
                res = _run_revoke(graph, uid)
        except GraphError as e:
            res = StepResult(sid, title, Status.FAILED, e.friendly)
        except Exception as e:  # network errors etc. — keep going with the other steps
            res = StepResult(sid, title, Status.FAILED, f"Unexpected error: {e}")
        progress(f"{title}: {res.status.value}. {res.detail}")
        results.append(res)
    return results
