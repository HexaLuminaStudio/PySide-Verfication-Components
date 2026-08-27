from PySide6.QtWidgets import QWidget

from ..components.cards import SliderVerificationCard, VerificationFlyoutBase
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
    ) -> None:
        super().__init__(
            VerificationImage,
            parent=parent,
            image_url=image_url,
            tolerance=tolerance,
            track_policy=track_policy,
        )


class VerificationFlyout(VerificationFlyoutBase):
    card_class = VerificationCard
