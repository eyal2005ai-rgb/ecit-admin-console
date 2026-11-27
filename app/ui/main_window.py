"""Main window: ECIT sidebar with tasks, sign-in bar, task pages."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from .. import connections as cx
from ..auth import AuthSession
from ..config import APP_NAME, APP_VERSION
from ..graph import GraphClient
from ..tasks import TASKS
from .common import AboutDialog, brand_footer, logo_label, run_in_background
from .offboarding_view import OffboardingView

STYLE = """
#sidebar { background: #0d2747; }
#sidebar QPushButton { color: #e8eef7; background: transparent; border: none; text-align: left;
                       padding: 9px 14px; font-size: 13px; border-radius: 6px; }
#sidebar QPushButton:hover:enabled { background: #1b3d68; }
#sidebar QPushButton:checked { background: #2a5a96; font-weight: bold; }
#sidebar QPushButton:disabled { color: #6f84a3; }
#sidebarTitle { color: #9fb3d1; font-size: 11px; padding: 10px 14px 2px 14px; }
#brandFooter { font-size: 10px; padding: 8px; }
#topbar { background: #f3f5f8; border-bottom: 1px solid #dde3ea; }
QPushButton#dangerButton:enabled { background: #c62828; color: white; border-radius: 4px; padding: 4px 12px; min-width: 150px; min-height: 22px; }
QGroupBox { font-weight: bold; margin-top: 8px; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION} — by ECIT")
        self.resize(1100, 760)
        self.setStyleSheet(STYLE)

        self.auth: AuthSession | None = None
        self.graph: GraphClient | None = None
        self.admin_upn = ""
        self.tenant: dict = {}

        root = QWidget()
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self._build_sidebar())
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.addWidget(self._build_topbar())
        self.pages = QStackedWidget()
        self.welcome = self._build_welcome()
        self.offboarding = OffboardingView(self)
        self.pages.addWidget(self.welcome)
        self.pages.addWidget(self.offboarding)
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(18, 12, 18, 12)
        wl.addWidget(self.pages)
        right.addWidget(wrap, 1)
        h.addLayout(right, 1)
        self.setCentralWidget(root)
        self._reload_connections(cx.last_used())
        self._update_signin_ui()

    # ------------------------------------------------------------------ layout
    def _build_sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(290)
        v = QVBoxLayout(side)
        v.setContentsMargins(10, 14, 10, 8)
        v.addWidget(logo_label(56))
        t = QLabel("TASKS")
        t.setObjectName("sidebarTitle")
        v.addWidget(t)
        self.task_buttons: dict[str, QPushButton] = {}
        for task in TASKS:
            label = (task.title if task.available else f"{task.title} \u00b7 soon").replace("&", "&&")
            b = QPushButton(label)
            b.setCheckable(task.available)
            b.setEnabled(task.available)
            b.setToolTip(task.description or "Coming in a future version")
            b.clicked.connect(lambda _=False, tid=task.task_id: self.open_task(tid))
            self.task_buttons[task.task_id] = b
            v.addWidget(b)
        v.addStretch(1)
        about = QPushButton("About && license")
        about.clicked.connect(lambda: AboutDialog(self).exec())
        v.addWidget(about)
        v.addWidget(brand_footer())
        return side

    def _build_topbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("topbar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(18, 8, 18, 8)
        h.addWidget(QLabel("Tenant:"))
        self.conn_combo = QComboBox()
        self.conn_combo.setMinimumWidth(200)
        h.addWidget(self.conn_combo)
        self.conn_btn = QPushButton("Connections…")
        self.conn_btn.setToolTip("Add or edit the app registration for each tenant you manage")
        self.conn_btn.clicked.connect(self.manage_connections)
        h.addWidget(self.conn_btn)
        self.signin_label = QLabel()
        h.addWidget(self.signin_label, 1)
        self.signin_btn = QPushButton()
        self.signin_btn.clicked.connect(self.toggle_sign_in)
        h.addWidget(self.signin_btn)
        return bar

    def _build_welcome(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        txt = QLabel(
            "<h2>Welcome</h2>"
            "<p>Everyday Microsoft 365 jobs in one window — no portal hopping.</p>"
            "<ol><li>First time only: click <b>Connections…</b> and follow the steps to register the app "
            "in your own tenant (about 5 minutes). Managing several tenants? Add one connection per tenant.</li>"
            "<li>Choose the tenant at the top, click <b>Sign in</b> and sign in with an admin account of that tenant.</li>"
            "<li>Pick a task on the left.</li>"
            "<li>Every task shows a preview before anything changes, and saves an audit report.</li></ol>"
            "<p style='color:#555'>Your sign-in stays on this computer and in memory only. "
            "ECIT never receives your credentials or tenant data.</p>")
        txt.setWordWrap(True)
        txt.setTextFormat(Qt.RichText)
        v.addWidget(txt)
        v.addStretch(1)
        return w

    # ------------------------------------------------------------------ actions
    def open_task(self, task_id: str):
        for tid, b in self.task_buttons.items():
            b.setChecked(tid == task_id)
        if task_id == "offboarding":
            self.pages.setCurrentWidget(self.offboarding)

    def toggle_sign_in(self):
        if self.auth and self.auth.signed_in:
            self.auth.sign_out()
            self.graph, self.admin_upn, self.tenant = None, "", {}
            self.offboarding.reset()
            self._update_signin_ui()
            return
        conn = self.conn_combo.currentData()
        if not conn:
            if not self.manage_connections():
                return
            conn = self.conn_combo.currentData()
            if not conn:
                return
        problems = cx.validate(conn)
        if problems:
            QMessageBox.warning(self, "Check the connection", "\n\n".join(problems))
            self.manage_connections(conn["name"])
            return
        cx.set_last(conn["name"])
        self.auth = AuthSession(conn["client_id"], cx.authority(conn))
        self.signin_btn.setEnabled(False)
        self.signin_label.setText("Signing in — complete the sign-in in your browser…")

        def work(_p):
            self.auth.sign_in()
            g = GraphClient(self.auth.token)
            return g, g.me(), g.organization()

        run_in_background(work, self._signed_in, self._sign_in_failed)

    def manage_connections(self, select: str = "") -> bool:
        from .connection_dialog import ConnectionDialog
        dlg = ConnectionDialog(self, select or (self.conn_combo.currentText() if self.conn_combo.currentData() else ""))
        ok = dlg.exec() == ConnectionDialog.Accepted
        self._reload_connections(getattr(dlg, "selected_name", "") if ok else "")
        return ok

    def _reload_connections(self, select: str = ""):
        select = select or (self.conn_combo.currentText() if self.conn_combo.count() else cx.last_used())
        self.conn_combo.clear()
        items = cx.load_all()
        for c in items:
            self.conn_combo.addItem(c["name"], c)
        if not items:
            self.conn_combo.addItem("(no tenant yet: click Connections…)", None)
        idx = next((i for i, c in enumerate(items) if c["name"].lower() == (select or "").lower()), 0)
        self.conn_combo.setCurrentIndex(idx)

    def _signed_in(self, result):
        self.graph, me, org = result
        self.admin_upn = me.get("userPrincipalName", "")
        self.tenant = org or {}
        self.signin_btn.setEnabled(True)
        self._update_signin_ui()
        self.offboarding.reset()

    def _sign_in_failed(self, msg: str):
        self.signin_btn.setEnabled(True)
        self._update_signin_ui()
        QMessageBox.critical(self, "Sign-in failed", msg)

    def _update_signin_ui(self):
        if self.graph:
            self.signin_label.setText(f"Signed in as <b>{self.admin_upn}</b> · Tenant: "
                                      f"<b>{self.tenant.get('displayName', '?')}</b>")
            self.signin_btn.setText("Sign out")
            self.conn_combo.setEnabled(False)
            self.conn_btn.setEnabled(False)
        else:
            self.conn_combo.setEnabled(True)
            self.conn_btn.setEnabled(True)
            self.signin_label.setText("Not signed in")
            self.signin_btn.setText("Sign in")
        self.offboarding.refresh_buttons()
