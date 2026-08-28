"""Card and flyout wrappers for condition-region verification."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..components.cards import InstructionLabel, VerificationFlyoutBase
from ..components.security import AttemptPolicy, ChallengeLifecycleController
from .image import REGION_COLORS, RegionSpec, VerificationImage, region_path


class ConditionFooter(QWidget):
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._condition_color = ""
        self._condition_shape = ""
        self._target_count = 0
        self._selected_count = 0
        self._description = ""
        self.setFixedSize(300, 34)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("确认区域选择")

    def setCondition(
        self,
        color: str,
        shape: str,
        target_count: int,
        description: str,
    ) -> None:
        self._condition_color = color
        self._condition_shape = shape
        self._target_count = target_count
        self._selected_count = 0
        self._description = description
        self.setAccessibleDescription(description + "；按回车确认")
        self.setToolTip(description + "，选择完成后确认")
        self.update()

    def setSelectedCount(self, count: int) -> None:
        self._selected_count = max(0, int(count))
        self.update()

    def click(self) -> None:
        if self.isEnabled():
            self.clicked.emit()

    def _button_bounds(self) -> QRectF:
        return QRectF(self.width() - 64, 0, 64, self.height())

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(1.0 if self.isEnabled() else 0.48)

        # A small funnel makes the condition sample read as a filter, without text.
        painter.setPen(
            QPen(
                QColor("#526177"),
                1.7,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.drawLine(QPointF(5, 9), QPointF(23, 9))
        painter.drawLine(QPointF(5, 9), QPointF(12, 17))
        painter.drawLine(QPointF(23, 9), QPointF(16, 17))
        painter.drawLine(QPointF(12, 17), QPointF(12, 24))
        painter.drawLine(QPointF(12, 24), QPointF(16, 21))
        painter.drawLine(QPointF(16, 17), QPointF(16, 21))

        sample_bounds = QRectF(31, 5, 28, 24)
        sample_shape = self._condition_shape or "circle"
        sample_color = QColor(
            REGION_COLORS.get(self._condition_color, QColor("#68778b"))
        )
        painter.setPen(QPen(sample_color.darker(112), 1.4))
        sample_fill = QColor(sample_color)
        sample_fill.setAlpha(190 if self._condition_color else 48)
        painter.setBrush(sample_fill)
        painter.drawPath(region_path(sample_shape, sample_bounds))

        painter.setPen(QPen(QColor("#526177"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        count_bounds = QRectF(68, 5, 50, 24)
        painter.drawRoundedRect(count_bounds, 7, 7)
        dot_count = max(1, min(12, self._target_count))
        diameter = min(5.0, (count_bounds.width() - 10) / dot_count - 1)
        total_width = dot_count * diameter + (dot_count - 1) * 2
        start_x = count_bounds.center().x() - total_width / 2 + diameter / 2
        for index in range(dot_count):
            selected = index < min(self._selected_count, dot_count)
            painter.setPen(QPen(QColor("#16856b") if selected else QColor("#7b8797"), 1))
            painter.setBrush(QColor("#16856b") if selected else Qt.BrushStyle.NoBrush)
            painter.drawEllipse(
                QPointF(start_x + index * (diameter + 2), count_bounds.center().y()),
                diameter / 2,
                diameter / 2,
            )

        button = self._button_bounds()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#198ff2") if self.isEnabled() else QColor("#9aabc0"))
        painter.drawRoundedRect(button, 7, 7)
        check_center = button.center()
        check_pen = QPen(QColor("#ffffff"), 2.2)
        check_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        check_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(check_pen)
        painter.drawLine(check_center + QPointF(-8, 0), check_center + QPointF(-2, 6))
        painter.drawLine(check_center + QPointF(-2, 6), check_center + QPointF(9, -7))
        if self.hasFocus():
            painter.setPen(QPen(QColor("#064f8c"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(button.adjusted(1, 1, -1, -1), 7, 7)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.isEnabled()
            and self._button_bounds().contains(event.position())
        ):
            self.setFocus()
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class VerificationCard(QWidget):
    verificationSuccess = Signal()
    verificationFailed = Signal(str)
    verificationRequested = Signal(dict)
    challengeRefreshRequested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        region_count: int = 9,
        regions: Sequence[RegionSpec | Mapping[str, str]] | None = None,
        condition_color: str | None = None,
        condition_shape: str | None = None,
        require_server_verification: bool = False,
        challenge_token: str | None = None,
        challenge_ttl_seconds: float | None = None,
        attempt_policy: AttemptPolicy | None = None,
        server_timeout_seconds: float = 10.0,
    ) -> None:
        super().__init__(parent)
        self.require_server_verification = bool(require_server_verification)
        self._lifecycle = ChallengeLifecycleController(
            require_server_verification=require_server_verification,
            challenge_token=challenge_token,
            challenge_ttl_seconds=challenge_ttl_seconds,
            attempt_policy=attempt_policy,
            server_timeout_seconds=server_timeout_seconds,
            parent=self,
        )
        self._lifecycle.serverTimedOut.connect(self._handle_server_timeout)
        self._guard = self._lifecycle.guard
        self.verifyImage = VerificationImage(
            parent=self,
            region_count=region_count,
            regions=regions,
            condition_color=condition_color,
            condition_shape=condition_shape,
        )

        self.submitButton = ConditionFooter(self)
        self.tipLabel = self.submitButton
        self.instructionLabel = InstructionLabel("", self)
        self._sync_footer()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.instructionLabel)
        layout.addWidget(self.verifyImage)
        layout.addWidget(self.submitButton)

        self.verifyImage.verificationComplete.connect(self._verify)
        self.verifyImage.challengeChanged.connect(self._sync_footer)
        self.verifyImage.selectionChanged.connect(self.submitButton.setSelectedCount)
        self.submitButton.clicked.connect(self._submit)

    def _sync_footer(self, _description: str = "") -> None:
        self.instructionLabel.setText(self.verifyImage.verificationText)
        self.instructionLabel.setDetails(
            "点击区域可选择或取消，选完后点击勾号确认。"
            "键盘：方向键移动，空格选择，回车确认。"
        )
        self.submitButton.setCondition(
            self.verifyImage.conditionColor,
            self.verifyImage.conditionShape,
            len(self.verifyImage.targetIds),
            self.verifyImage.verificationText,
        )

    def _submit(self) -> None:
        if self.submitButton.hasFocus():
            self.verifyImage.inputMethod = "keyboard"
        self.verifyImage.verify()

    def _set_interaction_enabled(self, enabled: bool) -> None:
        self.verifyImage.setEnabled(enabled)
        self.tipLabel.setEnabled(enabled)
        self.submitButton.setEnabled(enabled)

    def _refresh_challenge(self) -> None:
        self._set_interaction_enabled(True)
        self.verifyImage.refreshImage()
        self._lifecycle.start_challenge()

    def _fail(self, reason: str, *, count_attempt: bool = True) -> None:
        if count_attempt:
            self._lifecycle.record_failure()
        self.verificationFailed.emit(reason)
        self._refresh_challenge()

    def _verify(self, success: bool, answer: list[str]) -> None:
        allowed, guard_reason, _remaining = self._lifecycle.can_attempt()
        if not allowed:
            self._fail(guard_reason, count_attempt=False)
            if self.require_server_verification:
                self._lifecycle.invalidate_server_challenge()
                self.challengeRefreshRequested.emit()
            return
        if not success:
            self._fail("选择的区域不符合条件")
            if self.require_server_verification:
                self._lifecycle.invalidate_server_challenge()
                self.challengeRefreshRequested.emit()
            return
        if not self.require_server_verification:
            self._lifecycle.record_success()
            self._set_interaction_enabled(False)
            self.verificationSuccess.emit()
            return

        server_attempt, reason = self._lifecycle.begin_server_attempt()
        if server_attempt is None:
            self._fail(reason, count_attempt=False)
            self.challengeRefreshRequested.emit()
            return
        payload = {
            **server_attempt,
            "answer": answer,
            "behavior": self.verifyImage.behavior(),
        }
        self._set_interaction_enabled(False)
        self.verificationRequested.emit(payload)

    def setChallengeToken(
        self, token: str, *, expires_in: float | None = None
    ) -> None:
        self._lifecycle.set_challenge_token(token, expires_in=expires_in)
        self._set_interaction_enabled(True)

    def resolveServerVerification(
        self, attempt_id: str, accepted: bool, reason: str = ""
    ) -> bool:
        if not self._lifecycle.resolve_server_attempt(attempt_id):
            return False
        self._set_interaction_enabled(True)
        if accepted:
            self._lifecycle.record_success()
            self._set_interaction_enabled(False)
            self.verificationSuccess.emit()
            return True
        self._fail(reason or "服务端拒绝了本次验证")
        self.challengeRefreshRequested.emit()
        return True

    def _handle_server_timeout(self) -> None:
        self._fail("服务端验证超时，请重试", count_attempt=False)
        self.challengeRefreshRequested.emit()

    def reset(self) -> None:
        self._lifecycle.reset()
        self._refresh_challenge()
        if self.require_server_verification:
            self.challengeRefreshRequested.emit()


class VerificationFlyout(VerificationFlyoutBase):
    card_class = VerificationCard
