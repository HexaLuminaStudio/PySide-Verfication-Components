"""Accessible slider control and lightweight interaction analysis.

The analysis is intentionally a usability signal, not a security boundary. A
desktop client can always be automated, so applications should still validate
the protected operation on a trusted backend.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from typing import Sequence

from PySide6.QtCore import QEasingCurve, QPointF, Property, QPropertyAnimation, QRect, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget


@dataclass(frozen=True, slots=True)
class TrackPolicy:
    """Tunable, deliberately conservative interaction checks."""

    min_samples: int = 4
    min_duration: float = 0.12
    max_duration: float = 15.0
    min_distance: float = 18.0
    reject_perfect_linear_tracks: bool = True


def analyze_track(
    track: Sequence[tuple[float, float]], policy: TrackPolicy | None = None
) -> dict[str, object]:
    """Return one stable result for a pointer track."""

    policy = policy or TrackPolicy()
    if len(track) < policy.min_samples:
        return {"result": False, "msg": ["滑动轨迹过短"]}

    xs = [float(point[0]) for point in track]
    ts = [float(point[1]) for point in track]
    duration = ts[-1] - ts[0]
    distance = abs(xs[-1] - xs[0])
    if duration < policy.min_duration or duration > policy.max_duration:
        return {"result": False, "msg": ["滑动时间异常"]}
    if distance < policy.min_distance:
        return {"result": False, "msg": ["滑动距离过短"]}

    if policy.reject_perfect_linear_tracks and len(track) >= 6:
        intervals = [ts[i] - ts[i - 1] for i in range(1, len(ts))]
        deltas = [xs[i] - xs[i - 1] for i in range(1, len(xs))]
        mean_interval = statistics.fmean(intervals)
        mean_delta = statistics.fmean(deltas)
        interval_spread = max(intervals) - min(intervals)
        delta_spread = max(deltas) - min(deltas)
        regular_timing = mean_interval > 0 and interval_spread <= max(0.0005, mean_interval * 0.01)
        regular_motion = abs(mean_delta) > 0 and delta_spread <= max(0.05, abs(mean_delta) * 0.01)
        if regular_timing and regular_motion:
            return {"result": False, "msg": ["滑动轨迹过于规律"]}

    return {"result": True, "msg": []}


class VerificationSlider(QWidget):
    """A keyboard-accessible verification slider with a stable public API."""

    resultSignal = Signal(dict)
    valueChanged = Signal(int)
    sliderPressed = Signal()
    sliderReleased = Signal()

    NORMAL_PEN = QColor(201, 204, 207)
    NORMAL_BRUSH = QColor(255, 255, 255)
    ACTIVE = QColor(25, 145, 250)
    ERROR = QColor(220, 68, 78)
    SUCCESS = QColor(29, 148, 122)

    def __init__(self, parent: QWidget | None = None, policy: TrackPolicy | None = None):
        super().__init__(parent)
        self.setFixedSize(300, 40)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAccessibleName("验证码滑块")
        self.setAccessibleDescription("拖动或使用左右方向键移动，松开或按回车提交")

        self.minimum = 0
        self.maximum = 266
        self._value = 0
        self._pressed = False
        self._hovered = False
        self._state = "normal"
        self._track: list[tuple[float, float]] = []
        self._policy = policy or TrackPolicy()
        self._animation = QPropertyAnimation(self, b"value", self)
        self._animation.setDuration(360)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def getValue(self) -> int:
        return self._value

    def setValue(self, value: int) -> None:
        bounded = max(self.minimum, min(self.maximum, int(value)))
        if bounded == self._value:
            return
        self._value = bounded
        self.valueChanged.emit(round(self._value * 300 / self.maximum))
        self.update()

    value = Property(int, getValue, setValue)

    def setError(self, error: bool = True) -> None:
        self._state = "error" if error else "normal"
        self.update()

    def setSuccess(self, success: bool = True) -> None:
        self._state = "success" if success else "normal"
        self.update()

    def reset(self) -> None:
        self._state = "normal"
        self.setValue(0)
        self.setEnabled(True)

    def resetAnimation(self) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._value)
        self._animation.setEndValue(0)
        self._animation.start()

    def _submit(self) -> None:
        result = analyze_track(self._track, self._policy)
        result.update({"value": round(self._value * 300 / self.maximum), "endTime": time.monotonic()})
        self.resultSignal.emit(result)
        self.sliderReleased.emit()
        if not result["result"]:
            self.setError(True)
            self.resetAnimation()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._state != "success":
            handle = QRect(1 + self._value, 1, 32, 32)
            if handle.adjusted(-4, -4, 4, 4).contains(event.position().toPoint()):
                self._pressed = True
                self._state = "normal"
                self._track = [(event.position().x(), time.monotonic())]
                self.sliderPressed.emit()
                self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._pressed:
            self.setValue(round(event.position().x() - 17))
            self._track.append((event.position().x(), time.monotonic()))
        else:
            hovered = QRect(1 + self._value, 1, 32, 32).adjusted(-4, -4, 4, 4).contains(
                event.position().toPoint()
            )
            if hovered != self._hovered:
                self._hovered = hovered
                self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._pressed:
            self._track.append((event.position().x(), time.monotonic()))
            self._pressed = False
            self._submit()
            self.update()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            direction = -1 if event.key() == Qt.Key.Key_Left else 1
            now = time.monotonic()
            if not self._track:
                self._track = [(float(self._value), now)]
                self.sliderPressed.emit()
            step = 1 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 8
            self.setValue(self._value + direction * step)
            self._track.append((float(self._value), now))
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space) and self._track:
            self._submit()
            self._track = []
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        groove = QRect(1, 1, 298, 32)
        state_color = self.SUCCESS if self._state == "success" else self.ERROR if self._state == "error" else self.ACTIVE

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(241, 244, 247))
        painter.drawRoundedRect(groove, 6, 6)
        if self._value:
            painter.setBrush(QColor(state_color.red(), state_color.green(), state_color.blue(), 42))
            painter.drawRoundedRect(QRect(1, 1, self._value + 16, 32), 6, 6)

        handle = QRect(1 + self._value, 1, 32, 32)
        active_handle = self._pressed or self._state != "normal"
        painter.setPen(QPen(state_color if (self._hovered or active_handle) else self.NORMAL_PEN, 1))
        painter.setBrush(state_color if active_handle else self.NORMAL_BRUSH)
        painter.drawRoundedRect(handle, 6, 6)

        icon_color = QColor(255, 255, 255) if active_handle else QColor(86, 96, 109)
        painter.setPen(QPen(icon_color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        center = handle.center()
        if self._state == "success":
            painter.drawLine(QPointF(center.x() - 5, center.y()), QPointF(center.x() - 1, center.y() + 4))
            painter.drawLine(QPointF(center.x() - 1, center.y() + 4), QPointF(center.x() + 6, center.y() - 4))
        elif self._state == "error":
            painter.drawLine(center.x() - 4, center.y() - 4, center.x() + 4, center.y() + 4)
            painter.drawLine(center.x() + 4, center.y() - 4, center.x() - 4, center.y() + 4)
        else:
            painter.drawLine(center.x() - 5, center.y(), center.x() + 5, center.y())
            painter.drawLine(center.x() + 2, center.y() - 3, center.x() + 5, center.y())
            painter.drawLine(center.x() + 2, center.y() + 3, center.x() + 5, center.y())
