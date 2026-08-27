"""Offline image widget for the picture-straightening challenge."""

from __future__ import annotations

import math
import secrets
from collections.abc import Sequence

from PySide6.QtCore import Property, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from ..components.background import orientation_background
from ..components.rendering import cover_pixmap, effective_dpr


class VerificationImage(QWidget):
    """Rotate an aspect-preserving photo on a neutral stage."""

    errorOccurred = Signal(str)

    def __init__(
        self,
        imageList: Sequence[QPixmap] | None = None,
        parent: QWidget | None = None,
        *,
        initial_angle_degrees: float | None = None,
        angle_tolerance_degrees: float = 6.0,
        image_scale: float = 0.9,
    ) -> None:
        super().__init__(parent)
        self.imageList = list(imageList or [])
        self._width = 300
        self._height = 169
        self.imageScale = max(0.65, min(1.0, float(image_scale)))
        self._image_width = round(self._width * self.imageScale)
        self._image_height = round(self._height * self.imageScale)
        self._dpr = effective_dpr(self)
        self._fixed_initial_angle = self._normalise_initial_angle(
            initial_angle_degrees
        )
        self.angleTolerance = max(0.0, min(45.0, float(angle_tolerance_degrees)))
        self.initialAngle = 0.0
        self.currentAngle = 0.0
        self._slider_value = 0.0
        self.loading = False
        self.setFixedSize(self._width, self._height)
        self.setAccessibleName("图片旋正验证画面")
        self.setAccessibleDescription("拖动下方滑块，将倾斜的画面调整为正常方向")
        self.setToolTip("拖动滑块，将画面旋正")
        self._load_local_image()

    @staticmethod
    def _normalise_initial_angle(value: float | None) -> float | None:
        if value is None:
            return None
        angle = float(value)
        if not math.isfinite(angle):
            raise ValueError("初始旋转角度必须是有限数值")
        return angle % 360.0

    def _next_initial_angle(self) -> float:
        if self._fixed_initial_angle is not None:
            return self._fixed_initial_angle
        return float(secrets.randbelow(281) + 40)

    def _load_local_image(self) -> None:
        if self.imageList:
            source = self.imageList[secrets.randbelow(len(self.imageList))]
            if source is None or source.isNull():
                self.errorOccurred.emit("图片加载失败：图片为空")
                self.fallback_to_local_image()
                return
            self.setSourcePixmap(source)
            return
        self.fallback_to_local_image()

    def setSourcePixmap(self, source: QPixmap) -> None:
        if source.isNull():
            raise ValueError("图片为空")
        self.currentImage = cover_pixmap(
            source,
            self._image_width,
            self._image_height,
            dpr=self._dpr,
        )
        self.initialAngle = self._next_initial_angle()
        self.setAngle(0.0)

    def fallback_to_local_image(self) -> None:
        source = orientation_background(
            self._image_width,
            self._image_height,
            dpr=self._dpr,
        )
        self.setSourcePixmap(source)
        self.loading = False
        self.update()

    def refreshImage(self) -> None:
        self._load_local_image()

    def setAngle(self, mapped_value: float) -> None:
        self._slider_value = max(0.0, min(300.0, float(mapped_value)))
        applied_rotation = self._slider_value / 300.0 * 360.0
        self.currentAngle = (self.initialAngle + applied_rotation) % 360.0
        self.update()

    def getAngle(self) -> float:
        return self._slider_value

    angle = Property(float, getAngle, setAngle)

    def getCorrectValue(self) -> float:
        return ((360.0 - self.initialAngle) % 360.0) / 360.0 * 300.0

    def verify(self) -> bool:
        circular_error = min(self.currentAngle, 360.0 - self.currentAngle)
        return circular_error <= self.angleTolerance

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), 5, 5)
        painter.setClipPath(clip)
        stage = QLinearGradient(QPointF(0, 0), QPointF(0, self._height))
        stage.setColorAt(0, QColor("#31495b"))
        stage.setColorAt(1, QColor("#172733"))
        painter.fillRect(self.rect(), stage)

        painter.save()
        painter.translate(self._width / 2, self._height / 2)
        painter.rotate(self.currentAngle)
        photo_rect = QRectF(
            -self._image_width / 2,
            -self._image_height / 2,
            self._image_width,
            self._image_height,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(5, 13, 20, 86))
        painter.drawRoundedRect(photo_rect.translated(0, 3), 5, 5)

        painter.save()
        photo_clip = QPainterPath()
        photo_clip.addRoundedRect(photo_rect, 4, 4)
        painter.setClipPath(photo_clip, Qt.ClipOperation.IntersectClip)
        painter.drawPixmap(
            QPointF(-self._image_width / 2, -self._image_height / 2),
            self.currentImage,
        )
        painter.restore()

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 92), 1))
        painter.drawRoundedRect(photo_rect.adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
        painter.restore()

        shade = QLinearGradient(QPointF(0, 0), QPointF(0, 52))
        shade.setColorAt(0, QColor(9, 19, 31, 138))
        shade.setColorAt(1, QColor(9, 19, 31, 0))
        painter.fillRect(QRectF(0, 0, self._width, 52), shade)

        hint_rect = QRectF(12, 10, 40, 30)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(13, 27, 42, 190))
        painter.drawRoundedRect(hint_rect, 6, 6)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(
            QPen(
                QColor("#ffffff"),
                1.8,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.drawArc(QRectF(21, 17, 18, 18), 35 * 16, 280 * 16)
        painter.drawLine(QPointF(39, 19), QPointF(35, 18))
        painter.drawLine(QPointF(39, 19), QPointF(38, 23))

        if self.loading:
            painter.fillRect(self.rect(), QColor(9, 19, 31, 166))
            painter.setPen(QPen(QColor("#ffffff"), 2.2))
            painter.drawArc(
                QRectF(self._width / 2 - 10, self._height / 2 - 10, 20, 20),
                35 * 16,
                280 * 16,
            )

        painter.end()
