"""Dynamic target tracking verification challenge."""

from __future__ import annotations

import math
import secrets
import time
from collections.abc import Sequence

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget


class VerificationImage(QWidget):
    verificationComplete = Signal(bool, dict)
    challengeChanged = Signal(str)
    trackingRejected = Signal(str)
    progressChanged = Signal(float, bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        waypoints: Sequence[tuple[float, float] | QPointF] | None = None,
        target_id: str | None = None,
        path_id: str | None = None,
        tracking_duration: float | None = None,
        target_speed: float = 60.0,
        tracking_radius: float = 30.0,
        hard_miss_radius: float = 72.0,
        min_follow_ratio: float = 0.78,
        max_miss_duration: float = 0.55,
        reduced_motion: bool = False,
        max_payload_samples: int = 180,
    ) -> None:
        super().__init__(parent)
        requested_duration = (
            None if tracking_duration is None else float(tracking_duration)
        )
        numeric_values = (
            float(target_speed),
            float(tracking_radius),
            float(hard_miss_radius),
            float(min_follow_ratio),
            float(max_miss_duration),
        )
        if not all(math.isfinite(value) for value in numeric_values):
            raise ValueError("动态追踪参数必须是有限数值")
        if requested_duration is not None and not math.isfinite(requested_duration):
            raise ValueError("动态追踪参数必须是有限数值")
        self._requested_tracking_duration = (
            None
            if requested_duration is None
            else max(0.25, min(12.0, requested_duration))
        )
        self.targetSpeed = max(35.0, min(120.0, numeric_values[0]))
        self.trackingDuration = 0.0
        self.trackingRadius = max(20.0, min(42.0, numeric_values[1]))
        self.hardMissRadius = max(
            self.trackingRadius + 10,
            min(120.0, numeric_values[2]),
        )
        self.minFollowRatio = max(0.5, min(0.98, numeric_values[3]))
        self.maxMissDuration = max(0.15, min(2.0, numeric_values[4]))
        self.reducedMotion = bool(reduced_motion)
        self.maxPayloadSamples = max(16, min(360, int(max_payload_samples)))
        self._fixed_waypoints = self._validate_waypoints(waypoints)
        self._fixed_target_id = str(target_id) if target_id else None
        self._fixed_path_id = str(path_id) if path_id else None

        self.waypoints: list[QPointF] = []
        self._curve_points: list[QPointF] = []
        self._curve_offsets: list[float] = []
        self.pathLength = 0.0
        self.targetId = ""
        self.pathId = ""
        self.targetPosition = QPointF()
        self.pointerPosition = QPointF()
        self.targetTrail: list[QPointF] = []
        self.trace: list[tuple[QPointF, float]] = []
        self.inputMethod = "pointer"
        self.missCount = 0
        self.followRatio = 0.0
        self.maxDeviation = 0.0
        self.averageDeviation = 0.0
        self.longestMissDuration = 0.0
        self._active = False
        self._inside_target = False
        self._started_at: float | None = None
        self._last_tick_at: float | None = None
        self._last_elapsed = 0.0
        self._follow_time = 0.0
        self._current_miss_duration = 0.0
        self._deviation_sum = 0.0
        self._sample_count = 0
        self.verificationText = "按住并持续跟随移动目标"

        self.setFixedSize(300, 169)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAccessibleName("动态目标追踪验证码")
        self.setAccessibleDescription(
            "按住目标并持续跟随；键盘用户按空格开始，再用方向键移动追踪光标"
        )
        self.setToolTip("按住目标，持续跟随直到进度完成")
        self._timer = QTimer(self)
        self._timer.setInterval(16 if not self.reducedMotion else 24)
        self._timer.timeout.connect(self._tick)
        self.generateChallenge()

    def _validate_waypoints(
        self,
        values: Sequence[tuple[float, float] | QPointF] | None,
    ) -> tuple[QPointF, ...] | None:
        if values is None:
            return None
        if not 4 <= len(values) <= 8:
            raise ValueError("waypoints 必须包含 4 到 8 个坐标")
        result: list[QPointF] = []
        for value in values:
            if isinstance(value, QPointF):
                point = QPointF(value)
            else:
                try:
                    x, y = value
                    point = QPointF(float(x), float(y))
                except (TypeError, ValueError) as error:
                    raise ValueError("waypoints 必须由二维坐标组成") from error
            if not math.isfinite(point.x()) or not math.isfinite(point.y()):
                raise ValueError("waypoints 坐标必须是有限数值")
            margin = max(22.0, self.trackingRadius)
            if not margin <= point.x() <= 300 - margin or not (
                margin <= point.y() <= 169 - margin
            ):
                raise ValueError("waypoints 坐标超出目标可移动区域")
            result.append(point)
        if max(
            math.hypot(point.x() - result[0].x(), point.y() - result[0].y())
            for point in result[1:]
        ) < 12:
            raise ValueError("waypoints 必须形成实际移动路径")
        return tuple(result)

    def _random_waypoints(self) -> list[QPointF]:
        random = secrets.SystemRandom()
        center = QPointF(150, 84)
        scale = 0.68 if self.reducedMotion else 1.0
        result = [
            QPointF(
                center.x() + (random.randint(32, 76) * scale),
                center.y() + (random.randint(-42, 42) * scale),
            )
        ]
        while len(result) < 6:
            candidate = QPointF(
                center.x() + random.randint(-112, 112) * scale,
                center.y() + random.randint(-55, 55) * scale,
            )
            if math.hypot(
                candidate.x() - result[-1].x(),
                candidate.y() - result[-1].y(),
            ) < 40 * scale:
                continue
            result.append(candidate)
        return result

    def _build_smooth_curve(self) -> None:
        curve = [QPointF(point) for point in self.waypoints]
        for _pass in range(2):
            smoothed = [QPointF(curve[0])]
            for start, end in zip(curve, curve[1:]):
                smoothed.append(
                    QPointF(
                        start.x() * 0.75 + end.x() * 0.25,
                        start.y() * 0.75 + end.y() * 0.25,
                    )
                )
                smoothed.append(
                    QPointF(
                        start.x() * 0.25 + end.x() * 0.75,
                        start.y() * 0.25 + end.y() * 0.75,
                    )
                )
            smoothed.append(QPointF(curve[-1]))
            curve = smoothed
        self._curve_points = curve
        self._curve_offsets = [0.0]
        for start, end in zip(curve, curve[1:]):
            length = math.hypot(end.x() - start.x(), end.y() - start.y())
            self._curve_offsets.append(self._curve_offsets[-1] + length)
        self.pathLength = self._curve_offsets[-1]
        effective_speed = (
            min(self.targetSpeed, 45.0)
            if self.reducedMotion
            else self.targetSpeed
        )
        self.trackingDuration = (
            self._requested_tracking_duration
            if self._requested_tracking_duration is not None
            else max(4.5, min(8.0, self.pathLength / effective_speed))
        )

    def generateChallenge(self) -> None:
        self._timer.stop()
        self.waypoints = (
            [QPointF(point) for point in self._fixed_waypoints]
            if self._fixed_waypoints is not None
            else self._random_waypoints()
        )
        self._build_smooth_curve()
        self.targetId = self._fixed_target_id or secrets.token_urlsafe(8)
        self.pathId = self._fixed_path_id or secrets.token_urlsafe(8)
        self.targetPosition = QPointF(self.waypoints[0])
        self.pointerPosition = QPointF(self.targetPosition)
        self.targetTrail.clear()
        self.trace.clear()
        self.inputMethod = "pointer"
        self.missCount = 0
        self.followRatio = 0.0
        self.maxDeviation = 0.0
        self.averageDeviation = 0.0
        self.longestMissDuration = 0.0
        self._active = False
        self._inside_target = False
        self._started_at = None
        self._last_tick_at = None
        self._last_elapsed = 0.0
        self._follow_time = 0.0
        self._current_miss_duration = 0.0
        self._deviation_sum = 0.0
        self._sample_count = 0
        self.challengeChanged.emit(self.verificationText)
        self.progressChanged.emit(0.0, False)
        self.update()

    def refreshImage(self) -> None:
        self.generateChallenge()

    def targetPositionAt(self, progress: float) -> QPointF:
        progress = max(0.0, min(1.0, float(progress)))
        target_distance = progress * self.pathLength
        segment_index = 0
        for index in range(len(self._curve_offsets) - 1):
            if target_distance <= self._curve_offsets[index + 1]:
                segment_index = index
                break
        start_offset = self._curve_offsets[segment_index]
        segment_length = self._curve_offsets[segment_index + 1] - start_offset
        local_progress = (
            0.0
            if segment_length <= 1e-9
            else (target_distance - start_offset) / segment_length
        )
        start = self._curve_points[segment_index]
        end = self._curve_points[segment_index + 1]
        return QPointF(
            start.x() + (end.x() - start.x()) * local_progress,
            start.y() + (end.y() - start.y()) * local_progress,
        )

    def _distance_to_target(self, point: QPointF) -> float:
        return math.hypot(
            point.x() - self.targetPosition.x(),
            point.y() - self.targetPosition.y(),
        )

    def startTracking(
        self,
        point: QPointF | None = None,
        *,
        input_method: str = "pointer",
    ) -> bool:
        if not self.isEnabled() or self._active:
            return False
        point = QPointF(self.targetPosition if point is None else point)
        if self._distance_to_target(point) > self.trackingRadius:
            self.trackingRejected.emit("请从移动目标上开始追踪")
            return False
        now = time.monotonic()
        self.inputMethod = input_method
        self.pointerPosition = point
        self.trace = [(QPointF(point), now)]
        self.targetTrail = [QPointF(self.targetPosition)]
        self.missCount = 0
        self.followRatio = 0.0
        self.maxDeviation = self._distance_to_target(point)
        self.averageDeviation = 0.0
        self.longestMissDuration = 0.0
        self._active = True
        self._inside_target = True
        self._started_at = now
        self._last_tick_at = now
        self._last_elapsed = 0.0
        self._follow_time = 0.0
        self._current_miss_duration = 0.0
        self._deviation_sum = 0.0
        self._sample_count = 0
        self._timer.start()
        self.progressChanged.emit(0.0, True)
        self.update()
        return True

    def updatePointer(self, point: QPointF, *, input_method: str | None = None) -> None:
        self.pointerPosition = QPointF(
            max(0.0, min(self.width() - 1.0, point.x())),
            max(0.0, min(self.height() - 1.0, point.y())),
        )
        if input_method:
            self.inputMethod = input_method
        self.update()

    def _append_sample(self, now: float) -> None:
        if len(self.trace) >= 720:
            self.trace.pop(1)
        self.trace.append((QPointF(self.pointerPosition), now))

    def _tick(self) -> None:
        if not self._active or self._started_at is None:
            return
        now = time.monotonic()
        previous_tick = self._last_tick_at or now
        delta = max(0.0, min(0.1, now - previous_tick))
        elapsed = max(0.0, now - self._started_at)
        progress = min(1.0, elapsed / self.trackingDuration)
        self.targetPosition = self.targetPositionAt(progress)
        self.targetTrail.append(QPointF(self.targetPosition))
        if len(self.targetTrail) > 26:
            self.targetTrail.pop(0)

        deviation = self._distance_to_target(self.pointerPosition)
        inside = deviation <= self.trackingRadius
        if inside:
            self._follow_time += delta
            self._current_miss_duration = 0.0
        else:
            if self._inside_target:
                self.missCount += 1
            self._current_miss_duration += delta
            self.longestMissDuration = max(
                self.longestMissDuration,
                self._current_miss_duration,
            )
        self._inside_target = inside
        self.maxDeviation = max(self.maxDeviation, deviation)
        self._deviation_sum += deviation
        self._sample_count += 1
        self.averageDeviation = self._deviation_sum / self._sample_count
        self._last_tick_at = now
        self._last_elapsed = elapsed
        self.followRatio = min(1.0, self._follow_time / self.trackingDuration)
        self._append_sample(now)
        self.progressChanged.emit(progress, inside)

        if deviation > self.hardMissRadius:
            self._reject("距离移动目标过远，请重新跟随")
            return
        if self._current_miss_duration > self.maxMissDuration:
            self._reject("连续偏离目标时间过长，请重新跟随")
            return
        if progress >= 1.0:
            self._finish()
            return
        self.update()

    def _finish(self) -> None:
        self._timer.stop()
        self._active = False
        accepted = (
            self.followRatio >= self.minFollowRatio
            and self.longestMissDuration <= self.maxMissDuration
        )
        self.progressChanged.emit(1.0, accepted)
        if accepted:
            self.verificationComplete.emit(True, self.answer())
        else:
            self.trackingRejected.emit("有效跟随时间不足，请重新跟随目标")
        self.update()

    def _reject(self, reason: str) -> None:
        self._timer.stop()
        self._active = False
        self.progressChanged.emit(0.0, False)
        self.trackingRejected.emit(reason)
        self.update()

    def cancelTracking(self) -> None:
        if self._active:
            self._reject("追踪提前结束，请保持按住直到完成")

    def _payload_trace(self) -> list[dict[str, float | int]]:
        if not self.trace:
            return []
        count = min(self.maxPayloadSamples, len(self.trace))
        if count == 1:
            indexes = [0]
        else:
            indexes = [
                round(index * (len(self.trace) - 1) / (count - 1))
                for index in range(count)
            ]
        first_time = self.trace[0][1]
        return [
            {
                "x": round(self.trace[index][0].x(), 2),
                "y": round(self.trace[index][0].y(), 2),
                "t": max(0, round((self.trace[index][1] - first_time) * 1000)),
            }
            for index in indexes
        ]

    def answer(self) -> dict[str, object]:
        return {
            "targetId": self.targetId,
            "pathId": self.pathId,
            "trace": self._payload_trace(),
        }

    def behavior(self) -> dict[str, object]:
        return {
            "inputMethod": self.inputMethod,
            "duration": round(self._last_elapsed, 4),
            "sampleCount": len(self.trace),
            "followRatio": round(self.followRatio, 4),
            "missCount": self.missCount,
            "longestMissDuration": round(self.longestMissDuration, 4),
            "averageDeviation": round(self.averageDeviation, 2),
            "maxDeviation": round(self.maxDeviation, 2),
            "trackingRadius": self.trackingRadius,
            "targetSpeed": self.targetSpeed,
            "effectiveTargetSpeed": round(
                self.pathLength / self.trackingDuration,
                2,
            ),
            "pathLength": round(self.pathLength, 2),
            "pathInterpolation": "chaikin-2-arc-length-v1",
            "reducedMotion": self.reducedMotion,
        }

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f3f6f9"))

        if len(self.targetTrail) > 1:
            for index, (start, end) in enumerate(
                zip(self.targetTrail, self.targetTrail[1:])
            ):
                opacity = round(20 + 70 * (index + 1) / len(self.targetTrail))
                painter.setPen(
                    QPen(
                        QColor(25, 143, 242, opacity),
                        2.2,
                        Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap,
                    )
                )
                painter.drawLine(start, end)

        painter.setPen(QPen(QColor(25, 143, 242, 90), 2, Qt.PenStyle.DashLine))
        painter.setBrush(QColor(25, 143, 242, 18))
        painter.drawEllipse(
            self.targetPosition,
            self.trackingRadius,
            self.trackingRadius,
        )
        painter.setPen(QPen(QColor("#0f725c"), 2))
        painter.setBrush(QColor("#16856b"))
        painter.drawEllipse(self.targetPosition, 11, 11)
        painter.setPen(QPen(QColor("#ffffff"), 1.6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(self.targetPosition, 4, 4)

        if self._active or self.hasFocus():
            deviation = self._distance_to_target(self.pointerPosition)
            cursor_color = QColor("#16856b") if deviation <= self.trackingRadius else QColor("#d54858")
            painter.setPen(QPen(cursor_color, 1.8))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(self.pointerPosition, 7, 7)
            painter.drawLine(
                self.pointerPosition + QPointF(-11, 0),
                self.pointerPosition + QPointF(-5, 0),
            )
            painter.drawLine(
                self.pointerPosition + QPointF(5, 0),
                self.pointerPosition + QPointF(11, 0),
            )
            painter.drawLine(
                self.pointerPosition + QPointF(0, -11),
                self.pointerPosition + QPointF(0, -5),
            )
            painter.drawLine(
                self.pointerPosition + QPointF(0, 5),
                self.pointerPosition + QPointF(0, 11),
            )

        if not self.isEnabled():
            painter.fillRect(self.rect(), QColor(9, 19, 31, 112))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#ffffff"))
            for offset in (-7, 0, 7):
                painter.drawEllipse(
                    QPointF(self.width() / 2 + offset, self.height() / 2),
                    1.8,
                    1.8,
                )
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.setFocus()
            self.startTracking(event.position(), input_method="pointer")
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._active:
            self.updatePointer(event.position(), input_method="pointer")
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._active:
            self.cancelTracking()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if not self._active:
                self.pointerPosition = QPointF(self.targetPosition)
                self.startTracking(self.pointerPosition, input_method="keyboard")
            event.accept()
            return
        moves = {
            Qt.Key.Key_Left: QPointF(-7, 0),
            Qt.Key.Key_Right: QPointF(7, 0),
            Qt.Key.Key_Up: QPointF(0, -7),
            Qt.Key.Key_Down: QPointF(0, 7),
        }
        if self._active and key in moves:
            self.updatePointer(
                self.pointerPosition + moves[key],
                input_method="keyboard",
            )
            event.accept()
            return
        if key == Qt.Key.Key_Escape and self._active:
            self.cancelTracking()
            event.accept()
            return
        super().keyPressEvent(event)
