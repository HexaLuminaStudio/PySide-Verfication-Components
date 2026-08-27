"""Compatibility package for the verification components."""

from .basicSliderVerification import VerificationCard as BasicSliderCard
from .basicSliderVerification import VerificationFlyout as BasicSliderFlyout
from .circleSliderVerification import VerificationCard as CircleSliderCard
from .circleSliderVerification import VerificationFlyout as CircleSliderFlyout
from .conditionRegionVerification import RegionSpec
from .conditionRegionVerification import VerificationCard as ConditionRegionCard
from .conditionRegionVerification import VerificationFlyout as ConditionRegionFlyout
from .dragMatchVerification import VerificationCard as DragMatchCard
from .dragMatchVerification import VerificationFlyout as DragMatchFlyout
from .dynamicTargetVerification import VerificationCard as DynamicTargetCard
from .dynamicTargetVerification import VerificationFlyout as DynamicTargetFlyout
from .figureSliderVerification import VerificationCard as FigureSliderCard
from .figureSliderVerification import VerificationFlyout as FigureSliderFlyout
from .iconClickVerification import VerificationCard as IconClickCard
from .iconClickVerification import VerificationFlyout as IconClickFlyout
from .pathTraceVerification import VerificationCard as PathTraceCard
from .pathTraceVerification import VerificationFlyout as PathTraceFlyout
from .rotateSliderVerification import VerificationCard as RotateSliderCard
from .rotateSliderVerification import VerificationFlyout as RotateSliderFlyout
from .shortMemoryVerification import VerificationCard as ShortMemoryCard
from .shortMemoryVerification import VerificationFlyout as ShortMemoryFlyout
from .textClickVerification import VerificationCard as TextClickCard
from .textClickVerification import VerificationFlyout as TextClickFlyout
from .tileOrderVerification import VerificationCard as TileOrderCard
from .tileOrderVerification import VerificationFlyout as TileOrderFlyout
from .components import AttemptPolicy, ChallengeLifecycleController, TrackPolicy

__all__ = [
    "AttemptPolicy",
    "ChallengeLifecycleController",
    "BasicSliderCard",
    "BasicSliderFlyout",
    "CircleSliderCard",
    "CircleSliderFlyout",
    "ConditionRegionCard",
    "ConditionRegionFlyout",
    "DragMatchCard",
    "DragMatchFlyout",
    "DynamicTargetCard",
    "DynamicTargetFlyout",
    "FigureSliderCard",
    "FigureSliderFlyout",
    "IconClickCard",
    "IconClickFlyout",
    "PathTraceCard",
    "PathTraceFlyout",
    "RotateSliderCard",
    "RotateSliderFlyout",
    "ShortMemoryCard",
    "ShortMemoryFlyout",
    "TextClickCard",
    "TextClickFlyout",
    "TileOrderCard",
    "TileOrderFlyout",
    "RegionSpec",
    "TrackPolicy",
]
