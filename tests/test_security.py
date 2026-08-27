from PySide6.QtTest import QSignalSpy, QTest

from pyside_verification import (
    AttemptPolicy,
    BasicSliderCard,
    ChallengeLifecycleController,
    IconClickCard,
    RotateSliderCard,
    TileOrderCard,
)
from src.components.security import AttemptGuard


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_attempt_guard_enforces_cooldown():
    clock = FakeClock()
    policy = AttemptPolicy(
        max_failures=2,
        window_seconds=60,
        cooldown_seconds=30,
        challenge_ttl_seconds=120,
    )
    guard = AttemptGuard(policy, clock=clock)

    assert guard.can_attempt()[0] is True
    assert guard.record_failure()[0] is False
    blocked, remaining = guard.record_failure()
    assert blocked is True
    assert remaining == 30
    assert guard.can_attempt()[0] is False

    clock.now = 31
    assert guard.can_attempt()[0] is True


def test_attempt_guard_rejects_expired_challenge():
    clock = FakeClock()
    guard = AttemptGuard(
        AttemptPolicy(challenge_ttl_seconds=10),
        clock=clock,
    )
    clock.now = 10
    allowed, reason, _remaining = guard.can_attempt()
    assert allowed is False
    assert "过期" in reason


def test_lifecycle_controller_consumes_only_matching_server_attempt(qapp):
    lifecycle = ChallengeLifecycleController(
        require_server_verification=True,
        challenge_token="opaque-token",
        server_timeout_seconds=60,
    )

    attempt, reason = lifecycle.begin_server_attempt()

    assert reason == ""
    assert attempt is not None
    assert attempt["challengeToken"] == "opaque-token"
    assert lifecycle.pending_attempt_id == attempt["attemptId"]
    assert lifecycle.resolve_server_attempt("stale-attempt") is False
    assert lifecycle.has_challenge_token is True
    assert lifecycle.resolve_server_attempt(attempt["attemptId"]) is True
    assert lifecycle.pending_attempt_id is None
    assert lifecycle.has_challenge_token is False


def test_lifecycle_controller_replacing_token_invalidates_pending_attempt(qapp):
    lifecycle = ChallengeLifecycleController(
        require_server_verification=True,
        challenge_token="first-token",
        server_timeout_seconds=60,
    )
    first_attempt, _reason = lifecycle.begin_server_attempt()
    assert first_attempt is not None

    lifecycle.set_challenge_token("replacement-token", expires_in=30)
    replacement_attempt, reason = lifecycle.begin_server_attempt()

    assert reason == ""
    assert replacement_attempt is not None
    assert replacement_attempt["challengeToken"] == "replacement-token"
    assert lifecycle.resolve_server_attempt(first_attempt["attemptId"]) is False


def test_lifecycle_controller_timeout_invalidates_server_challenge(qapp):
    lifecycle = ChallengeLifecycleController(
        require_server_verification=True,
        challenge_token="timeout-token",
        server_timeout_seconds=60,
    )
    timed_out = QSignalSpy(lifecycle.serverTimedOut)
    attempt, _reason = lifecycle.begin_server_attempt()
    assert attempt is not None

    lifecycle._handle_server_timeout()

    assert timed_out.count() == 1
    assert lifecycle.pending_attempt_id is None
    assert lifecycle.has_challenge_token is False


def test_server_mode_waits_for_authoritative_acceptance(qapp):
    card = BasicSliderCard(
        require_server_verification=True,
        challenge_token="opaque-server-token",
        server_timeout_seconds=60,
    )
    card._position_matches = lambda: True
    requested = QSignalSpy(card.verificationRequested)
    succeeded = QSignalSpy(card.verificationSuccess)

    card._verify(
        {
            "result": True,
            "value": 123,
            "riskScore": 12,
            "inputMethod": "pointer",
            "metrics": {"duration": 0.8},
            "signals": [],
        }
    )

    assert requested.count() == 1
    assert succeeded.count() == 0
    assert card.verifySlider._state == "pending"
    payload = requested.at(0)[0]
    assert payload["challengeToken"] == "opaque-server-token"
    assert payload["answer"] == 123
    assert payload["behavior"]["riskScore"] == 12

    assert card.resolveServerVerification("wrong-id", True) is False
    assert succeeded.count() == 0
    assert card.resolveServerVerification(payload["attemptId"], True) is True
    assert succeeded.count() == 1
    assert card.verifySlider._state == "success"


def test_server_mode_fails_closed_without_challenge_token(qapp):
    card = BasicSliderCard(require_server_verification=True)
    card._position_matches = lambda: True
    failed = QSignalSpy(card.verificationFailed)
    requested = QSignalSpy(card.verificationRequested)

    card._verify({"result": True, "value": 100})

    assert requested.count() == 0
    assert failed.count() == 1
    assert "服务端挑战" in failed.at(0)[0]


def test_click_challenge_also_requires_server_acceptance(qapp):
    card = IconClickCard(
        require_server_verification=True,
        challenge_token="click-token",
        server_timeout_seconds=60,
    )
    card.verifyImage.userClicks = list(card.verifyImage.targetPositions)
    requested = QSignalSpy(card.verificationRequested)
    succeeded = QSignalSpy(card.verificationSuccess)

    card.verifyImage.verify()

    assert requested.count() == 1
    assert succeeded.count() == 0
    payload = requested.at(0)[0]
    assert len(payload["answer"]) == len(card.verifyImage.targetPositions)
    assert card.resolveServerVerification(payload["attemptId"], True) is True
    assert succeeded.count() == 1


def test_rotate_challenge_uses_shared_server_lifecycle(qapp):
    card = RotateSliderCard(
        initial_angle_degrees=120,
        require_server_verification=True,
        challenge_token="rotate-token",
        server_timeout_seconds=60,
    )
    answer = round(card.verifyImage.getCorrectValue())
    card.verifyImage.setAngle(answer)
    requested = QSignalSpy(card.verificationRequested)
    succeeded = QSignalSpy(card.verificationSuccess)

    card._verify(
        {
            "result": True,
            "value": answer,
            "riskScore": 8,
            "inputMethod": "keyboard",
            "metrics": {"duration": 1.2},
            "signals": [],
        }
    )

    assert requested.count() == 1
    assert succeeded.count() == 0
    payload = requested.at(0)[0]
    assert payload["challengeToken"] == "rotate-token"
    assert payload["answer"] == answer
    assert card.resolveServerVerification(payload["attemptId"], True) is True
    assert succeeded.count() == 1


def test_tile_order_challenge_uses_opaque_ids_in_server_payload(qapp):
    card = TileOrderCard(
        initial_order=[1, 0, 2, 3],
        tile_ids=["tile-a", "tile-b", "tile-c", "tile-d"],
        require_server_verification=True,
        challenge_token="tile-order-token",
        server_timeout_seconds=60,
        animation_duration_ms=120,
    )
    requested = QSignalSpy(card.verificationRequested)
    succeeded = QSignalSpy(card.verificationSuccess)

    card.verifyImage.swapTiles(0, 1)
    QTest.qWait(170)

    assert requested.count() == 1
    assert succeeded.count() == 0
    payload = requested.at(0)[0]
    assert payload["challengeToken"] == "tile-order-token"
    assert payload["answer"] == ["tile-a", "tile-b", "tile-c", "tile-d"]
    assert payload["behavior"]["initialOrder"] == [
        "tile-b",
        "tile-a",
        "tile-c",
        "tile-d",
    ]
    assert payload["behavior"]["moveCount"] == 1
    assert card.resolveServerVerification(payload["attemptId"], True) is True
    assert succeeded.count() == 1
