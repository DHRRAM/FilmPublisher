"""Application bootstrap for the Film Publisher desktop client."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from config.manager import ConfigManager
from database.bootstrap import bootstrap_database
from ui.main_window import MainWindow


def run(argv: Sequence[str] | None = None) -> int:
    """Initialize application services and start the Qt event loop."""

    config_manager = ConfigManager()
    config = config_manager.load()
    bootstrap_database(config.database_path)

    app = QApplication(list(argv) if argv is not None else sys.argv)
    app.setApplicationName(config.project_name)
    app.setOrganizationName("Film Publisher")

    window = MainWindow(config=config)
    window.show()

    return app.exec()
