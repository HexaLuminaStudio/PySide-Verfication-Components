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
            self.localImage()

    def load_image_from_url(self, url: str):

        self.loading = True
        self.loadingChanged.emit(True)
        self.update()
        request = QNetworkRequest(QUrl(url))
        self.network_manager.get(request)

    def on_image_downloaded(self, reply: QNetworkReply):

        if reply.error() != QNetworkReply.NetworkError.NoError:
            self.errorOccurred.emit(f"图片加载失败：{reply.errorString()}")
            self.localImage()
        else:
            data = reply.readAll()
            pixmap = QPixmap()
            if not pixmap.loadFromData(data):
                self.errorOccurred.emit("图片数据无法解析，已使用离线背景")
                self.localImage()
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

    def create_puzzle_path(self, x, y, width, height, radius=None):

        if radius is None:
            radius = width // 7
        rect_path = QPainterPath()
        rect_path.addRect(x, y, width - radius, height)

        circle_path = QPainterPath()
        circle_x = x + width - 2 * radius
        circle_y = y + (height - 2 * radius) / 2
        circle_path.addEllipse(circle_x, circle_y, 2 * radius, 2 * radius)

        return rect_path.united(circle_path)

    def localImage(self):
        self.currentImage = procedural_background(self._width, self._height)

        self.pixmapX = randint(50, self._width - 35 - 1)
        self.pixmapY = randint(40, self._height - 35 - 1)
        self.loading = False
        self.loadingChanged.emit(False)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg_path = QPainterPath()
        bg_path.addRoundedRect(0, 0, self._width, self._height, 5, 5)
        painter.setClipPath(bg_path)
        painter.drawPixmap(0, 0, self.currentImage)
        painter.setClipPath(bg_path, Qt.ClipOperation.NoClip)

        shape_size = 35
        radius = shape_size // 3
        shape_path = self.create_puzzle_path(
            self.pixmapX, self.pixmapY, shape_size, shape_size, radius
        )

        painter.save()
        painter.setClipPath(shape_path)
        shadow_pixmap = self.currentImage.copy(
            self.pixmapX, self.pixmapY, shape_size, shape_size
        )
        painter.drawPixmap(self.pixmapX, self.pixmapY, shadow_pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
        painter.fillRect(
            QRect(self.pixmapX, self.pixmapY, shape_size, shape_size),
            QColor(0, 0, 0, 200),
        )
        painter.restore()

        painter.save()
        slider_path = QPainterPath(shape_path)
        slider_path.translate(self._moveX - self.pixmapX, 0)
        painter.setClipPath(slider_path)
        slider_pixmap = self.currentImage.copy(
            self.pixmapX, self.pixmapY, shape_size, shape_size
        )
        painter.drawPixmap(self._moveX, self.pixmapY, slider_pixmap)

        painter.setClipping(False)
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(slider_path)
        painter.restore()

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

    def refresh_image(self):

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
            self.localImage()

    refreshImage = refresh_image


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = QWidget()
    window.setWindowTitle("验证码图片加载测试")
    layout = QVBoxLayout(window)

    v_image = VerificationImage()
    layout.addWidget(v_image)

    from PySide6.QtWidgets import QPushButton

    btn_refresh = QPushButton("刷新图片")
    btn_refresh.clicked.connect(v_image.refresh_image)
    layout.addWidget(btn_refresh)

    window.show()
    sys.exit(app.exec())
