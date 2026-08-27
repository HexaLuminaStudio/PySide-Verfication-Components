"""Offline-safe background generation used when no image provider is configured."""

from __future__ import annotations

import secrets

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPixmap

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


def orientation_background(width: int, height: int, *, dpr: float = 1.0) -> QPixmap:
    """Create an upright landscape with strong orientation cues."""

    pixmap = new_canvas(width, height, dpr=dpr)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    sky = QLinearGradient(QPointF(0, 0), QPointF(0, height))
    sky.setColorAt(0, QColor("#78b9e8"))
    sky.setColorAt(0.64, QColor("#d9edf4"))
    sky.setColorAt(1, QColor("#f5d9a7"))
    painter.fillRect(pixmap.rect(), sky)

    sun_size = width * 0.12
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 227, 150, 235))
    painter.drawEllipse(QRectF(width * 0.72, height * 0.16, sun_size, sun_size))

    far_mountain = QPainterPath(QPointF(-width * 0.08, height * 0.69))
    far_mountain.lineTo(width * 0.22, height * 0.35)
    far_mountain.lineTo(width * 0.42, height * 0.64)
    far_mountain.lineTo(width * 0.62, height * 0.42)
    far_mountain.lineTo(width * 1.08, height * 0.72)
    far_mountain.lineTo(width * 1.08, height * 1.05)
    far_mountain.lineTo(-width * 0.08, height * 1.05)
    far_mountain.closeSubpath()
    painter.setBrush(QColor("#567d86"))
    painter.drawPath(far_mountain)

    near_mountain = QPainterPath(QPointF(-width * 0.08, height * 0.78))
    near_mountain.lineTo(width * 0.18, height * 0.52)
    near_mountain.lineTo(width * 0.39, height * 0.75)
    near_mountain.lineTo(width * 0.70, height * 0.55)
    near_mountain.lineTo(width * 1.08, height * 0.79)
    near_mountain.lineTo(width * 1.08, height * 1.05)
    near_mountain.lineTo(-width * 0.08, height * 1.05)
    near_mountain.closeSubpath()
    painter.setBrush(QColor("#315a56"))
    painter.drawPath(near_mountain)

    ground = QLinearGradient(QPointF(0, height * 0.74), QPointF(0, height))
    ground.setColorAt(0, QColor("#46715a"))
    ground.setColorAt(1, QColor("#1f4039"))
    painter.fillRect(QRectF(0, height * 0.74, width, height * 0.26), ground)

    painter.setPen(QColor(255, 255, 255, 48))
    painter.drawLine(QPointF(0, height * 0.74), QPointF(width, height * 0.74))
    painter.end()
    return pixmap
