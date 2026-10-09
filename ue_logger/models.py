"""Qt event model and view filtering rules."""

import re
from datetime import datetime

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor

from .delegates import badge_color
from ue_logger_backend.parser import LogEntry, VERBOSITIES, parse_line


# Colors chosen for readability against the application's dark theme.
VERBOSITY_COLORS = {
    "Fatal": "#ff4d4d", "Error": "#ff6b6b", "Warning": "#e5c07b",
    "Display": "#98c379", "Log": "#c8ccd4", "Verbose": "#7f848e",
    "VeryVerbose": "#5c6370",
}
VERBOSITY_ORDER = {level: rank for rank, level in enumerate(VERBOSITIES)}


class LogTableModel(QAbstractTableModel):
    """Expose Unreal events through a Qt table model."""

    HEADERS = ("Level", "Project", "Category", "Message", "Date", "Time", "Frame")

    def __init__(self) -> None:
        """Create an empty model and its index of observed categories."""
        super().__init__()
        self.entries: list[LogEntry] = []
        self.categories: set[str] = set()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of top-level events."""
        return 0 if parent.isValid() else len(self.entries)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of table columns."""
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole):
        """Provide the horizontal column headers."""
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        """Return the value, color, or tooltip data for a table cell."""
        if not index.isValid():
            return None
        entry = self.entries[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 3:
                first, separator, _rest = entry.message.partition("\n")
                return first + (" …" if separator else "")
            return (entry.verbosity, entry.project_name or entry.project_id or "Local",
                    entry.category, entry.message, entry.date, entry.time,
                    entry.frame)[index.column()]
        if role == Qt.ItemDataRole.UserRole + 1:
            if index.column() == 0:
                return QColor(VERBOSITY_COLORS.get(entry.verbosity, "#c8ccd4"))
            if index.column() == 1:
                return badge_color(entry.project_id or entry.project_name or "Local", "project")
            if index.column() == 2:
                return badge_color(entry.category, "category")
        if role == Qt.ItemDataRole.ForegroundRole and index.column() == 0:
            return QColor(VERBOSITY_COLORS.get(entry.verbosity, "#c8ccd4"))
        if role == Qt.ItemDataRole.ToolTipRole and index.column() == 3:
            return entry.message
        return None

    def clear(self) -> None:
        """Remove all events and categories from the model."""
        self.beginResetModel()
        self.entries.clear()
        self.categories.clear()
        self.endResetModel()

    def add_lines(
        self,
        lines: list[str],
        project_id: str = "",
        project_name: str = "",
    ) -> list[str]:
        """Add events and append unrecognized lines to the previous message."""
        additions: list[LogEntry] = []
        for line in lines:
            entry = parse_line(line, project_id, project_name)
            if entry is not None:
                additions.append(entry)
            elif additions:
                additions[-1].message += "\n" + line
            elif self.entries:
                self.entries[-1].message += "\n" + line
                last = len(self.entries) - 1
                self.dataChanged.emit(self.index(last, 3), self.index(last, 3))

        new_categories: list[str] = []
        if additions:
            start = len(self.entries)
            self.beginInsertRows(QModelIndex(), start, start + len(additions) - 1)
            self.entries.extend(additions)
            self.endInsertRows()
            for entry in additions:
                if entry.category not in self.categories:
                    self.categories.add(entry.category)
                    new_categories.append(entry.category)
        return new_categories


class LogFilterProxy(QSortFilterProxyModel):
    """Filter by selected verbosity levels, categories, and text or regex search."""

    def __init__(self) -> None:
        """Configure default filters to display standard log entries."""
        super().__init__()
        self.enabled_levels = {"Fatal", "Error", "Warning", "Display", "Log"}
        self.hidden_categories: set[str] = set()
        self.hidden_projects: set[str] = set()
        self.search_text = ""
        self.use_regex = False
        self._regex: re.Pattern[str] | None = None
        self.time_range: tuple[datetime, datetime] | None = None

    def set_time_range(self, time_range: tuple[datetime, datetime] | None) -> None:
        """Limit displayed entries to a time range, or remove the time filter."""
        self.time_range = time_range
        self.invalidateFilter()

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        """Compare columns using their natural data types for readable sorting."""
        entries = self.sourceModel().entries
        left_entry = entries[left.row()]
        right_entry = entries[right.row()]
        column = left.column()

        if column == 0:
            left_value = VERBOSITY_ORDER.get(left_entry.verbosity, len(VERBOSITY_ORDER))
            right_value = VERBOSITY_ORDER.get(right_entry.verbosity, len(VERBOSITY_ORDER))
        elif column == 1:
            left_value = left_entry.project_name or left_entry.project_id
            right_value = right_entry.project_name or right_entry.project_id
        elif column == 2:
            left_value, right_value = left_entry.category, right_entry.category
        elif column == 3:
            left_value, right_value = left_entry.message, right_entry.message
        elif column == 4:
            left_value = f"{left_entry.date} {left_entry.time}"
            right_value = f"{right_entry.date} {right_entry.time}"
        elif column == 5:
            left_value, right_value = left_entry.time, right_entry.time
        else:
            left_value = int(left_entry.frame) if left_entry.frame.isdigit() else -1
            right_value = int(right_entry.frame) if right_entry.frame.isdigit() else -1

        if isinstance(left_value, str) and isinstance(right_value, str):
            return left_value.casefold() < right_value.casefold()
        return left_value < right_value

    def accepts_entry(self, entry: LogEntry, include_time: bool = True) -> bool:
        """Check active filters, optionally ignoring the selected time range."""
        if entry.verbosity not in self.enabled_levels:
            return False
        if entry.category in self.hidden_categories:
            return False
        if entry.project_id in self.hidden_projects:
            return False
        if self.search_text:
            if self.use_regex:
                if self._regex is not None and not self._regex.search(entry.message):
                    return False
            else:
                needle = self.search_text.casefold()
                if needle not in entry.message.casefold() and needle not in entry.category.casefold():
                    return False
        if include_time and self.time_range is not None:
            if not entry.date or not entry.time:
                return False
            try:
                timestamp = datetime.strptime(
                    f"{entry.date} {entry.time}", "%Y-%m-%d %H:%M:%S"
                )
            except ValueError:
                return False
            start, end = self.time_range
            if not start <= timestamp <= end:
                return False
        return True

    def set_levels(self, levels: set[str]) -> None:
        """Set the exact verbosity levels allowed in the table."""
        self.enabled_levels = set(levels)
        self.invalidateFilter()

    def set_hidden_categories(self, categories: set[str]) -> None:
        """Set the categories hidden from the table."""
        self.hidden_categories = set(categories)
        self.invalidateFilter()

    def set_hidden_projects(self, projects: set[str]) -> None:
        """Hide events from projects that are not selected."""
        self.hidden_projects = set(projects)
        self.invalidateFilter()

    def set_search(self, text: str, use_regex: bool) -> None:
        """Update the search; an invalid expression does not hide results."""
        self.search_text = text
        self.use_regex = use_regex
        self._regex = None
        if use_regex and text:
            try:
                self._regex = re.compile(text, re.IGNORECASE)
            except re.error:
                pass
        self.invalidateFilter()

    def filterAcceptsRow(self, row: int, parent: QModelIndex) -> bool:
        """Return whether the source event passes all active filters."""
        entry: LogEntry = self.sourceModel().entries[row]
        return self.accepts_entry(entry)
