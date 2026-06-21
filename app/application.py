"""Application bootstrap for the Film Publisher desktop client."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from config.manager import ConfigManager
from database.repository import SQLiteRepository
from services.publisher import PublisherService
from ui.main_window import MainWindow


def run(argv: Sequence[str] | None = None) -> int:
    """Initialize application services and start the Qt event loop."""

    config_manager = ConfigManager()
    config = config_manager.load()
    repository = SQLiteRepository(config.database_path)
    publisher = PublisherService(repository, config.asset_root)

    app = QApplication(list(argv) if argv is not None else sys.argv)
    app.setApplicationName(config.project_name)
    app.setOrganizationName("Film Publisher")

    window = MainWindow(
        config=config,
        repository=repository,
        publisher=publisher,
    )
    window.show()

    return app.exec()
