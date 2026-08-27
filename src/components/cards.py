"""Shared card and flyout building blocks for verification widgets."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QPoint, QTimer, Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .flyout import Flyout, FlyoutView, PullUpFlyoutAnimationManager
from .slider import TrackPolicy, VerificationSlider


class SliderVerificationCard(QWidget):
    """Reusable host for all slider-based image challenges."""

    verificationSuccess = Signal()
    verificationFailed = Signal(str)

    def __init__(
        self,
        image_factory: Callable[..., QWidget],
        *,
        tolerance: int = 8,
        image_url: str | None = None,
        track_policy: TrackPolicy | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tolerance = max(0, int(tolerance))
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

    def _verify(self, result: dict[str, Any]) -> None:
        if bool(result.get("result")) and self._position_matches():
            self.verifySlider.setSuccess(True)
            self.verificationSuccess.emit()
            return
        reasons = result.get("msg") or ["位置不匹配"]
        if isinstance(reasons, str):
            reasons = [reasons]
        self.verifySlider.setSuccess(False)
        self.verifySlider.setError(True)
        self._refresh()
        self.verificationFailed.emit("；".join(str(reason) for reason in reasons))

    def reset(self) -> None:
        self._refresh()
        self.verifySlider.reset()


class ClickVerificationCard(QWidget):
    """Reusable host for text/icon click challenges."""

    verificationSuccess = Signal()
    verificationFailed = Signal(str)

    def __init__(
        self,
        image_factory: Callable[..., QWidget],
        *,
        image_url: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
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

    def _verify(self, success: bool, _correct: list[int]) -> None:
        if success:
            self.verificationSuccess.emit()
            return
        self.verificationFailed.emit("点击顺序或位置不正确")
        self.reset()

    def reset(self) -> None:
        self.verifyImage.refreshImage()
        QTimer.singleShot(0, self._sync_tip)


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
    card_class: type[QWidget]

    def __init__(self, parent: QWidget | None = None, **card_kwargs: Any) -> None:
        card = self.card_class(**card_kwargs)
        view = VerificationFlyoutView(card)
        super().__init__(view, parent, isDeleteOnClose=True)
        self.view = view
        card.verificationSuccess.connect(self._close_successfully)
        card.verificationFailed.connect(self.failed)

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
        QTimer.singleShot(180, self.fadeOut)
