import random

from PySide6.QtWidgets import (
    QWidget,
)
from PySide6.QtCore import (
    Qt,
    QPropertyAnimation,
    Signal,
    QPoint,
    QRectF,
    QUrl,
)
from PySide6.QtGui import (
    QPixmap,
    QPainter,
    QColor,
    QFont,
    QPen,
    QPainterPath,
    QMouseEvent,
    QBrush,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from ..components.background import procedural_background
from ..components.glyphs import draw_text_challenge
from ..components.rendering import cover_pixmap, effective_dpr, new_canvas


class VerificationImage(QWidget):
    clickSignal = Signal(int, int)
    verificationComplete = Signal(bool, list)
    challengeChanged = Signal(str)
    loadingChanged = Signal(bool)
    errorOccurred = Signal(str)

    def __init__(self, parent=None, image_url: str | None = None):
        super().__init__(parent=parent)

        self.image_url = image_url

        self._width = 300
        self._height = 169
        self._dpr = effective_dpr(self)
        self.setFixedSize(self._width, self._height)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("文字点选验证码")
        self.keyboardCursor = QPoint(self._width // 2, self._height // 2)

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

        self.networkManager = QNetworkAccessManager(self)
        self.networkManager.setTransferTimeout(5000)
        self._activeReply = None

        self.currentImage = new_canvas(self._width, self._height, dpr=self._dpr)

        self.loading = False
        if self.image_url:
            self.loadImageFromUrl(self.image_url)
        else:
            self.fallbackToLocalImage()

    def loadImageFromUrl(self, url: str):
        self.loading = True
        self.loadingChanged.emit(True)
        self.update()
        request = QNetworkRequest(QUrl(url))
        if self._activeReply is not None:
            self._activeReply.abort()
            self._activeReply.deleteLater()
        self._activeReply = self.networkManager.get(request)
        self._activeReply.finished.connect(
            lambda reply=self._activeReply: self.onImageDownloaded(reply)
        )

    def onImageDownloaded(self, reply: QNetworkReply):
        if reply is not self._activeReply:
            reply.deleteLater()
            return
        self._activeReply = None
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self.errorOccurred.emit(f"图片加载失败：{reply.errorString()}")
            self.fallbackToLocalImage()
        else:
            data = reply.readAll()
            pixmap = QPixmap()
            if not pixmap.loadFromData(data):
                self.errorOccurred.emit("图片数据无法解析，已使用离线背景")
                self.fallbackToLocalImage()
            else:
                self.currentImage = cover_pixmap(
                    pixmap, self._width, self._height, dpr=self._dpr
                )
                self.loading = False
                self.loadingChanged.emit(False)
                self.generateText()
                self.update()

        reply.deleteLater()

    def fallbackToLocalImage(self):
        self.currentImage = procedural_background(
            self._width, self._height, dpr=self._dpr
        )
        self.loading = False
        self.loadingChanged.emit(False)
        self.generateText()
        self.update()

    def generateText(self):
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
        self.challengeChanged.emit(self.verificationText)
        self.setAccessibleDescription(self.verificationText)
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

        if self.hasFocus() and not self.loading:
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawEllipse(self.keyboardCursor, 7, 7)
            painter.drawLine(self.keyboardCursor.x() - 10, self.keyboardCursor.y(), self.keyboardCursor.x() + 10, self.keyboardCursor.y())
            painter.drawLine(self.keyboardCursor.x(), self.keyboardCursor.y() - 10, self.keyboardCursor.x(), self.keyboardCursor.y() + 10)

        if self.loading:
            painter.save()
            painter.setBrush(QColor(0, 0, 0, 150))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(0, 0, self._width, self._height, 5, 5)
            painter.setPen(QColor(255, 255, 255))
            font = QFont("微软雅黑", 16)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "加载中...")
            painter.restore()

        super().paintEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self.loading:
            self.setFocus()
            pos = event.pos()
            self.userClicks.append(pos)
            self.update()

            if len(self.userClicks) == len(self.targetChars):
                self.verify()

    def keyPressEvent(self, event) -> None:
        if self.loading:
            return super().keyPressEvent(event)
        moves = {
            Qt.Key.Key_Left: QPoint(-8, 0),
            Qt.Key.Key_Right: QPoint(8, 0),
            Qt.Key.Key_Up: QPoint(0, -8),
            Qt.Key.Key_Down: QPoint(0, 8),
        }
        if event.key() in moves:
            candidate = self.keyboardCursor + moves[event.key()]
            self.keyboardCursor = QPoint(
                max(0, min(self._width - 1, candidate.x())),
                max(0, min(self._height - 1, candidate.y())),
            )
            self.update()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.userClicks.append(QPoint(self.keyboardCursor))
            self.update()
            if len(self.userClicks) == len(self.targetChars):
                self.verify()
            event.accept()
            return
        super().keyPressEvent(event)

    def verify(self):
        if len(self.userClicks) != len(self.targetPositions):
            self.verificationComplete.emit(False, [])
            return

        tolerance = 20
        correct = []
        for i, (userPos, targetPos) in enumerate(
            zip(self.userClicks, self.targetPositions)
        ):
            distance = (
                (userPos.x() - targetPos.x()) ** 2
                + (userPos.y() - targetPos.y()) ** 2
            ) ** 0.5
            if distance <= tolerance:
                correct.append(i)

        success = len(correct) == len(self.targetChars)
        self.verificationComplete.emit(success, correct)

    def reset(self):
        self.refreshImage()

    def refreshImage(self):
        if (
            hasattr(self, "animation")
            and self.animation.state() == QPropertyAnimation.State.Running
        ):
            self.animation.stop()
            self.animation.deleteLater()
            delattr(self, "animation")
        if self.image_url:
            self.loadImageFromUrl(self.image_url)
        else:
            self.fallbackToLocalImage()
