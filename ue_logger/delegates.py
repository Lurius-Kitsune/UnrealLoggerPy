"""Délégués Qt pour dessiner des badges de log et de catégorie."""

from hashlib import blake2b

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem


def badge_color(value: str, namespace: str = "") -> QColor:
    """Retourne une teinte stable pseudo-aléatoire pour un nom donné."""
    digest = blake2b(f"{namespace}:{value}".encode("utf-8"), digest_size=4).digest()
    color = QColor()
    color.setHsl(int.from_bytes(digest[:2], "big") % 360, 180, 150 + digest[2] % 20)
    return color


class LogBadgeDelegate(QStyledItemDelegate):
    """Dessine le niveau, le projet ou la catégorie comme une pastille compacte."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        """Peint le fond standard de la cellule puis son badge arrondi."""
        cell = QStyleOptionViewItem(option)
        self.initStyleOption(cell, index)
        text = cell.text
        cell.text = ""
        style = cell.widget.style() if cell.widget else None
        if style:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, cell, painter, cell.widget)
        color = index.data(Qt.ItemDataRole.UserRole + 1)
        if not isinstance(color, QColor):
            color = QColor("#64748b")
        metrics = painter.fontMetrics()
        badge_width = min(cell.rect.width() - 12, metrics.horizontalAdvance(text) + 20)
        badge_width = max(24, badge_width)
        badge = cell.rect.adjusted(0, 0, 0, 0)
        badge.setLeft(cell.rect.center().x() - badge_width // 2)
        badge.setRight(cell.rect.center().x() + badge_width // 2)
        badge.setTop(cell.rect.top() + 4)
        badge.setBottom(cell.rect.bottom() - 4)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        background = QColor(color)
        background.setAlpha(48)
        painter.setBrush(background)
        painter.drawRoundedRect(badge, 8, 8)
        painter.setPen(color.lighter(125))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


class CategoryBadgeDelegate(QStyledItemDelegate):
    """Dessine les catégories en badges bleus actifs ou grisées si masquées."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        """Peint une pastille pleine largeur selon l'état de la case à cocher."""
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        checked = bool(index.data(Qt.ItemDataRole.UserRole))
        rect = option.rect.adjusted(3, 3, -3, -3)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#1d4ed8" if checked else "#2a3341"))
        painter.drawRoundedRect(rect, 9, 9)
        painter.setPen(QColor("#ffffff" if checked else "#8995a7"))
        painter.drawText(rect.adjusted(11, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter, text)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        """Réserve une hauteur régulière entre les badges de catégories."""
        hint = super().sizeHint(option, index)
        return QSize(hint.width(), 32)

