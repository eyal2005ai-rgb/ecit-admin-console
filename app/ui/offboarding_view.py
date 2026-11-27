"""Offboarding page: find user -> choose steps -> preview (dry run) -> confirm -> run -> report."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                               QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from .. import audit
from ..tasks import offboarding as ob
from .common import run_in_background


class OffboardingView(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main              # MainWindow: gives .graph, .admin_upn, .tenant
        self.user: dict | None = None
        self.preview_ok = False
        self.report_path = None
        self._busy = False

        lay = QVBoxLayout(self)
        title = QLabel("<h2>Offboard employee</h2>"
                       "<span style='color:#555'>Lock a leaving employee out of Microsoft 365. "
                       "Nothing changes until you preview and confirm.</span>")
        title.setWordWrap(True)
        lay.addWidget(title)

        # 1. Find the user
        g1 = QGroupBox("1. Find the employee")
        l1 = QVBoxLayout(g1)
        row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Name or email, e.g. dana or dana@contoso.com")
        self.search_edit.returnPressed.connect(self.do_search)
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.do_search)
        row.addWidget(self.search_edit)
        row.addWidget(self.search_btn)
        l1.addLayout(row)
        self.results = QListWidget()
        self.results.setMaximumHeight(120)
        self.results.currentItemChanged.connect(self.on_pick)
        l1.addWidget(self.results)
        self.user_card = QLabel("No employee selected.")
        self.user_card.setWordWrap(True)
        self.user_card.setTextFormat(Qt.RichText)
        l1.addWidget(self.user_card)
        lay.addWidget(g1)

        # 2. Steps
        g2 = QGroupBox("2. Choose what to do")
        l2 = QVBoxLayout(g2)
        self.step_boxes: dict[str, QCheckBox] = {}
        for sid, stitle, desc in ob.STEPS:
            cb = QCheckBox(f"{stitle} — {desc}")
            cb.setChecked(True)
            cb.toggled.connect(self.invalidate_preview)
            self.step_boxes[sid] = cb
            l2.addWidget(cb)
        lay.addWidget(g2)

        # 3. Preview / run
        g3 = QGroupBox("3. Preview, confirm and run")
        l3 = QVBoxLayout(g3)
        btns = QHBoxLayout()
        self.preview_btn = QPushButton("Preview changes (dry run)")
        self.preview_btn.clicked.connect(self.do_preview)
        self.run_btn = QPushButton("Run offboarding…")
        self.run_btn.setObjectName("dangerButton")
        self.run_btn.clicked.connect(self.do_run)
        self.report_btn = QPushButton("Open report")
        self.report_btn.clicked.connect(self.open_report)
        btns.addWidget(self.preview_btn)
        btns.addWidget(self.run_btn)
        btns.addStretch(1)
        btns.addWidget(self.report_btn)
        l3.addLayout(btns)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("The preview and the results appear here.")
        l3.addWidget(self.log)
        lay.addWidget(g3, 1)
        self.refresh_buttons()

    # ------------------------------------------------------------------ state
    def selected_steps(self) -> list[str]:
        return [sid for sid, cb in self.step_boxes.items() if cb.isChecked()]

    def invalidate_preview(self, *_):
        self.preview_ok = False
        self.refresh_buttons()

    def refresh_buttons(self):
        signed = self.main.graph is not None
        self.search_btn.setEnabled(signed and not self._busy)
        self.preview_btn.setEnabled(signed and self.user is not None and bool(self.selected_steps())
                                    and not self._busy)
        self.run_btn.setEnabled(self.preview_ok and not self._busy)
        self.report_btn.setEnabled(self.report_path is not None)

    def set_busy(self, busy: bool):
        self._busy = busy
        self.refresh_buttons()

    def reset(self):
        self.user = None
        self.results.clear()
        self.user_card.setText("No employee selected.")
        self.log.clear()
        self.report_path = None
        self.invalidate_preview()

    # ----------------------------------------------------------------- search
    def do_search(self):
        text = self.search_edit.text().strip()
        if len(text) < 2 or self.main.graph is None:
            return
        self.set_busy(True)
        self.results.clear()
        graph = self.main.graph
        run_in_background(lambda _p: graph.search_users(text), self.on_results, self.on_error)

    def on_results(self, users):
        self.set_busy(False)
        if not users:
            self.results.addItem("No users found.")
            return
        for u in users:
            state = "" if u.get("accountEnabled", True) else "  [blocked]"
            item = QListWidgetItem(f"{u.get('displayName')} — {u.get('userPrincipalName')}{state}")
            item.setData(Qt.UserRole, u)
            self.results.addItem(item)

    def on_pick(self, item, _prev=None):
        u = item.data(Qt.UserRole) if item else None
        self.user = u
        self.report_path = None
        self.invalidate_preview()
        if not u:
            self.user_card.setText("No employee selected.")
            return
        try:
            warnings = ob.validate_target(u, self.main.admin_upn)
        except ob.TargetNotAllowed as e:
            self.user = None
            self.user_card.setText(f"<span style='color:#c62828'><b>{e}</b></span>")
            self.refresh_buttons()
            return
        lic = len(u.get("assignedLicenses") or [])
        role = " · ".join(x for x in (u.get("jobTitle"), u.get("department")) if x)
        card = (f"<b>{u.get('displayName')}</b> &lt;{u.get('userPrincipalName')}&gt;<br/>"
                f"{role}<br/>"
                f"Sign-in: {'enabled' if u.get('accountEnabled', True) else 'BLOCKED'} · "
                f"Licenses: {lic}")
        for w in warnings:
            card += f"<br/><span style='color:#b26a00'>⚠ {w}</span>"
        self.user_card.setText(card)
        self.refresh_buttons()

    # ---------------------------------------------------------------- preview
    def do_preview(self):
        if not self.user:
            return
        self.set_busy(True)
        self.log.clear()
        graph, user, steps = self.main.graph, self.user, self.selected_steps()
        run_in_background(lambda _p: ob.build_plan(graph, user, steps), self.on_plan, self.on_error)

    def on_plan(self, plan):
        self.set_busy(False)
        lines = [f"PREVIEW — nothing has been changed yet.",
                 f"Tenant: {self.main.tenant.get('displayName', '')}",
                 f"Employee: {self.user.get('displayName')} <{self.user.get('userPrincipalName')}>", ""]
        for i, p in enumerate(plan, 1):
            lines.append(f"{i}. {p.title}")
            lines += [f"     • {a}" for a in p.actions]
        lines += ["", "If this is correct, click “Run offboarding…”."]
        self.log.setPlainText("\n".join(lines))
        self.preview_ok = True
        self.refresh_buttons()

    # -------------------------------------------------------------------- run
    def do_run(self):
        upn = self.user.get("userPrincipalName", "")
        text, ok = QInputDialog.getText(
            self, "Confirm offboarding",
            f"This will lock {self.user.get('displayName')} out of Microsoft 365 now.\n"
            f"Some changes cannot be undone automatically.\n\n"
            f"Type the user's email address to confirm:\n{upn}")
        if not ok:
            return
        if text.strip().lower() != upn.lower():
            QMessageBox.warning(self, "Not confirmed", "The address you typed does not match. Nothing was changed.")
            return
        self.set_busy(True)
        self.preview_ok = False
        self.log.appendPlainText("\n— RUNNING —")
        graph, user, steps = self.main.graph, self.user, self.selected_steps()
        run_in_background(lambda progress: ob.execute(graph, user, steps, progress),
                          self.on_done, self.on_error, self.log.appendPlainText)

    def on_done(self, results):
        record = audit.build_record("offboarding", self.main.tenant, self.main.admin_upn, self.user, results)
        try:
            audit.append_jsonl(record)
            self.report_path = audit.write_pdf(record)
            self.log.appendPlainText(f"\nAudit report saved: {self.report_path}")
        except Exception as e:  # never lose the on-screen result because of the report
            self.log.appendPlainText(f"\nCould not save the audit report: {e}")
        failed = [r for r in results if r.status.value in ("Failed", "Partly done")]
        self.log.appendPlainText("\nFinished with problems — see above." if failed
                                 else "\nFinished successfully.")
        bar = self.log.verticalScrollBar()
        bar.setValue(bar.maximum())
        self.set_busy(False)

    def on_error(self, message: str):
        self.set_busy(False)
        self.log.appendPlainText(f"Error: {message}")

    def open_report(self):
        if self.report_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.report_path)))
