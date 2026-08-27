from random import randint
from typing import List

from PySide6.QtWidgets import (
    QWidget,
)
from PySide6.QtCore import (
    Qt,
    QPropertyAnimation,
    QEasingCurve,
    Signal,
    QPoint,
    QRectF,
    Property,
)
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QPainterPath

from ..components.background import procedural_background
from ..components.rendering import copy_logical, cover_pixmap, effective_dpr


class VerificationImage(QWidget):
    errorOccurred = Signal(str)

    def __init__(self, imageList: List[QPixmap] | None = None, parent=None):
        super().__init__(parent=parent)
        self.imageList = list(imageList or [])

        self._width = 300
        self._height = 169
        self._dpr = effective_dpr(self)
        self.setFixedSize(self._width, self._height)

        try:
            idx = randint(0, len(self.imageList) - 1)
            self.currentImage = cover_pixmap(
                self.imageList[idx], self._width, self._height, dpr=self._dpr
            )
            if self.currentImage.isNull():
                raise ValueError("图片为空")
        except (IndexError, ValueError, TypeError) as error:
            self.errorOccurred.emit(f"图片加载失败：{error}")
            self.currentImage = procedural_background(
                self._width, self._height, dpr=self._dpr
            )

        self.pixmapX = randint(50, self._width - 35 - 1)
        self.pixmapY = randint(40, self._height - 35 - 1)

        self._moveX = 1

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        path = QPainterPath()
        rect = QRectF(0, 0, self._width, self._height)
        path.addRoundedRect(rect, 5, 5)
        painter.setClipPath(path)
        painter.drawPixmap(QPoint(0, 0), self.currentImage)

        shadowPixmap = copy_logical(self.currentImage, self.pixmapX, self.pixmapY, 35, 35)
        shadowPainter = QPainter(shadowPixmap)
        shadowPainter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceAtop
        )
        shadowPainter.fillRect(shadowPixmap.rect(), QColor(0, 0, 0, 150))
        shadowPainter.end()
        painter.drawPixmap(QPoint(self.pixmapX, self.pixmapY), shadowPixmap)

        movePixmap = copy_logical(self.currentImage, self.pixmapX, self.pixmapY, 35, 35)
        movePainter = QPainter(movePixmap)
        movePainter.setPen(QPen(QColor(255, 255, 255), 2))
        movePainter.setBrush(Qt.BrushStyle.NoBrush)
        movePainter.drawRect(QRectF(1, 1, 33, 33))
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

    def refreshImage(self):

        if (
            hasattr(self, "animation")
            and self.animation.state() == QPropertyAnimation.State.Running
        ):
            self.animation.stop()
            self.animation.deleteLater()

            delattr(self, "animation")

        try:
            idx = randint(0, len(self.imageList) - 1)
            self.currentImage = cover_pixmap(
                QPixmap(self.imageList[idx]), self._width, self._height, dpr=self._dpr
            )
            if self.currentImage.isNull():
                raise ValueError("图片为空")
        except (IndexError, ValueError, TypeError) as error:
            self.errorOccurred.emit(f"图片加载失败：{error}")
            self.currentImage = procedural_background(
                self._width, self._height, dpr=self._dpr
            )

        self.pixmapX = randint(50, self._width - 35 - 1)
        self.pixmapY = randint(40, self._height - 35 - 1)

        self.setMoveX(0)
