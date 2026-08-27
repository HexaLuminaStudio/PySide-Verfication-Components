"""Card and flyout wrappers for path-tracing verification."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..components.cards import VerificationFlyoutBase
from ..components.security import AttemptPolicy, ChallengeLifecycleController
from .image import VerificationImage


class PathTraceHint(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(34)
        self.setAccessibleName("验证提示")
        self.setText("从起点连续描摹至终点")

    def setText(self, text: str) -> None:
        self.setAccessibleDescription(text)
        self.setToolTip(text)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(1.0 if self.isEnabled() else 0.45)
        center_x = self.width() / 2
        points = (
            QPointF(center_x - 43, 20),
            QPointF(center_x - 14, 11),
            QPointF(center_x + 15, 22),
            QPointF(center_x + 43, 13),
        )
        painter.setPen(
            QPen(
                QColor("#526177"),
                2.0,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        for start, end in zip(points, points[1:]):
            painter.drawLine(start, end)
        for index, point in enumerate(points):
            painter.setPen(QPen(QColor("#ffffff"), 1))
            painter.setBrush(QColor("#198ff2") if index == 0 else QColor("#16856b"))
            painter.drawEllipse(point, 4.5, 4.5)
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
        node_count: int = 5,
        nodes: Sequence[tuple[float, float] | QPointF] | None = None,
        node_ids: Sequence[str] | None = None,
        hit_radius: float = 18.0,
        path_tolerance: float = 14.0,
        backtrack_tolerance: float = 12.0,
        max_payload_samples: int = 128,
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
            node_count=node_count,
            nodes=nodes,
            node_ids=node_ids,
            hit_radius=hit_radius,
            path_tolerance=path_tolerance,
            backtrack_tolerance=backtrack_tolerance,
            max_payload_samples=max_payload_samples,
        )
        self.tipLabel = PathTraceHint(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.verifyImage)
        layout.addWidget(self.tipLabel)

        self.verifyImage.verificationComplete.connect(self._verify)
        self.verifyImage.challengeChanged.connect(self.tipLabel.setText)
        self.verifyImage.pathRejected.connect(self.verificationFailed.emit)

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

    def _verify(self, success: bool, answer: dict[str, object]) -> None:
        allowed, guard_reason, _remaining = self._lifecycle.can_attempt()
        if not allowed:
            self._fail(guard_reason, count_attempt=False)
            if self.require_server_verification:
                self._lifecycle.invalidate_server_challenge()
                self.challengeRefreshRequested.emit()
            return
        if not success:
            self._fail("路径尚未完整描摹")
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
