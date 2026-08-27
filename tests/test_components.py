from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtTest import QSignalSpy, QTest

from pyside_verification import (
    BasicSliderCard,
    BasicSliderFlyout,
    CircleSliderCard,
    FigureSliderCard,
    IconClickCard,
    TextClickCard,
)


def test_all_cards_construct_offline(qapp):
    cards = [
        BasicSliderCard(),
        FigureSliderCard(),
        CircleSliderCard(),
        TextClickCard(),
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
