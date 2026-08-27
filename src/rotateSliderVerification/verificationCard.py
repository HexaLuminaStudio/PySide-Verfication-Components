"""Card and flyout wrappers for picture-straightening verification."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWidget

from ..components.cards import SliderVerificationCard, VerificationFlyoutBase
from ..components.security import AttemptPolicy
from ..components.slider import TrackPolicy
from .url_image import VerificationImage


class VerificationCard(SliderVerificationCard):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        image_url: str | None = None,
        angle_tolerance_degrees: float = 6.0,
        initial_angle_degrees: float | None = None,
        image_scale: float = 0.9,
        track_policy: TrackPolicy | None = None,
        require_server_verification: bool = False,
        challenge_token: str | None = None,
        challenge_ttl_seconds: float | None = None,
        attempt_policy: AttemptPolicy | None = None,
        server_timeout_seconds: float = 10.0,
    ) -> None:
        def image_factory(
            *, parent: QWidget | None = None, image_url: str | None = None
        ) -> VerificationImage:
            return VerificationImage(
                parent=parent,
                image_url=image_url,
                initial_angle_degrees=initial_angle_degrees,
                angle_tolerance_degrees=angle_tolerance_degrees,
                image_scale=image_scale,
            )

        typed_factory: Callable[..., QWidget] = image_factory
        super().__init__(
            typed_factory,
            parent=parent,
            image_url=image_url,
            tolerance=round(angle_tolerance_degrees),
            track_policy=track_policy,
            require_server_verification=require_server_verification,
            challenge_token=challenge_token,
            challenge_ttl_seconds=challenge_ttl_seconds,
            attempt_policy=attempt_policy,
            server_timeout_seconds=server_timeout_seconds,
        )
        self.verifySlider.setAccessibleName("图片旋正滑块")
        self.verifySlider.setAccessibleDescription(
            "使用左右方向键旋转图片，按住 Shift 可微调，按回车或空格提交"
        )


class VerificationFlyout(VerificationFlyoutBase):
    card_class = VerificationCard
