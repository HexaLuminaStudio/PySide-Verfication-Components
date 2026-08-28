"""Card and flyout wrappers for shape drag-matching verification."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..components.cards import InstructionLabel, VerificationFlyoutBase
from ..components.security import AttemptPolicy, ChallengeLifecycleController
from .image import VerificationImage


class VerificationCard(QWidget):
    verificationSuccess = Signal()
    verificationFailed = Signal(str)
    verificationRequested = Signal(dict)
    challengeRefreshRequested = Signal()

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
            shape_count=shape_count,
            shape_types=shape_types,
            shape_ids=shape_ids,
            target_ids=target_ids,
            target_order=target_order,
            animation_duration_ms=animation_duration_ms,
        )
        self.instructionLabel = InstructionLabel(
            "把彩色图形拖入相同的虚线轮廓",
            self,
            details=(
                "全部归位后自动提交。"
                "键盘：左右键选图形，空格拿起；左右键选轮廓，再按空格放下。"
            ),
        )
        self.tipLabel = self.instructionLabel

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.instructionLabel)
        layout.addWidget(self.verifyImage)

        self.verifyImage.verificationComplete.connect(self._verify)

    def _refresh_challenge(self) -> None:
        self.verifyImage.setEnabled(True)
        self.tipLabel.setEnabled(True)
        self.verifyImage.refreshImage()
        self._lifecycle.start_challenge()

    def _fail(self, reason: str, *, count_attempt: bool = True) -> None:
        if count_attempt:
            self._lifecycle.record_failure()
        self.verificationFailed.emit(reason)
        self._refresh_challenge()

    def _verify(self, success: bool, answer: list[dict[str, str]]) -> None:
        allowed, guard_reason, _remaining = self._lifecycle.can_attempt()
        if not allowed:
            self._fail(guard_reason, count_attempt=False)
            if self.require_server_verification:
                self._lifecycle.invalidate_server_challenge()
                self.challengeRefreshRequested.emit()
            return
        if not success:
            self._fail("仍有图形没有正确归位")
            if self.require_server_verification:
                self._lifecycle.invalidate_server_challenge()
                self.challengeRefreshRequested.emit()
            return
        if not self.require_server_verification:
            self._lifecycle.record_success()
            self.verifyImage.setEnabled(False)
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
        self.verifyImage.setEnabled(False)
        self.tipLabel.setEnabled(False)
        self.verificationRequested.emit(payload)

    def setChallengeToken(
        self, token: str, *, expires_in: float | None = None
    ) -> None:
        self._lifecycle.set_challenge_token(token, expires_in=expires_in)
        self.verifyImage.setEnabled(True)
        self.tipLabel.setEnabled(True)

    def resolveServerVerification(
        self, attempt_id: str, accepted: bool, reason: str = ""
    ) -> bool:
        if not self._lifecycle.resolve_server_attempt(attempt_id):
            return False
        self.verifyImage.setEnabled(True)
        self.tipLabel.setEnabled(True)
        if accepted:
            self._lifecycle.record_success()
            self.verifyImage.setEnabled(False)
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
