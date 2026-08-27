"""Interactive shape-to-silhouette matching challenge."""

from __future__ import annotations

import math
import secrets
import time
from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


SHAPE_TYPES = ("circle", "triangle", "diamond", "hexagon", "star", "heart")
SHAPE_COLORS = (
    QColor("#2878c8"),
    QColor("#c4485d"),
    QColor("#148566"),
    QColor("#9a56b5"),
)


def shape_path(kind: str, center: QPointF, size: float) -> QPainterPath:
    """Build one crisp vector shape around ``center``."""

    x = center.x()
    y = center.y()
    radius = size / 2
    path = QPainterPath()
    if kind == "circle":
        path.addEllipse(QRectF(x - radius, y - radius, size, size))
    elif kind == "triangle":
        path.moveTo(x, y - radius)
        path.lineTo(x + radius * 0.92, y + radius * 0.82)
        path.lineTo(x - radius * 0.92, y + radius * 0.82)
        path.closeSubpath()
    elif kind == "diamond":
        path.moveTo(x, y - radius)
        path.lineTo(x + radius, y)
        path.lineTo(x, y + radius)
        path.lineTo(x - radius, y)
        path.closeSubpath()
    elif kind == "hexagon":
        for index in range(6):
            angle = math.pi / 3 * index - math.pi / 2
            point = QPointF(x + radius * math.cos(angle), y + radius * math.sin(angle))
            path.moveTo(point) if index == 0 else path.lineTo(point)
        path.closeSubpath()
    elif kind == "star":
        for index in range(10):
            point_radius = radius if index % 2 == 0 else radius * 0.43
            angle = math.pi / 5 * index - math.pi / 2
            point = QPointF(
                x + point_radius * math.cos(angle),
                y + point_radius * math.sin(angle),
            )
            path.moveTo(point) if index == 0 else path.lineTo(point)
        path.closeSubpath()
    elif kind == "heart":
        path.moveTo(x, y + radius * 0.88)
        path.cubicTo(
            x - radius * 1.05,
            y + radius * 0.18,
            x - radius * 0.94,
            y - radius * 0.72,
            x - radius * 0.38,
            y - radius * 0.72,
        )
        path.cubicTo(
            x - radius * 0.08,
            y - radius * 0.72,
            x,
            y - radius * 0.45,
            x,
            y - radius * 0.31,
        )
        path.cubicTo(
            x,
            y - radius * 0.45,
            x + radius * 0.08,
            y - radius * 0.72,
            x + radius * 0.38,
            y - radius * 0.72,
        )
        path.cubicTo(
            x + radius * 0.94,
            y - radius * 0.72,
            x + radius * 1.05,
            y + radius * 0.18,
            x,
            y + radius * 0.88,
        )
        path.closeSubpath()
    else:
        raise ValueError(f"不支持的图形类型：{kind}")
    return path


@dataclass(slots=True)
class ShapeItem:
    shape_id: str
    kind: str
    color: QColor
    source_center: QPointF
    current_center: QPointF
    placed_slot: int | None = None


class VerificationImage(QWidget):
    verificationComplete = Signal(bool, list)
    challengeChanged = Signal(str)
    placementRejected = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        shape_count: int = 3,
        shape_types: Sequence[str] | None = None,
        shape_ids: Sequence[str] | None = None,
        target_ids: Sequence[str] | None = None,
        target_order: Sequence[int] | None = None,
        animation_duration_ms: int = 180,
    ) -> None:
        super().__init__(parent)
        self._width = 300
        self._height = 169
        self.shapeCount = max(2, min(4, int(shape_count)))
        self.shapeSize = 38.0 if self.shapeCount == 4 else 42.0
        self.animationDuration = max(0, min(600, int(animation_duration_ms)))
        self._fixed_shape_types = self._validate_shape_types(shape_types)
        self.shapeIds = self._validate_ids(shape_ids, "shape", "shape_ids")
        self.targetIds = self._validate_ids(target_ids, "target", "target_ids")
        self._fixed_target_order = self._validate_target_order(target_order)
        self.shapes: list[ShapeItem] = []
        self.targetOrder: list[int] = []
        self.targetCenters: list[QPointF] = []
        self.focusedShape = 0
        self.keyboardTarget = 0
        self.draggedShape: int | None = None
        self.hoveredTarget: int | None = None
        self._keyboard_grabbed = False
        self._animation_shape: int | None = None
        self._animation_from = QPointF()
        self._animation_to = QPointF()
        self._animation_slot: int | None = None
        self._wrong_target: int | None = None
        self._move_progress = 0.0
        self._started_at: float | None = None
        self.moveCount = 0
        self.missCount = 0
        self.inputMethod = "pointer"
        self.verificationText = "将图形拖入对应轮廓"

        self.setFixedSize(self._width, self._height)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAccessibleName("图形拖拽归位验证码")
        self.setAccessibleDescription(
            "将上方彩色图形拖入下方相同轮廓；键盘用户按空格选择图形，再选择目标"
        )
        self.setToolTip("将图形拖入对应轮廓")

        self._move_animation = QPropertyAnimation(self, b"moveProgress", self)
        self._move_animation.setStartValue(0.0)
        self._move_animation.setEndValue(1.0)
        self._move_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._move_animation.finished.connect(self._finish_move_animation)
        self.generateChallenge()

    def _validate_shape_types(
        self, values: Sequence[str] | None
    ) -> tuple[str, ...] | None:
        if values is None:
            return None
        normalised = tuple(str(value) for value in values)
        if len(normalised) != self.shapeCount or len(set(normalised)) != self.shapeCount:
            raise ValueError("shape_types 必须为每个图形提供唯一类型")
        if any(value not in SHAPE_TYPES for value in normalised):
            raise ValueError("shape_types 包含不支持的图形类型")
        return normalised

    def _validate_ids(
        self,
        values: Sequence[str] | None,
        prefix: str,
        field_name: str,
    ) -> list[str]:
        if values is None:
            return [f"{prefix}-{index}" for index in range(self.shapeCount)]
        normalised = [str(value) for value in values]
        if len(normalised) != self.shapeCount or len(set(normalised)) != self.shapeCount:
            raise ValueError(f"{field_name} 必须为每个项目提供唯一标识")
        return normalised

    def _validate_target_order(
        self, order: Sequence[int] | None
    ) -> tuple[int, ...] | None:
        if order is None:
            return None
        normalised = tuple(int(value) for value in order)
        if len(normalised) != self.shapeCount or set(normalised) != set(
            range(self.shapeCount)
        ):
            raise ValueError("target_order 必须是所有图形索引的完整排列")
        return normalised

    def _row_centers(self, y: float) -> list[QPointF]:
        if self.shapeCount == 2:
            xs = (91.0, 209.0)
        elif self.shapeCount == 3:
            xs = (55.0, 150.0, 245.0)
        else:
            xs = (39.0, 113.0, 187.0, 261.0)
        return [QPointF(x, y) for x in xs]

    def _new_target_order(self) -> list[int]:
        if self._fixed_target_order is not None:
            return list(self._fixed_target_order)
        order = list(range(self.shapeCount))
        while order == list(range(self.shapeCount)):
            secrets.SystemRandom().shuffle(order)
        return order

    def generateChallenge(self) -> None:
        self._move_animation.stop()
        kinds = (
            list(self._fixed_shape_types)
            if self._fixed_shape_types is not None
            else secrets.SystemRandom().sample(list(SHAPE_TYPES), self.shapeCount)
        )
        source_centers = self._row_centers(43.0)
        self.targetCenters = self._row_centers(127.0)
        self.targetOrder = self._new_target_order()
        self.shapes = [
            ShapeItem(
                shape_id=self.shapeIds[index],
                kind=kinds[index],
                color=QColor(SHAPE_COLORS[index]),
                source_center=QPointF(source_centers[index]),
                current_center=QPointF(source_centers[index]),
            )
            for index in range(self.shapeCount)
        ]
        self.focusedShape = 0
        self.keyboardTarget = 0
        self.draggedShape = None
        self.hoveredTarget = None
        self._keyboard_grabbed = False
        self._animation_shape = None
        self._animation_slot = None
        self._wrong_target = None
        self._move_progress = 0.0
        self._started_at = None
        self.moveCount = 0
        self.missCount = 0
        self.inputMethod = "pointer"
        self.challengeChanged.emit(self.verificationText)
        self.update()

    def refreshImage(self) -> None:
        self.generateChallenge()

    def _is_animating(self) -> bool:
        return self._animation_shape is not None

    def _begin_interaction(self, input_method: str) -> None:
        if self._started_at is None:
            self._started_at = time.monotonic()
        self.inputMethod = input_method

    def getMoveProgress(self) -> float:
        return self._move_progress

    def setMoveProgress(self, progress: float) -> None:
        self._move_progress = max(0.0, min(1.0, float(progress)))
        if self._animation_shape is not None:
            x = self._animation_from.x() + (
                self._animation_to.x() - self._animation_from.x()
            ) * self._move_progress
            y = self._animation_from.y() + (
                self._animation_to.y() - self._animation_from.y()
            ) * self._move_progress
            self.shapes[self._animation_shape].current_center = QPointF(x, y)
        self.update()

    moveProgress = Property(float, getMoveProgress, setMoveProgress)

    def targetForShape(self, shape_index: int) -> int:
        return self.targetOrder.index(shape_index)

    def answer(self) -> list[dict[str, str]]:
        result = []
        for shape in self.shapes:
            if shape.placed_slot is None:
                continue
            result.append(
                {
                    "shapeId": shape.shape_id,
                    "targetId": self.targetIds[shape.placed_slot],
                }
            )
        return result

    def behavior(self) -> dict[str, object]:
        duration = 0.0 if self._started_at is None else time.monotonic() - self._started_at
        return {
            "inputMethod": self.inputMethod,
            "moveCount": self.moveCount,
            "missCount": self.missCount,
            "duration": round(duration, 4),
            "targetOrder": [
                {
                    "targetId": self.targetIds[slot],
                    "shapeId": self.shapeIds[shape_index],
                }
                for slot, shape_index in enumerate(self.targetOrder)
            ],
        }

    def attemptPlacement(
        self,
        shape_index: int,
        target_slot: int | None,
        *,
        input_method: str = "pointer",
        animated: bool = True,
    ) -> bool:
        if self._is_animating() or not (0 <= shape_index < self.shapeCount):
            return False
        shape = self.shapes[shape_index]
        if shape.placed_slot is not None:
            return False
        self._begin_interaction(input_method)
        accepted = (
            target_slot is not None
            and 0 <= target_slot < self.shapeCount
            and self.targetOrder[target_slot] == shape_index
        )
        destination = (
            QPointF(self.targetCenters[target_slot])
            if accepted and target_slot is not None
            else QPointF(shape.source_center)
        )
        self._animation_shape = shape_index
        self._animation_from = QPointF(shape.current_center)
        self._animation_to = destination
        self._animation_slot = target_slot if accepted else None
        self._wrong_target = None if accepted else target_slot
        if animated and self.animationDuration > 0:
            self._move_animation.stop()
            self._move_animation.setDuration(
                self.animationDuration if accepted else min(260, self.animationDuration + 50)
            )
            self._move_animation.setStartValue(0.0)
            self._move_animation.setEndValue(1.0)
            self._move_animation.start()
        else:
            self.setMoveProgress(1.0)
            self._finish_move_animation()
        return accepted

    def _finish_move_animation(self) -> None:
        shape_index = self._animation_shape
        accepted_slot = self._animation_slot
        wrong_target = self._wrong_target
        self._animation_shape = None
        self._animation_slot = None
        self._wrong_target = None
        self._move_progress = 0.0
        if shape_index is None:
            return
        shape = self.shapes[shape_index]
        if accepted_slot is not None:
            shape.current_center = QPointF(self.targetCenters[accepted_slot])
            shape.placed_slot = accepted_slot
            self.moveCount += 1
            self._focus_next_unplaced()
            self._complete_if_solved()
        else:
            shape.current_center = QPointF(shape.source_center)
            self.missCount += 1
            self.placementRejected.emit(
                "目标轮廓不匹配" if wrong_target is not None else "请拖入一个目标轮廓"
            )
        self.update()

    def _focus_next_unplaced(self) -> None:
        for index, shape in enumerate(self.shapes):
            if shape.placed_slot is None:
                self.focusedShape = index
                self.keyboardTarget = 0
                return

    def _complete_if_solved(self) -> None:
        if all(shape.placed_slot is not None for shape in self.shapes):
            self.verificationComplete.emit(True, self.answer())

    def verify(self) -> None:
        solved = all(shape.placed_slot is not None for shape in self.shapes)
        self.verificationComplete.emit(solved, self.answer())

    def _shape_at(self, point: QPointF) -> int | None:
        for index in reversed(range(self.shapeCount)):
            shape = self.shapes[index]
            if shape.placed_slot is not None:
                continue
            hit_path = shape_path(shape.kind, shape.current_center, self.shapeSize + 12)
            if hit_path.contains(point):
                return index
        return None

    def _target_at(self, point: QPointF) -> int | None:
        for slot, center in enumerate(self.targetCenters):
            if math.hypot(point.x() - center.x(), point.y() - center.y()) <= 31:
                return slot
        return None

    def _draw_target(self, painter: QPainter, slot: int) -> None:
        shape_index = self.targetOrder[slot]
        shape = self.shapes[shape_index]
        occupied = shape.placed_slot == slot
        active = slot == self.hoveredTarget or (
            self._keyboard_grabbed and slot == self.keyboardTarget and self.hasFocus()
        )
        wrong = slot == self._wrong_target
        color = (
            QColor("#d54858")
            if wrong
            else QColor("#16856b")
            if occupied
            else QColor("#198ff2")
            if active
            else QColor("#7b8797")
        )
        target_path = shape_path(shape.kind, self.targetCenters[slot], self.shapeSize + 8)
        painter.setPen(QPen(color, 2, Qt.PenStyle.DashLine))
        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 22))
        painter.drawPath(target_path)

    def _draw_shape(
        self,
        painter: QPainter,
        index: int,
        *,
        elevated: bool = False,
    ) -> None:
        shape = self.shapes[index]
        path = shape_path(shape.kind, shape.current_center, self.shapeSize)
        if elevated:
            shadow = shape_path(
                shape.kind,
                shape.current_center + QPointF(3, 4),
                self.shapeSize,
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(9, 19, 31, 58))
            painter.drawPath(shadow)
        painter.setPen(QPen(QColor(255, 255, 255, 210), 1.2))
        painter.setBrush(shape.color)
        painter.drawPath(path)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f3f6f9"))
        painter.setPen(QPen(QColor("#d8e0e8"), 1))
        painter.drawLine(QPointF(14, 84.5), QPointF(self._width - 14, 84.5))

        for slot in range(self.shapeCount):
            self._draw_target(painter, slot)

        for index, shape in enumerate(self.shapes):
            if index == self.draggedShape or index == self._animation_shape:
                continue
            self._draw_shape(painter, index)
            if (
                self.hasFocus()
                and not self._keyboard_grabbed
                and index == self.focusedShape
                and shape.placed_slot is None
            ):
                focus = shape_path(
                    shape.kind,
                    shape.current_center,
                    self.shapeSize + 10,
                )
                painter.setPen(QPen(QColor("#198ff2"), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(focus)

        active_shape = (
            self.draggedShape
            if self.draggedShape is not None
            else self._animation_shape
        )
        if active_shape is not None:
            self._draw_shape(painter, active_shape, elevated=True)

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
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.isEnabled()
            and not self._is_animating()
        ):
            shape_index = self._shape_at(event.position())
            if shape_index is not None:
                self.setFocus()
                self.draggedShape = shape_index
                self.focusedShape = shape_index
                self._keyboard_grabbed = False
                self._begin_interaction("pointer")
                self.update()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.draggedShape is not None:
            point = event.position()
            self.shapes[self.draggedShape].current_center = QPointF(
                max(20.0, min(self._width - 20.0, point.x())),
                max(20.0, min(self._height - 20.0, point.y())),
            )
            self.hoveredTarget = self._target_at(point)
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.draggedShape is not None:
            shape_index = self.draggedShape
            target_slot = self._target_at(event.position())
            self.draggedShape = None
            self.hoveredTarget = None
            self.attemptPlacement(
                shape_index,
                target_slot,
                input_method="pointer",
            )
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if self._is_animating():
            event.accept()
            return
        available = [
            index for index, shape in enumerate(self.shapes) if shape.placed_slot is None
        ]
        if not available:
            super().keyPressEvent(event)
            return
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            direction = -1 if event.key() == Qt.Key.Key_Left else 1
            if self._keyboard_grabbed:
                self.keyboardTarget = max(
                    0,
                    min(self.shapeCount - 1, self.keyboardTarget + direction),
                )
            else:
                position = available.index(self.focusedShape)
                self.focusedShape = available[(position + direction) % len(available)]
            self.update()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._begin_interaction("keyboard")
            if self._keyboard_grabbed:
                shape_index = self.focusedShape
                self._keyboard_grabbed = False
                self.attemptPlacement(
                    shape_index,
                    self.keyboardTarget,
                    input_method="keyboard",
                )
            else:
                self._keyboard_grabbed = True
                self.keyboardTarget = 0
            self.update()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape and self._keyboard_grabbed:
            self._keyboard_grabbed = False
            self.update()
            event.accept()
            return
        super().keyPressEvent(event)
