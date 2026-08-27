
from typing import Union

from PySide6.QtCore import (
    Qt,
    QPropertyAnimation,
    QPoint,
    QParallelAnimationGroup,
    QEasingCurve,
    QMargins,
    QObject,
    Signal,
    QRect,
)
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import (
    QWidget,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QVBoxLayout,
    QApplication,
)


class FlyoutView(QWidget):
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._bgColor = QColor(255, 255, 255)
        self._borderColor = QColor(0, 0, 0, 50)
        self._borderRadius = 5

        self.vBoxLayout = QVBoxLayout(self)
        self.viewLayout = QHBoxLayout()
        self.widgetLayout = QVBoxLayout()

        self.vBoxLayout.setContentsMargins(1, 1, 1, 1)
        self.vBoxLayout.setSpacing(0)
        self.widgetLayout.setContentsMargins(0, 8, 0, 8)
        self.widgetLayout.setSpacing(0)
        self.viewLayout.setSpacing(4)

        self.vBoxLayout.addLayout(self.viewLayout)
        self.viewLayout.addLayout(self.widgetLayout)

        margins = QMargins(6, 5, 6, 5)
        margins.setLeft(20)
        margins.setRight(20)
        self.viewLayout.setContentsMargins(margins)

    def addWidget(self, widget: QWidget, stretch=0, align=Qt.AlignLeft):
        self.widgetLayout.addSpacing(8)
        self.widgetLayout.addWidget(widget, stretch, align)

    def showEvent(self, e):
        super().showEvent(e)
        self.adjustSize()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing)
        painter.setBrush(self._bgColor)
        painter.setPen(self._borderColor)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(rect, self._borderRadius, self._borderRadius)


class Flyout(QWidget):
    closed = Signal()

    def __init__(
        self,
        view: FlyoutView,
        parent=None,
        isDeleteOnClose=True,
    ):
        super().__init__(parent=parent)
        self.view = view
        self.hBoxLayout = QHBoxLayout(self)
        self.aniManager = None
        self.isDeleteOnClose = isDeleteOnClose

        self.hBoxLayout.setContentsMargins(10, 10, 10, 10)
        self.hBoxLayout.addWidget(self.view)

        self._shadowBlurRadius = 80
        self._shadowOffset = (4, 4)
        self._shadowColor = QColor(0, 0, 0, 30)

        self.setShadowEffect()

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        )

    def setShadowEffect(self, blurRadius=None, offset=None):
        if blurRadius is None:
            blurRadius = self._shadowBlurRadius
        if offset is None:
            offset = self._shadowOffset
        color = self._shadowColor

        self.shadowEffect = QGraphicsDropShadowEffect(self.view)
        self.shadowEffect.setBlurRadius(blurRadius)
        self.shadowEffect.setOffset(*offset)
        self.shadowEffect.setColor(color)
        self.view.setGraphicsEffect(None)
        self.view.setGraphicsEffect(self.shadowEffect)

    def closeEvent(self, e):
        if self.isDeleteOnClose:
            self.deleteLater()
        super().closeEvent(e)
        self.closed.emit()

    def showEvent(self, e):
        self.activateWindow()
        super().showEvent(e)

    def exec(self, pos: QPoint):
        self.aniManager = PullUpFlyoutAnimationManager(self)
        self.show()
        self.aniManager.exec(pos)

    def fadeOut(self):
        self.fadeOutAni = QPropertyAnimation(self, b"windowOpacity", self)
        self.fadeOutAni.finished.connect(self.close)
        self.fadeOutAni.setStartValue(1)
        self.fadeOutAni.setEndValue(0)
        self.fadeOutAni.setDuration(120)
        self.fadeOutAni.start()

    @classmethod
    def create(
        cls,
        target: Union[QWidget, QPoint] = None,
        parent=None,
        isDeleteOnClose=True,
    ):
        view = FlyoutView()
        w = cls(view, parent, isDeleteOnClose)

        if target is not None:
            w.show()
            if isinstance(target, QWidget):
                target = PullUpFlyoutAnimationManager(w).position(target)
            w.exec(target)

        view.closed.connect(w.close)
        return w


class FlyoutAnimationManager(QObject):
    def __init__(self, flyout: Flyout):
        super().__init__()
        self.flyout = flyout
        self.aniGroup = QParallelAnimationGroup(self)
        self.slideAni = QPropertyAnimation(flyout, b"pos", self)
        self.opacityAni = QPropertyAnimation(flyout, b"windowOpacity", self)

        self.slideAni.setDuration(187)
        self.opacityAni.setDuration(187)

        self.opacityAni.setStartValue(0)
        self.opacityAni.setEndValue(1)

        self.slideAni.setEasingCurve(QEasingCurve.OutQuad)
        self.opacityAni.setEasingCurve(QEasingCurve.OutQuad)
        self.aniGroup.addAnimation(self.slideAni)
        self.aniGroup.addAnimation(self.opacityAni)

    def exec(self, pos: QPoint):
        raise NotImplementedError

    def _adjustPosition(self, pos):
        screen = QApplication.screenAt(pos) or QApplication.primaryScreen()
        rect = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        w, h = self.flyout.sizeHint().width() + 5, self.flyout.sizeHint().height()
        x = max(rect.left(), min(pos.x(), rect.right() - w))
        y = max(rect.top(), min(pos.y() - 4, rect.bottom() - h + 5))
        return QPoint(x, y)

    def position(self, target: QWidget):
        raise NotImplementedError


class PullUpFlyoutAnimationManager(FlyoutAnimationManager):
    def position(self, target: QWidget):
        w = self.flyout
        pos = target.mapToGlobal(QPoint())
        x = pos.x() + target.width() // 2 - w.sizeHint().width() // 2
        y = pos.y() - w.sizeHint().height() + w.layout().contentsMargins().bottom()
        return QPoint(x, y)

    def exec(self, pos: QPoint):
        pos = self._adjustPosition(pos)
        self.slideAni.setStartValue(pos + QPoint(0, 8))
        self.slideAni.setEndValue(pos)
        self.aniGroup.start()
