"""ECIT Admin Console — entry point."""
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog

from app import settings
from app.config import APP_NAME, resource_path
from app.ui.common import EulaDialog
from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(QIcon(str(resource_path("ecit_icon.png"))))

    if not settings.eula_accepted():
        if EulaDialog(require_accept=True).exec() != QDialog.Accepted:
            return 0
        settings.accept_eula()

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
