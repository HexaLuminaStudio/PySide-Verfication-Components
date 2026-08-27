"""Shared card and flyout building blocks for verification widgets."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QPoint, QTimer, Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .flyout import Flyout, FlyoutView, PullUpFlyoutAnimationManager
from .security import AttemptPolicy, ChallengeLifecycleController
from .slider import TrackPolicy, VerificationSlider


class SliderVerificationCard(QWidget):
    """Reusable host for all slider-based image challenges."""

    verificationSuccess = Signal()
    verificationFailed = Signal(str)
    verificationRequested = Signal(dict)
    challengeRefreshRequested = Signal()

    def __init__(
        self,
        image_factory: Callable[..., QWidget],
        *,
        tolerance: int = 8,
        image_url: str | None = None,
        track_policy: TrackPolicy | None = None,
        require_server_verification: bool = False,
        challenge_token: str | None = None,
        challenge_ttl_seconds: float | None = None,
        attempt_policy: AttemptPolicy | None = None,
        server_timeout_seconds: float = 10.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tolerance = max(0, int(tolerance))
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
        self._guard = self._lifecycle.guard  # compatibility for existing integrations
        self.verifyImage = image_factory(parent=self, image_url=image_url)
        self.verifySlider = VerificationSlider(self, policy=track_policy)
        self.verifySlider.valueChanged.connect(self._move_image)
        self.verifySlider.resultSignal.connect(self._verify)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.verifyImage)
        layout.addWidget(self.verifySlider)

    def _move_image(self, value: int) -> None:
        mover = getattr(self.verifyImage, "setAngle", None) or getattr(self.verifyImage, "setMoveX")
        mover(value)

    def _position_matches(self) -> bool:
        verifier = getattr(self.verifyImage, "verify", None)
        if callable(verifier):
            return bool(verifier())
        return abs(self.verifyImage.getMoveX() - self.verifyImage.getCorrectValue()) <= self.tolerance

    def _refresh(self) -> None:
        refresh = getattr(self.verifyImage, "refreshImage", None) or getattr(
            self.verifyImage, "refresh_image"
        )
        refresh()

    def _fail(self, reason: str, *, count_attempt: bool = True) -> None:
        if count_attempt:
            self._lifecycle.record_failure()
        self.verifySlider.setPending(False)
        self.verifySlider.setSuccess(False)
        self._refresh()
        self._lifecycle.start_challenge()
        self.verifySlider.showErrorAndReset()
        self.verificationFailed.emit(reason)

    def setChallengeToken(
        self, token: str, *, expires_in: float | None = None
    ) -> None:
        """Install an opaque, server-issued challenge token for one attempt."""

        self._lifecycle.set_challenge_token(token, expires_in=expires_in)
        self.verifySlider.setPending(False)

    def resolveServerVerification(
        self, attempt_id: str, accepted: bool, reason: str = ""
    ) -> bool:
        """Resolve the outstanding request from an application's network layer."""

        if not self._lifecycle.resolve_server_attempt(attempt_id):
            return False
        if accepted:
            self._lifecycle.record_success()
            self.verifySlider.setSuccess(True)
            self.verificationSuccess.emit()
            return True
        self._fail(reason or "服务端拒绝了本次验证")
        self.challengeRefreshRequested.emit()
        return True

    def _handle_server_timeout(self) -> None:
        self._fail("服务端验证超时，请重试", count_attempt=False)
        self.challengeRefreshRequested.emit()

    def _verify(self, result: dict[str, Any]) -> None:
        allowed, guard_reason, _remaining = self._lifecycle.can_attempt()
        if not allowed:
            self._fail(guard_reason, count_attempt=False)
            if self.require_server_verification:
                self._lifecycle.invalidate_server_challenge()
                self.challengeRefreshRequested.emit()
            return

        if not bool(result.get("result")) or not self._position_matches():
            reasons = result.get("msg") or ["位置不匹配"]
            if isinstance(reasons, str):
                reasons = [reasons]
            self._fail("；".join(str(reason) for reason in reasons))
            if self.require_server_verification:
                self._lifecycle.invalidate_server_challenge()
                self.challengeRefreshRequested.emit()
            return

        if not self.require_server_verification:
            self._lifecycle.record_success()
            self.verifySlider.setSuccess(True)
            self.verificationSuccess.emit()
            return

        server_attempt, reason = self._lifecycle.begin_server_attempt()
        if server_attempt is None:
            self._fail(reason, count_attempt=False)
            self.challengeRefreshRequested.emit()
            return

        payload = {
            **server_attempt,
            "answer": result.get("value"),
            "behavior": {
                "riskScore": result.get("riskScore"),
                "inputMethod": result.get("inputMethod"),
                "metrics": result.get("metrics", {}),
                "signals": result.get("signals", []),
            },
        }
        self.verifySlider.setPending(True)
        self.verificationRequested.emit(payload)

    def reset(self) -> None:
        self._lifecycle.reset()
        self._refresh()
        self.verifySlider.reset()
        if self.require_server_verification:
            self.challengeRefreshRequested.emit()


class ClickVerificationCard(QWidget):
    """Reusable host for text/icon click challenges."""

    verificationSuccess = Signal()
    verificationFailed = Signal(str)
    verificationRequested = Signal(dict)
    challengeRefreshRequested = Signal()

    def __init__(
        self,
        image_factory: Callable[..., QWidget],
        *,
        image_url: str | None = None,
        require_server_verification: bool = False,
        challenge_token: str | None = None,
        challenge_ttl_seconds: float | None = None,
        attempt_policy: AttemptPolicy | None = None,
        server_timeout_seconds: float = 10.0,
        parent: QWidget | None = None,
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
        self._guard = self._lifecycle.guard  # compatibility for existing integrations
        try:
            self.verifyImage = image_factory(parent=self, image_url=image_url)
        except TypeError:
            self.verifyImage = image_factory(parent=self)
        self.tipLabel = QLabel("正在生成验证内容…", self)
        self.tipLabel.setWordWrap(True)
        self.tipLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tipLabel.setMinimumHeight(34)
        self.tipLabel.setAccessibleName("验证提示")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.verifyImage)
        layout.addWidget(self.tipLabel)

        self.verifyImage.verificationComplete.connect(self._verify)
        challenge_changed = getattr(self.verifyImage, "challengeChanged", None)
        if challenge_changed is not None:
            challenge_changed.connect(self.tipLabel.setText)
        QTimer.singleShot(0, self._sync_tip)

    def _sync_tip(self) -> None:
        self.tipLabel.setText(self.verifyImage.verificationText or "正在生成验证内容…")

    def _fail(self, reason: str, *, count_attempt: bool = True) -> None:
        if count_attempt:
            self._lifecycle.record_failure()
        self.verifyImage.setEnabled(True)
        self.tipLabel.setEnabled(True)
        self.verificationFailed.emit(reason)
        self._refresh_challenge()

    def _refresh_challenge(self) -> None:
        self.verifyImage.refreshImage()
        self._lifecycle.start_challenge()
        QTimer.singleShot(0, self._sync_tip)

    def _click_answer(self) -> list[dict[str, int]]:
        return [
            {"x": int(point.x()), "y": int(point.y())}
            for point in getattr(self.verifyImage, "userClicks", [])
        ]

    def _verify(self, success: bool, correct: list[int]) -> None:
        allowed, guard_reason, _remaining = self._lifecycle.can_attempt()
        if not allowed:
            self._fail(guard_reason, count_attempt=False)
            if self.require_server_verification:
                self._lifecycle.invalidate_server_challenge()
                self.challengeRefreshRequested.emit()
            return
        if not success:
            self._fail("点击顺序或位置不正确")
            if self.require_server_verification:
                self._lifecycle.invalidate_server_challenge()
                self.challengeRefreshRequested.emit()
            return
        if not self.require_server_verification:
            self._lifecycle.record_success()
            self.verificationSuccess.emit()
            return
        server_attempt, reason = self._lifecycle.begin_server_attempt()
        if server_attempt is None:
            self._fail(reason, count_attempt=False)
            self.challengeRefreshRequested.emit()
            return

        payload = {
            **server_attempt,
            "answer": self._click_answer(),
            "behavior": {
                "inputMethod": "keyboard" if self.verifyImage.hasFocus() else "pointer",
                "matchedLocally": len(correct),
            },
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
        self.verifyImage.setEnabled(True)
        self.tipLabel.setEnabled(True)
        self._refresh_challenge()
        if self.require_server_verification:
            self.challengeRefreshRequested.emit()


class VerificationFlyoutView(FlyoutView):
    def __init__(self, card: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.card = card
        self.widgetLayout.setContentsMargins(12, 12, 12, 12)
        self.viewLayout.setContentsMargins(0, 0, 0, 0)
        self.widgetLayout.addWidget(card)
        self.adjustSize()


class VerificationFlyoutBase(Flyout):
    """Base class preserving the original ``create(...)`` entry point."""

    success = Signal()
    failed = Signal(str)
    verificationRequested = Signal(dict)
    challengeRefreshRequested = Signal()
    card_class: type[QWidget]

    def __init__(self, parent: QWidget | None = None, **card_kwargs: Any) -> None:
        card = self.card_class(**card_kwargs)
        view = VerificationFlyoutView(card)
        super().__init__(view, parent, isDeleteOnClose=True)
        self.view = view
        card.verificationSuccess.connect(self._close_successfully)
        card.verificationFailed.connect(self.failed.emit)
        requested = getattr(card, "verificationRequested", None)
        if requested is not None:
            requested.connect(self.verificationRequested.emit)
        refresh_requested = getattr(card, "challengeRefreshRequested", None)
        if refresh_requested is not None:
            refresh_requested.connect(self.challengeRefreshRequested.emit)

    @classmethod
    def create(
        cls,
        target: QWidget | QPoint | None = None,
        parent: QWidget | None = None,
        **card_kwargs: Any,
    ) -> "VerificationFlyoutBase":
        flyout = cls(parent=parent, **card_kwargs)
        if target is not None:
            position = (
                PullUpFlyoutAnimationManager(flyout).position(target)
                if isinstance(target, QWidget)
                else target
            )
            flyout.exec(position)
        return flyout

    def _close_successfully(self) -> None:
        self.success.emit()
        delay = 420 if hasattr(self.view.card, "verifySlider") else 180
        QTimer.singleShot(delay, self.fadeOut)

    def setChallengeToken(
        self, token: str, *, expires_in: float | None = None
    ) -> None:
        setter = getattr(self.view.card, "setChallengeToken", None)
        if setter is None:
            raise TypeError("当前验证码类型不支持服务端挑战令牌")
        setter(token, expires_in=expires_in)

    def resolveServerVerification(
        self, attempt_id: str, accepted: bool, reason: str = ""
    ) -> bool:
        resolver = getattr(self.view.card, "resolveServerVerification", None)
        if resolver is None:
            return False
        return bool(resolver(attempt_id, accepted, reason))
