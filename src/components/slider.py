"""Accessible slider control and lightweight interaction analysis.

The analysis is intentionally a usability signal, not a security boundary. A
desktop client can always be automated, so applications should still validate
the protected operation on a trusted backend.
"""

from __future__ import annotations

import statistics
import time
from math import pi, sin
from dataclasses import dataclass
from typing import Sequence

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QPointF,
    Property,
    QPropertyAnimation,
    QRect,
    Qt,
    Signal,
)
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

    ERROR_RETURN_DURATION_MS = 520
    ERROR_SHAKE_DURATION_MS = 360
    SUCCESS_DURATION_MS = 360
    HOVER_DURATION_MS = 160

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
        self._hover_progress = 0.0
        self._feedback_progress = 0.0
        self._shake_offset = 0.0
        self._track: list[tuple[float, float]] = []
        self._policy = policy or TrackPolicy()

        self._reset_animation = QPropertyAnimation(self, b"value")
        self._reset_animation.setDuration(self.ERROR_RETURN_DURATION_MS)
        self._reset_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation = self._reset_animation  # compatibility with earlier releases

        self._shake_animation = QPropertyAnimation(self, b"shakeOffset")
        self._shake_animation.setDuration(self.ERROR_SHAKE_DURATION_MS)
        self._shake_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        for step, offset in ((0.0, 0.0), (0.18, -4.0), (0.38, 4.0), (0.58, -3.0), (0.78, 2.0), (1.0, 0.0)):
            self._shake_animation.setKeyValueAt(step, offset)

        self._error_animation = QParallelAnimationGroup(self)
        self._error_animation.addAnimation(self._reset_animation)
        self._error_animation.addAnimation(self._shake_animation)
        self._error_animation.finished.connect(self._finish_error_feedback)

        self._success_animation = QPropertyAnimation(self, b"feedbackProgress", self)
        self._success_animation.setDuration(self.SUCCESS_DURATION_MS)
        self._success_animation.setStartValue(0.0)
        self._success_animation.setEndValue(1.0)
        self._success_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._hover_animation = QPropertyAnimation(self, b"hoverProgress", self)
        self._hover_animation.setDuration(self.HOVER_DURATION_MS)
        self._hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

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

    def getHoverProgress(self) -> float:
        return self._hover_progress

    def setHoverProgress(self, progress: float) -> None:
        self._hover_progress = max(0.0, min(1.0, float(progress)))
        self.update()

    hoverProgress = Property(float, getHoverProgress, setHoverProgress)

    def getFeedbackProgress(self) -> float:
        return self._feedback_progress

    def setFeedbackProgress(self, progress: float) -> None:
        self._feedback_progress = max(0.0, min(1.0, float(progress)))
        self.update()

    feedbackProgress = Property(float, getFeedbackProgress, setFeedbackProgress)

    def getShakeOffset(self) -> float:
        return self._shake_offset

    def setShakeOffset(self, offset: float) -> None:
        self._shake_offset = float(offset)
        self.update()

    shakeOffset = Property(float, getShakeOffset, setShakeOffset)

    def setError(self, error: bool = True) -> None:
        if not error:
            self._error_animation.stop()
            self._state = "normal"
            self._shake_offset = 0.0
            self._feedback_progress = 0.0
            self.setEnabled(True)
        else:
            self._state = "error"
        self.update()

    def setSuccess(self, success: bool = True) -> None:
        self._success_animation.stop()
        if success:
            self._error_animation.stop()
            self._state = "success"
            self._pressed = False
            self._hovered = False
            self.setEnabled(False)
            self._success_animation.start()
        else:
            self._state = "normal"
            self._feedback_progress = 0.0
            self.setEnabled(True)
        self.update()

    def reset(self) -> None:
        self._error_animation.stop()
        self._success_animation.stop()
        self._hover_animation.stop()
        self._state = "normal"
        self._pressed = False
        self._hovered = False
        self._hover_progress = 0.0
        self._feedback_progress = 0.0
        self._shake_offset = 0.0
        self._track = []
        self.setValue(0)
        self.setEnabled(True)
        self.update()

    def resetAnimation(self) -> None:
        """Compatibility alias for the consolidated error feedback animation."""

        self.showErrorAndReset()

    def showErrorAndReset(self) -> None:
        """Run one interrupt-safe error animation and restore the normal state."""

        if self._error_animation.state() == QAbstractAnimation.State.Running:
            return
        self._success_animation.stop()
        self._state = "error"
        self._pressed = False
        self._hovered = False
        self._feedback_progress = 1.0
        self.setEnabled(False)
        self._reset_animation.setStartValue(self._value)
        self._reset_animation.setEndValue(0)
        self._error_animation.start()
        self.update()

    def _finish_error_feedback(self) -> None:
        self._state = "normal"
        self._feedback_progress = 0.0
        self._shake_offset = 0.0
        self._track = []
        self.setEnabled(True)
        self.update()

    def _set_hovered(self, hovered: bool) -> None:
        if hovered == self._hovered:
            return
        self._hovered = hovered
        self._hover_animation.stop()
        self._hover_animation.setStartValue(self._hover_progress)
        self._hover_animation.setEndValue(1.0 if hovered else 0.0)
        self._hover_animation.start()

    def _submit(self) -> None:
        result = analyze_track(self._track, self._policy)
        result.update({"value": round(self._value * 300 / self.maximum), "endTime": time.monotonic()})
        self.resultSignal.emit(result)
        self.sliderReleased.emit()
        self._track = []

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._state != "success":
            handle = QRect(1 + self._value, 1, 32, 32)
            if handle.adjusted(-4, -4, 4, 4).contains(event.position().toPoint()):
                self._pressed = True
                self._state = "normal"
                self._hover_animation.stop()
                self._hover_progress = 1.0
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
            self._set_hovered(hovered)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        if not self._pressed:
            self._set_hovered(False)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._pressed:
            self._track.append((event.position().x(), time.monotonic()))
            self._pressed = False
            self._submit()
            if self.isEnabled():
                self._set_hovered(self.rect().contains(event.position().toPoint()))
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
        if self.hasFocus() and self._state == "normal":
            painter.setPen(QPen(QColor(25, 145, 250, 150), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(groove.adjusted(0, 0, -1, -1), 6, 6)
            painter.setPen(Qt.PenStyle.NoPen)
        if self._value:
            painter.setBrush(QColor(state_color.red(), state_color.green(), state_color.blue(), 42))
            painter.drawRoundedRect(QRect(1, 1, self._value + 16, 32), 6, 6)

        pulse = sin(pi * self._feedback_progress) if self._state == "success" else 0.0
        grow = round(pulse * 1.5)
        handle = QRect(1 + self._value + round(self._shake_offset), 1, 32, 32).adjusted(
            -grow, -grow, grow, grow
        )
        active_handle = self._pressed or self._state != "normal"
        hover_mix = 1.0 if active_handle else self._hover_progress
        pen_color = QColor(
            round(self.NORMAL_PEN.red() + (state_color.red() - self.NORMAL_PEN.red()) * hover_mix),
            round(self.NORMAL_PEN.green() + (state_color.green() - self.NORMAL_PEN.green()) * hover_mix),
            round(self.NORMAL_PEN.blue() + (state_color.blue() - self.NORMAL_PEN.blue()) * hover_mix),
        )
        painter.setPen(QPen(pen_color, 1))
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
