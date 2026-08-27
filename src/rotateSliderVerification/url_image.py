"""Remote-image adapter for the picture-straightening challenge."""

from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QWidget

from .image import VerificationImage as LocalVerificationImage


class VerificationImage(LocalVerificationImage):
    loadingChanged = Signal(bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        image_url: str | None = None,
        *,
        initial_angle_degrees: float | None = None,
        angle_tolerance_degrees: float = 6.0,
        image_scale: float = 0.9,
    ) -> None:
        self.image_url = image_url
        super().__init__(
            parent=parent,
            initial_angle_degrees=initial_angle_degrees,
            angle_tolerance_degrees=angle_tolerance_degrees,
            image_scale=image_scale,
        )
        self.network_manager = QNetworkAccessManager(self)
        self.network_manager.setTransferTimeout(5000)
        self._active_reply: QNetworkReply | None = None
        if self.image_url:
            self.load_image_from_url(self.image_url)

    def _set_loading(self, loading: bool) -> None:
        self.loading = loading
        self.loadingChanged.emit(loading)
        self.update()

    def load_image_from_url(self, url: str) -> None:
        self._set_loading(True)
        if self._active_reply is not None:
            self._active_reply.abort()
            self._active_reply.deleteLater()
        request = QNetworkRequest(QUrl(url))
        self._active_reply = self.network_manager.get(request)
        self._active_reply.finished.connect(
            lambda reply=self._active_reply: self.on_image_downloaded(reply)
        )

    def on_image_downloaded(self, reply: QNetworkReply) -> None:
        if reply is not self._active_reply:
            reply.deleteLater()
            return
        self._active_reply = None
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self.errorOccurred.emit(f"图片加载失败：{reply.errorString()}")
            self.fallback_to_local_image()
        else:
            pixmap = QPixmap()
            if not pixmap.loadFromData(reply.readAll()):
                self.errorOccurred.emit("图片数据无法解析，已使用离线背景")
                self.fallback_to_local_image()
            else:
                self.setSourcePixmap(pixmap)
        self._set_loading(False)
        reply.deleteLater()

    def refreshImage(self) -> None:
        if self.image_url:
            self.load_image_from_url(self.image_url)
        else:
            self.fallback_to_local_image()
