"""Connections: the admin's own app registration per tenant (add / edit / remove)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
                               QTextBrowser, QVBoxLayout)

from .. import connections as cx
from ..config import APP_NAME, SCOPES, docs_path
from .common import logo_label

ENTRA_URL = "https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade"

HOW_TO = f"""
<h3>One-time setup in your tenant (about 5 minutes)</h3>
<p>The app signs in through an app registration that <b>you</b> own in your tenant.
ECIT has no access to it, and you can delete it at any time.</p>
<ol>
<li>Open <b>entra.microsoft.com</b> → <b>Identity → Applications → App registrations → New registration</b>.</li>
<li>Name: <code>ECIT Admin Console</code>. Supported account types:
    <b>Accounts in this organizational directory only (Single tenant)</b>.</li>
<li>Redirect URI: platform <b>Public client/native (mobile &amp; desktop)</b>, value
    <code>{cx.REDIRECT_URI}</code>. Click <b>Register</b>.</li>
<li><b>Authentication</b> → Advanced settings → <b>Allow public client flows: Yes</b> → Save.</li>
<li><b>API permissions</b> → Add a permission → Microsoft Graph → <b>Delegated permissions</b>, add:
    <br/><code>{'<br/>'.join(SCOPES)}</code></li>
<li>Click <b>Grant admin consent for &lt;your tenant&gt;</b> (Global Administrator or Privileged Role Administrator).</li>
<li>From the <b>Overview</b> page copy the <b>Application (client) ID</b> and the
    <b>Directory (tenant) ID</b> into the fields above, and click <b>Save</b>.</li>
</ol>
<p><b>Faster option (PowerShell, Windows or Mac):</b> click <b>Save PowerShell script…</b>, then run
<code>.\\create-app-registration.ps1 -TenantId contoso.onmicrosoft.com</code> as a Global Administrator.
It does steps 1–6, grants admin consent and prints both IDs. (Needs the Microsoft Graph PowerShell module.)</p>
<p>Managing several tenants? Repeat this in each tenant and save one connection per tenant.</p>
<p style='color:#555'>No client secret or certificate is needed. Your sign-in stays on this computer, in memory only.</p>
"""


class ConnectionDialog(QDialog):
    def __init__(self, parent=None, select: str = ""):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} — Connections")
        self.resize(720, 760)
        self._editing: str | None = None

        lay = QVBoxLayout(self)
        lay.addWidget(logo_label(36))

        top = QHBoxLayout()
        top.addWidget(QLabel("Saved connection:"))
        self.combo = QComboBox()
        self.combo.currentIndexChanged.connect(self._load_selected)
        top.addWidget(self.combo, 1)
        self.new_btn = QPushButton("New")
        self.new_btn.clicked.connect(self._new)
        self.del_btn = QPushButton("Delete")
        self.del_btn.clicked.connect(self._delete)
        top.addWidget(self.new_btn)
        top.addWidget(self.del_btn)
        lay.addLayout(top)

        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Contoso Ltd")
        self.tenant = QLineEdit()
        self.tenant.setPlaceholderText("Directory (tenant) ID, or contoso.onmicrosoft.com")
        self.client = QLineEdit()
        self.client.setPlaceholderText("Application (client) ID of YOUR app registration")
        form.addRow("Name", self.name)
        form.addRow("Tenant", self.tenant)
        form.addRow("Application (client) ID", self.client)
        lay.addLayout(form)

        tools = QHBoxLayout()
        open_btn = QPushButton("Open Entra admin center")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(ENTRA_URL)))
        copy_btn = QPushButton("Copy permission list")
        copy_btn.clicked.connect(lambda: QGuiApplication.clipboard().setText("\n".join(SCOPES)))
        script_btn = QPushButton("Save PowerShell script…")
        script_btn.clicked.connect(self._save_script)
        tools.addWidget(open_btn)
        tools.addWidget(copy_btn)
        tools.addWidget(script_btn)
        tools.addStretch(1)
        lay.addLayout(tools)

        help_box = QTextBrowser()
        help_box.setHtml(HOW_TO)
        help_box.setOpenExternalLinks(True)
        lay.addWidget(help_box, 1)

        buttons = QDialogButtonBox()
        self.save_btn = buttons.addButton("Save", QDialogButtonBox.AcceptRole)
        buttons.addButton("Close", QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self._refresh(select or cx.last_used())

    # ------------------------------------------------------------------ helpers
    def _refresh(self, select: str = ""):
        self.combo.blockSignals(True)
        self.combo.clear()
        items = cx.load_all()
        for c in items:
            self.combo.addItem(c["name"], c)
        self.combo.addItem("➕ New connection…", None)
        idx = next((i for i, c in enumerate(items) if c["name"].lower() == select.lower()), 0 if items else len(items))
        self.combo.setCurrentIndex(idx)
        self.combo.blockSignals(False)
        self._load_selected()

    def _load_selected(self, *_):
        c = self.combo.currentData()
        self._editing = c["name"] if c else None
        self.name.setText(c["name"] if c else "")
        self.tenant.setText(c["tenant"] if c else "")
        self.client.setText(c["client_id"] if c else "")
        self.del_btn.setEnabled(c is not None)
        (self.name if not c else self.tenant).setFocus()

    def _save_script(self):
        src = docs_path("create-app-registration.ps1")
        target, _ = QFileDialog.getSaveFileName(self, "Save PowerShell script",
                                                "create-app-registration.ps1", "PowerShell (*.ps1)")
        if not target:
            return
        try:
            with open(src, "rb") as f_in, open(target, "wb") as f_out:
                f_out.write(f_in.read())
        except OSError as e:
            QMessageBox.critical(self, "Could not save", str(e))
            return
        QMessageBox.information(self, "Saved", f"Saved to:\n{target}")

    def _new(self):
        self.combo.setCurrentIndex(self.combo.count() - 1)

    def _delete(self):
        if not self._editing:
            return
        if QMessageBox.question(self, "Delete connection",
                                f"Delete the saved connection “{self._editing}” from this computer?\n\n"
                                "This does not change anything in Microsoft 365. To remove the app "
                                "registration itself, delete it in the Entra admin center.") \
                != QMessageBox.Yes:
            return
        cx.remove(self._editing)
        self._refresh()

    def _save(self):
        conn = {"name": self.name.text(), "tenant": self.tenant.text(), "client_id": self.client.text()}
        problems = cx.validate(conn)
        if problems:
            QMessageBox.warning(self, "Check the connection", "\n\n".join(problems))
            return
        cx.upsert(conn, old_name=self._editing)
        self.selected_name = cx.normalize(conn)["name"]
        self.accept()
