from PySide6.QtCore import QAbstractAnimation
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
