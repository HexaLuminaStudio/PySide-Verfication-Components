import random
import math
from PySide6.QtWidgets import (
    QWidget,
)
from PySide6.QtCore import (
    Qt,
    QPropertyAnimation,
    QEasingCurve,
    QPoint,
    QRectF,
    QUrl,
    Property,
    QPointF,
    Signal,
)
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QPen, QPainterPath
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from ..components.background import procedural_background
from ..components.rendering import copy_logical, cover_pixmap, effective_dpr, new_canvas


class VerificationImage(QWidget):
    loadingChanged = Signal(bool)
    errorOccurred = Signal(str)

    def __init__(self, parent=None, image_url: str | None = None):
        super().__init__(parent=parent)

        self.image_url = image_url

        self._width = 300
        self._height = 169
        self._dpr = effective_dpr(self)
        self.setFixedSize(self._width, self._height)

        
        self.network_manager = QNetworkAccessManager(self)
        self.network_manager.setTransferTimeout(5000)
        self._active_reply = None

        
        self.currentImage = new_canvas(self._width, self._height, dpr=self._dpr)

        
        self.centerX = self._width // 2  
        self.centerY = self._height // 2  
        self.radius = 60  
        self.gapAngle = 0.0  
        self.gapX = 0  
        self.gapY = 0  
        self.currentAngle = 0.0  
        self.angleTolerance = 0.1  
        self.positionTolerance = 5  

        
        self.sliderPixmap = None

        
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
        if self._active_reply is not None:
            self._active_reply.abort()
            self._active_reply.deleteLater()
        self._active_reply = self.network_manager.get(request)
        self._active_reply.finished.connect(
            lambda reply=self._active_reply: self.on_image_downloaded(reply)
        )

    def on_image_downloaded(self, reply: QNetworkReply):
        if reply is not self._active_reply:
            reply.deleteLater()
            return
        self._active_reply = None
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
                self.currentImage = cover_pixmap(
                    pixmap, self._width, self._height, dpr=self._dpr
                )
                
                self.generate_circle_and_gap()
                self.loading = False
                self.loadingChanged.emit(False)
                self.update()
        reply.deleteLater()

    def fallback_to_local_image(self):
        self.currentImage = procedural_background(
            self._width, self._height, dpr=self._dpr
        )
        self.generate_circle_and_gap()
        self.loading = False
        self.loadingChanged.emit(False)
        self.update()

    def generate_circle_and_gap(self):
        
        max_attempts = 100
        for _ in range(max_attempts):
            
            cx = random.randint(50, self._width - 50)
            cy = random.randint(50, self._height - 50)
            
            max_r = (
                min(cx, self._width - cx, cy, self._height - cy) - 18
            )  
            if max_r < 30:
                continue
            r = random.randint(30, int(max_r))
            
            angle = random.uniform(0, 2 * math.pi)
            gx = cx + r * math.cos(angle)
            gy = cy + r * math.sin(angle)
            
            if (18 <= gx <= self._width - 18) and (18 <= gy <= self._height - 18):
                self.centerX = cx
                self.centerY = cy
                self.radius = r
                self.gapAngle = angle
                self.gapX = gx
                self.gapY = gy
                
                self.sliderPixmap = copy_logical(
                    self.currentImage, gx - 17.5, gy - 17.5, 35, 35
                )
                self.currentAngle = 0.0  
                return
        
        self.centerX = self._width // 2
        self.centerY = self._height // 2
        self.radius = 60
        self.gapAngle = 0.0
        self.gapX = self.centerX + self.radius
        self.gapY = self.centerY
        self.sliderPixmap = copy_logical(
            self.currentImage, self.gapX - 17.5, self.gapY - 17.5, 35, 35
        )
        self.currentAngle = 0.0

    def setAngle(self, mapped_value: float):
        
        
        actual_deg = (mapped_value / 300.0) * 360.0
        self.currentAngle = math.radians(actual_deg)
        self.update()

    def getAngleDeg(self) -> float:
        
        actual_deg = math.degrees(self.currentAngle)
        mapped = (actual_deg / 360.0) * 300.0
        
        return max(0.0, min(300.0, mapped))

        

    angleDeg = Property(float, getAngleDeg, setAngle)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        
        path = QPainterPath()
        rect = QRectF(0, 0, self._width, self._height)
        path.addRoundedRect(rect, 5, 5)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, self.currentImage)

        
        painter.setPen(QPen(QColor(255, 255, 255, 150), 2, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(
            QPointF(self.centerX, self.centerY), self.radius, self.radius
        )

        
        shadowPixmap = copy_logical(
            self.currentImage, self.gapX - 17.5, self.gapY - 17.5, 35, 35
        )
        shadowPainter = QPainter(shadowPixmap)
        shadowPainter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceAtop
        )
        shadowPainter.fillRect(shadowPixmap.rect(), QColor(0, 0, 0, 200))
        shadowPainter.end()
        painter.drawPixmap(
            QPoint(int(self.gapX - 17.5), int(self.gapY - 17.5)), shadowPixmap
        )

        if self.sliderPixmap:
            
            sx = self.centerX + self.radius * math.cos(self.currentAngle)
            sy = self.centerY + self.radius * math.sin(self.currentAngle)
            
            painter.save()
            painter.translate(sx, sy)
            
            painter.drawPixmap(QPoint(-17, -17), self.sliderPixmap)
            
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(-17, -17, 34, 34)
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

    def resetAnimation(self):

        if (
            hasattr(self, "animation")
            and self.animation.state() == QPropertyAnimation.State.Running
        ):
            self.animation.stop()
            self.animation.deleteLater()
            delattr(self, "animation")
        self.animation = QPropertyAnimation(self, b"angleDeg")
        self.animation.setDuration(800)
        self.animation.setStartValue(self.getAngleDeg())  
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

    def verify(self) -> bool:

        sx = self.centerX + self.radius * math.cos(self.currentAngle)
        sy = self.centerY + self.radius * math.sin(self.currentAngle)

        dist = math.hypot(sx - self.gapX, sy - self.gapY)
        return dist <= self.positionTolerance
