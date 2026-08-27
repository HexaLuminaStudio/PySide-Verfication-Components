import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from pyside_verification import (
    BasicSliderFlyout,
    CircleSliderFlyout,
    ConditionRegionFlyout,
    DragMatchFlyout,
    FigureSliderFlyout,
    IconClickFlyout,
    PathTraceFlyout,
    RotateSliderFlyout,
    TextClickFlyout,
    TileOrderFlyout,
)


class Demo(QWidget):
    COMPONENTS = (
        ("普通滑动验证码", BasicSliderFlyout),
        ("形状滑动验证码", FigureSliderFlyout),
        ("圆形滑动验证码", CircleSliderFlyout),
        ("图片旋正验证码", RotateSliderFlyout),
        ("图块排序验证码", TileOrderFlyout),
        ("图形拖拽验证码", DragMatchFlyout),
        ("路径描摹验证码", PathTraceFlyout),
        ("条件区域点选", ConditionRegionFlyout),
        ("文字点选验证码", TextClickFlyout),
        ("图标点选验证码", IconClickFlyout),
    )

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PySide 验证码组件")
        self.setMinimumWidth(440)

        title = QLabel("选择一种验证方式", self)
        title.setObjectName("title")
        description = QLabel("组件默认离线运行，也可以在业务代码中传入图片服务地址。", self)
        description.setWordWrap(True)
        description.setObjectName("description")
        self.status = QLabel("尚未开始验证", self)
        self.status.setObjectName("status")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        for index, (label, flyout_class) in enumerate(self.COMPONENTS):
            button = QPushButton(label, self)
            button.setMinimumHeight(42)
            button.clicked.connect(
                lambda _checked=False, source=button, name=label, cls=flyout_class: self.show_verification(
                    source, name, cls
                )
            )
            grid.addWidget(button, index // 2, index % 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(4)
        layout.addLayout(grid)
        layout.addSpacing(4)
        layout.addWidget(self.status)

        self.setStyleSheet(
            """
            QWidget { background: #f6f8fb; color: #172033; font-family: "Microsoft YaHei UI"; }
            QLabel#title { font-size: 22px; font-weight: 600; }
            QLabel#description { color: #566176; font-size: 13px; }
            QLabel#status { background: #e9eef6; border-radius: 6px; padding: 9px; color: #3d4b62; }
            QPushButton { background: #ffffff; border: 1px solid #d8deea; border-radius: 7px; padding: 8px 14px; }
            QPushButton:hover { border-color: #198ff2; color: #0876d1; }
            QPushButton:pressed { background: #edf6fe; }
            QPushButton:focus { border: 2px solid #0876d1; }
            """
        )

    def show_verification(self, source: QPushButton, name: str, flyout_class: type) -> None:
        self.status.setText(f"正在进行：{name}")
        flyout = flyout_class.create(target=source, parent=self)
        flyout.success.connect(lambda: self.status.setText(f"验证成功：{name}"))
        flyout.failed.connect(lambda reason: self.status.setText(f"验证失败：{reason}，请重试"))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    demo = Demo()
    demo.show()
    sys.exit(app.exec())
