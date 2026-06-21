import sys
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QGridLayout,
)

from src.basicSliderVerification import VerificationFlyout as NormalVerificationFlyout
from src.figureSliderVerification import VerificationFlyout as FigureVerificationFlyout
from src.circleSliderVerification import VerificationFlyout as CircleVerificationFlyout
from src.textClickVerification import VerificationFlyout as TextClickVerificationFlyout
from src.iconClickVerification import VerificationFlyout as IconClickVerificationFlyout


class Demo(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("验证码示例")
        # self.setMinimumSize(400, 300)

        layout = QGridLayout(self)

        normalVer = QPushButton("普通滑动验证码", self)
        normalVer.clicked.connect(self.showNormalVer)
        layout.addWidget(normalVer, 0, 0)

        fighureVer = QPushButton("形状滑动验证码", self)
        fighureVer.clicked.connect(self.showFigureVer)
        layout.addWidget(fighureVer, 0, 1)

        circleVer = QPushButton("圆形滑动验证码", self)
        circleVer.clicked.connect(self.showCircleVer)
        layout.addWidget(circleVer, 1, 0)

        textClickVer = QPushButton("文字点选验证码", self)
        textClickVer.clicked.connect(self.showTextClickVer)
        layout.addWidget(textClickVer, 1, 1)

        iconClickVer = QPushButton("图标点选验证码", self)
        iconClickVer.clicked.connect(self.showIconClickVer)
        layout.addWidget(iconClickVer, 2, 0)

    def showNormalVer(self):

        a = NormalVerificationFlyout.create(target=self.sender(), parent=self)
        a.success.connect(lambda: print("普通滑动验证码验证成功"))

    def showFigureVer(self):

        a = FigureVerificationFlyout.create(target=self.sender(), parent=self)
        a.success.connect(lambda: print("形状滑动验证码验证成功"))

    def showCircleVer(self):

        a = CircleVerificationFlyout.create(target=self.sender(), parent=self)
        a.success.connect(lambda: print("圆形滑动验证码验证成功"))

    def showTextClickVer(self):

        a = TextClickVerificationFlyout.create(target=self.sender(), parent=self)
        a.success.connect(lambda: print("文字点选验证码验证成功"))

    def showIconClickVer(self):

        a = IconClickVerificationFlyout.create(target=self.sender(), parent=self)
        a.success.connect(lambda: print("图标点选验证码验证成功"))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    demo = Demo()
    demo.show()
    sys.exit(app.exec())
