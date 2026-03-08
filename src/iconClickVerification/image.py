import random
import math
from typing import List, Optional

from PySide6.QtCore import Qt, QPoint, QRect, QSize, Signal
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPixmap,
    QFont,
    QPen,
    QBrush,
    QPainterPath,
    QMouseEvent,
)


class Icon:
    def __init__(self, icon_type: str, x: int, y: int, size: int):
        self.iconType = icon_type
        self.x = x
        self.y = y
        self.size = size
        self.colors = [
            QColor(255, 0, 0),
            QColor(0, 255, 0),
            QColor(0, 0, 255),
            QColor(255, 255, 0),
            QColor(255, 0, 255),
            QColor(0, 255, 255),
        ]
        self.color = random.choice(self.colors)

    def draw(self, painter: QPainter):
        painter.save()
        painter.setPen(QPen(self.color, 2))
        painter.setBrush(QBrush(self.color, Qt.BrushStyle.Dense1Pattern))

        center_x = self.x + self.size // 2
        center_y = self.y + self.size // 2
        half_size = self.size // 2

        if self.iconType == "circle":
            painter.drawEllipse(self.x, self.y, self.size, self.size)
        elif self.iconType == "square":
            painter.drawRect(self.x, self.y, self.size, self.size)
        elif self.iconType == "triangle":
            path = QPainterPath()
            path.moveTo(center_x, self.y)
            path.lineTo(self.x, self.y + self.size)
            path.lineTo(self.x + self.size, self.y + self.size)
            path.closeSubpath()
            painter.drawPath(path)
        elif self.iconType == "star":
            path = QPainterPath()
            outerRadius = half_size * 0.9
            innerRadius = half_size * 0.4
            for i in range(10):
                angle = 2 * 3.14159 * i / 10 - 3.14159 / 2
                if i % 2 == 0:
                    radius = outerRadius
                else:
                    radius = innerRadius
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            path.closeSubpath()
            painter.drawPath(path)
        elif self.iconType == "cross":
            painter.drawLine(
                self.x + self.size // 4,
                self.y + self.size // 4,
                self.x + self.size * 3 // 4,
                self.y + self.size * 3 // 4,
            )
            painter.drawLine(
                self.x + self.size * 3 // 4,
                self.y + self.size // 4,
                self.x + self.size // 4,
                self.y + self.size * 3 // 4,
            )
        elif self.iconType == "diamond":
            path = QPainterPath()
            path.moveTo(center_x, self.y)
            path.lineTo(self.x + self.size, center_y)
            path.lineTo(center_x, self.y + self.size)
            path.lineTo(self.x, center_y)
            path.closeSubpath()
            painter.drawPath(path)
        elif self.iconType == "pentagon":
            path = QPainterPath()
            for i in range(5):
                angle = 2 * 3.14159 * i / 5 - 3.14159 / 2
                x = center_x + half_size * 0.9 * math.cos(angle)
                y = center_y + half_size * 0.9 * math.sin(angle)
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            path.closeSubpath()
            painter.drawPath(path)
        elif self.iconType == "hexagon":
            path = QPainterPath()
            for i in range(6):
                angle = 2 * 3.14159 * i / 6 - 3.14159 / 2
                x = center_x + half_size * 0.9 * math.cos(angle)
                y = center_y + half_size * 0.9 * math.sin(angle)
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            path.closeSubpath()
            painter.drawPath(path)
        elif self.iconType == "heart":
            path = QPainterPath()
            size = self.size
            x = self.x
            y = self.y
            path.moveTo(x + size // 2, y + size // 4)
            path.cubicTo(x + size // 2, y, x, y, x, y + size // 4)
            path.cubicTo(
                x,
                y + size // 2,
                x + size // 2,
                y + size * 3 // 4,
                x + size // 2,
                y + size,
            )
            path.cubicTo(
                x + size // 2,
                y + size * 3 // 4,
                x + size,
                y + size // 2,
                x + size,
                y + size // 4,
            )
            path.cubicTo(x + size, y, x + size // 2, y, x + size // 2, y + size // 4)
            painter.drawPath(path)
        elif self.iconType == "ellipse":
            painter.drawEllipse(self.x, self.y, self.size, int(self.size * 0.6))

        painter.restore()

    def contains(self, point: QPoint) -> bool:
        return QRect(self.x, self.y, self.size, self.size).contains(point)


class VerificationImage(QWidget):
    verificationComplete = Signal(bool, list)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._width = 300
        self._height = 169
        self.setFixedSize(self._width, self._height)

        self.iconTypes = [
            "circle",
            "square",
            "triangle",
            "star",
            "cross",
            "diamond",
            "pentagon",
            "hexagon",
            "heart",
            "ellipse",
        ]
        self.icons = []
        self.targetIcons = []
        self.targetPositions = []
        self.userClicks = []
        self.verificationText = ""

        self.generateImage()

    def generateImage(self):
        self.currentImage = QPixmap(self._width, self._height)
        self.currentImage.fill(QColor(240, 240, 240))

        painter = QPainter(self.currentImage)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        self.icons.clear()
        minIconSize = 30
        maxIconSize = 50
        padding = 20
        attempts = 0
        maxAttempts = 100

        requiredTypes = self.iconTypes.copy()
        random.shuffle(requiredTypes)

        for iconType in requiredTypes:
            if len(self.icons) >= 9:
                break

            placed = False
            typeAttempts = 0
            maxTypeAttempts = 50

            while not placed and typeAttempts < maxTypeAttempts:
                typeAttempts += 1
                iconSize = random.randint(minIconSize, maxIconSize)
                x = random.randint(padding, self._width - iconSize - padding)
                y = random.randint(padding, self._height - iconSize - padding)

                newIcon = Icon(iconType, x, y, iconSize)
                overlap = False

                for existingIcon in self.icons:
                    if QRect(
                        newIcon.x, newIcon.y, newIcon.size, newIcon.size
                    ).intersects(
                        QRect(
                            existingIcon.x,
                            existingIcon.y,
                            existingIcon.size,
                            existingIcon.size,
                        )
                    ):
                        overlap = True
                        break

                if not overlap:
                    self.icons.append(newIcon)
                    newIcon.draw(painter)
                    placed = True

        while len(self.icons) < 9 and attempts < maxAttempts:
            attempts += 1

            typeCounts = {}
            for icon in self.icons:
                if icon.iconType not in typeCounts:
                    typeCounts[icon.iconType] = 0
                typeCounts[icon.iconType] += 1

            weights = []
            for iconType in self.iconTypes:
                count = typeCounts.get(iconType, 0)
                weight = 1.0 / (count + 1)
                weights.append(weight)

            iconType = random.choices(self.iconTypes, weights=weights, k=1)[0]

            iconSize = random.randint(minIconSize, maxIconSize)
            x = random.randint(padding, self._width - iconSize - padding)
            y = random.randint(padding, self._height - iconSize - padding)

            newIcon = Icon(iconType, x, y, iconSize)
            overlap = False

            for existingIcon in self.icons:
                if QRect(newIcon.x, newIcon.y, newIcon.size, newIcon.size).intersects(
                    QRect(
                        existingIcon.x,
                        existingIcon.y,
                        existingIcon.size,
                        existingIcon.size,
                    )
                ):
                    overlap = True
                    break

            if not overlap:
                self.icons.append(newIcon)
                newIcon.draw(painter)

        painter.end()

        if self.icons:
            targetCount = min(3, len(self.icons))
            self.targetIcons = random.sample(self.icons, targetCount)

            self.targetPositions = [
                QPoint(icon.x + icon.size // 2, icon.y + icon.size // 2)
                for icon in self.targetIcons
            ]

            colorNames = {
                (255, 0, 0): "红色",
                (0, 255, 0): "绿色",
                (0, 0, 255): "蓝色",
                (255, 255, 0): "黄色",
                (255, 0, 255): "紫色",
                (0, 255, 255): "青色",
            }

            typeNames = {
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

            targetDescriptions = []
            for icon in self.targetIcons:
                colorKey = (icon.color.red(), icon.color.green(), icon.color.blue())
                colorName = colorNames.get(colorKey, "未知颜色")
                typeName = typeNames.get(icon.iconType, icon.iconType)
                targetDescriptions.append(f"{colorName}的{typeName}")

            self.verificationText = "点击: " + " ".join(targetDescriptions)
        else:
            self.targetIcons = []
            self.targetPositions = []
            self.verificationText = "点击: 无"

        self.userClicks = []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.drawPixmap(QPoint(0, 0), self.currentImage)

        for i, pos in enumerate(self.userClicks):
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.setBrush(QBrush(QColor(255, 0, 0, 50)))
            painter.drawEllipse(pos, 10, 10)
            painter.drawText(pos.x() + 15, pos.y() + 5, str(i + 1))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            self.userClicks.append(pos)
            self.update()

            if len(self.userClicks) == len(self.targetIcons):
                self.verify()

    def verify(self):
        if len(self.userClicks) != len(self.targetPositions):
            self.verificationComplete.emit(False, [])
            return

        tolerance = 25
        correct = []
        for i, (userPos, targetPos) in enumerate(
            zip(self.userClicks, self.targetPositions)
        ):
            distance = (
                (userPos.x() - targetPos.x()) ** 2 + (userPos.y() - targetPos.y()) ** 2
            ) ** 0.5
            if distance <= tolerance:
                correct.append(i)

        success = len(correct) == len(self.targetIcons)
        self.verificationComplete.emit(success, correct)

    def reset(self):
        self.generateImage()

    def refreshImage(self):
        self.generateImage()
