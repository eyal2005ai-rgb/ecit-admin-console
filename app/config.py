"""Central configuration for the ECIT One-Window Admin Console."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "ECIT Admin Console"
APP_ID = "ECITAdminConsole"
APP_VERSION = "0.1.0"
PUBLISHER = "ECIT IT Services"
CONTACT_EMAIL = "info@ecit.co.il"
WEBSITE = "https://ecit.co.il"
BRAND_LINE = f"Free tool by ECIT · {CONTACT_EMAIL} · ecit.co.il"

# ---------------------------------------------------------------------------
# Microsoft Entra app registration
# There is NO built-in client ID. Each admin registers the app in their own
# tenant (see docs/SETUP_APP_REGISTRATION.md) and enters the tenant and
# Application (client) ID in the app: Connections → Add. See app/connections.py.
# ---------------------------------------------------------------------------
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Least-privileged delegated permissions for v1 (Offboarding: core account lock).
SCOPES = [
    "User.Read",                              # who is signed in
    "User.Read.All",                          # search / read the target user
    "User.EnableDisableAccount.All",          # block sign-in
    "User-PasswordProfile.ReadWrite.All",     # reset password
    "User.RevokeSessions.All",                # revoke sign-in sessions
    "UserAuthenticationMethod.ReadWrite.All", # remove MFA methods
]

EULA_VERSION = "2026-11-draft-1"


def resource_path(relative: str) -> Path:
    """Path to a bundled resource; works from source and from a PyInstaller build."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "resources" / relative


def docs_path(relative: str) -> Path:
    """Path to a bundled document (setup guide, PowerShell script)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "docs" / relative


def data_dir() -> Path:
    """Per-user writable folder for settings and audit logs."""
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = root / APP_ID
    path.mkdir(parents=True, exist_ok=True)
    return path


def audit_dir() -> Path:
    path = data_dir() / "audit"
    path.mkdir(parents=True, exist_ok=True)
    return path
