# ECIT Admin Console — v0.1.0

Everyday Microsoft 365 admin jobs in **one window** instead of clicking through several portals.
Free tool by ECIT · info@ecit.co.il · ecit.co.il

**v0.1 contains one task: Offboard employee (core account lock).** The other tasks in the sidebar
are placeholders marked "soon".

## What Offboard employee does

1. **Find** the employee (search by name or email).
2. **Choose** the steps (all on by default):
   - Block sign-in
   - Reset password to a random 24-character value (never shown, never logged)
   - Remove MFA methods (Authenticator, phones, FIDO2 keys, OATH tokens, email, Windows Hello…)
   - Revoke all sessions (runs last on purpose)
3. **Preview (dry run)** — only reads from Microsoft 365 and lists exactly what will change.
4. **Confirm** by typing the employee's email address.
5. **Run** — each step reports Done / Partly done / Failed; one failing step doesn't stop the others.
6. **Audit report** — a branded PDF plus a line in `audit-log.jsonl`, saved on this computer:
   - Mac: `~/Library/Application Support/ECITAdminConsole/audit/`
   - Windows: `%APPDATA%\ECITAdminConsole\audit\`

Safety rails: you can't offboard the account you're signed in with; any change to the user or the
steps cancels the preview; sign-in tokens live in memory only (closing the app signs you out).

## Branding & EULA

- ECIT logo in the sidebar, About screen, app icon and every PDF report; "Free tool by ECIT" line
  in the sidebar and on every PDF page.
- EULA (`resources/EULA.txt`): accepted on first launch (and again if its version changes),
  shown as an accept screen in the Windows installer, viewable any time under **About & license**.
- `resources/ecit_logo.png` is the ECIT IT Services logo (taken from ecit.co.il, 371×216).
  For a sharper look, replace it with a higher-resolution PNG export of the same logo.
- **Have a lawyer review `resources/EULA.txt`** — it is marked DRAFT. If you change it, bump
  `EULA_VERSION` in `app/config.py` so users accept the new text.

## Before first use

There is **no built-in app registration**. Each admin who downloads the app registers it once in
their own tenant (Entra admin center, about 5 minutes, or `docs/create-app-registration.ps1`) and
enters the Directory (tenant) ID and Application (client) ID under **Connections…** in the app.
MSPs save one connection per customer tenant. Full guide: **docs/SETUP_APP_REGISTRATION.md**
(also shown step by step inside the Connections window).

## Run from source (Mac or Windows)

```bash
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m pytest -q tests        # 19 tests, uses a fake Microsoft 365 — no tenant needed
python main.py
```

## Build installers (unsigned)

- Mac: `./packaging/build_mac.sh` → `dist/ECIT-Admin-Console-0.1.0-mac.dmg` (set `DMG_NAME` to rename)
- Or push a tag `v*`: GitHub Actions (`.github/workflows/release.yml`) builds Windows + both Mac versions and creates a pre-release with SHA256SUMS.txt
- Windows: `packaging\build_windows.bat` (needs Inno Setup 6) → `dist\ECIT-Admin-Console-0.1.0-setup.exe`

PyInstaller can't cross-compile: build the Mac version on a Mac and the Windows version on Windows.

## Project layout

```
main.py                    entry point (EULA gate → main window)
app/config.py              name, version, Graph permissions, folders
app/connections.py         saved tenant connections (admin's own app registration per tenant)
app/auth.py                Microsoft sign-in (MSAL, delegated, in-memory)
app/graph.py               Graph REST client with throttling retries
app/tasks/__init__.py      task registry (sidebar) — add new tasks here
app/tasks/offboarding.py   offboarding logic: validate → plan (dry run) → execute
app/audit.py               JSONL log + branded PDF report
app/ui/                    main window, connections, offboarding page, EULA/About dialogs
docs/                      setup guide + PowerShell script for the admin's app registration
resources/                 logo, EULA
packaging/                 PyInstaller spec, build scripts, Inno Setup installer
tests/                     unit tests with a fake Graph
```

## Next tasks for the console (suggested order)

Mailbox handover (convert to shared, auto-reply, manager access) and OneDrive handover + license
removal as extra Offboarding steps; then New employee, Reset password + sign out, and
"Why can't this user sign in?".
