from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QSignalSpy, QTest

from pyside_verification import (
    AttemptPolicy,
    BasicSliderCard,
    ChallengeLifecycleController,
    ConditionRegionCard,
    DragMatchCard,
    DynamicTargetCard,
    IconClickCard,
    PathTraceCard,
    RotateSliderCard,
    ShortMemoryCard,
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


def test_drag_match_challenge_uses_opaque_ids_in_server_payload(qapp):
    card = DragMatchCard(
        shape_types=["circle", "triangle", "star"],
        shape_ids=["shape-a", "shape-b", "shape-c"],
        target_ids=["slot-1", "slot-2", "slot-3"],
        target_order=[1, 2, 0],
        animation_duration_ms=0,
        require_server_verification=True,
        challenge_token="drag-match-token",
        server_timeout_seconds=60,
    )
    requested = QSignalSpy(card.verificationRequested)
    succeeded = QSignalSpy(card.verificationSuccess)

    for shape_index in range(3):
        card.verifyImage.attemptPlacement(
            shape_index,
            card.verifyImage.targetForShape(shape_index),
            animated=False,
        )

    assert requested.count() == 1
    assert succeeded.count() == 0
    payload = requested.at(0)[0]
    assert payload["challengeToken"] == "drag-match-token"
    assert payload["answer"] == [
        {"shapeId": "shape-a", "targetId": "slot-3"},
        {"shapeId": "shape-b", "targetId": "slot-1"},
        {"shapeId": "shape-c", "targetId": "slot-2"},
    ]
    assert payload["behavior"]["moveCount"] == 3
    assert payload["behavior"]["missCount"] == 0
    assert card.resolveServerVerification(payload["attemptId"], True) is True
    assert succeeded.count() == 1


def test_path_trace_challenge_sends_bounded_trace_and_opaque_ids(qapp):
    nodes = [(30, 80), (90, 42), (150, 126), (210, 48), (270, 88)]
    card = PathTraceCard(
        node_count=5,
        nodes=nodes,
        node_ids=["n-a", "n-b", "n-c", "n-d", "n-e"],
        max_payload_samples=16,
        require_server_verification=True,
        challenge_token="path-trace-token",
        server_timeout_seconds=60,
    )
    card.show()
    card.verifyImage.setFocus()
    requested = QSignalSpy(card.verificationRequested)
    succeeded = QSignalSpy(card.verificationSuccess)

    QTest.keyClick(card.verifyImage, Qt.Key.Key_Space)
    for _index in range(4):
        QTest.keyClick(card.verifyImage, Qt.Key.Key_Right)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Space)

    assert requested.count() == 1
    assert succeeded.count() == 0
    payload = requested.at(0)[0]
    assert payload["challengeToken"] == "path-trace-token"
    assert payload["answer"]["nodeIds"] == ["n-a", "n-b", "n-c", "n-d", "n-e"]
    assert 1 <= len(payload["answer"]["trace"]) <= 16
    assert set(payload["answer"]["trace"][0]) == {"x", "y", "t"}
    assert payload["behavior"]["inputMethod"] == "keyboard"
    assert payload["behavior"]["nodeHitCount"] == 5
    assert payload["behavior"]["pathLength"] > 0
    assert card.resolveServerVerification(payload["attemptId"], True) is True
    assert succeeded.count() == 1


def test_condition_region_challenge_uses_opaque_ids_in_server_payload(qapp):
    regions = [
        {"region_id": "area-a", "color": "blue", "shape": "circle"},
        {"region_id": "area-b", "color": "blue", "shape": "circle"},
        {"region_id": "area-c", "color": "blue", "shape": "triangle"},
        {"region_id": "area-d", "color": "green", "shape": "circle"},
        {"region_id": "area-e", "color": "orange", "shape": "square"},
        {"region_id": "area-f", "color": "purple", "shape": "diamond"},
    ]
    card = ConditionRegionCard(
        region_count=6,
        regions=regions,
        condition_color="blue",
        condition_shape="circle",
        require_server_verification=True,
        challenge_token="condition-region-token",
        server_timeout_seconds=60,
    )
    requested = QSignalSpy(card.verificationRequested)
    succeeded = QSignalSpy(card.verificationSuccess)

    card.verifyImage.toggleRegion(0)
    card.verifyImage.toggleRegion(1)
    card.submitButton.click()

    assert requested.count() == 1
    assert succeeded.count() == 0
    payload = requested.at(0)[0]
    assert payload["challengeToken"] == "condition-region-token"
    assert payload["answer"] == ["area-a", "area-b"]
    assert payload["behavior"]["toggleCount"] == 2
    assert payload["behavior"]["selectedCount"] == 2
    assert payload["behavior"]["inputMethod"] == "pointer"
    assert card.resolveServerVerification(payload["attemptId"], True) is True
    assert succeeded.count() == 1


def test_dynamic_target_challenge_sends_bounded_trace_and_opaque_ids(qapp):
    card = DynamicTargetCard(
        waypoints=[(100, 80), (118, 80), (100, 80), (118, 80)],
        target_id="moving-target-a",
        path_id="path-v3",
        tracking_duration=0.25,
        tracking_radius=24,
        max_payload_samples=16,
        require_server_verification=True,
        challenge_token="dynamic-target-token",
        server_timeout_seconds=60,
    )
    requested = QSignalSpy(card.verificationRequested)
    succeeded = QSignalSpy(card.verificationSuccess)

    assert card.verifyImage.startTracking(QPointF(100, 80))
    QTest.qWait(340)

    assert requested.count() == 1
    assert succeeded.count() == 0
    payload = requested.at(0)[0]
    assert payload["challengeToken"] == "dynamic-target-token"
    assert payload["answer"]["targetId"] == "moving-target-a"
    assert payload["answer"]["pathId"] == "path-v3"
    assert 1 <= len(payload["answer"]["trace"]) <= 16
    assert set(payload["answer"]["trace"][0]) == {"x", "y", "t"}
    assert payload["behavior"]["followRatio"] >= 0.78
    assert payload["behavior"]["sampleCount"] >= len(payload["answer"]["trace"])
    assert card.resolveServerVerification(payload["attemptId"], True) is True
    assert succeeded.count() == 1


def test_short_memory_challenge_uses_opaque_ids_in_server_payload(qapp):
    cell_ids = [f"opaque-cell-{index}" for index in range(9)]
    sequence = [0, 5, 2, 7]
    card = ShortMemoryCard(
        sequence_length=4,
        sequence_indices=sequence,
        cell_ids=cell_ids,
        sequence_id="server-memory-v2",
        require_server_verification=True,
        challenge_token="short-memory-token",
        server_timeout_seconds=60,
    )
    card.verifyImage.finishPresentation()
    requested = QSignalSpy(card.verificationRequested)
    succeeded = QSignalSpy(card.verificationSuccess)

    for index in sequence:
        card.verifyImage.selectCell(index)

    assert requested.count() == 1
    assert succeeded.count() == 0
    payload = requested.at(0)[0]
    assert payload["challengeToken"] == "short-memory-token"
    assert payload["answer"] == {
        "sequenceId": "server-memory-v2",
        "cellIds": [cell_ids[index] for index in sequence],
    }
    assert payload["behavior"]["sequenceLength"] == 4
    assert payload["behavior"]["selectionCount"] == 4
    assert payload["behavior"]["inputMethod"] == "pointer"
    assert card.resolveServerVerification(payload["attemptId"], True) is True
    assert succeeded.count() == 1
