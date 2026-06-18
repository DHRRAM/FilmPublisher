"""Main application window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QLabel,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from film_publisher.config.manager import AppConfig


class MainWindow(QMainWindow):
    """Primary desktop window for Film Publisher."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config

        self.setWindowTitle(config.app_name)
        self.resize(920, 560)

        self.setCentralWidget(self._build_central_widget())
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Ready")

    def _build_central_widget(self) -> QWidget:
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(18)

        title = QLabel(self._config.app_name, root)
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        root_layout.addWidget(title)

        details_frame = QFrame(root)
        details_frame.setFrameShape(QFrame.Shape.StyledPanel)
        details_layout = QFormLayout(details_frame)
        details_layout.setContentsMargins(16, 16, 16, 16)
        details_layout.setSpacing(10)

        details_layout.addRow("Database", QLabel(str(self._config.database_path), details_frame))
        details_layout.addRow(
            "Box Drive",
            QLabel(str(self._config.box_drive_root) if self._config.box_drive_root else "Not configured", details_frame),
        )

        root_layout.addWidget(details_frame)

        select_button = QPushButton("Select File", root)
        select_button.setEnabled(False)
        root_layout.addWidget(select_button, alignment=Qt.AlignmentFlag.AlignLeft)
        root_layout.addStretch(1)

        return root
