from PySide6.QtCore import QAbstractAnimation, QPoint, Qt
from PySide6.QtTest import QSignalSpy, QTest

from pyside_verification import BasicSliderCard
from src.components.slider import VerificationSlider


def test_error_feedback_runs_once_and_clears_state(qapp):
    slider = VerificationSlider()
    slider.setValue(180)
    state_changes = QSignalSpy(slider._error_animation.stateChanged)

    slider.showErrorAndReset()
    slider.showErrorAndReset()

    assert slider._state == "error"
    assert not slider.isEnabled()
    assert slider._error_animation.state() == QAbstractAnimation.State.Running
    assert state_changes.count() == 1

    QTest.qWait(600)
    assert slider.getValue() == 0
    assert slider._state == "normal"
    assert slider.isEnabled()
    assert slider.getShakeOffset() == 0


def test_error_return_keeps_puzzle_and_handle_in_sync(qapp):
    card = BasicSliderCard()
    card.verifySlider.setValue(170)
    card._verify({"result": False, "msg": ["测试失败"]})

    QTest.qWait(600)
    assert card.verifySlider.getValue() == 0
    assert card.verifyImage.getMoveX() == 1


def test_reset_safely_interrupts_feedback_animation(qapp):
    slider = VerificationSlider()
    slider.setValue(140)
    slider.showErrorAndReset()
    QTest.qWait(60)
    slider.reset()
    QTest.qWait(560)

    assert slider._error_animation.state() == QAbstractAnimation.State.Stopped
    assert slider._state == "normal"
    assert slider.getValue() == 0
    assert slider.isEnabled()


def test_success_feedback_locks_until_explicit_reset(qapp):
    slider = VerificationSlider()
    slider.setValue(120)
    slider.setSuccess(True)
    QTest.qWait(400)

    assert slider._state == "success"
    assert not slider.isEnabled()
    assert slider.getFeedbackProgress() == 1.0

    slider.reset()
    assert slider._state == "normal"
    assert slider.isEnabled()
    assert slider.getFeedbackProgress() == 0.0


def test_real_mouse_event_sequence_has_valid_timestamps(qapp):
    slider = VerificationSlider()
    slider.show()
    result_spy = QSignalSpy(slider.resultSignal)

    QTest.mousePress(slider, Qt.MouseButton.LeftButton, pos=QPoint(17, 17))
    for delay, position in (
        (18, QPoint(58, 19)),
        (24, QPoint(105, 15)),
        (31, QPoint(166, 20)),
        (39, QPoint(236, 17)),
    ):
        QTest.qWait(delay)
        QTest.mouseMove(slider, position)
    QTest.qWait(22)
    QTest.mouseRelease(
        slider,
        Qt.MouseButton.LeftButton,
        pos=QPoint(236, 17),
    )

    assert result_spy.count() == 1
    result = result_spy.at(0)[0]
    assert result["result"] is True
    assert "轨迹时间戳异常" not in result["msg"]


def test_keyboard_sequence_does_not_duplicate_first_timestamp(qapp):
    slider = VerificationSlider()
    slider.show()
    slider.setFocus()
    result_spy = QSignalSpy(slider.resultSignal)

    for _ in range(4):
        QTest.keyClick(slider, Qt.Key.Key_Right)
        QTest.qWait(5)
    QTest.keyClick(slider, Qt.Key.Key_Return)

    assert result_spy.count() == 1
    result = result_spy.at(0)[0]
    assert result["result"] is True
    assert result["inputMethod"] == "keyboard"
