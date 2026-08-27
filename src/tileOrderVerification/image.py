"""Offline image widget for the tile-order verification challenge."""

from __future__ import annotations

import math
import secrets
import time
from collections.abc import Sequence

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from ..components.background import orientation_background
from ..components.rendering import copy_logical, cover_pixmap, effective_dpr


class VerificationImage(QWidget):
    """Split an image into vertical tiles and let the user restore their order."""

    verificationComplete = Signal(bool, list)
    challengeChanged = Signal(str)
    orderChanged = Signal(list)
    errorOccurred = Signal(str)

    def __init__(
        self,
        imageList: Sequence[QPixmap] | None = None,
        parent: QWidget | None = None,
        *,
        tile_count: int = 4,
        initial_order: Sequence[int] | None = None,
        tile_ids: Sequence[str] | None = None,
        animation_duration_ms: int = 180,
    ) -> None:
        super().__init__(parent)
        self.imageList = list(imageList or [])
        self._width = 300
        self._height = 169
        self.tileCount = max(3, min(6, int(tile_count)))
        self.tileWidth = self._width // self.tileCount
        self.animationDuration = max(0, min(600, int(animation_duration_ms)))
        self._dpr = effective_dpr(self)
        self._fixed_initial_order = self._validate_initial_order(initial_order)
        self.tileIds = self._validate_tile_ids(tile_ids)
        self.sourceImage = QPixmap()
        self.tiles: list[QPixmap] = []
        self.order: list[int] = []
        self.initialOrder: list[int] = []
        self.focusedIndex = 0
        self.hoveredIndex: int | None = None
        self.draggedIndex: int | None = None
        self.dropIndex: int | None = None
        self._drag_offset_x = 0.0
        self._drag_x = 0.0
        self._keyboard_grabbed = False
        self._completion_emitted = False
        self._swap_progress = 0.0
        self._animation_first: int | None = None
        self._animation_second: int | None = None
        self._started_at: float | None = None
        self.moveCount = 0
        self.inputMethod = "pointer"
        self.loading = False
        self.verificationText = "拖动图块恢复图片顺序"

        self.setFixedSize(self._width, self._height)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAccessibleName("图块排序验证码")
        self.setAccessibleDescription(
            "拖动图块恢复图片；键盘用户按空格拿起图块，再用左右方向键移动"
        )
        self.setToolTip("拖动图块恢复图片顺序")
        self._swap_animation = QPropertyAnimation(self, b"swapProgress", self)
        self._swap_animation.setDuration(self.animationDuration)
        self._swap_animation.setStartValue(0.0)
        self._swap_animation.setEndValue(1.0)
        self._swap_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._swap_animation.finished.connect(self._finish_swap_animation)
        self._load_local_image()

    def _validate_initial_order(
        self, order: Sequence[int] | None
    ) -> tuple[int, ...] | None:
        if order is None:
            return None
        normalised = tuple(int(value) for value in order)
        if len(normalised) != self.tileCount or set(normalised) != set(
            range(self.tileCount)
        ):
            raise ValueError("initial_order 必须是所有图块索引的完整排列")
        if list(normalised) == list(range(self.tileCount)):
            raise ValueError("initial_order 不能已经是正确顺序")
        return normalised

    def _validate_tile_ids(self, tile_ids: Sequence[str] | None) -> list[str]:
        if tile_ids is None:
            return [str(index) for index in range(self.tileCount)]
        normalised = [str(value) for value in tile_ids]
        if len(normalised) != self.tileCount or len(set(normalised)) != self.tileCount:
            raise ValueError("tile_ids 必须为每个图块提供唯一标识")
        return normalised

    def _new_order(self) -> list[int]:
        if self._fixed_initial_order is not None:
            return list(self._fixed_initial_order)
        order = list(range(self.tileCount))
        while order == list(range(self.tileCount)):
            secrets.SystemRandom().shuffle(order)
        return order

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
        self.sourceImage = cover_pixmap(
            source,
            self._width,
            self._height,
            dpr=self._dpr,
        )
        self.tiles = [
            copy_logical(
                self.sourceImage,
                index * self.tileWidth,
                0,
                self.tileWidth,
                self._height,
            )
            for index in range(self.tileCount)
        ]
        self._reset_interaction()

    def fallback_to_local_image(self) -> None:
        source = orientation_background(
            self._width,
            self._height,
            dpr=self._dpr,
        )
        self.setSourcePixmap(source)
        self.loading = False
        self.update()

    def refreshImage(self) -> None:
        self._load_local_image()

    def _reset_interaction(self) -> None:
        self._swap_animation.stop()
        self.order = self._new_order()
        self.initialOrder = list(self.order)
        self.focusedIndex = 0
        self.hoveredIndex = None
        self.draggedIndex = None
        self.dropIndex = None
        self._keyboard_grabbed = False
        self._completion_emitted = False
        self._swap_progress = 0.0
        self._animation_first = None
        self._animation_second = None
        self._started_at = None
        self.moveCount = 0
        self.inputMethod = "pointer"
        self.challengeChanged.emit(self.verificationText)
        self.orderChanged.emit(self.answer())
        self.update()

    def answer(self) -> list[str]:
        return [self.tileIds[index] for index in self.order]

    def behavior(self) -> dict[str, object]:
        duration = 0.0 if self._started_at is None else time.monotonic() - self._started_at
        return {
            "inputMethod": self.inputMethod,
            "moveCount": self.moveCount,
            "duration": round(duration, 4),
            "initialOrder": [self.tileIds[index] for index in self.initialOrder],
        }

    def _begin_interaction(self, input_method: str) -> None:
        if self._started_at is None:
            self._started_at = time.monotonic()
        self.inputMethod = input_method

    def getSwapProgress(self) -> float:
        return self._swap_progress

    def setSwapProgress(self, progress: float) -> None:
        self._swap_progress = max(0.0, min(1.0, float(progress)))
        self.update()

    swapProgress = Property(float, getSwapProgress, setSwapProgress)

    def _is_animating(self) -> bool:
        return self._animation_first is not None and self._animation_second is not None

    def swapTiles(
        self,
        first: int,
        second: int,
        *,
        input_method: str = "pointer",
        animated: bool = True,
    ) -> bool:
        if self._is_animating():
            return False
        if not (0 <= first < self.tileCount and 0 <= second < self.tileCount):
            return False
        if first == second:
            return False
        self._begin_interaction(input_method)
        if animated and self.animationDuration > 0:
            self._animation_first = first
            self._animation_second = second
            self._swap_animation.stop()
            self._swap_animation.setDuration(self.animationDuration)
            self._swap_animation.setStartValue(0.0)
            self._swap_animation.setEndValue(1.0)
            self._swap_animation.start()
            return True
        self._commit_swap(first, second)
        return True

    def _commit_swap(self, first: int, second: int) -> None:
        self.order[first], self.order[second] = self.order[second], self.order[first]
        self.moveCount += 1
        self.orderChanged.emit(self.answer())
        self.update()
        self._complete_if_solved()

    def _finish_swap_animation(self) -> None:
        first = self._animation_first
        second = self._animation_second
        self._animation_first = None
        self._animation_second = None
        self._swap_progress = 0.0
        if first is not None and second is not None:
            self._commit_swap(first, second)
        self.update()

    def setOrder(self, order: Sequence[int], *, verify: bool = False) -> None:
        normalised = [int(value) for value in order]
        if len(normalised) != self.tileCount or set(normalised) != set(
            range(self.tileCount)
        ):
            raise ValueError("order 必须是所有图块索引的完整排列")
        self._swap_animation.stop()
        self._animation_first = None
        self._animation_second = None
        self._swap_progress = 0.0
        self.order = normalised
        self.orderChanged.emit(self.answer())
        self.update()
        if verify:
            self.verify()

    def verify(self) -> None:
        solved = self.order == list(range(self.tileCount))
        self.verificationComplete.emit(solved, self.answer())

    def _complete_if_solved(self) -> None:
        if self._completion_emitted or self.order != list(range(self.tileCount)):
            return
        self._completion_emitted = True
        self.verificationComplete.emit(True, self.answer())

    def _tile_at(self, x: float) -> int:
        return max(0, min(self.tileCount - 1, int(x // self.tileWidth)))

    def _draw_tile(
        self,
        painter: QPainter,
        tile_id: int,
        x: float,
        *,
        y: float = 0.0,
        active: bool = False,
        elevated: bool = False,
    ) -> None:
        tile = self.tiles[tile_id]
        target = QRectF(x, y, self.tileWidth, self._height)
        if elevated:
            painter.fillRect(
                target.translated(3, 4),
                QColor(5, 13, 20, 72),
            )
        painter.drawPixmap(QPointF(x, y), tile)
        if active:
            painter.fillRect(target, QColor(25, 145, 250, 28))
        painter.setPen(QPen(QColor(255, 255, 255, 128), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(target.adjusted(0.5, 0.5, -0.5, -0.5))

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), 5, 5)
        painter.setClipPath(clip)
        painter.fillRect(self.rect(), QColor("#172733"))

        animated_slots = {
            slot
            for slot in (self._animation_first, self._animation_second)
            if slot is not None
        }
        for slot, tile_id in enumerate(self.order):
            if slot in animated_slots:
                painter.save()
                painter.setOpacity(0.26)
                self._draw_tile(
                    painter,
                    tile_id,
                    slot * self.tileWidth,
                )
                painter.restore()
                continue
            x = slot * self.tileWidth
            if slot == self.draggedIndex:
                painter.fillRect(
                    QRectF(x, 0, self.tileWidth, self._height),
                    QColor(15, 29, 40, 210),
                )
                continue
            active = slot == self.hoveredIndex or (
                self.hasFocus() and slot == self.focusedIndex
            )
            self._draw_tile(painter, tile_id, x, active=active)

        if self._is_animating():
            first = self._animation_first
            second = self._animation_second
            assert first is not None and second is not None
            progress = self._swap_progress
            wave = math.sin(math.pi * progress) * 6.0
            first_x = (
                first + (second - first) * progress
            ) * self.tileWidth
            second_x = (
                second + (first - second) * progress
            ) * self.tileWidth
            self._draw_tile(
                painter,
                self.order[second],
                second_x,
                y=wave,
                active=True,
            )
            self._draw_tile(
                painter,
                self.order[first],
                first_x,
                y=-wave,
                active=True,
                elevated=True,
            )

        if self.dropIndex is not None and self.draggedIndex is not None:
            drop_x = self.dropIndex * self.tileWidth
            painter.setPen(QPen(QColor("#66b7f4"), 3))
            painter.drawLine(
                QPointF(drop_x + 1.5, 7),
                QPointF(drop_x + 1.5, self._height - 7),
            )

        if self.draggedIndex is not None:
            tile_id = self.order[self.draggedIndex]
            drag_x = max(
                -self.tileWidth * 0.15,
                min(
                    self._width - self.tileWidth * 0.85,
                    self._drag_x - self._drag_offset_x,
                ),
            )
            painter.fillRect(
                QRectF(drag_x + 3, 5, self.tileWidth, self._height - 4),
                QColor(5, 13, 20, 78),
            )
            self._draw_tile(painter, tile_id, drag_x, active=True)

        if self._keyboard_grabbed and self.hasFocus():
            focus_rect = QRectF(
                self.focusedIndex * self.tileWidth + 2,
                2,
                self.tileWidth - 4,
                self._height - 4,
            )
            painter.setPen(QPen(QColor("#198ff2"), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(focus_rect, 4, 4)

        if self.loading or not self.isEnabled():
            painter.fillRect(self.rect(), QColor(9, 19, 31, 132))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#ffffff"))
            center_x = self._width / 2
            center_y = self._height / 2
            for offset in (-7, 0, 7):
                painter.drawEllipse(QPointF(center_x + offset, center_y), 1.8, 1.8)

        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.isEnabled()
            and not self._is_animating()
        ):
            self.setFocus()
            self.inputMethod = "pointer"
            self.draggedIndex = self._tile_at(event.position().x())
            self.focusedIndex = self.draggedIndex
            self.dropIndex = self.draggedIndex
            self._drag_offset_x = event.position().x() - (
                self.draggedIndex * self.tileWidth
            )
            self._drag_x = event.position().x()
            self._begin_interaction("pointer")
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.draggedIndex is not None:
            self._drag_x = event.position().x()
            self.dropIndex = self._tile_at(event.position().x())
            self.update()
            event.accept()
            return
        hovered = self._tile_at(event.position().x()) if self.rect().contains(
            event.position().toPoint()
        ) else None
        if hovered != self.hoveredIndex:
            self.hoveredIndex = hovered
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        if self.draggedIndex is None:
            self.hoveredIndex = None
            self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.draggedIndex is not None:
            first = self.draggedIndex
            second = self._tile_at(event.position().x())
            self.draggedIndex = None
            self.dropIndex = None
            self.focusedIndex = second
            self.swapTiles(first, second, input_method="pointer")
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if self._is_animating():
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            direction = -1 if event.key() == Qt.Key.Key_Left else 1
            target = max(0, min(self.tileCount - 1, self.focusedIndex + direction))
            if self._keyboard_grabbed:
                if self.swapTiles(
                    self.focusedIndex,
                    target,
                    input_method="keyboard",
                ):
                    self.focusedIndex = target
            else:
                self.focusedIndex = target
            self.update()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._begin_interaction("keyboard")
            self._keyboard_grabbed = not self._keyboard_grabbed
            self.update()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape and self._keyboard_grabbed:
            self._keyboard_grabbed = False
            self.update()
            event.accept()
            return
        super().keyPressEvent(event)
