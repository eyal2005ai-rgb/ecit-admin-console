"""Shared UI helpers: background workers, branding widgets, dialogs."""
from __future__ import annotations

import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QLabel, QPlainTextEdit,
                               QVBoxLayout)

from ..config import (APP_NAME, APP_VERSION, BRAND_LINE, CONTACT_EMAIL, PUBLISHER, WEBSITE,
                      resource_path)


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(str)


class Worker(QRunnable):
    """Runs fn(progress_callback) on a background thread; results come back as Qt signals."""

    def __init__(self, fn: Callable[[Callable[[str], None]], Any]):
        super().__init__()
        self.fn = fn
        self.signals = _Signals()

    def run(self) -> None:
        try:
            result = self.fn(self.signals.progress.emit)
        except Exception as e:  # surfaced to the UI
            traceback.print_exc()
            self.signals.failed.emit(getattr(e, "friendly", None) or str(e))
        else:
            self.signals.done.emit(result)


def run_in_background(fn, on_done=None, on_failed=None, on_progress=None) -> Worker:
    w = Worker(fn)
    if on_done:
        w.signals.done.connect(on_done)
    if on_failed:
        w.signals.failed.connect(on_failed)
    if on_progress:
        w.signals.progress.connect(on_progress)
    QThreadPool.globalInstance().start(w)
    return w


def logo_label(height: int = 48) -> QLabel:
    lbl = QLabel()
    pix = QPixmap(str(resource_path("ecit_logo.png")))
    if not pix.isNull():
        lbl.setPixmap(pix.scaledToHeight(height, Qt.SmoothTransformation))
    else:
        lbl.setText("<b>ECIT</b>")
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


def eula_text() -> str:
    try:
        return resource_path("EULA.txt").read_text(encoding="utf-8")
    except OSError:
        return f"License text missing. Contact {CONTACT_EMAIL}."


class EulaDialog(QDialog):
    """First-launch acceptance. `require_accept=False` shows it read-only (About → License)."""

    def __init__(self, parent=None, require_accept: bool = True):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} — License Agreement")
        self.resize(640, 560)
        lay = QVBoxLayout(self)
        lay.addWidget(logo_label(40))
        text = QPlainTextEdit(eula_text())
        text.setReadOnly(True)
        lay.addWidget(text)
        if require_accept:
            self.check = QCheckBox("I have read and accept the license agreement, and I understand "
                                   "this tool makes real changes to Microsoft 365.")
            lay.addWidget(self.check)
            buttons = QDialogButtonBox()
            self.accept_btn = buttons.addButton("Accept", QDialogButtonBox.AcceptRole)
            buttons.addButton("Decline", QDialogButtonBox.RejectRole)
            self.accept_btn.setEnabled(False)
            self.check.toggled.connect(self.accept_btn.setEnabled)
        else:
            buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        lay = QVBoxLayout(self)
        lay.addWidget(logo_label(64))
        info = QLabel(
            f"<h3>{APP_NAME}</h3><p>Version {APP_VERSION}</p>"
            f"<p>By {PUBLISHER}<br/><a href='mailto:{CONTACT_EMAIL}'>{CONTACT_EMAIL}</a> · "
            f"<a href='{WEBSITE}'>ecit.co.il</a></p>"
            "<p>Need help managing Microsoft 365? ECIT offers professional managed services.</p>")
        info.setOpenExternalLinks(True)
        info.setAlignment(Qt.AlignCenter)
        info.setWordWrap(True)
        lay.addWidget(info)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        lic = buttons.addButton("View license", QDialogButtonBox.ActionRole)
        lic.clicked.connect(lambda: EulaDialog(self, require_accept=False).exec())
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)


def brand_footer() -> QLabel:
    lbl = QLabel(f"<a href='{WEBSITE}' style='color:#9fb3d1'>{BRAND_LINE}</a>")
    lbl.setOpenExternalLinks(True)
    lbl.setWordWrap(True)
    lbl.setObjectName("brandFooter")
    lbl.setAlignment(Qt.AlignCenter)
    return lbl
