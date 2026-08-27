from PySide6.QtWidgets import QWidget

from ..components.cards import ClickVerificationCard, VerificationFlyoutBase
from .url_image import VerificationImage


class VerificationCard(ClickVerificationCard):
    def __init__(self, parent: QWidget | None = None, *, image_url: str | None = None) -> None:
        super().__init__(VerificationImage, parent=parent, image_url=image_url)


class VerificationFlyout(VerificationFlyoutBase):
    card_class = VerificationCard
