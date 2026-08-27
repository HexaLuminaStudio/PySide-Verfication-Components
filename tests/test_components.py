from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtTest import QSignalSpy, QTest

from pyside_verification import (
    BasicSliderCard,
    BasicSliderFlyout,
    CircleSliderCard,
    FigureSliderCard,
    IconClickCard,
    RotateSliderCard,
    TextClickCard,
    TileOrderCard,
)


def test_all_cards_construct_offline(qapp):
    cards = [
        BasicSliderCard(),
        FigureSliderCard(),
        CircleSliderCard(),
        RotateSliderCard(),
        TextClickCard(),
        TileOrderCard(),
        IconClickCard(),
    ]
    assert all(card.sizeHint().width() == 300 for card in cards)
    assert all(not getattr(card.verifyImage, "loading", False) for card in cards)


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
