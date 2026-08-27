"""Continuous path-tracing verification challenge."""

from __future__ import annotations

import math
import secrets
import time
from collections.abc import Sequence

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget


def distance_to_segment(point: QPointF, start: QPointF, end: QPointF) -> float:
    """Return the shortest distance from ``point`` to a line segment."""

    dx = end.x() - start.x()
    dy = end.y() - start.y()
    length_squared = dx * dx + dy * dy
    if length_squared <= 1e-9:
        return math.hypot(point.x() - start.x(), point.y() - start.y())
    projection = (
        (point.x() - start.x()) * dx + (point.y() - start.y()) * dy
    ) / length_squared
    projection = max(0.0, min(1.0, projection))
    nearest = QPointF(start.x() + projection * dx, start.y() + projection * dy)
    return math.hypot(point.x() - nearest.x(), point.y() - nearest.y())


class VerificationImage(QWidget):
    """A trace surface that requires visiting every node in order."""

    verificationComplete = Signal(bool, dict)
    challengeChanged = Signal(str)
    pathRejected = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        node_count: int = 5,
        nodes: Sequence[tuple[float, float] | QPointF] | None = None,
        node_ids: Sequence[str] | None = None,
        hit_radius: float = 18.0,
        path_tolerance: float = 14.0,
        backtrack_tolerance: float = 12.0,
        max_payload_samples: int = 128,
    ) -> None:
        super().__init__(parent)
        self._width = 300
        self._height = 169
        requested_count = int(node_count)
        if not 4 <= requested_count <= 7:
            raise ValueError("node_count 必须在 4 到 7 之间")
        self.nodeCount = requested_count
        hit_radius_value = float(hit_radius)
        path_tolerance_value = float(path_tolerance)
        backtrack_tolerance_value = float(backtrack_tolerance)
        if not all(
            math.isfinite(value)
            for value in (
                hit_radius_value,
                path_tolerance_value,
                backtrack_tolerance_value,
            )
        ):
            raise ValueError("路径容差参数必须是有限数值")
        self.hitRadius = max(12.0, min(28.0, hit_radius_value))
        self.pathTolerance = max(8.0, min(22.0, path_tolerance_value))
        self.backtrackTolerance = max(
            0.0,
            min(24.0, backtrack_tolerance_value),
        )
        self.maxPayloadSamples = max(16, min(256, int(max_payload_samples)))
        self._fixed_nodes = self._validate_nodes(nodes)
        self.nodeIds = self._validate_ids(node_ids)
        self.nodes: list[QPointF] = []
        self.trace: list[tuple[QPointF, float]] = []
        self.reachedCount = 0
        self.missCount = 0
        self.inputMethod = "pointer"
        self._tracing = False
        self._started_at: float | None = None
        self._last_pointer: QPointF | None = None
        self._segment_lengths: list[float] = []
        self._route_offsets: list[float] = []
        self._max_route_progress = 0.0
        self._max_deviation = 0.0
        self.verificationText = "从起点连续描摹至终点"

        self.setFixedSize(self._width, self._height)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAccessibleName("路径描摹验证码")
        self.setAccessibleDescription(
            "从起点按住并依次经过所有节点；键盘用户按空格开始，使用方向键推进"
        )
        self.setToolTip("从起点按住，连续经过所有节点后松开")
        self.generateChallenge()

    def _validate_nodes(
        self,
        values: Sequence[tuple[float, float] | QPointF] | None,
    ) -> tuple[QPointF, ...] | None:
        if values is None:
            return None
        if len(values) != self.nodeCount:
            raise ValueError("nodes 数量必须与 node_count 一致")
        result: list[QPointF] = []
        for value in values:
            if isinstance(value, QPointF):
                point = QPointF(value)
            else:
                try:
                    x, y = value
                    point = QPointF(float(x), float(y))
                except (TypeError, ValueError) as error:
                    raise ValueError("nodes 必须由二维坐标组成") from error
            if not math.isfinite(point.x()) or not math.isfinite(point.y()):
                raise ValueError("nodes 坐标必须是有限数值")
            if not 20 <= point.x() <= self._width - 20:
                raise ValueError("nodes 横坐标超出可用区域")
            if not 20 <= point.y() <= self._height - 20:
                raise ValueError("nodes 纵坐标超出可用区域")
            result.append(point)
        minimum_spacing = max(28.0, self.hitRadius * 2 + 4)
        if any(
            math.hypot(first.x() - second.x(), first.y() - second.y())
            < minimum_spacing
            for first, second in zip(result, result[1:])
        ):
            raise ValueError("相邻 nodes 距离过近")
        return tuple(result)

    def _validate_ids(self, values: Sequence[str] | None) -> list[str]:
        if values is None:
            return [f"node-{index}" for index in range(self.nodeCount)]
        result = [str(value) for value in values]
        if len(result) != self.nodeCount or len(set(result)) != self.nodeCount:
            raise ValueError("node_ids 必须为每个节点提供唯一标识")
        return result

    def _random_nodes(self) -> list[QPointF]:
        random = secrets.SystemRandom()
        left = 28.0
        right = self._width - 28.0
        step = (right - left) / (self.nodeCount - 1)
        y_values: list[float] = []
        for index in range(self.nodeCount):
            choices = list(range(31, self._height - 30, 8))
            if y_values:
                separated = [value for value in choices if abs(value - y_values[-1]) >= 24]
                choices = separated or choices
            y_values.append(float(random.choice(choices)))
        return [
            QPointF(left + step * index, y_values[index])
            for index in range(self.nodeCount)
        ]

    def generateChallenge(self) -> None:
        self.nodes = (
            [QPointF(point) for point in self._fixed_nodes]
            if self._fixed_nodes is not None
            else self._random_nodes()
        )
        self._segment_lengths = [
            math.hypot(end.x() - start.x(), end.y() - start.y())
            for start, end in zip(self.nodes, self.nodes[1:])
        ]
        self._route_offsets = [0.0]
        for length in self._segment_lengths:
            self._route_offsets.append(self._route_offsets[-1] + length)
        self.trace.clear()
        self.reachedCount = 0
        self.missCount = 0
        self.inputMethod = "pointer"
        self._tracing = False
        self._started_at = None
        self._last_pointer = None
        self._max_route_progress = 0.0
        self._max_deviation = 0.0
        self.challengeChanged.emit(self.verificationText)
        self.update()

    def refreshImage(self) -> None:
        self.generateChallenge()

    def _elapsed(self) -> float:
        return 0.0 if self._started_at is None else time.monotonic() - self._started_at

    def _begin(self, input_method: str) -> None:
        if self._started_at is None:
            self._started_at = time.monotonic()
        self.inputMethod = input_method

    def _append_sample(self, point: QPointF, *, force: bool = False) -> None:
        now = time.monotonic()
        if self.trace and not force:
            previous, previous_time = self.trace[-1]
            distance = math.hypot(point.x() - previous.x(), point.y() - previous.y())
            if distance < 1.5 and now - previous_time < 0.012:
                return
        if len(self.trace) >= 512:
            self.trace.pop(1)
        self.trace.append((QPointF(point), now))

    def _route_projection(self, point: QPointF, segment_index: int) -> float:
        start = self.nodes[segment_index]
        end = self.nodes[segment_index + 1]
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length_squared = dx * dx + dy * dy
        if length_squared <= 1e-9:
            return 0.0
        projection = (
            (point.x() - start.x()) * dx + (point.y() - start.y()) * dy
        ) / length_squared
        return max(0.0, min(1.0, projection))

    def _accept_route_point(self, point: QPointF) -> bool:
        if self.reachedCount >= self.nodeCount:
            deviation = math.hypot(
                point.x() - self.nodes[-1].x(),
                point.y() - self.nodes[-1].y(),
            )
            self._max_deviation = max(self._max_deviation, deviation)
            return deviation <= self.hitRadius

        segment_index = self.reachedCount - 1
        start = self.nodes[segment_index]
        end = self.nodes[segment_index + 1]
        deviation = distance_to_segment(point, start, end)
        self._max_deviation = max(self._max_deviation, deviation)
        near_anchor = min(
            math.hypot(point.x() - start.x(), point.y() - start.y()),
            math.hypot(point.x() - end.x(), point.y() - end.y()),
        ) <= self.hitRadius
        if deviation > self.pathTolerance and not near_anchor:
            return False

        projection = self._route_projection(point, segment_index)
        progress = (
            self._route_offsets[segment_index]
            + projection * self._segment_lengths[segment_index]
        )
        if progress + self.backtrackTolerance < self._max_route_progress:
            return False
        self._max_route_progress = max(self._max_route_progress, progress)

        if math.hypot(point.x() - end.x(), point.y() - end.y()) <= self.hitRadius:
            self.reachedCount += 1
            self._max_route_progress = max(
                self._max_route_progress,
                self._route_offsets[self.reachedCount - 1],
            )
        return True

    def _validate_pointer_segment(self, start: QPointF, end: QPointF) -> bool:
        distance = math.hypot(end.x() - start.x(), end.y() - start.y())
        sample_count = max(1, math.ceil(distance / 4.0))
        for index in range(1, sample_count + 1):
            fraction = index / sample_count
            point = QPointF(
                start.x() + (end.x() - start.x()) * fraction,
                start.y() + (end.y() - start.y()) * fraction,
            )
            if not self._accept_route_point(point):
                return False
        return True

    def _reset_active_trace(self) -> None:
        self.trace.clear()
        self.reachedCount = 0
        self._tracing = False
        self._last_pointer = None
        self._max_route_progress = 0.0
        self._max_deviation = 0.0
        self.update()

    def _reject(self, reason: str) -> None:
        self.missCount += 1
        self._reset_active_trace()
        self.pathRejected.emit(reason)

    def _complete(self) -> None:
        self._tracing = False
        self._last_pointer = None
        self.verificationComplete.emit(True, self.answer())
        self.update()

    def _payload_trace(self) -> list[dict[str, float | int]]:
        if not self.trace:
            return []
        sample_count = min(self.maxPayloadSamples, len(self.trace))
        if sample_count == 1:
            indexes = [0]
        else:
            indexes = [
                round(index * (len(self.trace) - 1) / (sample_count - 1))
                for index in range(sample_count)
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
            "nodeIds": list(self.nodeIds),
            "trace": self._payload_trace(),
        }

    def behavior(self) -> dict[str, object]:
        path_length = 0.0
        for (start, _), (end, _) in zip(self.trace, self.trace[1:]):
            path_length += math.hypot(end.x() - start.x(), end.y() - start.y())
        return {
            "inputMethod": self.inputMethod,
            "duration": round(self._elapsed(), 4),
            "sampleCount": len(self.trace),
            "pathLength": round(path_length, 2),
            "nodeHitCount": self.reachedCount,
            "missCount": self.missCount,
            "maxDeviation": round(self._max_deviation, 2),
            "pathTolerance": self.pathTolerance,
        }

    def verify(self) -> None:
        self.verificationComplete.emit(
            self.reachedCount == self.nodeCount,
            self.answer(),
        )

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f3f6f9"))

        route_pen = QPen(
            QColor("#a9b5c4"),
            2.0,
            Qt.PenStyle.DashLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        route_pen.setDashPattern([2.5, 3.5])
        painter.setPen(route_pen)
        for start, end in zip(self.nodes, self.nodes[1:]):
            painter.drawLine(start, end)

        if len(self.trace) > 1:
            painter.setPen(
                QPen(
                    QColor("#198ff2"),
                    5.0,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            for (start, _), (end, _) in zip(self.trace, self.trace[1:]):
                painter.drawLine(start, end)

        for index, point in enumerate(self.nodes):
            visited = index < self.reachedCount
            is_start = index == 0
            is_end = index == self.nodeCount - 1
            if visited:
                fill = QColor("#16856b")
                outline = QColor("#0f725c")
            elif is_start:
                fill = QColor("#198ff2")
                outline = QColor("#0876d1")
            else:
                fill = QColor("#ffffff")
                outline = QColor("#68778b")
            painter.setPen(QPen(outline, 2.2))
            painter.setBrush(fill)
            painter.drawEllipse(point, 8.5, 8.5)
            if is_start and not visited:
                painter.setPen(QPen(QColor(25, 143, 242, 82), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(point, 13.5, 13.5)
            if is_end:
                painter.setPen(QPen(QColor("#68778b"), 1.6))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(point, 13.0, 13.0)

        if self.hasFocus() and not self._tracing:
            focus_index = min(self.reachedCount, self.nodeCount - 1)
            painter.setPen(QPen(QColor("#198ff2"), 2, Qt.PenStyle.DotLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(self.nodes[focus_index], 17.0, 17.0)

        if not self.isEnabled():
            painter.fillRect(self.rect(), QColor(9, 19, 31, 112))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#ffffff"))
            for offset in (-7, 0, 7):
                painter.drawEllipse(
                    QPointF(self._width / 2 + offset, self._height / 2),
                    1.8,
                    1.8,
                )
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.setFocus()
            point = event.position()
            start = self.nodes[0]
            if math.hypot(point.x() - start.x(), point.y() - start.y()) > self.hitRadius:
                self._reject("请从起点开始描摹")
                event.accept()
                return
            self._begin("pointer")
            self._reset_active_trace()
            self._tracing = True
            self.reachedCount = 1
            self._max_route_progress = 0.0
            self._max_deviation = 0.0
            self._last_pointer = QPointF(point)
            self._append_sample(point, force=True)
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._tracing and self._last_pointer is not None:
            point = QPointF(event.position())
            if not self._validate_pointer_segment(self._last_pointer, point):
                self._reject("轨迹偏离了指定路径，请沿虚线重新描摹")
                event.accept()
                return
            self._append_sample(point)
            self._last_pointer = point
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._tracing:
            point = QPointF(event.position())
            if self._last_pointer is not None:
                if not self._validate_pointer_segment(self._last_pointer, point):
                    self._reject("轨迹偏离了指定路径，请沿虚线重新描摹")
                    event.accept()
                    return
            self._append_sample(point, force=True)
            if self.reachedCount == self.nodeCount:
                self._complete()
            else:
                self._reject("路径尚未完成，请保持按住并依次经过所有节点")
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        submit_keys = (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space)
        if key in submit_keys:
            self._begin("keyboard")
            if not self._tracing:
                self._reset_active_trace()
                self._tracing = True
                self.reachedCount = 1
                self._max_route_progress = 0.0
                self._max_deviation = 0.0
                self._append_sample(self.nodes[0], force=True)
            elif self.reachedCount == self.nodeCount:
                self._complete()
            self.update()
            event.accept()
            return
        if self._tracing and key in (
            Qt.Key.Key_Right,
            Qt.Key.Key_Down,
            Qt.Key.Key_Left,
            Qt.Key.Key_Up,
        ):
            forward = key in (Qt.Key.Key_Right, Qt.Key.Key_Down)
            if forward and self.reachedCount < self.nodeCount:
                self.reachedCount += 1
                self._append_sample(self.nodes[self.reachedCount - 1], force=True)
                self._max_route_progress = self._route_offsets[self.reachedCount - 1]
            elif not forward and self.reachedCount > 1:
                self.reachedCount -= 1
                self.trace = self.trace[: self.reachedCount]
                self._max_route_progress = self._route_offsets[self.reachedCount - 1]
            self.update()
            event.accept()
            return
        if key == Qt.Key.Key_Escape and self._tracing:
            self._reject("已取消本次描摹")
            event.accept()
            return
        super().keyPressEvent(event)
