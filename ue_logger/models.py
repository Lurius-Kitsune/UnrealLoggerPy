"""Modèle Qt des événements et règles de filtrage de la vue."""

import re
from datetime import datetime

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor

from .delegates import badge_color
from ue_logger_backend.parser import LogEntry, VERBOSITIES, parse_line


# Couleurs lisibles sur le thème sombre de l'application.
VERBOSITY_COLORS = {
    "Fatal": "#ff4d4d", "Error": "#ff6b6b", "Warning": "#e5c07b",
    "Display": "#98c379", "Log": "#c8ccd4", "Verbose": "#7f848e",
    "VeryVerbose": "#5c6370",
}
VERBOSITY_ORDER = {level: rank for rank, level in enumerate(VERBOSITIES)}


class LogTableModel(QAbstractTableModel):
    """Expose les événements Unreal sous forme de tableau Qt."""

    HEADERS = ("Niveau", "Projet", "Catégorie", "Message", "Date", "Heure", "Frame")

    def __init__(self) -> None:
        """Crée un modèle vide et son index de catégories observées."""
        super().__init__()
        self.entries: list[LogEntry] = []
        self.categories: set[str] = set()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Retourne le nombre d'événements de premier niveau."""
        return 0 if parent.isValid() else len(self.entries)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Retourne le nombre de colonnes du tableau."""
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole):
        """Fournit les titres des colonnes horizontales."""
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        """Retourne la valeur, la couleur ou l'aide contextuelle d'une cellule."""
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
        """Supprime tous les événements et catégories du modèle."""
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
        """Ajoute des événements et rattache les lignes non reconnues au message précédent."""
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
    """Filtre par niveaux cochés, catégories et recherche textuelle/regex."""

    def __init__(self) -> None:
        """Configure les filtres par défaut pour afficher les logs standards."""
        super().__init__()
        self.enabled_levels = {"Fatal", "Error", "Warning", "Display", "Log"}
        self.hidden_categories: set[str] = set()
        self.hidden_projects: set[str] = set()
        self.search_text = ""
        self.use_regex = False
        self._regex: re.Pattern[str] | None = None
        self.time_range: tuple[datetime, datetime] | None = None

    def set_time_range(self, time_range: tuple[datetime, datetime] | None) -> None:
        """Limite les lignes affichées à une plage temporelle, ou retire ce filtre."""
        self.time_range = time_range
        self.invalidateFilter()

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        """Compare les colonnes avec leur type naturel pour un tri lisible."""
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
        """Vérifie les filtres actifs, avec option pour ignorer la plage temporelle."""
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
        """Définit précisément les niveaux de log autorisés dans la table."""
        self.enabled_levels = set(levels)
        self.invalidateFilter()

    def set_hidden_categories(self, categories: set[str]) -> None:
        """Définit les catégories masquées dans la table."""
        self.hidden_categories = set(categories)
        self.invalidateFilter()

    def set_hidden_projects(self, projects: set[str]) -> None:
        """Masque les événements provenant des projets décochés."""
        self.hidden_projects = set(projects)
        self.invalidateFilter()

    def set_search(self, text: str, use_regex: bool) -> None:
        """Met à jour la recherche; une expression invalide ne masque pas les résultats."""
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
        """Indique si l'événement source passe tous les filtres actifs."""
        entry: LogEntry = self.sourceModel().entries[row]
        return self.accepts_entry(entry)
