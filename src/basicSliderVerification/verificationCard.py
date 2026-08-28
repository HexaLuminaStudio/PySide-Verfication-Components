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
        tolerance: int = 6,
        track_policy: TrackPolicy | None = None,
        require_server_verification: bool = False,
        challenge_token: str | None = None,
        challenge_ttl_seconds: float | None = None,
        attempt_policy: AttemptPolicy | None = None,
        server_timeout_seconds: float = 10.0,
    ) -> None:
        super().__init__(
            VerificationImage,
            parent=parent,
            instruction_text="拖动滑块，让拼图块对准缺口",
            image_url=image_url,
            tolerance=tolerance,
            track_policy=track_policy,
            require_server_verification=require_server_verification,
            challenge_token=challenge_token,
            challenge_ttl_seconds=challenge_ttl_seconds,
            attempt_policy=attempt_policy,
            server_timeout_seconds=server_timeout_seconds,
        )


class VerificationFlyout(VerificationFlyoutBase):
    card_class = VerificationCard
