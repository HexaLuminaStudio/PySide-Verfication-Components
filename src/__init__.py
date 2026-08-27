"""Compatibility package for the verification components."""

from .basicSliderVerification import VerificationCard as BasicSliderCard
from .basicSliderVerification import VerificationFlyout as BasicSliderFlyout
from .circleSliderVerification import VerificationCard as CircleSliderCard
from .circleSliderVerification import VerificationFlyout as CircleSliderFlyout
from .figureSliderVerification import VerificationCard as FigureSliderCard
from .figureSliderVerification import VerificationFlyout as FigureSliderFlyout
from .iconClickVerification import VerificationCard as IconClickCard
from .iconClickVerification import VerificationFlyout as IconClickFlyout
from .textClickVerification import VerificationCard as TextClickCard
from .textClickVerification import VerificationFlyout as TextClickFlyout
from .components import TrackPolicy

__all__ = [
    "BasicSliderCard",
    "BasicSliderFlyout",
    "CircleSliderCard",
    "CircleSliderFlyout",
    "FigureSliderCard",
    "FigureSliderFlyout",
    "IconClickCard",
    "IconClickFlyout",
    "TextClickCard",
    "TextClickFlyout",
    "TrackPolicy",
]
