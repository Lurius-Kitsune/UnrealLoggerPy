"""Interactive time histogram for Unreal Engine logs."""

from collections import Counter
from datetime import datetime, timedelta

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QToolTip, QWidget


# Stable Unreal verbosity colors shared across all categories.
LEVEL_COLORS = {
    "Fatal": "#ff4d4d",
    "Error": "#ff6b6b",
    "Warning": "#e5c07b",
    "Display": "#98c379",
    "Log": "#c8ccd4",
    "Verbose": "#7f848e",
    "VeryVerbose": "#5c6370",
}


class FrequencyChart(QWidget):
    """Display stacked time bars and allow selecting a time range."""

    range_selected = Signal(object, object)
    reset_requested = Signal()

    def __init__(self, parent=None) -> None:
        """Initialize chart state and mouse interactions."""
        super().__init__(parent)
        self.setMinimumHeight(190)
        self.setMouseTracking(True)
        self.entries = []
        self.period = "all"
        self.custom_start = None
        self.custom_end = None
        self.selected_range = None
        self._plot_rect = QRectF()
        self._display_start = None
        self._display_end = None
        self._drag_start = None
        self._drag_current = None
        self._hits = []

    def set_entries(self, entries) -> None:
        """Replace the displayed events and redraw the chart."""
        self.entries = list(entries)
        self.update()

    def set_period(self, period, start=None, end=None) -> None:
        """Set the base period without changing the drag selection."""
        self.period = period
        self.custom_start = start
        self.custom_end = end
        self.update()

    def clear_selection(self) -> None:
        """Clear only the selected range without changing the period."""
        self.selected_range = None
        self._drag_start = None
        self._drag_current = None
        self.update()

    def _entry_datetime(self, entry):
        """Convert the event date and time, or ignore entries without a timestamp."""
        if not entry.date or not entry.time:
            return None
        try:
            return datetime.strptime(f"{entry.date} {entry.time}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    def _bounds(self, events):
        """Return the requested bounds, adjusted to the available data."""
        now = datetime.now()
        if self.period == "custom" and self.custom_start and self.custom_end:
            start, end = self.custom_start, self.custom_end
        elif isinstance(self.period, int):
            end = now
            start = end - timedelta(seconds=self.period)
        elif events:
            start = min(event[0] for event in events)
            end = max(event[0] for event in events)
        else:
            return None, None
        if end <= start:
            end = start + timedelta(seconds=1)
        return start, end

    def _x_for_time(self, value):
        """Map a timestamp to the chart's horizontal coordinate."""
        span = (self._display_end - self._display_start).total_seconds()
        return self._plot_rect.left() + (value - self._display_start).total_seconds() / span * self._plot_rect.width()

    def _time_for_x(self, x):
        """Convert a horizontal coordinate to a timestamp in the displayed period."""
        ratio = (x - self._plot_rect.left()) / self._plot_rect.width()
        return self._display_start + (self._display_end - self._display_start) * ratio

    def paintEvent(self, _event) -> None:
        """Draw the histogram, verbosity legend, and active selection."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#151b25"))
        events = [(stamp, entry) for entry in self.entries if (stamp := self._entry_datetime(entry))]
        start, end = self._bounds(events)
        self._hits = []
        if start is None:
            painter.setPen(QColor("#aab1bd"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No timestamped logs in this period")
            self._plot_rect = QRectF()
            self._display_start = self._display_end = None
            return
        events = [(stamp, entry) for stamp, entry in events if start <= stamp <= end]
        self._display_start, self._display_end = start, end
        counts = Counter(entry.verbosity for _, entry in events)
        total = sum(counts.values())
        painter.setFont(QFont("Segoe UI", 8))
        legend_x, legend_y = 12, 18
        for level, color in LEVEL_COLORS.items():
            if not counts[level]:
                continue
            percent = counts[level] * 100 / total if total else 0
            painter.fillRect(QRectF(legend_x, legend_y - 9, 9, 9), QColor(color))
            painter.setPen(QColor("#d7dbe2"))
            label = f"{level} {percent:.0f}%"
            painter.drawText(legend_x + 14, legend_y, label)
            legend_x += painter.fontMetrics().horizontalAdvance(label) + 29
            if legend_x > self.width() - 120:
                legend_x = 12
                legend_y += 16
        top = legend_y + 8
        self._plot_rect = QRectF(48, top, max(1, self.width() - 64), max(1, self.height() - top - 28))
        painter.setPen(QPen(QColor("#555d69"), 1))
        painter.drawLine(QPoint(48, int(self._plot_rect.bottom())), QPoint(int(self._plot_rect.right()), int(self._plot_rect.bottom())))
        bins_count = min(24, max(1, int(self._plot_rect.width() / 24)))
        bins = [Counter() for _ in range(bins_count)]
        duration = (end - start).total_seconds()
        for stamp, entry in events:
            ratio = (stamp - start).total_seconds() / duration
            index = min(bins_count - 1, max(0, int(ratio * bins_count)))
            bins[index][entry.verbosity] += 1
        peak = max((sum(bucket.values()) for bucket in bins), default=1)
        plot_bottom = self._plot_rect.bottom()
        bin_width = self._plot_rect.width() / bins_count
        for index, bucket in enumerate(bins):
            x = self._plot_rect.left() + index * bin_width + 2
            bar_width = max(2, bin_width - 4)
            y = plot_bottom
            interval_start = start + (end - start) * (index / bins_count)
            interval_end = start + (end - start) * ((index + 1) / bins_count)
            for level in LEVEL_COLORS:
                value = bucket[level]
                if not value:
                    continue
                height = self._plot_rect.height() * value / peak
                y -= height
                rect = QRectF(x, y, bar_width, height)
                painter.fillRect(rect, QColor(LEVEL_COLORS[level]))
                level_counts = "\n".join(
                    f"{name} : {bucket[name]}" for name in LEVEL_COLORS if bucket[name]
                )
                tooltip = (f"{interval_start:%H:%M:%S} – {interval_end:%H:%M:%S}\n"
                           f"Total : {sum(bucket.values())}\n{level_counts}")
                self._hits.append((rect, tooltip))
        painter.setPen(QColor("#aab1bd"))
        for fraction, align in ((0, Qt.AlignmentFlag.AlignLeft), (0.5, Qt.AlignmentFlag.AlignHCenter), (1, Qt.AlignmentFlag.AlignRight)):
            x = self._plot_rect.left() + fraction * self._plot_rect.width()
            label = (start + (end - start) * fraction).strftime("%H:%M:%S")
            painter.drawText(QRectF(x - 42, plot_bottom + 5, 84, 18), align, label)
        selection = self._drag_range() or self.selected_range
        if selection:
            visible_start, visible_end = max(start, selection[0]), min(end, selection[1])
            if visible_start < visible_end:
                x1, x2 = self._x_for_time(visible_start), self._x_for_time(visible_end)
                painter.fillRect(QRectF(x1, self._plot_rect.top(), x2 - x1, self._plot_rect.height()), QColor(80, 150, 230, 55))
                painter.setPen(QPen(QColor("#61a9f5"), 1))
                painter.drawRect(QRectF(x1, self._plot_rect.top(), x2 - x1, self._plot_rect.height()))

    def _drag_range(self):
        """Return the temporary bounds while the user drags a selection."""
        if self._drag_start is None or self._drag_current is None or self._display_start is None:
            return None
        values = sorted((self._time_for_x(self._drag_start), self._time_for_x(self._drag_current)))
        return values

    def mousePressEvent(self, event) -> None:
        """Start a range selection when the click is inside the plot area."""
        if event.button() == Qt.MouseButton.LeftButton and self._plot_rect.contains(event.position()):
            self._drag_start = event.position().x()
            self._drag_current = self._drag_start
            self.update()

    def mouseMoveEvent(self, event) -> None:
        """Update the selection or display details for the hovered bar."""
        if self._drag_start is not None:
            self._drag_current = max(self._plot_rect.left(), min(self._plot_rect.right(), event.position().x()))
            self.update()
            return
        hit = next((tip for rect, tip in self._hits if rect.contains(event.position())), None)
        if hit:
            QToolTip.showText(event.globalPosition().toPoint(), hit, self)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            QToolTip.hideText()
            self.unsetCursor()

    def mouseReleaseEvent(self, event) -> None:
        """Commit the selected range without changing the base period."""
        if event.button() != Qt.MouseButton.LeftButton or self._drag_start is None:
            return
        self._drag_current = max(self._plot_rect.left(), min(self._plot_rect.right(), event.position().x()))
        if abs(self._drag_current - self._drag_start) >= 8:
            selected = self._drag_range()
            if selected and (selected[1] - selected[0]).total_seconds() >= 1:
                self.selected_range = selected
                self.range_selected.emit(*selected)
        self._drag_start = self._drag_current = None
        self.update()

    def mouseDoubleClickEvent(self, _event) -> None:
        """Clear the active selection while preserving the current period."""
        self.clear_selection()
        self.reset_requested.emit()
