import sys
import time
import random
from random import randint
from math import sqrt
from typing import List

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
)
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPen, QPainterPath


class VerificationImage(QWidget):
    def __init__(self, imageList: List[QPixmap] | None = None, parent=None):
        super().__init__(parent=parent)
        self.imageList = list(imageList or [])

        self._width = 300
        self._height = 169
        self.setFixedSize(self._width, self._height)

        try:
            idx = randint(0, 12)
            self.currentImage = self.imageList[idx].scaled(
                self._width,
                self._height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            if self.currentImage.isNull():
                raise Exception("图片加载失败")
        except Exception as e:
            print(f"图片加载失败: {e}，使用灰色背景")
            self.currentImage = QPixmap(self._width, self._height)
            self.currentImage.fill(QColor(200, 200, 200))

        self.pixmapX = randint(50, self._width - 35 - 1)
        self.pixmapY = randint(40, self._height - 35 - 1)

        self._moveX = 1

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
        shadowPainter.fillRect(shadowPixmap.rect(), QColor(0, 0, 0, 150))
        shadowPainter.end()
        painter.drawPixmap(QPoint(self.pixmapX, self.pixmapY), shadowPixmap)

        movePixmap = self.currentImage.copy(self.pixmapX, self.pixmapY, 35, 35)
        movePainter = QPainter(movePixmap)
        movePainter.setPen(QPen(QColor(255, 255, 255), 2))
        movePainter.setBrush(Qt.BrushStyle.NoBrush)
        movePainter.drawRect(0, 0, 34, 34)
        movePainter.end()
        painter.drawPixmap(QPoint(self._moveX, self.pixmapY), movePixmap)

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

    def refresh_image(self):

        if (
            hasattr(self, "animation")
            and self.animation.state() == QPropertyAnimation.State.Running
        ):
            self.animation.stop()
            self.animation.deleteLater()

            delattr(self, "animation")

        try:
            idx = randint(0, len(self.imageList) - 1)
            self.currentImage = QPixmap(self.imageList[idx]).scaled(
                self._width,
                self._height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            if self.currentImage.isNull():
                raise Exception("图片加载失败")
        except Exception as e:
            print(f"图片加载失败: {e}，使用灰色背景")
            self.currentImage = QPixmap(self._width, self._height)
            self.currentImage.fill(QColor(200, 200, 200))

        self.pixmapX = randint(50, self._width - 35 - 1)
        self.pixmapY = randint(40, self._height - 35 - 1)

        self.setMoveX(0)
