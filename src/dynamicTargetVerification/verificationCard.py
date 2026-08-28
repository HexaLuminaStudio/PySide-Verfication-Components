"""Card and flyout wrappers for dynamic target verification."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..components.cards import InstructionLabel, VerificationFlyoutBase
from ..components.security import AttemptPolicy, ChallengeLifecycleController
from .image import VerificationImage


class TrackingHint(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._progress = 0.0
        self._inside = False
        self.setFixedSize(300, 34)
        self.setAccessibleName("追踪进度")
        self.setAccessibleDescription("按住目标并持续跟随，圆点全部亮起后完成")
        self.setToolTip("按住目标并持续跟随")

    def setProgress(self, progress: float, inside: bool) -> None:
        self._progress = max(0.0, min(1.0, float(progress)))
        self._inside = bool(inside)
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(1.0 if self.isEnabled() else 0.45)
        center_y = self.height() / 2
        target = QPointF(52, center_y)
        painter.setPen(QPen(QColor(25, 143, 242, 88), 1.6, Qt.PenStyle.DashLine))
        painter.setBrush(QColor(25, 143, 242, 16))
        painter.drawEllipse(target, 12, 12)
        painter.setPen(QPen(QColor("#0f725c"), 1.5))
        painter.setBrush(QColor("#16856b"))
        painter.drawEllipse(target, 5, 5)
        painter.setPen(QPen(QColor("#16856b") if self._inside else QColor("#68778b"), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        cursor = QPointF(79, center_y)
        painter.drawEllipse(cursor, 5, 5)
        painter.drawLine(cursor + QPointF(-8, 0), cursor + QPointF(-4, 0))
        painter.drawLine(cursor + QPointF(4, 0), cursor + QPointF(8, 0))
        painter.drawLine(cursor + QPointF(0, -8), cursor + QPointF(0, -4))
        painter.drawLine(cursor + QPointF(0, 4), cursor + QPointF(0, 8))

        dot_count = 8
        filled_count = round(self._progress * dot_count)
        start_x = 128
        for index in range(dot_count):
            filled = index < filled_count
            painter.setPen(QPen(QColor("#16856b") if filled else QColor("#7b8797"), 1))
            painter.setBrush(QColor("#16856b") if filled else Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(start_x + index * 14, center_y), 3, 3)
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
            waypoints=waypoints,
            target_id=target_id,
            path_id=path_id,
            tracking_duration=tracking_duration,
            target_speed=target_speed,
            tracking_radius=tracking_radius,
            hard_miss_radius=hard_miss_radius,
            min_follow_ratio=min_follow_ratio,
            max_miss_duration=max_miss_duration,
            reduced_motion=reduced_motion,
            max_payload_samples=max_payload_samples,
        )
        self.tipLabel = TrackingHint(self)
        self.instructionLabel = InstructionLabel(
            "按住蓝色目标，持续跟随至进度完成",
            self,
            details=(
                "跟随时保持指针在虚线圆内。"
                "键盘：空格开始，方向键跟随。"
            ),
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.instructionLabel)
        layout.addWidget(self.verifyImage)
        layout.addWidget(self.tipLabel)

        self.verifyImage.verificationComplete.connect(self._verify)
        self.verifyImage.trackingRejected.connect(self._handle_tracking_rejected)
        self.verifyImage.progressChanged.connect(self.tipLabel.setProgress)

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

    def _handle_tracking_rejected(self, reason: str) -> None:
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
            self._fail("动态目标跟随未完成")
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
