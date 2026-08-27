import sys
import time
import random
from random import randint
from math import sqrt
from typing import List, Optional

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QSlider,
    QStyle,
    QStyleOptionSlider,
    QMessageBox,
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
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPen, QPainterPath
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from ..components.background import procedural_background


class VerificationImage(QWidget):
    loadingChanged = Signal(bool)
    errorOccurred = Signal(str)

    def __init__(self, parent=None, image_url: str | None = None):
        super().__init__(parent=parent)

        self.image_url = image_url

        self._width = 300
        self._height = 169
        self.setFixedSize(self._width, self._height)

        self.network_manager = QNetworkAccessManager(self)
        self.network_manager.setTransferTimeout(5000)
        self.network_manager.finished.connect(self.on_image_downloaded)

        self.currentImage = QPixmap(self._width, self._height)
        self.currentImage.fill(QColor(200, 200, 200))

        self.pixmapX = randint(50, self._width - 35 - 1)
        self.pixmapY = randint(40, self._height - 35 - 1)
        self._moveX = 1

        self.loading = False
        if self.image_url:
            self.load_image_from_url(self.image_url)
        else:
            self.fallback_to_local_image()

    def load_image_from_url(self, url: str):

        self.loading = True
        self.loadingChanged.emit(True)
        self.update()
        request = QNetworkRequest(QUrl(url))
        self.network_manager.get(request)

    def on_image_downloaded(self, reply: QNetworkReply):

        if reply.error() != QNetworkReply.NetworkError.NoError:
            self.errorOccurred.emit(f"图片加载失败：{reply.errorString()}")
            self.fallback_to_local_image()
        else:

            data = reply.readAll()
            pixmap = QPixmap()
            if not pixmap.loadFromData(data):
                self.errorOccurred.emit("图片数据无法解析，已使用离线背景")
                self.fallback_to_local_image()
            else:

                self.currentImage = pixmap.scaled(
                    self._width,
                    self._height,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

                self.pixmapX = randint(50, self._width - 35 - 1)
                self.pixmapY = randint(40, self._height - 35 - 1)
                self.loading = False
                self.loadingChanged.emit(False)
                self.update()

        reply.deleteLater()

    def fallback_to_local_image(self):

        self.currentImage = procedural_background(self._width, self._height)

        self.pixmapX = randint(50, self._width - 35 - 1)
        self.pixmapY = randint(40, self._height - 35 - 1)
        self.loading = False
        self.loadingChanged.emit(False)
        self.update()

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        rect = QRectF(0, 0, self._width, self._height)
        path.addRoundedRect(rect, 5, 5)
        painter.setClipPath(path)
        painter.drawPixmap(QPoint(0, 0), self.currentImage)

        shadowPixmap = self.currentImage.copy(self.pixmapX, self.pixmapY, 35, 35)
        shadowPainter = QPainter(shadowPixmap)
        shadowPainter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceAtop
        )
        shadowPainter.fillRect(shadowPixmap.rect(), QColor(0, 0, 0, 200))
        shadowPainter.end()
        painter.drawPixmap(QPoint(self.pixmapX, self.pixmapY), shadowPixmap)

        movePixmap = self.currentImage.copy(self.pixmapX, self.pixmapY, 35, 35)
        movePainter = QPainter(movePixmap)
        movePainter.setPen(QPen(QColor(255, 255, 255), 2))
        movePainter.setBrush(Qt.BrushStyle.NoBrush)
        movePainter.drawRect(0, 0, 34, 34)
        movePainter.end()
        painter.drawPixmap(QPoint(self._moveX, self.pixmapY), movePixmap)

        if self.loading:
            painter.save()

            painter.setBrush(QColor(0, 0, 0, 150))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(0, 0, self._width, self._height, 5, 5)

            painter.setPen(QColor(255, 255, 255))
            font = QFont("Microsoft YaHei", 16)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "加载中...")
            painter.restore()

        super().paintEvent(event)

    def setMoveX(self, mapped_value):
        internal_value = int(mapped_value * 266 / 300)
        self._moveX = 1 + internal_value
        self.update()

    def getMoveX(self):
        return self._moveX

    def getCorrectValue(self):
        return self.pixmapX

    value = Property(int, getMoveX, setMoveX)

    def resetAnimation(self):

        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setDuration(800)
        self.animation.setStartValue(self._moveX)
        self.animation.setEndValue(0)
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuint)
        self.animation.start()

    def refreshImage(self):

        if (
            hasattr(self, "animation")
            and self.animation.state() == QPropertyAnimation.State.Running
        ):
            self.animation.stop()
            self.animation.deleteLater()
            delattr(self, "animation")

        if self.image_url:
            self.load_image_from_url(self.image_url)
        else:
            self.fallback_to_local_image()
