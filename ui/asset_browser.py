"""Asset browser view for inspecting published film assets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.models import Asset, AssetDependency, PublishRecord
from database.repository import SQLiteRepository
from services.asset_classification import classify_asset_file


@dataclass(frozen=True, slots=True)
class AssetBrowserRow:
    """Flattened asset summary used by the browser table."""

    asset: Asset
    asset_type: str
    status: str
    latest_version: str
    last_publish_date: str


class AssetBrowserWidget(QWidget):
    """Browse assets with searchable summaries and detailed publish metadata."""

    def __init__(self, repository: SQLiteRepository, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repository = repository
        self._rows: list[AssetBrowserRow] = []
        self._thumbnail_path: Path | None = None

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._build_asset_list(splitter))
        splitter.addWidget(self._build_detail_panel(splitter))
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, stretch=1)

    def _build_asset_list(self, parent: QWidget) -> QWidget:
        panel = QWidget(parent)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(10)

        filter_row = QWidget(panel)
        filter_layout = QHBoxLayout(filter_row)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(8)

        self.search_edit = QLineEdit(filter_row)
        self.search_edit.setPlaceholderText("Search assets")
        self.search_edit.textChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.search_edit, stretch=2)

        self.type_filter = QComboBox(filter_row)
        self.type_filter.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.type_filter)

        self.status_filter = QComboBox(filter_row)
        self.status_filter.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.status_filter)

        refresh_button = QPushButton("Refresh", filter_row)
        refresh_button.clicked.connect(self.refresh)
        filter_layout.addWidget(refresh_button)

        layout.addWidget(filter_row)

        self.asset_table = QTableWidget(0, 5, panel)
        self.asset_table.setHorizontalHeaderLabels(
            ["Name", "Asset Type", "Status", "Latest Version", "Last Publish Date"]
        )
        self.asset_table.setAlternatingRowColors(True)
        self.asset_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.asset_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.asset_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.asset_table.setSortingEnabled(True)
        self.asset_table.verticalHeader().setVisible(False)
        self.asset_table.itemSelectionChanged.connect(self._asset_selection_changed)

        header = self.asset_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.asset_table, stretch=1)

        return panel

    def _build_detail_panel(self, parent: QWidget) -> QWidget:
        panel = QWidget(parent)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(12)

        summary_frame = QFrame(panel)
        summary_frame.setFrameShape(QFrame.Shape.StyledPanel)
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setContentsMargins(14, 14, 14, 14)
        summary_layout.setSpacing(16)

        self.thumbnail_label = QLabel(summary_frame)
        self.thumbnail_label.setFixedSize(180, 120)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setFrameShape(QFrame.Shape.StyledPanel)
        self.thumbnail_label.setText("No Thumbnail")
        summary_layout.addWidget(self.thumbnail_label)

        details = QWidget(summary_frame)
        details_layout = QGridLayout(details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setHorizontalSpacing(12)
        details_layout.setVerticalSpacing(6)

        self.detail_name_label = QLabel("-", details)
        self.detail_type_label = QLabel("-", details)
        self.detail_status_label = QLabel("-", details)
        self.detail_version_label = QLabel("-", details)
        self.detail_date_label = QLabel("-", details)

        self._add_detail_row(details_layout, 0, "Name", self.detail_name_label)
        self._add_detail_row(details_layout, 1, "Asset Type", self.detail_type_label)
        self._add_detail_row(details_layout, 2, "Status", self.detail_status_label)
        self._add_detail_row(
            details_layout,
            3,
            "Latest Version",
            self.detail_version_label,
        )
        self._add_detail_row(
            details_layout,
            4,
            "Last Publish Date",
            self.detail_date_label,
        )
        details_layout.setColumnStretch(1, 1)
        summary_layout.addWidget(details, stretch=1)
        layout.addWidget(summary_frame)

        self.detail_tabs = QTabWidget(panel)
        self.publish_history_table = self._create_table(
            ["Version", "Published", "Type", "Path"]
        )
        self.dependencies_table = self._create_table(
            ["Asset", "Dependency Type", "Created", "Metadata"]
        )
        self.dependents_table = self._create_table(
            ["Asset", "Dependency Type", "Created", "Metadata"]
        )
        self.deliverables_table = self._create_table(
            ["Version", "Type", "Published", "Path"]
        )
        self.dcc_table = self._create_table(["Version", "Type", "Published", "Path"])
        self.resources_table = self._create_table(
            ["Version", "Type", "Published", "Path"]
        )

        self.detail_tabs.addTab(self.publish_history_table, "Publish History")
        self.detail_tabs.addTab(self.dependencies_table, "Dependencies")
        self.detail_tabs.addTab(self.dependents_table, "Dependents")
        self.detail_tabs.addTab(self.deliverables_table, "Published Deliverables")
        self.detail_tabs.addTab(self.dcc_table, "Source DCC Files")
        self.detail_tabs.addTab(self.resources_table, "Resources")
        layout.addWidget(self.detail_tabs, stretch=1)

        return panel

    @staticmethod
    def _add_detail_row(
        layout: QGridLayout,
        row: int,
        label_text: str,
        value_label: QLabel,
    ) -> None:
        label = QLabel(label_text, layout.parentWidget())
        label.setStyleSheet("color: palette(mid);")
        value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        value_label.setWordWrap(True)
        layout.addWidget(label, row, 0)
        layout.addWidget(value_label, row, 1)

    @staticmethod
    def _create_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSortingEnabled(True)
        table.verticalHeader().setVisible(False)

        header = table.horizontalHeader()
        for column in range(len(headers) - 1):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(len(headers) - 1, QHeaderView.ResizeMode.Stretch)
        return table

    def refresh(self) -> None:
        """Reload asset summaries from the repository."""

        selected_asset_id = self._current_asset_id()
        assets = self._repository.list_assets()
        publishes = self._repository.list_publishes()
        publishes_by_asset: dict[int, list[PublishRecord]] = {}
        for publish in publishes:
            publishes_by_asset.setdefault(publish.asset_id, []).append(publish)

        self._rows = [
            self._build_asset_row(asset, publishes_by_asset.get(asset.id, []))
            for asset in assets
        ]
        self._populate_filter_options()
        self._populate_asset_table()
        self._apply_filters(select_asset_id=selected_asset_id)

    def _build_asset_row(
        self,
        asset: Asset,
        publishes: list[PublishRecord],
    ) -> AssetBrowserRow:
        publishes = sorted(publishes, key=lambda record: (record.version, record.id), reverse=True)
        latest_publish = publishes[0] if publishes else None
        asset_type = (
            self._publish_type_label(latest_publish)
            if latest_publish is not None
            else "Unclassified"
        )
        status = "Published" if latest_publish is not None else "Unpublished"
        latest_version = f"v{latest_publish.version:03d}" if latest_publish else "-"
        last_publish_date = latest_publish.publish_date if latest_publish else "-"
        return AssetBrowserRow(
            asset=asset,
            asset_type=asset_type,
            status=status,
            latest_version=latest_version,
            last_publish_date=last_publish_date,
        )

    def _populate_filter_options(self) -> None:
        current_type = self.type_filter.currentData()
        current_status = self.status_filter.currentData()

        self.type_filter.blockSignals(True)
        self.status_filter.blockSignals(True)

        self.type_filter.clear()
        self.type_filter.addItem("All Types", None)
        for asset_type in sorted({row.asset_type for row in self._rows}):
            self.type_filter.addItem(asset_type, asset_type)
        self._restore_combo_selection(self.type_filter, current_type)

        self.status_filter.clear()
        self.status_filter.addItem("All Statuses", None)
        for status in ("Published", "Unpublished"):
            self.status_filter.addItem(status, status)
        self._restore_combo_selection(self.status_filter, current_status)

        self.type_filter.blockSignals(False)
        self.status_filter.blockSignals(False)

    @staticmethod
    def _restore_combo_selection(combo: QComboBox, value: object | None) -> None:
        if value is None:
            combo.setCurrentIndex(0)
            return
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(0)

    def _populate_asset_table(self) -> None:
        self.asset_table.setSortingEnabled(False)
        self.asset_table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            values = [
                row.asset.name,
                row.asset_type,
                row.status,
                row.latest_version,
                row.last_publish_date,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, row.asset.id)
                if column in {3, 4}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.asset_table.setItem(row_index, column, item)
        self.asset_table.setSortingEnabled(True)
        self.asset_table.sortItems(0, Qt.SortOrder.AscendingOrder)

    def _apply_filters(self, _value: object | None = None, select_asset_id: int | None = None) -> None:
        query = self.search_edit.text().strip().casefold()
        selected_type = self.type_filter.currentData()
        selected_status = self.status_filter.currentData()

        for row in range(self.asset_table.rowCount()):
            values = [
                self.asset_table.item(row, column).text()
                for column in range(self.asset_table.columnCount())
            ]
            row_text = " ".join(values).casefold()
            matches_query = not query or query in row_text
            matches_type = selected_type is None or values[1] == selected_type
            matches_status = selected_status is None or values[2] == selected_status
            self.asset_table.setRowHidden(
                row,
                not (matches_query and matches_type and matches_status),
            )

        if select_asset_id is not None and self._select_asset(select_asset_id):
            return
        current_row = self.asset_table.currentRow()
        if current_row >= 0 and not self.asset_table.isRowHidden(current_row):
            self._asset_selection_changed()
            return
        self._select_first_visible_asset()

    def _select_asset(self, asset_id: int) -> bool:
        for row in range(self.asset_table.rowCount()):
            if self.asset_table.isRowHidden(row):
                continue
            item = self.asset_table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == asset_id:
                self.asset_table.selectRow(row)
                return True
        return False

    def _select_first_visible_asset(self) -> None:
        for row in range(self.asset_table.rowCount()):
            if not self.asset_table.isRowHidden(row):
                self.asset_table.selectRow(row)
                return
        self.asset_table.clearSelection()
        self._clear_detail_panel()

    def _asset_selection_changed(self) -> None:
        asset_id = self._current_asset_id()
        if asset_id is None:
            self._clear_detail_panel()
            return
        self._populate_detail_panel(asset_id)

    def _current_asset_id(self) -> int | None:
        row = self.asset_table.currentRow() if hasattr(self, "asset_table") else -1
        if row < 0:
            return None
        item = self.asset_table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, int) else None

    def _populate_detail_panel(self, asset_id: int) -> None:
        asset = self._repository.get_asset(asset_id)
        if asset is None:
            self._clear_detail_panel()
            return

        publishes = sorted(
            self._repository.list_publishes(asset.id),
            key=lambda record: (record.version, record.id),
            reverse=True,
        )
        latest_publish = publishes[0] if publishes else None
        asset_type = (
            self._publish_type_label(latest_publish)
            if latest_publish is not None
            else "Unclassified"
        )
        status = "Published" if latest_publish is not None else "Unpublished"

        self.detail_name_label.setText(asset.name)
        self.detail_type_label.setText(asset_type)
        self.detail_status_label.setText(status)
        self.detail_version_label.setText(
            f"v{latest_publish.version:03d}" if latest_publish else "-"
        )
        self.detail_date_label.setText(latest_publish.publish_date if latest_publish else "-")
        self._set_thumbnail(latest_publish.thumbnail_path if latest_publish else None)

        self._populate_publish_table(self.publish_history_table, publishes)
        self._populate_dependency_table(
            self.dependencies_table,
            self._repository.list_dependencies(asset.id),
            target_is_dependency=True,
        )
        self._populate_dependency_table(
            self.dependents_table,
            self._repository.list_dependents(asset.id),
            target_is_dependency=False,
        )
        self._populate_publish_table(
            self.deliverables_table,
            [
                publish
                for publish in publishes
                if self._publish_section(publish) == "Publish"
            ],
        )
        self._populate_publish_table(
            self.dcc_table,
            [publish for publish in publishes if self._publish_section(publish) == "DCC"],
        )
        self._populate_publish_table(
            self.resources_table,
            [
                publish
                for publish in publishes
                if self._publish_section(publish) == "Resources"
            ],
        )

    def _clear_detail_panel(self) -> None:
        self.detail_name_label.setText("-")
        self.detail_type_label.setText("-")
        self.detail_status_label.setText("-")
        self.detail_version_label.setText("-")
        self.detail_date_label.setText("-")
        self._set_thumbnail(None)
        for table in (
            self.publish_history_table,
            self.dependencies_table,
            self.dependents_table,
            self.deliverables_table,
            self.dcc_table,
            self.resources_table,
        ):
            table.setRowCount(0)

    def _populate_publish_table(
        self,
        table: QTableWidget,
        publishes: list[PublishRecord],
    ) -> None:
        table.setSortingEnabled(False)
        table.setRowCount(len(publishes))
        for row, publish in enumerate(publishes):
            values = [
                f"v{publish.version:03d}",
                publish.publish_date,
                self._publish_type_label(publish),
                publish.file_path,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {0, 1}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 3:
                    item.setToolTip(value)
                table.setItem(row, column, item)
        table.setSortingEnabled(True)

    def _populate_dependency_table(
        self,
        table: QTableWidget,
        dependencies: list[AssetDependency],
        *,
        target_is_dependency: bool,
    ) -> None:
        table.setSortingEnabled(False)
        table.setRowCount(len(dependencies))
        for row, dependency in enumerate(dependencies):
            related_asset_id = (
                dependency.depends_on_asset_id
                if target_is_dependency
                else dependency.asset_id
            )
            related_asset = self._repository.get_asset(related_asset_id)
            values = [
                related_asset.name if related_asset is not None else f"Asset {related_asset_id}",
                dependency.dependency_type,
                dependency.created_date,
                dependency.metadata_json or "",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 3:
                    item.setToolTip(value)
                table.setItem(row, column, item)
        table.setSortingEnabled(True)

    def _set_thumbnail(self, thumbnail_path: str | None) -> None:
        self._thumbnail_path = Path(thumbnail_path) if thumbnail_path else None
        self.thumbnail_label.clear()
        if self._thumbnail_path is None or not self._thumbnail_path.is_file():
            self.thumbnail_label.setText("No Thumbnail")
            return

        pixmap = QPixmap(str(self._thumbnail_path))
        if pixmap.isNull():
            self.thumbnail_label.setText("No Thumbnail")
            return
        self.thumbnail_label.setPixmap(
            pixmap.scaled(
                self.thumbnail_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.thumbnail_label.setToolTip(str(self._thumbnail_path))

    @staticmethod
    def _publish_type_label(publish: PublishRecord) -> str:
        try:
            return classify_asset_file(publish.file_path).display_name
        except ValueError:
            suffix = Path(publish.file_path).suffix
            return suffix.casefold() if suffix else "Unknown"

    @staticmethod
    def _publish_section(publish: PublishRecord) -> str:
        try:
            return classify_asset_file(publish.file_path).section
        except ValueError:
            return "Unknown"