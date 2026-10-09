"""Fenêtre principale de l'application UE Logger."""

from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDockWidget, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout,
    QDateTimeEdit, QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QPlainTextEdit, QPushButton, QSplitter, QTableView, QToolBar, QVBoxLayout,
    QWidget,
)

from .models import LogFilterProxy, LogTableModel
from .delegates import CategoryBadgeDelegate, LogBadgeDelegate
from .charts import FrequencyChart
from .socket_server import LogSocketServer
from ue_logger_backend import LogTailer, VERBOSITIES


class MainWindow(QMainWindow):
    """Présente les logs Unreal et leurs outils de recherche en temps réel."""

    def __init__(self, start_path: str | None = None) -> None:
        """Construit l'interface et démarre la lecture périodique."""
        super().__init__()
        self.setWindowTitle("UE Logger")
        self.resize(1300, 750)
        self.tailer = LogTailer()
        self.model = LogTableModel()
        self.proxy = LogFilterProxy()
        self.proxy.setSourceModel(self.model)
        self._network_backlog: list[tuple[str, str, list[str]]] = []
        self.project_items: dict[str, QListWidgetItem] = {}
        self.project_connection_counts: dict[str, int] = {}
        self.project_names: dict[str, str] = {}
        self.socket_server = LogSocketServer()
        self.socket_server.lines_received.connect(self._on_socket_lines)
        self.socket_server.project_connected.connect(self._on_project_connected)
        self.socket_server.project_disconnected.connect(self._on_project_disconnected)
        self.socket_server.server_status.connect(self._on_server_status)
        self._build_table()
        self._build_toolbar()
        self._build_category_dock()
        self.chart_refresh_timer = QTimer(self)
        self.chart_refresh_timer.setSingleShot(True)
        self.chart_refresh_timer.setInterval(1000)
        self.chart_refresh_timer.timeout.connect(self._refresh_chart)
        QShortcut(QKeySequence.StandardKey.Copy, self.view, activated=self._copy_selection)

        self.status = self.statusBar()
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.poll)
        self.timer.start()
        self.socket_server.start()
        if start_path:
            self.open_path(start_path)

    def _build_table(self) -> None:
        """Crée la table des événements et le panneau de message complet."""
        self.view = QTableView()
        self.view.setModel(self.proxy)
        badge_delegate = LogBadgeDelegate(self.view)
        for column in range(3):
            self.view.setItemDelegateForColumn(column, badge_delegate)
        self.view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.view.setAlternatingRowColors(True)
        self.view.setShowGrid(False)
        self.view.setSortingEnabled(True)
        self.view.verticalHeader().setVisible(False)
        self.view.verticalHeader().setDefaultSectionSize(24)
        header = self.view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionsClickable(True)
        header.setStretchLastSection(True)
        for column, width in enumerate((90, 130, 150, 360, 95, 90, 65)):
            self.view.setColumnWidth(column, width)
        self.view.sortByColumn(1, Qt.SortOrder.DescendingOrder)
        self.view.selectionModel().selectionChanged.connect(self._show_detail)

        self.detail = QPlainTextEdit(readOnly=True)
        self.detail.setPlaceholderText("Sélectionnez une ligne pour afficher le message complet.")

        chart_panel = QWidget()
        chart_panel.setObjectName("chartPanel")
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(6, 4, 6, 4)
        chart_header = QHBoxLayout()
        chart_header.addWidget(QLabel("Logs par intervalle"))
        chart_header.addWidget(QLabel("Période :"))
        self.period_combo = QComboBox()
        self.period_combo.addItem("Toute la session", "all")
        self.period_combo.addItem("Dernière minute", 60)
        self.period_combo.addItem("5 dernières minutes", 5 * 60)
        self.period_combo.addItem("15 dernières minutes", 15 * 60)
        self.period_combo.addItem("Dernière heure", 60 * 60)
        self.period_combo.addItem("6 dernières heures", 6 * 60 * 60)
        self.period_combo.addItem("Dernières 24 heures", 24 * 60 * 60)
        self.period_combo.addItem("Personnalisée", "custom")
        self.period_combo.currentIndexChanged.connect(self._on_chart_period_changed)
        chart_header.addWidget(self.period_combo)

        self.custom_period = QWidget()
        custom_period_layout = QHBoxLayout(self.custom_period)
        custom_period_layout.setContentsMargins(0, 0, 0, 0)
        custom_period_layout.addWidget(QLabel("Du"))
        self.period_start = QDateTimeEdit()
        self.period_start.setCalendarPopup(True)
        self.period_start.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        self.period_start.setDateTime(self.period_start.dateTime().addDays(-1))
        self.period_start.dateTimeChanged.connect(self._on_chart_dates_changed)
        custom_period_layout.addWidget(self.period_start)
        custom_period_layout.addWidget(QLabel("au"))
        self.period_end = QDateTimeEdit()
        self.period_end.setCalendarPopup(True)
        self.period_end.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        self.period_end.dateTimeChanged.connect(self._on_chart_dates_changed)
        custom_period_layout.addWidget(self.period_end)
        self.custom_period.setVisible(False)
        chart_header.addWidget(self.custom_period)
        chart_header.addStretch()
        chart_layout.addLayout(chart_header)
        self.chart = FrequencyChart()
        self.chart.setToolTip(
            "Faites glisser pour sélectionner une plage sans modifier la période. "
            "Survolez une barre pour ses détails; double-cliquez pour effacer la sélection."
        )
        self.chart.range_selected.connect(self._on_chart_range_selected)
        self.chart.reset_requested.connect(self._reset_chart_range)
        chart_layout.addWidget(self.chart)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.view)
        splitter.addWidget(chart_panel)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 1)
        self.setCentralWidget(splitter)

    def _build_toolbar(self) -> None:
        """Ajoute les commandes de suivi, de niveau et de recherche."""
        toolbar = QToolBar("Outils")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        toolbar.addAction("Ouvrir un fichier…", self._choose_file)
        toolbar.addAction("Ouvrir un dossier Logs…", self._choose_directory)
        self.socket_status_label = QLabel("Socket Unreal : démarrage…")
        self.socket_status_label.setObjectName("socketStatus")
        self.socket_status_label.setProperty("status", "starting")
        toolbar.addWidget(self.socket_status_label)
        toolbar.addAction("Copier commande UE", self._copy_unreal_command)
        toolbar.addSeparator()
        self.act_pause = QAction("Pause", self, checkable=True)
        self.act_pause.toggled.connect(self._on_pause_toggled)
        toolbar.addAction(self.act_pause)
        toolbar.addAction("Effacer", self._clear_logs)
        self.act_scroll = QAction("Défilement auto", self, checkable=True, checked=True)
        toolbar.addAction(self.act_scroll)
        toolbar.addSeparator()

        toolbar.addWidget(QLabel("  Recherche : "))
        self.search = QLineEdit(placeholderText="Texte ou expression…", clearButtonEnabled=True)
        self.search.setMinimumWidth(240)
        self.search.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search)
        self.regex = QCheckBox("Regex")
        self.regex.toggled.connect(self._on_search)
        toolbar.addWidget(self.regex)

    def _build_category_dock(self) -> None:
        """Ajoute les filtres de projet, niveau et catégorie dans le panneau latéral."""
        self.project_list = QListWidget()
        self.project_list.setMaximumHeight(130)
        self.project_list.itemChanged.connect(self._on_project_changed)

        self.level_checks: dict[str, QCheckBox] = {}
        level_group = QGroupBox("Niveaux affichés")
        level_layout = QGridLayout(level_group)
        level_layout.setContentsMargins(8, 6, 8, 6)
        for index, level in enumerate(VERBOSITIES):
            checkbox = QCheckBox(level)
            checkbox.setChecked(index < 5)
            checkbox.toggled.connect(self._on_level_toggled)
            self.level_checks[level] = checkbox
            level_layout.addWidget(checkbox, index // 2, index % 2)

        self.category_list = QListWidget()
        self.category_list.setItemDelegate(CategoryBadgeDelegate(self.category_list))
        self.category_list.setSpacing(3)
        self.category_list.itemClicked.connect(self._toggle_category_item)
        all_button = QPushButton("Tout")
        none_button = QPushButton("Aucun")
        all_button.clicked.connect(lambda: self._set_all_categories(True))
        none_button.clicked.connect(lambda: self._set_all_categories(False))
        buttons = QHBoxLayout()
        buttons.addWidget(all_button)
        buttons.addWidget(none_button)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(QLabel("Projets Unreal"))
        layout.addWidget(self.project_list)
        layout.addWidget(level_group)
        layout.addWidget(QLabel("Catégories"))
        layout.addLayout(buttons)
        layout.addWidget(self.category_list)
        dock = QDockWidget("Sources et filtres", self)
        dock.setWidget(content)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    def _on_search(self, *_args) -> None:
        """Applique les critères de recherche saisis dans la barre d'outils."""
        self.proxy.set_search(self.search.text(), self.regex.isChecked())
        self._schedule_chart_refresh()

    def _on_level_toggled(self, _checked: bool) -> None:
        """Applique les niveaux cochés et actualise les statistiques visibles."""
        levels = {level for level, checkbox in self.level_checks.items() if checkbox.isChecked()}
        self.proxy.set_levels(levels)
        self._schedule_chart_refresh()

    def _on_category_changed(self, _item: QListWidgetItem) -> None:
        """Actualise les catégories masquées après une modification de case."""
        hidden = {self.category_list.item(i).text()
                  for i in range(self.category_list.count())
                  if not self.category_list.item(i).data(Qt.ItemDataRole.UserRole)}
        self.proxy.set_hidden_categories(hidden)
        self._schedule_chart_refresh()

    def _toggle_category_item(self, item: QListWidgetItem) -> None:
        """Bascule l'état d'un badge après un clic sur sa ligne entière."""
        item.setData(Qt.ItemDataRole.UserRole, not bool(item.data(Qt.ItemDataRole.UserRole)))
        self._on_category_changed(item)

    def _set_all_categories(self, visible: bool) -> None:
        """Coche ou décoche toutes les catégories en une seule mise à jour."""
        self.category_list.blockSignals(True)
        for index in range(self.category_list.count()):
            self.category_list.item(index).setData(Qt.ItemDataRole.UserRole, visible)
        self.category_list.blockSignals(False)
        self._on_category_changed(None)

    def _show_detail(self, *_args) -> None:
        """Affiche le contenu complet de la première ligne sélectionnée."""
        rows = self.view.selectionModel().selectedRows()
        if not rows:
            self.detail.clear()
            return
        source = self.proxy.mapToSource(rows[0])
        entry = self.model.entries[source.row()]
        self.detail.setPlainText(
            f"{entry.project_name}  {entry.date} {entry.time}  "
            f"[{entry.frame}] {entry.category} "
            f"({entry.verbosity})\n\n{entry.message}"
        )

    def _copy_selection(self) -> None:
        """Copie les lignes sélectionnées dans le presse-papiers."""
        rows = sorted(row.row() for row in self.view.selectionModel().selectedRows())
        copied = []
        for row in rows:
            source_row = self.proxy.mapToSource(self.proxy.index(row, 0)).row()
            entry = self.model.entries[source_row]
            copied.append(f"{entry.project_name} [{entry.date} {entry.time}]"
                          f"[{entry.frame}]{entry.category}: "
                          f"{entry.verbosity}: {entry.message}")
        QApplication.clipboard().setText("\n".join(copied))

    def _choose_file(self) -> None:
        """Demande à l'utilisateur un fichier de log à suivre."""
        path, _filter = QFileDialog.getOpenFileName(
            self, "Ouvrir un log", "", "Logs Unreal (*.log *.txt);;Tous les fichiers (*)"
        )
        if path:
            self.open_path(path)

    def _choose_directory(self) -> None:
        """Demande un dossier Saved/Logs à surveiller."""
        directory = QFileDialog.getExistingDirectory(self, "Choisir le dossier Saved/Logs")
        if directory:
            self.open_path(directory)

    def _copy_unreal_command(self) -> None:
        """Copie la commande à coller dans la console Python de l'éditeur Unreal."""
        bridge_script = Path(__file__).resolve().parent.parent / "unreal_bridge" / "ue_logger_bridge.py"
        command = f'py "{bridge_script.as_posix()}"'
        QApplication.clipboard().setText(command)
        self.status.showMessage("Commande Unreal copiée. Collez-la dans la console Python de l'éditeur.", 6000)

    def _on_server_status(self, message: str) -> None:
        """Affiche l'état du serveur socket dans la barre d'état et les outils."""
        self.statusBar().showMessage(message)
        if hasattr(self, "socket_status_label"):
            state = "unavailable" if "Impossible" in message else "connected"
            self.socket_status_label.setProperty("status", state)
            self.socket_status_label.style().unpolish(self.socket_status_label)
            self.socket_status_label.style().polish(self.socket_status_label)
            label = "indisponible" if state == "unavailable" else "actif"
            self.socket_status_label.setText(f"Socket Unreal : {label}")

    def open_path(self, path: str) -> None:
        """Réinitialise l'affichage puis suit le fichier ou dossier choisi."""
        self._clear_logs()
        selected = Path(path)
        if selected.is_dir():
            self.tailer.set_directory(selected)
        else:
            self.tailer.set_file(selected)

    def _clear_logs(self) -> None:
        """Efface les événements visibles et les catégories mémorisées."""
        self.model.clear()
        self.proxy.set_time_range(None)
        if hasattr(self, "chart"):
            self.chart.clear_selection()
        self.category_list.clear()
        self.detail.clear()
        self._network_backlog.clear()
        self._schedule_chart_refresh()

    def _on_pause_toggled(self, paused: bool) -> None:
        """Met en attente les messages réseau pendant la pause puis les rejoue."""
        if not paused and self._network_backlog:
            queued = self._network_backlog
            self._network_backlog = []
            for project_id, project_name, lines in queued:
                self._append_lines(lines, project_id, project_name)

    def _on_socket_lines(self, project_id: str, project_name: str, lines: list[str]) -> None:
        """Reçoit les lignes relayées par le script Python exécuté dans Unreal."""
        if self.act_pause.isChecked():
            self._network_backlog.append((project_id, project_name, lines))
        else:
            self._append_lines(lines, project_id, project_name)

    def _on_project_connected(self, project_id: str, project_name: str) -> None:
        """Ajoute ou actualise une source Unreal connectée dans la liste."""
        self.project_names[project_id] = project_name
        self.project_connection_counts[project_id] = (
            self.project_connection_counts.get(project_id, 0) + 1
        )
        item = self.project_items.get(project_id)
        if item is None:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, project_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.project_items[project_id] = item
            self.project_list.addItem(item)
        item.setText(project_name)
        item.setIcon(self._project_status_icon(True))
        item.setToolTip("Connecté")
        self.status.showMessage(f"{project_name} connecté — réception des logs active.")
        self._on_project_changed(item)

    def _on_project_disconnected(self, project_id: str) -> None:
        """Marque une source comme déconnectée tout en conservant ses logs."""
        remaining = max(0, self.project_connection_counts.get(project_id, 1) - 1)
        self.project_connection_counts[project_id] = remaining
        item = self.project_items.get(project_id)
        if item is not None:
            item.setIcon(self._project_status_icon(remaining > 0))
            item.setToolTip("Connecté" if remaining else "Déconnecté")
        if remaining == 0:
            self.status.showMessage(
                f"{self.project_names.get(project_id, 'Projet Unreal')} déconnecté — "
                "les logs déjà reçus restent disponibles."
            )

    def _on_project_changed(self, _item: QListWidgetItem) -> None:
        """Filtre la table et le graphique selon les projets cochés."""
        hidden = {
            self.project_list.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(self.project_list.count())
            if self.project_list.item(index).checkState() == Qt.CheckState.Unchecked
        }
        self.proxy.set_hidden_projects(hidden)
        self._schedule_chart_refresh()

    def _project_status_icon(self, connected: bool) -> QIcon:
        """Crée une icône circulaire discrète pour l'état d'une source Unreal."""
        color = QColor("#35c98b" if connected else "#788397")
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#10141b"))
        painter.setBrush(color)
        painter.drawEllipse(3, 3, 10, 10)
        painter.end()
        return QIcon(pixmap)

    def _append_lines(
        self,
        lines: list[str],
        project_id: str = "",
        project_name: str = "",
    ) -> None:
        """Ajoute les lignes reçues à la table et actualise les catégories."""
        categories = self.model.add_lines(lines, project_id, project_name)
        if categories:
            self.category_list.blockSignals(True)
            for category in categories:
                item = QListWidgetItem(category)
                item.setData(Qt.ItemDataRole.UserRole, True)
                self.category_list.addItem(item)
            self.category_list.sortItems()
            self.category_list.blockSignals(False)
        if self.act_scroll.isChecked():
            self.view.scrollToBottom()
        self.status.showMessage(
            f"{self._source_label()}  |  {len(self.model.entries)} lignes, "
            f"{self.proxy.rowCount()} affichées"
        )
        self._schedule_chart_refresh()

    def _schedule_chart_refresh(self) -> None:
        """Regroupe les rafraîchissements du graphique pendant les flux rapides."""
        if not self.chart_refresh_timer.isActive():
            self.chart_refresh_timer.start()

    def _refresh_chart(self, *_args) -> None:
        """Calcule les occurrences en respectant les filtres hors plage sélectionnée."""
        if not hasattr(self, "chart"):
            return
        visible_entries = [
            entry for entry in self.model.entries
            if self.proxy.accepts_entry(entry, include_time=False)
        ]
        self.chart.set_entries(visible_entries)
        self.chart.set_period(
            self.period_combo.currentData(),
            datetime.fromtimestamp(self.period_start.dateTime().toSecsSinceEpoch()),
            datetime.fromtimestamp(self.period_end.dateTime().toSecsSinceEpoch()),
        )

    def _on_chart_range_selected(self, start: datetime, end: datetime) -> None:
        """Filtre la table sur la plage choisie sans remplacer la période du graphique."""
        self.proxy.set_time_range((start, end))
        period = self.period_combo.currentText()
        self.status.showMessage(
            f"Logs limités à {start:%H:%M:%S} – {end:%H:%M:%S}  |  "
            f"{self.proxy.rowCount()} ligne(s) affichée(s)  |  Période : {period}"
        )

    def _reset_chart_range(self) -> None:
        """Efface la plage graphique et conserve la période de base sélectionnée."""
        self.proxy.set_time_range(None)
        self._schedule_chart_refresh()
        self.status.showMessage(
            f"Filtre de plage effacé — période : {self.period_combo.currentText()}  |  "
            f"{self.proxy.rowCount()} ligne(s) affichée(s)"
        )

    def _on_chart_period_changed(self, *_args) -> None:
        """Affiche les dates si une période personnalisée a été sélectionnée."""
        if hasattr(self, "chart"):
            self.chart.clear_selection()
            self.proxy.set_time_range(None)
        is_custom = self.period_combo.currentData() == "custom"
        self.custom_period.setVisible(is_custom)
        self._schedule_chart_refresh()

    def _on_chart_dates_changed(self, *_args) -> None:
        """Actualise l'histogramme après un changement de date ou d'heure."""
        if hasattr(self, "chart"):
            self.chart.clear_selection()
            self.proxy.set_time_range(None)
        self._schedule_chart_refresh()

    def poll(self) -> None:
        """Récupère les lignes ajoutées depuis le dernier cycle de lecture."""
        if isinstance(self.period_combo.currentData(), int):
            self._schedule_chart_refresh()
        if self.act_pause.isChecked():
            return
        lines, switched = self.tailer.poll()
        if switched:
            self._clear_logs()
        if not lines:
            if switched and self.tailer.path is not None:
                self.status.showMessage(f"Suivi de {self._source_label()} — en attente de nouvelles lignes…")
            return
        source_path = self.tailer.path or self.tailer.directory
        local_name = source_path.stem if source_path and source_path.is_file() else (
            source_path.name if source_path else "Fichier local"
        )
        local_id = f"local:{source_path}" if source_path else "local"
        self._append_lines(lines, local_id, local_name)

    def _source_label(self) -> str:
        """Retourne le nom du projet connecté ou le chemin du log suivi."""
        project_count = sum(1 for count in self.project_connection_counts.values() if count > 0)
        if project_count:
            plural = "s" if project_count > 1 else ""
            return f"{project_count} projet Unreal{plural} connecté{plural}"
        return str(self.tailer.path or self.tailer.directory or "En attente de connexions Unreal")

    def closeEvent(self, event) -> None:
        """Ferme le socket local avant de détruire la fenêtre."""
        self.socket_server.stop()
        super().closeEvent(event)
