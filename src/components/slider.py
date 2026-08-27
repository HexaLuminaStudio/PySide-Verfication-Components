"""Accessible slider control and lightweight interaction analysis.

The analysis is intentionally a usability signal, not a security boundary. A
desktop client can always be automated, so applications should still validate
the protected operation on a trusted backend.
"""

from __future__ import annotations

import statistics
import time
from collections import Counter
from dataclasses import dataclass
from math import hypot, isfinite, pi, sin
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
    """Tunable client-side risk policy.

    These signals raise the cost of naive automation but are not a security
    boundary. Authoritative acceptance belongs on a trusted server.
    """

    min_samples: int = 3
    min_duration: float = 0.01
    max_duration: float = 15.0
    min_distance: float = 18.0
    reject_perfect_linear_tracks: bool = True
    risk_threshold: int = 65
    fast_duration: float = 0.20
    max_pointer_speed: float = 3500.0
    max_samples: int = 512


def _coefficient_of_variation(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = abs(statistics.fmean(values))
    return statistics.pstdev(values) / mean if mean > 1e-9 else 0.0


def _normalise_track(
    track: Sequence[tuple[float, ...]],
) -> list[tuple[float, float, float]]:
    points: list[tuple[float, float, float]] = []
    for point in track:
        if len(point) == 2:
            x, timestamp = point
            points.append((float(x), 0.0, float(timestamp)))
        elif len(point) >= 3:
            x, y, timestamp = point[:3]
            points.append((float(x), float(y), float(timestamp)))
    return points


def _coalesce_equal_timestamps(
    points: Sequence[tuple[float, float, float]],
) -> tuple[list[tuple[float, float, float]], int] | None:
    """Merge event-loop samples sharing a timestamp and reject time reversal."""

    if not points:
        return [], 0
    coalesced = [points[0]]
    duplicate_count = 0
    for point in points[1:]:
        previous_time = coalesced[-1][2]
        if point[2] < previous_time:
            return None
        if point[2] == previous_time:
            # Qt can deliver several positions inside one clock tick. Keeping
            # the latest position preserves the actual travelled endpoint and
            # avoids a zero interval during speed calculation.
            coalesced[-1] = point
            duplicate_count += 1
        else:
            coalesced.append(point)
    return coalesced, duplicate_count


def analyze_track(
    track: Sequence[tuple[float, ...]],
    policy: TrackPolicy | None = None,
    *,
    input_method: str = "pointer",
) -> dict[str, object]:
    """Return an explainable risk decision for a pointer or keyboard track."""

    policy = policy or TrackPolicy()
    points = _normalise_track(track[: policy.max_samples])
    if any(not all(isfinite(value) for value in point) for point in points):
        return {
            "result": False,
            "msg": ["轨迹数据异常"],
            "riskScore": 100,
            "inputMethod": input_method,
            "metrics": {"sampleCount": len(points)},
        }

    coalesced = _coalesce_equal_timestamps(points)
    if coalesced is None:
        return {
            "result": False,
            "msg": ["轨迹时间戳异常"],
            "riskScore": 100,
            "inputMethod": input_method,
            "metrics": {"sampleCount": len(points)},
        }
    points, duplicate_timestamp_count = coalesced
    if len(points) < policy.min_samples:
        return {
            "result": False,
            "msg": ["滑动轨迹过短"],
            "riskScore": 100,
            "inputMethod": input_method,
            "metrics": {
                "sampleCount": len(points),
                "duplicateTimestampCount": duplicate_timestamp_count,
            },
        }

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    ts = [point[2] for point in points]
    intervals = [ts[index] - ts[index - 1] for index in range(1, len(ts))]
    duration = ts[-1] - ts[0]
    distance = abs(xs[-1] - xs[0])
    if duration < policy.min_duration or duration > policy.max_duration:
        return {
            "result": False,
            "msg": ["滑动时间异常"],
            "riskScore": 100,
            "inputMethod": input_method,
            "metrics": {"sampleCount": len(points), "duration": round(duration, 4)},
        }
    if distance < policy.min_distance:
        return {
            "result": False,
            "msg": ["滑动距离过短"],
            "riskScore": 100,
            "inputMethod": input_method,
            "metrics": {"sampleCount": len(points), "distance": round(distance, 3)},
        }

    deltas_x = [xs[index] - xs[index - 1] for index in range(1, len(xs))]
    deltas_y = [ys[index] - ys[index - 1] for index in range(1, len(ys))]
    segment_lengths = [hypot(dx, dy) for dx, dy in zip(deltas_x, deltas_y)]
    speeds = [length / interval for length, interval in zip(segment_lengths, intervals)]
    path_length = sum(segment_lengths)
    straightness = distance / path_length if path_length > 0 else 1.0
    backward_distance = sum(abs(delta) for delta in deltas_x if delta < 0)
    backward_ratio = backward_distance / max(distance, 1.0)
    interval_cv = _coefficient_of_variation(intervals)
    delta_cv = _coefficient_of_variation([abs(value) for value in deltas_x])
    speed_cv = _coefficient_of_variation(speeds)
    median_speed = statistics.median(speeds)
    high_speed_ratio = sum(
        speed > policy.max_pointer_speed for speed in speeds
    ) / len(speeds)
    dominant_delta_ratio = Counter(round(value, 2) for value in deltas_x).most_common(1)[0][1] / len(deltas_x)
    dominant_interval_ratio = Counter(round(value, 4) for value in intervals).most_common(1)[0][1] / len(intervals)
    residuals = []
    for x, timestamp in zip(xs, ts):
        progress = (timestamp - ts[0]) / duration
        expected_x = xs[0] + (xs[-1] - xs[0]) * progress
        residuals.append(x - expected_x)
    linear_residual = (statistics.fmean(value * value for value in residuals)) ** 0.5

    metrics = {
        "sampleCount": len(points),
        "duplicateTimestampCount": duplicate_timestamp_count,
        "duration": round(duration, 4),
        "distance": round(distance, 3),
        "pathLength": round(path_length, 3),
        "straightness": round(straightness, 4),
        "verticalSpan": round(max(ys) - min(ys), 3),
        "backwardRatio": round(backward_ratio, 4),
        "intervalCv": round(interval_cv, 4),
        "deltaCv": round(delta_cv, 4),
        "speedCv": round(speed_cv, 4),
        "maxSpeed": round(max(speeds), 2),
        "medianSpeed": round(median_speed, 2),
        "highSpeedRatio": round(high_speed_ratio, 4),
        "linearResidual": round(linear_residual, 4),
        "dominantDeltaRatio": round(dominant_delta_ratio, 4),
        "dominantIntervalRatio": round(dominant_interval_ratio, 4),
    }

    risk_score = 0
    signals: list[str] = []
    if input_method == "pointer":
        if duration < policy.fast_duration:
            risk_score += 25
            signals.append("完成速度过快")
        if median_speed > policy.max_pointer_speed or high_speed_ratio >= 0.5:
            risk_score += 40
            signals.append("持续速度异常")
        if dominant_delta_ratio >= 0.8:
            risk_score += 22
            signals.append("重复步长比例过高")
        if dominant_interval_ratio >= 0.8:
            risk_score += 18
            signals.append("采样间隔过于一致")
        if speed_cv < 0.04:
            risk_score += 20
            signals.append("速度变化过低")
        if linear_residual < 0.35:
            risk_score += 18
            signals.append("轨迹与理想直线高度重合")
        if straightness > 0.9995:
            risk_score += 8
            signals.append("路径缺少自然偏移")
        if max(ys) - min(ys) < 0.5:
            risk_score += 5
        if backward_ratio > 0.45:
            risk_score += 15
            signals.append("回退比例异常")
        if (
            policy.reject_perfect_linear_tracks
            and interval_cv < 0.015
            and delta_cv < 0.015
        ):
            risk_score += 45
            signals.append("滑动轨迹过于规律")

    risk_score = min(100, risk_score)
    accepted = risk_score < policy.risk_threshold
    return {
        "result": accepted,
        "msg": [] if accepted else signals or ["人机风险评分过高"],
        "riskScore": risk_score,
        "inputMethod": input_method,
        "metrics": metrics,
        "signals": signals,
    }


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
        self._track: list[tuple[float, float, float]] = []
        self._input_method = "pointer"
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

    def setPending(self, pending: bool = True) -> None:
        """Lock interaction while a trusted service validates the attempt."""

        if pending:
            self._error_animation.stop()
            self._success_animation.stop()
            self._state = "pending"
            self._pressed = False
            self._hovered = False
            self.setEnabled(False)
        elif self._state == "pending":
            self._state = "normal"
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
        result = analyze_track(
            self._track, self._policy, input_method=self._input_method
        )
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
                self._input_method = "pointer"
                self._track = [
                    (event.position().x(), event.position().y(), time.monotonic())
                ]
                self.sliderPressed.emit()
                self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._pressed:
            self.setValue(round(event.position().x() - 17))
            self._track.append(
                (event.position().x(), event.position().y(), time.monotonic())
            )
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
            self._track.append(
                (event.position().x(), event.position().y(), time.monotonic())
            )
            self._pressed = False
            self._submit()
            if self.isEnabled():
                self._set_hovered(self.rect().contains(event.position().toPoint()))
            self.update()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            direction = -1 if event.key() == Qt.Key.Key_Left else 1
            if not self._track:
                self._input_method = "keyboard"
                self._track = [(float(self._value), 0.0, time.monotonic())]
                self.sliderPressed.emit()
            step = 1 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 8
            self.setValue(self._value + direction * step)
            self._track.append((float(self._value), 0.0, time.monotonic()))
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
        elif self._state == "pending":
            painter.setBrush(icon_color)
            painter.setPen(Qt.PenStyle.NoPen)
            for offset in (-5, 0, 5):
                painter.drawEllipse(QPointF(center.x() + offset, center.y()), 1.4, 1.4)
        else:
            painter.drawLine(center.x() - 5, center.y(), center.x() + 5, center.y())
            painter.drawLine(center.x() + 2, center.y() - 3, center.x() + 5, center.y())
            painter.drawLine(center.x() + 2, center.y() + 3, center.x() + 5, center.y())
