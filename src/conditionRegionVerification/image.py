"""Condition-based region selection challenge."""

from __future__ import annotations

import math
import secrets
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


REGION_COLORS = {
    "blue": QColor("#2878c8"),
    "green": QColor("#16856b"),
    "orange": QColor("#c56c18"),
    "purple": QColor("#8b55ad"),
    "red": QColor("#c4485d"),
}
COLOR_NAMES = {
    "blue": "蓝色",
    "green": "绿色",
    "orange": "橙色",
    "purple": "紫色",
    "red": "红色",
}
REGION_SHAPES = ("circle", "square", "triangle", "diamond", "hexagon")
SHAPE_NAMES = {
    "circle": "圆形",
    "square": "方形",
    "triangle": "三角形",
    "diamond": "菱形",
    "hexagon": "六边形",
}


@dataclass(frozen=True, slots=True)
class RegionSpec:
    """One selectable region supplied locally or by a server challenge."""

    region_id: str
    color: str
    shape: str


def region_path(shape: str, bounds: QRectF) -> QPainterPath:
    """Build a crisp vector path inside ``bounds``."""

    inset = min(bounds.width(), bounds.height()) * 0.13
    rect = bounds.adjusted(inset, inset, -inset, -inset)
    center = rect.center()
    radius_x = rect.width() / 2
    radius_y = rect.height() / 2
    path = QPainterPath()
    if shape == "circle":
        diameter = min(rect.width(), rect.height())
        path.addEllipse(
            QRectF(
                center.x() - diameter / 2,
                center.y() - diameter / 2,
                diameter,
                diameter,
            )
        )
    elif shape == "square":
        side = min(rect.width(), rect.height())
        path.addRoundedRect(
            QRectF(center.x() - side / 2, center.y() - side / 2, side, side),
            3,
            3,
        )
    elif shape == "triangle":
        path.moveTo(center.x(), center.y() - radius_y)
        path.lineTo(center.x() + radius_x, center.y() + radius_y)
        path.lineTo(center.x() - radius_x, center.y() + radius_y)
        path.closeSubpath()
    elif shape == "diamond":
        path.moveTo(center.x(), center.y() - radius_y)
        path.lineTo(center.x() + radius_x, center.y())
        path.lineTo(center.x(), center.y() + radius_y)
        path.lineTo(center.x() - radius_x, center.y())
        path.closeSubpath()
    elif shape == "hexagon":
        for index in range(6):
            angle = math.pi / 3 * index - math.pi / 2
            point = QPointF(
                center.x() + radius_x * math.cos(angle),
                center.y() + radius_y * math.sin(angle),
            )
            path.moveTo(point) if index == 0 else path.lineTo(point)
        path.closeSubpath()
    else:
        raise ValueError(f"不支持的区域形状：{shape}")
    return path


class VerificationImage(QWidget):
    verificationComplete = Signal(bool, list)
    challengeChanged = Signal(str)
    selectionChanged = Signal(int)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        region_count: int = 9,
        regions: Sequence[RegionSpec | Mapping[str, str]] | None = None,
        condition_color: str | None = None,
        condition_shape: str | None = None,
    ) -> None:
        super().__init__(parent)
        requested_count = int(region_count)
        if not 6 <= requested_count <= 12:
            raise ValueError("region_count 必须在 6 到 12 之间")
        self.regionCount = requested_count
        self._fixed_regions = self._validate_regions(regions)
        self._fixed_condition_color = self._validate_color(condition_color)
        self._fixed_condition_shape = self._validate_shape(condition_shape)
        if regions is not None and not (
            self._fixed_condition_color or self._fixed_condition_shape
        ):
            raise ValueError("传入 regions 时必须同时提供至少一个筛选条件")

        self.regions: list[RegionSpec] = []
        self.conditionColor = ""
        self.conditionShape = ""
        self.targetIds: list[str] = []
        self.selectedIds: list[str] = []
        self.regionBounds: list[QRectF] = []
        self.focusedIndex = 0
        self.inputMethod = "pointer"
        self.toggleCount = 0
        self.deselectionCount = 0
        self._started_at: float | None = None
        self.verificationText = ""

        self.setFixedSize(300, 169)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("条件区域点选验证码")
        self.setToolTip("选择所有符合条件的区域，再按确认")
        self.generateChallenge()

    def _validate_color(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalised = str(value).lower()
        if normalised not in REGION_COLORS:
            raise ValueError("condition_color 包含不支持的颜色")
        return normalised

    def _validate_shape(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalised = str(value).lower()
        if normalised not in REGION_SHAPES:
            raise ValueError("condition_shape 包含不支持的形状")
        return normalised

    def _validate_regions(
        self,
        values: Sequence[RegionSpec | Mapping[str, str]] | None,
    ) -> tuple[RegionSpec, ...] | None:
        if values is None:
            return None
        if len(values) != self.regionCount:
            raise ValueError("regions 数量必须与 region_count 一致")
        result: list[RegionSpec] = []
        for value in values:
            if isinstance(value, RegionSpec):
                region = value
            elif isinstance(value, Mapping):
                try:
                    region = RegionSpec(
                        region_id=str(value["region_id"]),
                        color=str(value["color"]).lower(),
                        shape=str(value["shape"]).lower(),
                    )
                except KeyError as error:
                    raise ValueError("regions 缺少 region_id、color 或 shape") from error
            else:
                raise ValueError("regions 必须由 RegionSpec 或映射组成")
            if not region.region_id:
                raise ValueError("region_id 不能为空")
            if region.color not in REGION_COLORS:
                raise ValueError("regions 包含不支持的颜色")
            if region.shape not in REGION_SHAPES:
                raise ValueError("regions 包含不支持的形状")
            result.append(region)
        if len({region.region_id for region in result}) != len(result):
            raise ValueError("region_id 必须唯一")
        return tuple(result)

    def _generate_regions(self) -> tuple[list[RegionSpec], str, str]:
        random = secrets.SystemRandom()
        condition_color = self._fixed_condition_color or ""
        condition_shape = self._fixed_condition_shape or ""
        if not condition_color and not condition_shape:
            condition_color = random.choice(list(REGION_COLORS))
            condition_shape = random.choice(list(REGION_SHAPES))
        target_count = min(3, max(2, self.regionCount // 4))
        specs: list[RegionSpec] = []
        for index in range(target_count):
            specs.append(
                RegionSpec(
                    f"region-{index}",
                    condition_color or random.choice(list(REGION_COLORS)),
                    condition_shape or random.choice(list(REGION_SHAPES)),
                )
            )
        while len(specs) < self.regionCount:
            candidate_color = random.choice(list(REGION_COLORS))
            candidate_shape = random.choice(list(REGION_SHAPES))
            color_matches = (
                not condition_color or candidate_color == condition_color
            )
            shape_matches = (
                not condition_shape or candidate_shape == condition_shape
            )
            if color_matches and shape_matches:
                continue
            specs.append(
                RegionSpec(
                    f"region-{len(specs)}",
                    candidate_color,
                    candidate_shape,
                )
            )
        random.shuffle(specs)
        return specs, condition_color, condition_shape

    def _layout_regions(self) -> list[QRectF]:
        columns = 3 if self.regionCount <= 9 else 4
        rows = math.ceil(self.regionCount / columns)
        margin_x = 10.0
        margin_y = 9.0
        gap = 7.0
        width = (self.width() - margin_x * 2 - gap * (columns - 1)) / columns
        height = (self.height() - margin_y * 2 - gap * (rows - 1)) / rows
        bounds = []
        for index in range(self.regionCount):
            row, column = divmod(index, columns)
            bounds.append(
                QRectF(
                    margin_x + column * (width + gap),
                    margin_y + row * (height + gap),
                    width,
                    height,
                )
            )
        return bounds

    def _matches_condition(self, region: RegionSpec) -> bool:
        color_matches = not self.conditionColor or region.color == self.conditionColor
        shape_matches = not self.conditionShape or region.shape == self.conditionShape
        return color_matches and shape_matches

    def _condition_text(self) -> str:
        color = COLOR_NAMES.get(self.conditionColor, "")
        shape = SHAPE_NAMES.get(self.conditionShape, "")
        return f"请选择所有{color}{shape}区域（{len(self.targetIds)} 个）"

    def generateChallenge(self) -> None:
        if self._fixed_regions is None:
            self.regions, self.conditionColor, self.conditionShape = (
                self._generate_regions()
            )
        else:
            self.regions = list(self._fixed_regions)
            self.conditionColor = self._fixed_condition_color or ""
            self.conditionShape = self._fixed_condition_shape or ""
        self.targetIds = [
            region.region_id for region in self.regions if self._matches_condition(region)
        ]
        if not self.targetIds or len(self.targetIds) == self.regionCount:
            raise ValueError("筛选条件必须命中部分但不是全部 regions")
        self.selectedIds.clear()
        self.focusedIndex = 0
        self.inputMethod = "pointer"
        self.toggleCount = 0
        self.deselectionCount = 0
        self._started_at = None
        self.regionBounds = self._layout_regions()
        self.verificationText = self._condition_text()
        self.setAccessibleDescription(self.verificationText)
        self.challengeChanged.emit(self.verificationText)
        self.selectionChanged.emit(0)
        self.update()

    def refreshImage(self) -> None:
        self.generateChallenge()

    def _begin(self, input_method: str) -> None:
        if self._started_at is None:
            self._started_at = time.monotonic()
        self.inputMethod = input_method

    def toggleRegion(self, index: int, *, input_method: str = "pointer") -> bool:
        if not self.isEnabled() or not 0 <= index < self.regionCount:
            return False
        self._begin(input_method)
        region_id = self.regions[index].region_id
        if region_id in self.selectedIds:
            self.selectedIds.remove(region_id)
            self.deselectionCount += 1
        else:
            self.selectedIds.append(region_id)
        self.toggleCount += 1
        self.focusedIndex = index
        self.selectionChanged.emit(len(self.selectedIds))
        self.update()
        return True

    def answer(self) -> list[str]:
        selected = set(self.selectedIds)
        return [
            region.region_id for region in self.regions if region.region_id in selected
        ]

    def behavior(self) -> dict[str, object]:
        duration = 0.0 if self._started_at is None else time.monotonic() - self._started_at
        return {
            "inputMethod": self.inputMethod,
            "duration": round(duration, 4),
            "toggleCount": self.toggleCount,
            "deselectionCount": self.deselectionCount,
            "selectedCount": len(self.selectedIds),
            "targetCount": len(self.targetIds),
        }

    def verify(self) -> None:
        selected = set(self.selectedIds)
        self.verificationComplete.emit(selected == set(self.targetIds), self.answer())

    def _region_at(self, point: QPointF) -> int | None:
        for index, bounds in enumerate(self.regionBounds):
            if bounds.contains(point):
                return index
        return None

    def _draw_check(self, painter: QPainter, bounds: QRectF) -> None:
        center = QPointF(bounds.right() - 10, bounds.top() + 10)
        pen = QPen(QColor("#ffffff"), 1.7)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(QColor("#167a64"))
        painter.drawEllipse(center, 8, 8)
        painter.drawLine(center + QPointF(-3.5, 0), center + QPointF(-0.8, 3))
        painter.drawLine(center + QPointF(-0.8, 3), center + QPointF(4, -3))

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f3f6f9"))
        for index, (region, bounds) in enumerate(zip(self.regions, self.regionBounds)):
            selected = region.region_id in self.selectedIds
            focused = self.hasFocus() and index == self.focusedIndex
            if selected:
                painter.setPen(QPen(QColor("#16856b"), 2.2))
                painter.setBrush(QColor(22, 133, 107, 18))
                painter.drawRoundedRect(bounds.adjusted(1, 1, -1, -1), 7, 7)
            elif focused:
                painter.setPen(QPen(QColor("#198ff2"), 1.8, Qt.PenStyle.DotLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(bounds.adjusted(1, 1, -1, -1), 7, 7)

            color = QColor(REGION_COLORS[region.color])
            shape = region_path(region.shape, bounds.adjusted(5, 4, -5, -4))
            painter.setPen(QPen(color.darker(112), 1.5))
            fill = QColor(color)
            fill.setAlpha(205 if selected else 165)
            painter.setBrush(fill)
            painter.drawPath(shape)
            if selected:
                self._draw_check(painter, bounds)

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
            index = self._region_at(event.position())
            if index is not None:
                self.setFocus()
                self.toggleRegion(index, input_method="pointer")
                event.accept()
                return
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        columns = 3 if self.regionCount <= 9 else 4
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            delta = {
                Qt.Key.Key_Left: -1,
                Qt.Key.Key_Right: 1,
                Qt.Key.Key_Up: -columns,
                Qt.Key.Key_Down: columns,
            }[key]
            self.focusedIndex = max(
                0,
                min(self.regionCount - 1, self.focusedIndex + delta),
            )
            self.update()
            event.accept()
            return
        if key == Qt.Key.Key_Space:
            self.toggleRegion(self.focusedIndex, input_method="keyboard")
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._begin("keyboard")
            self.verify()
            event.accept()
            return
        if key == Qt.Key.Key_Escape and self.selectedIds:
            self._begin("keyboard")
            self.deselectionCount += len(self.selectedIds)
            self.selectedIds.clear()
            self.selectionChanged.emit(0)
            self.update()
            event.accept()
            return
        super().keyPressEvent(event)
