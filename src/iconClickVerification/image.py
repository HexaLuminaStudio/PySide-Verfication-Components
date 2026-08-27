from __future__ import annotations

import math
import random
from typing import Optional

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
)
from PySide6.QtWidgets import QWidget

from ..components.rendering import effective_dpr, new_canvas


class Icon:
    COLORS = (
        QColor("#c83349"),
        QColor("#00875a"),
        QColor("#2459c4"),
        QColor("#d36b00"),
        QColor("#8a45b8"),
        QColor("#007f91"),
    )

    def __init__(self, icon_type: str, x: int, y: int, size: int):
        self.iconType = icon_type
        self.x = x
        self.y = y
        self.size = size
        self.color = random.choice(self.COLORS)

    @property
    def bounds(self) -> QRect:
        return QRect(self.x, self.y, self.size, self.size)

    def _regular_polygon(self, sides: int, radius_scale: float = 0.9) -> QPainterPath:
        center = QPointF(self.x + self.size / 2, self.y + self.size / 2)
        radius = self.size / 2 * radius_scale
        path = QPainterPath()
        for index in range(sides):
            angle = 2 * math.pi * index / sides - math.pi / 2
            point = QPointF(
                center.x() + radius * math.cos(angle),
                center.y() + radius * math.sin(angle),
            )
            path.moveTo(point) if index == 0 else path.lineTo(point)
        path.closeSubpath()
        return path

    def path(self) -> QPainterPath:
        inset = 2.0
        x, y, size = float(self.x), float(self.y), float(self.size)
        rect = QRectF(x + inset, y + inset, size - inset * 2, size - inset * 2)
        path = QPainterPath()

        if self.iconType == "circle":
            path.addEllipse(rect)
        elif self.iconType == "square":
            path.addRoundedRect(rect, 2.5, 2.5)
        elif self.iconType == "triangle":
            path.moveTo(x + size / 2, y + inset)
            path.lineTo(x + size - inset, y + size - inset)
            path.lineTo(x + inset, y + size - inset)
            path.closeSubpath()
        elif self.iconType == "star":
            center_x, center_y = x + size / 2, y + size / 2
            outer, inner = size * 0.46, size * 0.2
            for index in range(10):
                radius = outer if index % 2 == 0 else inner
                angle = math.pi * index / 5 - math.pi / 2
                point = QPointF(
                    center_x + radius * math.cos(angle),
                    center_y + radius * math.sin(angle),
                )
                path.moveTo(point) if index == 0 else path.lineTo(point)
            path.closeSubpath()
        elif self.iconType == "cross":
            path.moveTo(x + size * 0.22, y + size * 0.22)
            path.lineTo(x + size * 0.78, y + size * 0.78)
            path.moveTo(x + size * 0.78, y + size * 0.22)
            path.lineTo(x + size * 0.22, y + size * 0.78)
        elif self.iconType == "diamond":
            path.moveTo(x + size / 2, y + inset)
            path.lineTo(x + size - inset, y + size / 2)
            path.lineTo(x + size / 2, y + size - inset)
            path.lineTo(x + inset, y + size / 2)
            path.closeSubpath()
        elif self.iconType == "pentagon":
            return self._regular_polygon(5)
        elif self.iconType == "hexagon":
            return self._regular_polygon(6)
        elif self.iconType == "heart":
            path.moveTo(x + size / 2, y + size * 0.9)
            path.cubicTo(
                x + size * 0.13,
                y + size * 0.66,
                x + size * 0.03,
                y + size * 0.42,
                x + size * 0.08,
                y + size * 0.28,
            )
            path.cubicTo(
                x + size * 0.15,
                y + size * 0.07,
                x + size * 0.39,
                y + size * 0.08,
                x + size / 2,
                y + size * 0.27,
            )
            path.cubicTo(
                x + size * 0.61,
                y + size * 0.08,
                x + size * 0.85,
                y + size * 0.07,
                x + size * 0.92,
                y + size * 0.28,
            )
            path.cubicTo(
                x + size * 0.97,
                y + size * 0.42,
                x + size * 0.87,
                y + size * 0.66,
                x + size / 2,
                y + size * 0.9,
            )
            path.closeSubpath()
        elif self.iconType == "ellipse":
            ellipse_height = size * 0.62
            path.addEllipse(
                QRectF(
                    x + inset,
                    y + (size - ellipse_height) / 2,
                    size - inset * 2,
                    ellipse_height,
                )
            )
        return path

    def draw(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.color, 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        if self.iconType == "cross":
            painter.setBrush(Qt.BrushStyle.NoBrush)
        else:
            fill = QColor(self.color)
            fill.setAlpha(50)
            painter.setBrush(QBrush(fill))
        painter.drawPath(self.path())
        painter.restore()

    def contains(self, point: QPoint) -> bool:
        path = self.path()
        if self.iconType == "cross":
            stroker = QPainterPathStroker()
            stroker.setWidth(12)
            path = stroker.createStroke(path)
        return path.contains(QPointF(point))


class VerificationImage(QWidget):
    verificationComplete = Signal(bool, list)
    challengeChanged = Signal(str)

    TYPE_NAMES = {
        "circle": "圆形",
        "square": "正方形",
        "triangle": "三角形",
        "star": "星形",
        "cross": "叉形",
        "diamond": "菱形",
        "pentagon": "五边形",
        "hexagon": "六边形",
        "heart": "心形",
        "ellipse": "椭圆",
    }
    COLOR_NAMES = {
        "#c83349": "红色",
        "#00875a": "绿色",
        "#2459c4": "蓝色",
        "#d36b00": "橙色",
        "#8a45b8": "紫色",
        "#007f91": "青色",
    }

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._width = 300
        self._height = 169
        self._dpr = effective_dpr(self)
        self.setFixedSize(self._width, self._height)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("图标点选验证码")
        self.keyboardCursor = QPoint(self._width // 2, self._height // 2)

        self.iconTypes = list(self.TYPE_NAMES)
        self.icons: list[Icon] = []
        self.targetIcons: list[Icon] = []
        self.targetPositions: list[QPoint] = []
        self.userClicks: list[QPoint] = []
        self.verificationText = ""
        self.generateImage()

    def generateImage(self) -> None:
        self.currentImage = new_canvas(
            self._width, self._height, dpr=self._dpr, color=QColor("#f3f5f8")
        )
        painter = QPainter(self.currentImage)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.icons.clear()

        types = self.iconTypes.copy()
        random.shuffle(types)
        for icon_type in types:
            if len(self.icons) >= 9:
                break
            for _ in range(80):
                size = random.randint(30, 46)
                x = random.randint(16, self._width - size - 16)
                y = random.randint(16, self._height - size - 16)
                candidate = Icon(icon_type, x, y, size)
                occupied = candidate.bounds.adjusted(-5, -5, 5, 5)
                if any(occupied.intersects(icon.bounds) for icon in self.icons):
                    continue
                self.icons.append(candidate)
                candidate.draw(painter)
                break
        painter.end()

        self.targetIcons = random.sample(self.icons, min(3, len(self.icons)))
        self.targetPositions = [icon.bounds.center() for icon in self.targetIcons]
        descriptions = [
            f"{self.COLOR_NAMES[icon.color.name()]}的{self.TYPE_NAMES[icon.iconType]}"
            for icon in self.targetIcons
        ]
        self.verificationText = "点击: " + " ".join(descriptions) if descriptions else "点击: 无"
        self.userClicks = []
        self.challengeChanged.emit(self.verificationText)
        self.setAccessibleDescription(self.verificationText)
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(QPoint(0, 0), self.currentImage)

        marker_pen = QPen(QColor("#d92d3e"), 2)
        marker_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(marker_pen)
        painter.setBrush(QColor(217, 45, 62, 38))
        for index, position in enumerate(self.userClicks):
            painter.drawEllipse(position, 10, 10)
            painter.drawText(position.x() + 14, position.y() + 5, str(index + 1))

        if self.hasFocus():
            painter.setPen(QPen(QColor("#28344a"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(self.keyboardCursor, 7, 7)
            painter.drawLine(self.keyboardCursor.x() - 10, self.keyboardCursor.y(), self.keyboardCursor.x() + 10, self.keyboardCursor.y())
            painter.drawLine(self.keyboardCursor.x(), self.keyboardCursor.y() - 10, self.keyboardCursor.x(), self.keyboardCursor.y() + 10)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self.userClicks.append(event.position().toPoint())
            self.update()
            if len(self.userClicks) == len(self.targetIcons):
                self.verify()

    def keyPressEvent(self, event) -> None:
        moves = {
            Qt.Key.Key_Left: QPoint(-8, 0),
            Qt.Key.Key_Right: QPoint(8, 0),
            Qt.Key.Key_Up: QPoint(0, -8),
            Qt.Key.Key_Down: QPoint(0, 8),
        }
        if event.key() in moves:
            candidate = self.keyboardCursor + moves[event.key()]
            self.keyboardCursor = QPoint(
                max(0, min(self._width - 1, candidate.x())),
                max(0, min(self._height - 1, candidate.y())),
            )
            self.update()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.userClicks.append(QPoint(self.keyboardCursor))
            self.update()
            if len(self.userClicks) == len(self.targetIcons):
                self.verify()
            event.accept()
            return
        super().keyPressEvent(event)

    def verify(self) -> None:
        if len(self.userClicks) != len(self.targetIcons):
            self.verificationComplete.emit(False, [])
            return
        correct = [
            index
            for index, (position, target) in enumerate(zip(self.userClicks, self.targetIcons))
            if target.contains(position)
        ]
        self.verificationComplete.emit(len(correct) == len(self.targetIcons), correct)

    def reset(self) -> None:
        self.generateImage()

    def refreshImage(self) -> None:
        self.generateImage()
