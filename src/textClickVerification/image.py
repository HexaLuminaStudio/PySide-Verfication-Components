import sys
import random
from typing import List

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
)
from PySide6.QtCore import (
    Qt,
    QPropertyAnimation,
    Signal,
    QPoint,
    QRectF,
)
from PySide6.QtGui import (
    QPixmap,
    QPainter,
    QColor,
    QPen,
    QPainterPath,
    QMouseEvent,
    QBrush,
)

from ..components.background import procedural_background
from ..components.glyphs import draw_text_challenge
from ..components.rendering import cover_pixmap, effective_dpr


class VerificationImage(QWidget):
    clickSignal = Signal(int, int)
    verificationComplete = Signal(bool, list)

    def __init__(self, imageList: List[QPixmap] | None = None, parent=None):
        super().__init__(parent=parent)
        self.imageList = list(imageList or [])

        self._width = 300
        self._height = 169
        self._dpr = effective_dpr(self)
        self.setFixedSize(self._width, self._height)

        self.characters = "一二三四五六七八九十甲乙丙丁戊己庚辛壬癸"
        self.fontSizeRange = (20, 35)
        self.fontColors = [
            QColor(0, 0, 0),
            QColor(255, 0, 0),
            QColor(0, 255, 0),
            QColor(0, 0, 255),
            QColor(255, 255, 0),
            QColor(255, 0, 255),
            QColor(0, 255, 255),
        ]

        self.targetChars = []
        self.targetPositions = []
        self.userClicks = []
        self.verificationText = ""

        self.generateImage()

    def generateImage(self):
        if self.imageList:
            self.currentImage = cover_pixmap(
                random.choice(self.imageList), self._width, self._height, dpr=self._dpr
            )
        else:
            self.currentImage = procedural_background(
                self._width, self._height, dpr=self._dpr
            )
        placements = draw_text_challenge(
            self.currentImage,
            width=self._width,
            height=self._height,
            characters=self.characters,
            font_size_range=self.fontSizeRange,
        )
        if placements:
            targets = random.sample(placements, min(3, len(placements)))
            self.targetChars = [target.character for target in targets]
            self.targetPositions = [target.bounds.center().toPoint() for target in targets]
            self.verificationText = "点击: " + " ".join(self.targetChars)
        else:
            self.targetChars = []
            self.targetPositions = []
            self.verificationText = "点击: 无"

        self.userClicks = []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        path = QPainterPath()
        rect = QRectF(0, 0, self._width, self._height)
        path.addRoundedRect(rect, 5, 5)
        painter.setClipPath(path)
        painter.drawPixmap(QPoint(0, 0), self.currentImage)

        for i, pos in enumerate(self.userClicks):
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.setBrush(QBrush(QColor(255, 0, 0, 50)))
            painter.drawEllipse(pos, 10, 10)
            painter.drawText(pos.x() + 15, pos.y() + 5, str(i + 1))

        super().paintEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            self.userClicks.append(pos)
            self.update()

            if len(self.userClicks) == len(self.targetChars):
                self.verify()

    def verify(self):
        if len(self.userClicks) != len(self.targetPositions):
            self.verificationComplete.emit(False, [])
            return

        tolerance = 20
        correct = []
        for i, (userPos, targetPos) in enumerate(zip(self.userClicks, self.targetPositions)):
            distance = ((userPos.x() - targetPos.x()) ** 2 + (userPos.y() - targetPos.y()) ** 2) ** 0.5
            if distance <= tolerance:
                correct.append(i)

        success = len(correct) == len(self.targetChars)
        self.verificationComplete.emit(success, correct)

    def reset(self):
        self.generateImage()

    def refreshImage(self):
        if hasattr(self, "animation") and self.animation.state() == QPropertyAnimation.State.Running:
            self.animation.stop()
            self.animation.deleteLater()
            delattr(self, "animation")
        self.generateImage()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = QWidget()
    window.setWindowTitle("文字点选验证码测试")
    layout = QVBoxLayout(window)

    v_image = VerificationImage()
    layout.addWidget(v_image)

    def on_verification_complete(success, correct):
        print(f"验证结果: {'成功' if success else '失败'}")
        print(f"正确点击: {correct}")

    v_image.verificationComplete.connect(on_verification_complete)

    window.show()
    sys.exit(app.exec())
