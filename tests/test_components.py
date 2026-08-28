import math

import pytest

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtTest import QSignalSpy, QTest

from pyside_verification import (
    BasicSliderCard,
    BasicSliderFlyout,
    CircleSliderCard,
    ConditionRegionCard,
    DragMatchCard,
    DynamicTargetCard,
    FigureSliderCard,
    IconClickCard,
    PathTraceCard,
    RotateSliderCard,
    ShortMemoryCard,
    TextClickCard,
    TileOrderCard,
)


def test_all_cards_construct_offline(qapp):
    cards = [
        BasicSliderCard(),
        FigureSliderCard(),
        CircleSliderCard(),
        ConditionRegionCard(),
        DragMatchCard(),
        DynamicTargetCard(),
        PathTraceCard(),
        RotateSliderCard(),
        ShortMemoryCard(),
        TextClickCard(),
        TileOrderCard(),
        IconClickCard(),
    ]
    assert all(card.sizeHint().width() == 300 for card in cards)
    assert all(not getattr(card.verifyImage, "loading", False) for card in cards)


def test_all_cards_show_plain_language_instructions(qapp):
    cards_and_actions = [
        (BasicSliderCard(), "让拼图块对准缺口"),
        (FigureSliderCard(), "让彩色图形与轮廓重合"),
        (CircleSliderCard(), "旋转圆环并拼合图案"),
        (ConditionRegionCard(), "请选择所有"),
        (DragMatchCard(), "拖入相同的虚线轮廓"),
        (DynamicTargetCard(), "持续跟随至进度完成"),
        (PathTraceCard(), "沿虚线拖到绿色终点"),
        (RotateSliderCard(), "旋转至正常方向"),
        (ShortMemoryCard(), "提示消失后依次点击"),
        (TextClickCard(), "依次点击："),
        (TileOrderCard(), "还原完整图片"),
        (IconClickCard(), "依次点击："),
    ]

    for card, expected_action in cards_and_actions:
        text = card.instructionLabel.text()
        assert expected_action in text
        assert card.instructionLabel.wordWrap()
        assert card.instructionLabel.accessibleName() == "操作说明"
        assert card.instructionLabel.accessibleDescription()


def test_condition_instruction_names_the_current_target(qapp):
    card = make_condition_region_card()

    assert "请选择所有蓝色圆形区域（2 个）" in card.instructionLabel.text()
    assert "点击勾号确认" in card.instructionLabel.accessibleDescription()


def test_click_challenges_accept_the_generated_targets(qapp):
    for card_class in (TextClickCard, IconClickCard):
        card = card_class()
        spy = QSignalSpy(card.verificationSuccess)
        card.verifyImage.userClicks = list(card.verifyImage.targetPositions)
        card.verifyImage.verify()
        assert spy.count() == 1


def test_circle_challenge_can_reach_its_target(qapp):
    card = CircleSliderCard()
    mapped = card.verifyImage.gapAngle / (2 * 3.141592653589793) * 300
    card.verifyImage.setAngle(mapped)
    assert card.verifyImage.verify()


def test_rotate_challenge_can_reach_its_upright_angle(qapp):
    card = RotateSliderCard(initial_angle_degrees=137)
    correct_value = card.verifyImage.getCorrectValue()

    card.verifyImage.setAngle(correct_value)

    assert card.verifyImage.verify()
    assert abs(card.verifyImage.currentAngle) < 1e-9


def test_rotate_challenge_rejects_an_incorrect_angle(qapp):
    card = RotateSliderCard(
        initial_angle_degrees=90,
        angle_tolerance_degrees=6,
    )

    card.verifyImage.setAngle(0)

    assert not card.verifyImage.verify()


def test_tile_order_challenge_completes_after_correct_swap(qapp):
    card = TileOrderCard(
        initial_order=[1, 0, 2, 3],
        animation_duration_ms=120,
    )
    spy = QSignalSpy(card.verificationSuccess)

    assert card.verifyImage.swapTiles(0, 1)
    assert spy.count() == 0
    assert card.verifyImage.order == [1, 0, 2, 3]
    QTest.qWait(170)

    assert spy.count() == 1
    assert card.verifyImage.answer() == ["0", "1", "2", "3"]


def test_tile_order_challenge_supports_keyboard_reordering(qapp):
    card = TileOrderCard(
        initial_order=[1, 0, 2, 3],
        animation_duration_ms=120,
    )
    card.show()
    card.verifyImage.setFocus()
    spy = QSignalSpy(card.verificationSuccess)

    QTest.keyClick(card.verifyImage, Qt.Key.Key_Space)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Right)
    QTest.qWait(170)

    assert spy.count() == 1
    assert card.verifyImage.inputMethod == "keyboard"


def test_tile_order_challenge_supports_pointer_dragging(qapp):
    card = TileOrderCard(
        initial_order=[1, 0, 2, 3],
        animation_duration_ms=120,
    )
    card.show()
    spy = QSignalSpy(card.verificationSuccess)

    QTest.mousePress(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(37, 84),
    )
    QTest.mouseMove(card.verifyImage, QPoint(112, 84))
    QTest.mouseRelease(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(112, 84),
    )
    QTest.qWait(170)

    assert spy.count() == 1
    assert card.verifyImage.inputMethod == "pointer"


def test_tile_order_animation_can_be_disabled(qapp):
    card = TileOrderCard(
        initial_order=[1, 0, 2, 3],
        animation_duration_ms=0,
    )
    spy = QSignalSpy(card.verificationSuccess)

    assert card.verifyImage.swapTiles(0, 1)

    assert spy.count() == 1
    assert card.verifyImage.getSwapProgress() == 0.0


def test_tile_order_animation_blocks_overlapping_swaps(qapp):
    card = TileOrderCard(
        initial_order=[1, 0, 2, 3],
        animation_duration_ms=120,
    )

    assert card.verifyImage.swapTiles(0, 1)
    assert not card.verifyImage.swapTiles(2, 3)
    QTest.qWait(170)

    assert card.verifyImage.order == [0, 1, 2, 3]
    assert card.verifyImage.moveCount == 1


def test_tile_order_refresh_interrupts_pending_animation(qapp):
    card = TileOrderCard(
        initial_order=[1, 0, 2, 3],
        animation_duration_ms=120,
    )
    spy = QSignalSpy(card.verificationSuccess)

    assert card.verifyImage.swapTiles(0, 1)
    card.verifyImage.refreshImage()
    QTest.qWait(170)

    assert spy.count() == 0
    assert card.verifyImage.order == [1, 0, 2, 3]
    assert card.verifyImage.moveCount == 0


def test_tile_order_rejects_invalid_fixed_order(qapp):
    try:
        TileOrderCard(initial_order=[0, 1, 2, 3])
    except ValueError as error:
        assert "不能已经是正确顺序" in str(error)
    else:
        raise AssertionError("已经完成的初始排列必须被拒绝")


def test_drag_match_challenge_completes_after_all_shapes_are_placed(qapp):
    card = DragMatchCard(
        shape_types=["circle", "triangle", "star"],
        target_order=[1, 2, 0],
        animation_duration_ms=0,
    )
    spy = QSignalSpy(card.verificationSuccess)

    for shape_index in range(3):
        assert card.verifyImage.attemptPlacement(
            shape_index,
            card.verifyImage.targetForShape(shape_index),
            animated=False,
        )

    assert spy.count() == 1
    assert len(card.verifyImage.answer()) == 3


def test_drag_match_wrong_target_returns_shape_to_source(qapp):
    card = DragMatchCard(
        shape_types=["circle", "triangle", "star"],
        target_order=[1, 2, 0],
        animation_duration_ms=0,
    )
    rejected = QSignalSpy(card.verifyImage.placementRejected)
    shape = card.verifyImage.shapes[0]

    assert not card.verifyImage.attemptPlacement(0, 0, animated=False)

    assert rejected.count() == 1
    assert shape.placed_slot is None
    assert shape.current_center == shape.source_center
    assert card.verifyImage.missCount == 1


def test_drag_match_correct_target_uses_snap_animation(qapp):
    card = DragMatchCard(
        shape_types=["circle", "triangle", "star"],
        target_order=[1, 2, 0],
        animation_duration_ms=120,
    )
    shape = card.verifyImage.shapes[0]

    assert card.verifyImage.attemptPlacement(
        0,
        card.verifyImage.targetForShape(0),
    )
    assert shape.placed_slot is None
    QTest.qWait(170)

    assert shape.placed_slot == 2
    assert shape.current_center == card.verifyImage.targetCenters[2]


def test_drag_match_refresh_interrupts_pending_snap(qapp):
    card = DragMatchCard(
        shape_types=["circle", "triangle", "star"],
        target_order=[1, 2, 0],
        animation_duration_ms=120,
    )

    assert card.verifyImage.attemptPlacement(0, 2)
    card.verifyImage.refreshImage()
    QTest.qWait(170)

    assert all(shape.placed_slot is None for shape in card.verifyImage.shapes)
    assert card.verifyImage.moveCount == 0


def test_drag_match_challenge_supports_keyboard_placement(qapp):
    card = DragMatchCard(
        shape_types=["circle", "triangle", "star"],
        target_order=[1, 2, 0],
        animation_duration_ms=0,
    )
    card.show()
    card.verifyImage.setFocus()
    spy = QSignalSpy(card.verificationSuccess)

    QTest.keyClick(card.verifyImage, Qt.Key.Key_Space)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Right)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Right)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Space)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Space)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Space)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Space)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Right)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Space)

    assert spy.count() == 1
    assert card.verifyImage.inputMethod == "keyboard"


def test_drag_match_challenge_supports_pointer_placement(qapp):
    card = DragMatchCard(
        shape_count=2,
        shape_types=["circle", "triangle"],
        target_order=[1, 0],
        animation_duration_ms=0,
    )
    card.show()
    spy = QSignalSpy(card.verificationSuccess)

    for shape_index in range(2):
        source = card.verifyImage.shapes[shape_index].source_center.toPoint()
        target = card.verifyImage.targetCenters[
            card.verifyImage.targetForShape(shape_index)
        ].toPoint()
        QTest.mousePress(
            card.verifyImage,
            Qt.MouseButton.LeftButton,
            pos=source,
        )
        QTest.mouseMove(card.verifyImage, target)
        QTest.mouseRelease(
            card.verifyImage,
            Qt.MouseButton.LeftButton,
            pos=target,
        )

    assert spy.count() == 1
    assert card.verifyImage.inputMethod == "pointer"


TRACE_NODES = [(30, 80), (90, 42), (150, 126), (210, 48), (270, 88)]


def test_path_trace_challenge_completes_with_continuous_pointer_path(qapp):
    card = PathTraceCard(node_count=5, nodes=TRACE_NODES)
    card.show()
    succeeded = QSignalSpy(card.verificationSuccess)

    QTest.mousePress(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(*TRACE_NODES[0]),
    )
    for point in TRACE_NODES[1:]:
        QTest.mouseMove(card.verifyImage, QPoint(*point))
    QTest.mouseRelease(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(*TRACE_NODES[-1]),
    )

    assert succeeded.count() == 1
    assert card.verifyImage.reachedCount == 5
    assert card.verifyImage.inputMethod == "pointer"


def test_path_trace_fast_segment_cannot_skip_intermediate_nodes(qapp):
    straight_nodes = [(30, 84), (90, 84), (150, 84), (210, 84), (270, 84)]
    card = PathTraceCard(node_count=5, nodes=straight_nodes)
    card.show()
    succeeded = QSignalSpy(card.verificationSuccess)

    QTest.mousePress(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(*straight_nodes[0]),
    )
    QTest.mouseMove(card.verifyImage, QPoint(*straight_nodes[-1]))
    QTest.mouseRelease(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(*straight_nodes[-1]),
    )

    assert succeeded.count() == 1
    assert card.verifyImage.reachedCount == 5


def test_path_trace_rejects_area_filling_even_if_nodes_are_crossed(qapp):
    card = PathTraceCard(node_count=5, nodes=TRACE_NODES)
    card.show()
    rejected = QSignalSpy(card.verifyImage.pathRejected)
    succeeded = QSignalSpy(card.verificationSuccess)

    QTest.mousePress(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(*TRACE_NODES[0]),
    )
    QTest.mouseMove(card.verifyImage, QPoint(30, 150))
    for point in TRACE_NODES[1:]:
        QTest.mouseMove(card.verifyImage, QPoint(*point))
    QTest.mouseRelease(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(*TRACE_NODES[-1]),
    )

    assert rejected.count() == 1
    assert "偏离" in rejected.at(0)[0]
    assert succeeded.count() == 0
    assert card.verifyImage.reachedCount == 0


def test_path_trace_rejects_shortcut_across_a_zigzag_route(qapp):
    card = PathTraceCard(node_count=5, nodes=TRACE_NODES)
    card.show()
    rejected = QSignalSpy(card.verifyImage.pathRejected)

    QTest.mousePress(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(*TRACE_NODES[0]),
    )
    QTest.mouseMove(card.verifyImage, QPoint(*TRACE_NODES[-1]))

    assert rejected.count() == 1
    assert card.verifyImage.trace == []


def test_path_trace_rejects_large_backtracking_on_the_route(qapp):
    straight_nodes = [(30, 84), (90, 84), (150, 84), (210, 84), (270, 84)]
    card = PathTraceCard(node_count=5, nodes=straight_nodes)
    card.show()
    rejected = QSignalSpy(card.verifyImage.pathRejected)

    QTest.mousePress(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(*straight_nodes[0]),
    )
    QTest.mouseMove(card.verifyImage, QPoint(*straight_nodes[2]))
    QTest.mouseMove(card.verifyImage, QPoint(*straight_nodes[0]))

    assert rejected.count() == 1
    assert card.verifyImage.reachedCount == 0


def test_path_trace_allows_small_natural_pointer_deviation(qapp):
    straight_nodes = [(30, 84), (90, 84), (150, 84), (210, 84), (270, 84)]
    card = PathTraceCard(node_count=5, nodes=straight_nodes, path_tolerance=14)
    card.show()
    succeeded = QSignalSpy(card.verificationSuccess)

    QTest.mousePress(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(*straight_nodes[0]),
    )
    for x, y in straight_nodes[1:]:
        QTest.mouseMove(card.verifyImage, QPoint(x, y + 8))
    QTest.mouseRelease(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(*straight_nodes[-1]),
    )

    assert succeeded.count() == 1


def test_path_trace_rejects_drawing_after_reaching_the_end(qapp):
    straight_nodes = [(30, 84), (90, 84), (150, 84), (210, 84), (270, 84)]
    card = PathTraceCard(node_count=5, nodes=straight_nodes)
    card.show()
    rejected = QSignalSpy(card.verifyImage.pathRejected)
    succeeded = QSignalSpy(card.verificationSuccess)

    QTest.mousePress(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(*straight_nodes[0]),
    )
    QTest.mouseMove(card.verifyImage, QPoint(*straight_nodes[-1]))
    QTest.mouseMove(card.verifyImage, QPoint(270, 140))
    QTest.mouseRelease(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(270, 140),
    )

    assert rejected.count() == 1
    assert succeeded.count() == 0


def test_path_trace_rejects_wrong_start_without_replacing_challenge(qapp):
    card = PathTraceCard(node_count=5, nodes=TRACE_NODES)
    card.show()
    rejected = QSignalSpy(card.verifyImage.pathRejected)
    original_nodes = [point.toTuple() for point in card.verifyImage.nodes]

    QTest.mouseClick(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(150, 80),
    )

    assert rejected.count() == 1
    assert [point.toTuple() for point in card.verifyImage.nodes] == original_nodes
    assert card.verifyImage.reachedCount == 0
    assert card.verifyImage.missCount == 1


def test_path_trace_incomplete_release_resets_current_trace(qapp):
    card = PathTraceCard(node_count=5, nodes=TRACE_NODES)
    card.show()
    rejected = QSignalSpy(card.verifyImage.pathRejected)

    QTest.mousePress(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(*TRACE_NODES[0]),
    )
    QTest.mouseMove(card.verifyImage, QPoint(*TRACE_NODES[1]))
    QTest.mouseRelease(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(*TRACE_NODES[1]),
    )

    assert rejected.count() == 1
    assert card.verifyImage.trace == []
    assert card.verifyImage.reachedCount == 0
    assert card.verifyImage.missCount == 1


def test_path_trace_challenge_supports_keyboard_completion(qapp):
    card = PathTraceCard(node_count=5, nodes=TRACE_NODES)
    card.show()
    card.verifyImage.setFocus()
    succeeded = QSignalSpy(card.verificationSuccess)

    QTest.keyClick(card.verifyImage, Qt.Key.Key_Space)
    for _index in range(4):
        QTest.keyClick(card.verifyImage, Qt.Key.Key_Right)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Space)

    assert succeeded.count() == 1
    assert card.verifyImage.inputMethod == "keyboard"


def test_path_trace_rejects_invalid_fixed_nodes(qapp):
    with pytest.raises(ValueError, match="数量"):
        PathTraceCard(node_count=5, nodes=TRACE_NODES[:4])
    with pytest.raises(ValueError, match="距离过近"):
        PathTraceCard(
            node_count=4,
            nodes=[(30, 40), (45, 40), (150, 80), (260, 100)],
        )
    with pytest.raises(ValueError, match="有限数值"):
        PathTraceCard(path_tolerance=float("nan"))


CONDITION_REGIONS = [
    {"region_id": "area-a", "color": "blue", "shape": "circle"},
    {"region_id": "area-b", "color": "blue", "shape": "circle"},
    {"region_id": "area-c", "color": "blue", "shape": "triangle"},
    {"region_id": "area-d", "color": "green", "shape": "circle"},
    {"region_id": "area-e", "color": "orange", "shape": "square"},
    {"region_id": "area-f", "color": "purple", "shape": "diamond"},
]


def make_condition_region_card(**kwargs):
    return ConditionRegionCard(
        region_count=6,
        regions=CONDITION_REGIONS,
        condition_color="blue",
        condition_shape="circle",
        **kwargs,
    )


def test_condition_region_mouse_selection_requires_explicit_confirmation(qapp):
    card = make_condition_region_card()
    card.show()
    succeeded = QSignalSpy(card.verificationSuccess)

    for index in (0, 1):
        QTest.mouseClick(
            card.verifyImage,
            Qt.MouseButton.LeftButton,
            pos=card.verifyImage.regionBounds[index].center().toPoint(),
        )

    assert succeeded.count() == 0
    card.submitButton.click()

    assert succeeded.count() == 1
    assert card.verifyImage.answer() == ["area-a", "area-b"]


def test_condition_region_selection_can_be_toggled_before_submit(qapp):
    card = make_condition_region_card()

    assert card.verifyImage.toggleRegion(0)
    assert card.verifyImage.toggleRegion(2)
    assert card.verifyImage.toggleRegion(2)
    assert card.verifyImage.toggleRegion(1)

    assert card.verifyImage.answer() == ["area-a", "area-b"]
    assert card.verifyImage.deselectionCount == 1


def test_condition_region_wrong_selection_is_rejected(qapp):
    card = make_condition_region_card()
    failed = QSignalSpy(card.verificationFailed)

    card.verifyImage.toggleRegion(0)
    card.verifyImage.toggleRegion(2)
    card.submitButton.click()

    assert failed.count() == 1
    assert card.verifyImage.selectedIds == []


def test_condition_region_supports_keyboard_selection_and_submit(qapp):
    card = make_condition_region_card()
    card.show()
    card.verifyImage.setFocus()
    succeeded = QSignalSpy(card.verificationSuccess)

    QTest.keyClick(card.verifyImage, Qt.Key.Key_Space)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Right)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Space)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Return)

    assert succeeded.count() == 1
    assert card.verifyImage.inputMethod == "keyboard"


def test_condition_region_validates_server_supplied_regions(qapp):
    with pytest.raises(ValueError, match="数量"):
        ConditionRegionCard(
            region_count=6,
            regions=CONDITION_REGIONS[:5],
            condition_color="blue",
        )
    with pytest.raises(ValueError, match="至少一个筛选条件"):
        ConditionRegionCard(region_count=6, regions=CONDITION_REGIONS)
    with pytest.raises(ValueError, match="部分但不是全部"):
        ConditionRegionCard(
            region_count=6,
            regions=CONDITION_REGIONS,
            condition_color="blue",
            condition_shape="hexagon",
        )


TRACKING_WAYPOINTS = [(100, 80), (118, 80), (100, 80), (118, 80)]


def test_dynamic_target_follows_smooth_fixed_path(qapp):
    card = DynamicTargetCard(waypoints=TRACKING_WAYPOINTS)

    assert card.verifyImage.targetPositionAt(0) == QPointF(100, 80)
    assert card.verifyImage.targetPositionAt(1) == QPointF(118, 80)
    midpoint = card.verifyImage.targetPositionAt(0.5)
    assert 100 <= midpoint.x() <= 118
    assert midpoint.y() == 80


def test_dynamic_target_default_speed_is_length_based_and_comfortable(qapp):
    card = DynamicTargetCard(
        waypoints=[(70, 82), (122, 38), (190, 52), (236, 118), (154, 132)],
    )
    image = card.verifyImage

    assert 4.5 <= image.trackingDuration <= 8.0
    assert image.pathLength / image.trackingDuration <= 60.01
    steps = [image.targetPositionAt(index / 100) for index in range(101)]
    distances = [
        math.hypot(end.x() - start.x(), end.y() - start.y())
        for start, end in zip(steps, steps[1:])
    ]
    assert max(distances) <= image.pathLength / 100 * 1.02


def test_dynamic_target_reduced_motion_caps_automatic_speed(qapp):
    card = DynamicTargetCard(
        waypoints=[(70, 82), (122, 38), (190, 52), (236, 118), (154, 132)],
        reduced_motion=True,
    )

    assert card.verifyImage.pathLength / card.verifyImage.trackingDuration <= 45.01


def test_dynamic_target_completes_when_pointer_stays_within_target(qapp):
    card = DynamicTargetCard(
        waypoints=TRACKING_WAYPOINTS,
        tracking_duration=0.25,
        tracking_radius=24,
    )
    succeeded = QSignalSpy(card.verificationSuccess)

    assert card.verifyImage.startTracking(QPointF(100, 80))
    QTest.qWait(340)

    assert succeeded.count() == 1
    assert card.verifyImage.followRatio >= card.verifyImage.minFollowRatio


def test_dynamic_target_rejects_starting_outside_target(qapp):
    card = DynamicTargetCard(waypoints=TRACKING_WAYPOINTS)
    rejected = QSignalSpy(card.verifyImage.trackingRejected)

    assert not card.verifyImage.startTracking(QPointF(20, 20))

    assert rejected.count() == 1
    assert "目标" in rejected.at(0)[0]


def test_dynamic_target_rejects_large_pointer_deviation(qapp):
    card = DynamicTargetCard(
        waypoints=TRACKING_WAYPOINTS,
        hard_miss_radius=60,
    )
    rejected = QSignalSpy(card.verifyImage.trackingRejected)

    assert card.verifyImage.startTracking(QPointF(100, 80))
    card.verifyImage.updatePointer(QPointF(0, 0))
    card.verifyImage._tick()

    assert rejected.count() == 1
    assert "过远" in rejected.at(0)[0]


def test_dynamic_target_mouse_release_before_completion_fails(qapp):
    card = DynamicTargetCard(
        waypoints=TRACKING_WAYPOINTS,
        tracking_duration=0.5,
    )
    card.show()
    failed = QSignalSpy(card.verificationFailed)

    QTest.mousePress(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(100, 80),
    )
    QTest.mouseRelease(
        card.verifyImage,
        Qt.MouseButton.LeftButton,
        pos=QPoint(100, 80),
    )

    assert failed.count() == 1
    assert "提前结束" in failed.at(0)[0]


def test_dynamic_target_supports_keyboard_tracking(qapp):
    card = DynamicTargetCard(
        waypoints=TRACKING_WAYPOINTS,
        tracking_duration=0.25,
        tracking_radius=32,
    )
    card.show()
    card.verifyImage.setFocus()
    succeeded = QSignalSpy(card.verificationSuccess)

    QTest.keyClick(card.verifyImage, Qt.Key.Key_Space)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Right)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Left)
    QTest.qWait(340)

    assert succeeded.count() == 1
    assert card.verifyImage.inputMethod == "keyboard"


def test_dynamic_target_validates_path_configuration(qapp):
    with pytest.raises(ValueError, match="4 到 8"):
        DynamicTargetCard(waypoints=TRACKING_WAYPOINTS[:3])
    with pytest.raises(ValueError, match="实际移动路径"):
        DynamicTargetCard(waypoints=[(100, 80)] * 4)
    with pytest.raises(ValueError, match="有限数值"):
        DynamicTargetCard(min_follow_ratio=float("nan"))


MEMORY_SEQUENCE = [0, 5, 2, 7]
MEMORY_CELL_IDS = [f"memory-cell-{index}" for index in range(9)]


def make_short_memory_card(**kwargs):
    return ShortMemoryCard(
        sequence_length=4,
        sequence_indices=MEMORY_SEQUENCE,
        cell_ids=MEMORY_CELL_IDS,
        sequence_id="memory-sequence-a",
        **kwargs,
    )


def test_short_memory_ignores_input_until_recall_phase(qapp):
    card = make_short_memory_card()

    assert card.verifyImage.phase == "ready"
    assert not card.verifyImage.selectCell(0)
    assert card.verifyImage.userSequence == []


def test_short_memory_presentation_advances_to_recall(qapp):
    card = ShortMemoryCard(
        sequence_length=3,
        sequence_indices=[0, 1, 4],
        ready_delay_ms=0,
        flash_duration_ms=80,
        gap_duration_ms=30,
    )
    card.show()

    QTest.qWait(420)

    assert card.verifyImage.phase == "recall"
    assert card.verifyImage.activePresentationIndex is None


def test_short_memory_mouse_reproduces_sequence_in_order(qapp):
    card = make_short_memory_card()
    card.show()
    card.verifyImage.finishPresentation()
    succeeded = QSignalSpy(card.verificationSuccess)

    for index in MEMORY_SEQUENCE:
        QTest.mouseClick(
            card.verifyImage,
            Qt.MouseButton.LeftButton,
            pos=card.verifyImage.cellBounds[index].center().toPoint(),
        )

    assert succeeded.count() == 1
    assert card.verifyImage.answer() == {
        "sequenceId": "memory-sequence-a",
        "cellIds": [MEMORY_CELL_IDS[index] for index in MEMORY_SEQUENCE],
    }


def test_short_memory_wrong_order_is_rejected_immediately(qapp):
    card = make_short_memory_card()
    card.verifyImage.finishPresentation()
    failed = QSignalSpy(card.verificationFailed)

    assert not card.verifyImage.selectCell(1)

    assert failed.count() == 1
    assert "顺序" in failed.at(0)[0]


def test_short_memory_supports_keyboard_recall(qapp):
    card = ShortMemoryCard(
        sequence_length=3,
        sequence_indices=[0, 1, 4],
    )
    card.show()
    card.verifyImage.finishPresentation()
    card.verifyImage.setFocus()
    succeeded = QSignalSpy(card.verificationSuccess)

    QTest.keyClick(card.verifyImage, Qt.Key.Key_Space)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Right)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Space)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Down)
    QTest.keyClick(card.verifyImage, Qt.Key.Key_Space)

    assert succeeded.count() == 1
    assert card.verifyImage.inputMethod == "keyboard"


def test_short_memory_reduced_motion_uses_slower_presentation(qapp):
    card = ShortMemoryCard(reduced_motion=True)

    assert card.verifyImage.readyDelay >= 850
    assert card.verifyImage.flashDuration >= 800
    assert card.verifyImage.gapDuration >= 260


def test_short_memory_validates_server_sequence(qapp):
    with pytest.raises(ValueError, match="3 到 7"):
        ShortMemoryCard(sequence_length=2)
    with pytest.raises(ValueError, match="不能包含重复"):
        ShortMemoryCard(sequence_length=3, sequence_indices=[0, 0, 1])
    with pytest.raises(ValueError, match="9 个唯一"):
        ShortMemoryCard(cell_ids=["same"] * 9)


def test_flyout_can_be_created_without_showing(qapp):
    flyout = BasicSliderFlyout.create()
    assert not flyout.isVisible()
    assert flyout.view.card is not None
    spy = QSignalSpy(flyout.failed)
    flyout.view.card.verificationFailed.emit("测试原因")
    assert spy.count() == 1
    assert spy.at(0) == ["测试原因"]
    flyout.close()


def test_icon_click_uses_the_actual_vector_shape(qapp):
    card = IconClickCard()
    target = card.verifyImage.targetIcons[0]
    assert target.contains(target.bounds.center())
    assert not target.contains(QPoint(target.x - 2, target.y - 2))


def test_legacy_local_image_accepts_a_single_pixmap(qapp):
    from src.basicSliderVerification import LocalVerificationImage

    source = QPixmap(300, 169)
    source.fill(QColor("#123456"))
    image = LocalVerificationImage([source])
    assert image.currentImage.toImage().pixelColor(0, 0) == QColor("#123456")


def test_click_challenge_can_be_completed_from_keyboard(qapp):
    card = IconClickCard()
    card.show()
    card.verifyImage.setFocus()
    spy = QSignalSpy(card.verificationSuccess)
    for position in card.verifyImage.targetPositions:
        card.verifyImage.keyboardCursor = QPoint(position)
        QTest.keyClick(card.verifyImage, Qt.Key.Key_Return)
    assert spy.count() == 1
