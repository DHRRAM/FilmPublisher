"""Main application window for publishing local film assets."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config.manager import AppConfig
from core.models import Asset, PublishRecord
from database.repository import SQLiteRepository
from services.asset_classification import AssetFileType, classify_asset_file
from services.publisher import PublisherService
from ui.asset_browser import AssetBrowserWidget


class MainWindow(QMainWindow):
    """Primary desktop window for selecting and publishing an asset file."""

    def __init__(
        self,
        config: AppConfig,
        repository: SQLiteRepository,
        publisher: PublisherService,
    ) -> None:
        super().__init__()
        self._config = config
        self._repository = repository
        self._publisher = publisher
        self._selected_file: Path | None = None
        self.asset_browser_widget: AssetBrowserWidget | None = None

        self.setWindowTitle(config.project_name)
        self.setMinimumSize(840, 620)
        self.resize(980, 680)

        self.setCentralWidget(self._build_central_widget())
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Select a file to publish")
        self._update_publish_state()

    def _build_central_widget(self) -> QWidget:
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(24, 22, 24, 22)
        root_layout.setSpacing(18)

        title = QLabel(self._config.project_name, root)
        title_font = QFont(title.font())
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)
        root_layout.addWidget(title)

        tabs = QTabWidget(root)
        tabs.addTab(self._build_publish_tab(tabs), "Publish")
        self.asset_browser_widget = AssetBrowserWidget(self._repository, tabs)
        tabs.addTab(self.asset_browser_widget, "Asset Browser")
        root_layout.addWidget(tabs, stretch=1)

        return root

    def _build_publish_tab(self, parent: QWidget) -> QWidget:
        tab = QWidget(parent)
        root_layout = QVBoxLayout(tab)
        root_layout.setContentsMargins(0, 10, 0, 0)
        root_layout.setSpacing(18)

        root_layout.addWidget(self._build_publish_form(tab))
        root_layout.addWidget(self._build_publish_details(tab))

        history_label = QLabel("Publish History", tab)
        history_font = QFont(history_label.font())
        history_font.setPointSize(12)
        history_font.setBold(True)
        history_label.setFont(history_font)
        root_layout.addWidget(history_label)

        self.history_table = QTableWidget(0, 3, tab)
        self.history_table.setHorizontalHeaderLabels(
            ["Version", "Published", "Location"]
        )
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.history_table.setSortingEnabled(False)
        self.history_table.verticalHeader().setVisible(False)
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        root_layout.addWidget(self.history_table, stretch=1)

        self.empty_history_label = QLabel(
            "No publishes for the selected asset.", self.history_table
        )
        self.empty_history_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_history_label.setStyleSheet("color: palette(mid);")
        self.empty_history_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )

        return tab

    def _build_publish_form(self, parent: QWidget) -> QFrame:
        frame = QFrame(parent)
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QFormLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(12)

        file_row = QWidget(frame)
        file_layout = QHBoxLayout(file_row)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(8)

        self.file_path_edit = QLineEdit(file_row)
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText("Choose a source file")
        file_layout.addWidget(self.file_path_edit, stretch=1)

        self.browse_button = QPushButton("Browse...", file_row)
        self.browse_button.clicked.connect(self._browse_for_file)
        file_layout.addWidget(self.browse_button)
        layout.addRow("Source File", file_row)

        self.classification_label = QLabel("Select a supported file", frame)
        layout.addRow("Destination", self.classification_label)

        action_row = QWidget(frame)
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.addStretch(1)
        self.publish_button = QPushButton("Publish", action_row)
        self.publish_button.setDefault(True)
        self.publish_button.clicked.connect(self._publish)
        action_layout.addWidget(self.publish_button)
        layout.addRow("", action_row)

        return frame

    def _build_publish_details(self, parent: QWidget) -> QFrame:
        frame = QFrame(parent)
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QFormLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(8)

        self.current_version_label = QLabel("-", frame)
        self.last_publish_label = QLabel("-", frame)
        self.publish_location_label = QLabel(str(self._config.asset_root), frame)
        self.publish_location_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.publish_location_label.setWordWrap(True)

        layout.addRow("Current Version", self.current_version_label)
        layout.addRow("Last Publish Date", self.last_publish_label)
        layout.addRow("Publish Location", self.publish_location_label)
        return frame

    def resizeEvent(self, event) -> None:
        """Keep the empty-history message centered over the table body."""

        super().resizeEvent(event)
        self._position_empty_history_label()

    def _browse_for_file(self) -> None:
        start_directory = (
            str(self._selected_file.parent)
            if self._selected_file is not None
            else str(self._config.project_root)
        )
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Asset File",
            start_directory,
            "All Files (*.*)",
        )
        if not file_path:
            return

        self._selected_file = Path(file_path)
        self.file_path_edit.setText(str(self._selected_file))
        self.file_path_edit.setToolTip(str(self._selected_file))
        self._selection_changed()

    def _selection_changed(self, _value: str = "") -> None:
        file_type = self._selected_file_type()
        self.classification_label.setText(
            file_type.display_name if file_type is not None else "Unsupported file type"
        )
        self._refresh_asset_information()
        self._update_publish_state()

    def _publish(self) -> None:
        if self._selected_file is None:
            return

        self._set_busy(True)
        try:
            asset = self._selected_asset()
            if asset is None:
                asset = self._repository.create_asset(
                    name=self._selected_file.stem,
                )

            publish = self._publisher.publish(self._selected_file, asset.id)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Publish Failed", str(exc))
            self.statusBar().showMessage("Publish failed")
        else:
            self._refresh_asset_information(asset)
            if self.asset_browser_widget is not None:
                self.asset_browser_widget.refresh()
            self.statusBar().showMessage(
                f"Published {asset.name} v{publish.version:03d}", 5000
            )
            QMessageBox.information(
                self,
                "Publish Complete",
                f"Published version v{publish.version:03d}\n\n{publish.file_path}",
            )
        finally:
            self._set_busy(False)

    def _selected_asset(self) -> Asset | None:
        if self._selected_file is None:
            return None

        asset_name = self._selected_file.stem.casefold()
        return next(
            (
                asset
                for asset in self._repository.list_assets()
                if asset.name.casefold() == asset_name
            ),
            None,
        )

    def _refresh_asset_information(self, asset: Asset | None = None) -> None:
        asset = asset or self._selected_asset()
        records = self._repository.list_publishes(asset.id) if asset else []
        records.sort(key = lambda record: (record.version, record.id), reverse=True)

        if records:
            latest = records[0]
            self.current_version_label.setText(f"v{latest.version:03d}")
            self.last_publish_label.setText(latest.publish_date)
            self.publish_location_label.setText(latest.file_path)
        else:
            self.current_version_label.setText("Not published")
            self.last_publish_label.setText("-")
            self.publish_location_label.setText(self._expected_publish_location())

        self._populate_history(records)

    def _populate_history(self, records: list[PublishRecord]) -> None:
        self.history_table.setRowCount(len(records))
        for row, record in enumerate(records):
            version_item = QTableWidgetItem(f"v{record.version:03d}")
            version_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            date_item = QTableWidgetItem(record.publish_date)
            path_item = QTableWidgetItem(record.file_path)
            path_item.setToolTip(record.file_path)

            self.history_table.setItem(row, 0, version_item)
            self.history_table.setItem(row, 1, date_item)
            self.history_table.setItem(row, 2, path_item)

        self.empty_history_label.setVisible(not records)
        self._position_empty_history_label()

    def _position_empty_history_label(self) -> None:
        if not hasattr(self, "empty_history_label"):
            return
        viewport = self.history_table.viewport()
        self.empty_history_label.setGeometry(viewport.rect())
        self.empty_history_label.raise_()

    def _expected_publish_location(self) -> str:
        file_type = self._selected_file_type()
        if self._selected_file is None or file_type is None:
            return str(self._config.asset_root)
        return str(
            self._config.asset_root
            / self._selected_file.stem
            / file_type.relative_directory
        )

    def _selected_file_type(self) -> AssetFileType | None:
        if self._selected_file is None:
            return None
        try:
            return classify_asset_file(self._selected_file)
        except ValueError:
            return None

    def _update_publish_state(self) -> None:
        can_publish = (
            self._selected_file is not None
            and self._selected_file_type() is not None
        )
        self.publish_button.setEnabled(can_publish)

    def _set_busy(self, busy: bool) -> None:
        self.browse_button.setEnabled(not busy)
        if busy:
            self.publish_button.setEnabled(False)
            self.statusBar().showMessage("Publishing...")
        else:
            self._update_publish_state()
