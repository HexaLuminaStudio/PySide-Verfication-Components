"""Short-term visual sequence memory challenge."""

from __future__ import annotations

import secrets
import time
from collections.abc import Sequence

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen, QShowEvent
from PySide6.QtWidgets import QWidget


class VerificationImage(QWidget):
    verificationComplete = Signal(bool, dict)
    challengeChanged = Signal(str)
    sequenceRejected = Signal(str)
    phaseChanged = Signal(str)
    progressChanged = Signal(int, int, str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        sequence_length: int = 4,
        sequence_indices: Sequence[int] | None = None,
        cell_ids: Sequence[str] | None = None,
        sequence_id: str | None = None,
        ready_delay_ms: int = 700,
        flash_duration_ms: int = 520,
        gap_duration_ms: int = 170,
        reduced_motion: bool = False,
    ) -> None:
        super().__init__(parent)
        requested_length = int(sequence_length)
        if not 3 <= requested_length <= 7:
            raise ValueError("sequence_length 必须在 3 到 7 之间")
        self.sequenceLength = requested_length
        self.reducedMotion = bool(reduced_motion)
        self.readyDelay = max(0, min(3000, int(ready_delay_ms)))
        self.flashDuration = max(80, min(2000, int(flash_duration_ms)))
        self.gapDuration = max(30, min(800, int(gap_duration_ms)))
        if self.reducedMotion:
            self.readyDelay = max(850, self.readyDelay)
            self.flashDuration = max(800, self.flashDuration)
            self.gapDuration = max(260, self.gapDuration)
        self._fixed_sequence = self._validate_sequence(sequence_indices)
        self.cellIds = self._validate_cell_ids(cell_ids)
        self._fixed_sequence_id = str(sequence_id) if sequence_id else None

        self.sequence: list[int] = []
        self.sequenceId = ""
        self.cellBounds = self._layout_cells()
        self.userSequence: list[int] = []
        self.focusedIndex = 0
        self.inputMethod = "pointer"
        self.phase = "ready"
        self.activePresentationIndex: int | None = None
        self._presentation_cursor = 0
        self._highlight_on = False
        self._presentation_started = False
        self._recall_started_at: float | None = None
        self._recall_duration = 0.0
        self.verificationText = "记住亮起顺序，隐藏后按原顺序复现"

        self.setFixedSize(300, 169)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("短时记忆验证码")
        self.setToolTip("记住依次亮起的位置，再按相同顺序选择")
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance_presentation)
        self.generateChallenge()

    def _validate_sequence(self, values: Sequence[int] | None) -> tuple[int, ...] | None:
        if values is None:
            return None
        result = tuple(int(value) for value in values)
        if len(result) != self.sequenceLength:
            raise ValueError("sequence_indices 数量必须与 sequence_length 一致")
        if len(set(result)) != len(result):
            raise ValueError("sequence_indices 不能包含重复位置")
        if any(not 0 <= value < 9 for value in result):
            raise ValueError("sequence_indices 必须位于 0 到 8")
        return result

    def _validate_cell_ids(self, values: Sequence[str] | None) -> list[str]:
        if values is None:
            return [f"cell-{index}" for index in range(9)]
        result = [str(value) for value in values]
        if len(result) != 9 or len(set(result)) != 9:
            raise ValueError("cell_ids 必须提供 9 个唯一标识")
        if any(not value for value in result):
            raise ValueError("cell_ids 不能为空")
        return result

    def _layout_cells(self) -> list[QRectF]:
        margin_x = 17.0
        margin_y = 10.0
        gap_x = 10.0
        gap_y = 6.0
        width = (300 - margin_x * 2 - gap_x * 2) / 3
        height = (169 - margin_y * 2 - gap_y * 2) / 3
        return [
            QRectF(
                margin_x + column * (width + gap_x),
                margin_y + row * (height + gap_y),
                width,
                height,
            )
            for row in range(3)
            for column in range(3)
        ]

    def _set_phase(self, phase: str) -> None:
        self.phase = phase
        descriptions = {
            "ready": "即将播放记忆序列",
            "presenting": "正在播放记忆序列，请观察",
            "recall": "请按刚才的顺序选择区域",
            "complete": "序列复现完成",
        }
        description = descriptions[phase]
        self.setAccessibleDescription(description)
        self.phaseChanged.emit(phase)
        self.progressChanged.emit(
            len(self.userSequence),
            self.sequenceLength,
            phase,
        )
        self.update()

    def generateChallenge(self) -> None:
        self._timer.stop()
        self.sequence = (
            list(self._fixed_sequence)
            if self._fixed_sequence is not None
            else secrets.SystemRandom().sample(range(9), self.sequenceLength)
        )
        self.sequenceId = self._fixed_sequence_id or secrets.token_urlsafe(9)
        self.userSequence.clear()
        self.focusedIndex = 0
        self.inputMethod = "pointer"
        self.activePresentationIndex = None
        self._presentation_cursor = 0
        self._highlight_on = False
        self._presentation_started = False
        self._recall_started_at = None
        self._recall_duration = 0.0
        self._set_phase("ready")
        self.challengeChanged.emit(self.verificationText)
        if self.isVisible():
            self._schedule_presentation()

    def refreshImage(self) -> None:
        self.generateChallenge()

    def _schedule_presentation(self) -> None:
        if self.phase != "ready" or self._presentation_started:
            return
        self._presentation_started = True
        self._timer.start(self.readyDelay)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._schedule_presentation()

    def _advance_presentation(self) -> None:
        if self.phase == "ready":
            self._set_phase("presenting")
            self._presentation_cursor = 0
            self._highlight_on = True
            self.activePresentationIndex = self.sequence[0]
            self.progressChanged.emit(0, self.sequenceLength, "presenting")
            self._timer.start(self.flashDuration)
            self.update()
            return
        if self.phase != "presenting":
            return
        if self._highlight_on:
            self._highlight_on = False
            self.activePresentationIndex = None
            self._timer.start(self.gapDuration)
            self.update()
            return
        self._presentation_cursor += 1
        if self._presentation_cursor >= self.sequenceLength:
            self.finishPresentation()
            return
        self._highlight_on = True
        self.activePresentationIndex = self.sequence[self._presentation_cursor]
        self.progressChanged.emit(
            self._presentation_cursor,
            self.sequenceLength,
            "presenting",
        )
        self._timer.start(self.flashDuration)
        self.update()

    def finishPresentation(self) -> None:
        """Finish the reveal phase; useful for deterministic host-controlled starts."""

        self._timer.stop()
        self.activePresentationIndex = None
        self._highlight_on = False
        self._recall_started_at = time.monotonic()
        self._set_phase("recall")

    def selectCell(self, index: int, *, input_method: str = "pointer") -> bool:
        if not self.isEnabled() or self.phase != "recall" or not 0 <= index < 9:
            return False
        self.inputMethod = input_method
        self.focusedIndex = index
        expected = self.sequence[len(self.userSequence)]
        if index != expected:
            self.sequenceRejected.emit("选择顺序不正确，请重新记忆")
            return False
        self.userSequence.append(index)
        self.progressChanged.emit(
            len(self.userSequence),
            self.sequenceLength,
            "recall",
        )
        if len(self.userSequence) == self.sequenceLength:
            if self._recall_started_at is not None:
                self._recall_duration = time.monotonic() - self._recall_started_at
            self._set_phase("complete")
            self.verificationComplete.emit(True, self.answer())
        self.update()
        return True

    def answer(self) -> dict[str, object]:
        return {
            "sequenceId": self.sequenceId,
            "cellIds": [self.cellIds[index] for index in self.userSequence],
        }

    def behavior(self) -> dict[str, object]:
        return {
            "inputMethod": self.inputMethod,
            "recallDuration": round(self._recall_duration, 4),
            "sequenceLength": self.sequenceLength,
            "selectionCount": len(self.userSequence),
            "readyDelayMs": self.readyDelay,
            "flashDurationMs": self.flashDuration,
            "gapDurationMs": self.gapDuration,
            "reducedMotion": self.reducedMotion,
        }

    def _cell_at(self, point: QPointF) -> int | None:
        for index, bounds in enumerate(self.cellBounds):
            if bounds.contains(point):
                return index
        return None

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f3f6f9"))
        selected = set(self.userSequence)
        for index, bounds in enumerate(self.cellBounds):
            highlighted = index == self.activePresentationIndex
            recalled = index in selected
            focused = self.hasFocus() and self.phase == "recall" and index == self.focusedIndex
            if highlighted:
                painter.setPen(QPen(QColor("#0876d1"), 2.2))
                painter.setBrush(QColor("#198ff2"))
            elif recalled:
                painter.setPen(QPen(QColor("#0f725c"), 2.0))
                painter.setBrush(QColor("#16856b"))
            else:
                painter.setPen(QPen(QColor("#9aa7b7"), 1.4))
                painter.setBrush(QColor("#ffffff"))
            painter.drawRoundedRect(bounds, 8, 8)

            if highlighted:
                center = bounds.center()
                painter.setPen(QPen(QColor("#ffffff"), 2))
                painter.setBrush(QColor(255, 255, 255, 40))
                painter.drawEllipse(center, 10, 10)
                painter.setBrush(QColor("#ffffff"))
                painter.drawEllipse(center, 3.2, 3.2)
            elif recalled:
                center = bounds.center()
                painter.setPen(QPen(QColor("#ffffff"), 2))
                painter.drawLine(center + QPointF(-7, 0), center + QPointF(-2, 5))
                painter.drawLine(center + QPointF(-2, 5), center + QPointF(8, -6))

            if focused:
                painter.setPen(QPen(QColor("#198ff2"), 2, Qt.PenStyle.DotLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(bounds.adjusted(3, 3, -3, -3), 6, 6)

        if self.phase == "ready":
            center = QPointF(self.width() / 2, self.height() / 2)
            painter.setPen(QPen(QColor("#526177"), 2))
            painter.setBrush(QColor(243, 246, 249, 224))
            painter.drawEllipse(center, 25, 25)
            painter.drawArc(QRectF(center.x() - 14, center.y() - 8, 28, 16), 0, 180 * 16)
            painter.drawArc(QRectF(center.x() - 14, center.y() - 8, 28, 16), 180 * 16, 180 * 16)
            painter.setBrush(QColor("#16856b"))
            painter.drawEllipse(center, 4, 4)

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
        if event.button() == Qt.MouseButton.LeftButton and self.phase == "recall":
            index = self._cell_at(event.position())
            if index is not None:
                self.setFocus()
                self.selectCell(index, input_method="pointer")
                event.accept()
                return
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if self.phase == "recall" and key in (
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
        ):
            delta = {
                Qt.Key.Key_Left: -1,
                Qt.Key.Key_Right: 1,
                Qt.Key.Key_Up: -3,
                Qt.Key.Key_Down: 3,
            }[key]
            self.focusedIndex = max(0, min(8, self.focusedIndex + delta))
            self.update()
            event.accept()
            return
        if self.phase == "recall" and key in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):
            self.selectCell(self.focusedIndex, input_method="keyboard")
            event.accept()
            return
        super().keyPressEvent(event)
