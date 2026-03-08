import sys
import random
from random import randint
from typing import List, Tuple, Optional

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
)
from PySide6.QtCore import (
    Qt,
    QPropertyAnimation,
    QEasingCurve,
    Signal,
    QPoint,
    QSize,
    QRectF,
    QRect,
    Property,
    QUrl,
    QByteArray,
)
from PySide6.QtGui import (
    QIcon,
    QPixmap,
    QPainter,
    QColor,
    QFont,
    QPen,
    QPainterPath,
    QMouseEvent,
    QBrush,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply


class VerificationImage(QWidget):
    clickSignal = Signal(int, int)
    verificationComplete = Signal(bool, list)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self._width = 300
        self._height = 169
        self.setFixedSize(self._width, self._height)

        self.characters = "一二三四五六七八九十甲乙丙丁戊己庚辛壬癸"
        self.fontSizeRange = (20, 35)
        self.fontColors = [
            QColor(0, 0, 0),
            QColor(255, 0, 0),
            QColor(0, 255, 0),
            QColor(0, 0, 255),
            QColor(255, 255, 0),
            QColor(255, 0, 255),
            QColor(0, 255, 255),
        ]

        self.targetChars = []
        self.targetPositions = []
        self.userClicks = []
        self.verificationText = ""

        self.networkManager = QNetworkAccessManager(self)
        self.networkManager.finished.connect(self.onImageDownloaded)

        self.currentImage = QPixmap(self._width, self._height)
        self.currentImage.fill(QColor(200, 200, 200))

        self.loading = True
        self.loadImageFromUrl("https://api.elaina.cat/random/pc")

    def loadImageFromUrl(self, url: str):
        self.loading = True
        self.update()
        request = QNetworkRequest(QUrl(url))
        self.networkManager.get(request)

    def onImageDownloaded(self, reply: QNetworkReply):
        if reply.error() != QNetworkReply.NetworkError.NoError:
            print(f"网络错误: {reply.errorString()}，使用灰色背景")
            self.fallbackToLocalImage()
        else:
            data = reply.readAll()
            pixmap = QPixmap()
            if not pixmap.loadFromData(data):
                print("图片数据解析失败，使用灰色背景")
                self.fallbackToLocalImage()
            else:
                self.currentImage = pixmap.scaled(
                    self._width,
                    self._height,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.loading = False
                self.generateText()
                self.update()

        reply.deleteLater()

    def fallbackToLocalImage(self):
        self.currentImage.fill(QColor(200, 200, 200))
        self.loading = False
        self.generateText()
        self.update()

    def generateText(self):
        painter = QPainter(self.currentImage)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        charPositions = []
        displayedChars = []
        attempts = 0
        maxAttempts = 100

        while len(charPositions) < 12 and attempts < maxAttempts:
            attempts += 1
            char = random.choice(self.characters)

            if char in displayedChars:
                continue

            fontSize = randint(*self.fontSizeRange)
            font = QFont("微软雅黑", fontSize)
            painter.setFont(font)

            charWidth = painter.boundingRect(
                0, 0, 100, 100, Qt.AlignmentFlag.AlignLeft, char
            ).width()
            charHeight = painter.boundingRect(
                0, 0, 100, 100, Qt.AlignmentFlag.AlignTop, char
            ).height()

            x = randint(10, self._width - charWidth - 10)
            y = randint(10, self._height - charHeight - 10)

            rect = QRect(x, y, charWidth, charHeight)
            overlap = False
            for existingRect in charPositions:
                if rect.intersects(existingRect):
                    overlap = True
                    break

            if not overlap:
                charPositions.append(rect)
                displayedChars.append(char)
                color = random.choice(self.fontColors)
                painter.setPen(QPen(color))

                painter.save()

                rotation = randint(-15, 15)
                painter.translate(x + charWidth / 2, y + charHeight / 2)
                painter.rotate(rotation)
                painter.translate(-(x + charWidth / 2), -(y + charHeight / 2))

                opacity = random.uniform(0.7, 1.0)
                painter.setOpacity(opacity)

                painter.drawText(x, y + charHeight - 5, char)

                painter.restore()

        painter.end()

        if charPositions:

            targetCount = min(3, len(displayedChars))

            self.targetChars = random.sample(displayedChars, targetCount)
            self.targetPositions = []

            for char in self.targetChars:
                if char in displayedChars:
                    charIndex = displayedChars.index(char)
                    if charIndex < len(charPositions):
                        self.targetPositions.append(charPositions[charIndex].center())

            if len(self.targetPositions) != len(self.targetChars):

                self.targetChars = self.targetChars[: len(self.targetPositions)]

            self.verificationText = "点击: " + " ".join(self.targetChars)
        else:
            self.targetChars = []
            self.targetPositions = []
            self.verificationText = "点击: 无"

        self.userClicks = []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        rect = QRectF(0, 0, self._width, self._height)
        path.addRoundedRect(rect, 5, 5)
        painter.setClipPath(path)
        painter.drawPixmap(QPoint(0, 0), self.currentImage)

        for i, pos in enumerate(self.userClicks):
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.setBrush(QBrush(QColor(255, 0, 0, 50)))
            painter.drawEllipse(pos, 10, 10)
            painter.drawText(pos.x() + 15, pos.y() + 5, str(i + 1))

        if self.loading:
            painter.save()
            painter.setBrush(QColor(0, 0, 0, 150))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(0, 0, self._width, self._height, 5, 5)
            painter.setPen(QColor(255, 255, 255))
            font = QFont("微软雅黑", 16)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "加载中...")
            painter.restore()

        super().paintEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self.loading:
            pos = event.pos()
            self.userClicks.append(pos)
            self.update()

            if len(self.userClicks) == len(self.targetChars):
                self.verify()

    def verify(self):
        if len(self.userClicks) != len(self.targetPositions):
            self.verificationComplete.emit(False, [])
            return

        tolerance = 20
        correct = []
        for i, (userPos, targetPos) in enumerate(
            zip(self.userClicks, self.targetPositions)
        ):
            distance = (
                (userPos.x() - targetPos.x()) ** 2
                + (userPos.y() - targetPos.y()) ** 2
            ) ** 0.5
            if distance <= tolerance:
                correct.append(i)

        success = len(correct) == len(self.targetChars)
        self.verificationComplete.emit(success, correct)

    def reset(self):
        self.loadImageFromUrl("https://api.elaina.cat/random/pc")

    def refreshImage(self):
        if (
            hasattr(self, "animation")
            and self.animation.state() == QPropertyAnimation.State.Running
        ):
            self.animation.stop()
            self.animation.deleteLater()
            delattr(self, "animation")
        self.loadImageFromUrl("https://api.elaina.cat/random/pc")
