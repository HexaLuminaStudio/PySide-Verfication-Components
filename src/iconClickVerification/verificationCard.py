from PySide6.QtWidgets import QWidget

from ..components.cards import ClickVerificationCard, VerificationFlyoutBase
from .image import VerificationImage


class VerificationCard(ClickVerificationCard):
    def __init__(self, parent: QWidget | None = None, *, image_url: str | None = None) -> None:
        del image_url
        super().__init__(VerificationImage, parent=parent)


class VerificationFlyout(VerificationFlyoutBase):
    card_class = VerificationCard
