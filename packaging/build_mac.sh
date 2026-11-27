#!/bin/bash
# Builds "ECIT Admin Console.app" and a .dmg (unsigned). Run on a Mac from the project root.
set -euo pipefail
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q tests
rm -rf build dist
pyinstaller --noconfirm packaging/ecit_console.spec
mkdir -p dist/dmg && cp -R "dist/ECIT Admin Console.app" dist/dmg/ && cp resources/EULA.txt dist/dmg/ && cp docs/SETUP_APP_REGISTRATION.md docs/create-app-registration.ps1 dist/dmg/
ln -sf /Applications dist/dmg/Applications
hdiutil create -volname "ECIT Admin Console" -srcfolder dist/dmg -ov -format UDZO "dist/${DMG_NAME:-ECIT-Admin-Console-0.1.0-mac.dmg}"
echo "Done: dist/${DMG_NAME:-ECIT-Admin-Console-0.1.0-mac.dmg}"
echo "Unsigned: users must right-click > Open (or System Settings > Privacy & Security > Open Anyway)."
