"""Offline-safe background generation used when no image provider is configured."""

from __future__ import annotations

import secrets

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPixmap

from .rendering import new_canvas


def procedural_background(width: int, height: int, *, dpr: float = 1.0) -> QPixmap:
    """Create a lightweight, non-empty background without network access."""

    hue = secrets.randbelow(60) + 195
    start = QColor.fromHsv(hue, 52, 235)
    end = QColor.fromHsv((hue + 24) % 360, 78, 168)
    pixmap = new_canvas(width, height, dpr=dpr)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    gradient = QLinearGradient(QPointF(0, 0), QPointF(width, height))
    gradient.setColorAt(0, start)
    gradient.setColorAt(1, end)
    painter.fillRect(pixmap.rect(), gradient)
    for _ in range(12):
        diameter = secrets.randbelow(80) + 28
        x = secrets.randbelow(width + diameter) - diameter
        y = secrets.randbelow(height + diameter) - diameter
        painter.setPen(QColor(255, 255, 255, 18))
        painter.setBrush(QColor(255, 255, 255, 12))
        painter.drawEllipse(x, y, diameter, diameter)
    painter.end()
    return pixmap
