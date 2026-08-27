"""Card and flyout wrappers for short-term memory verification."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..components.cards import VerificationFlyoutBase
from ..components.security import AttemptPolicy, ChallengeLifecycleController
from .image import VerificationImage


class MemoryHint(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current = 0
        self._total = 4
        self._phase = "ready"
        self.setFixedSize(300, 34)
        self.setAccessibleName("记忆验证状态")
        self.setToolTip("先观察亮起顺序，再按相同顺序选择")

    def setProgress(self, current: int, total: int, phase: str) -> None:
        self._current = max(0, int(current))
        self._total = max(1, int(total))
        self._phase = phase
        descriptions = {
            "ready": "即将开始播放",
            "presenting": "正在播放记忆序列",
            "recall": "请复现刚才的顺序",
            "complete": "记忆验证完成",
        }
        self.setAccessibleDescription(descriptions.get(phase, "记忆验证"))
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(1.0 if self.isEnabled() else 0.45)
        center_y = self.height() / 2
        icon_center = QPointF(62, center_y)

        if self._phase in ("ready", "presenting"):
            painter.setPen(QPen(QColor("#526177"), 1.8))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            eye_bounds = QRectF(icon_center.x() - 12, center_y - 7, 24, 14)
            painter.drawArc(eye_bounds, 0, 180 * 16)
            painter.drawArc(eye_bounds, 180 * 16, 180 * 16)
            painter.setBrush(QColor("#16856b"))
            painter.drawEllipse(icon_center, 3.5, 3.5)
        else:
            painter.setPen(QPen(QColor("#526177"), 1.7))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(50, 7, 24, 20), 5, 5)
            painter.setBrush(QColor("#16856b"))
            painter.drawEllipse(icon_center, 3.5, 3.5)

        dot_count = self._total
        diameter = min(6.0, 76 / max(1, dot_count))
        spacing = diameter + 7
        start_x = 124
        active_count = self._current
        if self._phase == "presenting":
            active_count = min(self._total, self._current + 1)
        for index in range(dot_count):
            active = index < active_count
            color = QColor("#198ff2") if self._phase == "presenting" else QColor("#16856b")
            painter.setPen(QPen(color if active else QColor("#7b8797"), 1))
            painter.setBrush(color if active else Qt.BrushStyle.NoBrush)
            painter.drawEllipse(
                QPointF(start_x + index * spacing, center_y),
                diameter / 2,
                diameter / 2,
            )
        painter.end()


class VerificationCard(QWidget):
    verificationSuccess = Signal()
    verificationFailed = Signal(str)
    verificationRequested = Signal(dict)
    challengeRefreshRequested = Signal()

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
            sequence_length=sequence_length,
            sequence_indices=sequence_indices,
            cell_ids=cell_ids,
            sequence_id=sequence_id,
            ready_delay_ms=ready_delay_ms,
            flash_duration_ms=flash_duration_ms,
            gap_duration_ms=gap_duration_ms,
            reduced_motion=reduced_motion,
        )
        self.tipLabel = MemoryHint(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.verifyImage)
        layout.addWidget(self.tipLabel)

        self.verifyImage.verificationComplete.connect(self._verify)
        self.verifyImage.sequenceRejected.connect(self._handle_sequence_rejected)
        self.verifyImage.progressChanged.connect(self.tipLabel.setProgress)
        self.tipLabel.setProgress(0, sequence_length, "ready")

    def _set_interaction_enabled(self, enabled: bool) -> None:
        self.verifyImage.setEnabled(enabled)
        self.tipLabel.setEnabled(enabled)

    def _refresh_challenge(self) -> None:
        self._set_interaction_enabled(True)
        self.verifyImage.refreshImage()
        self._lifecycle.start_challenge()

    def _fail(self, reason: str, *, count_attempt: bool = True) -> None:
        if count_attempt:
            self._lifecycle.record_failure()
        self.verificationFailed.emit(reason)
        self._refresh_challenge()

    def _handle_sequence_rejected(self, reason: str) -> None:
        self._fail(reason)
        if self.require_server_verification:
            self._lifecycle.invalidate_server_challenge()
            self.challengeRefreshRequested.emit()

    def _verify(self, success: bool, answer: dict[str, object]) -> None:
        allowed, guard_reason, _remaining = self._lifecycle.can_attempt()
        if not allowed:
            self._fail(guard_reason, count_attempt=False)
            if self.require_server_verification:
                self._lifecycle.invalidate_server_challenge()
                self.challengeRefreshRequested.emit()
            return
        if not success:
            self._fail("记忆顺序不正确")
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
