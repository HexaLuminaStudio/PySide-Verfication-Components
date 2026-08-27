"""High-DPI-safe pixmap helpers shared by verification widgets."""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QWidget


def effective_dpr(widget: QWidget | None = None, dpr: float | None = None) -> float:
    """Return a safe device pixel ratio without downscaling below 1x."""

    value = dpr if dpr is not None else widget.devicePixelRatioF() if widget else 1.0
    return max(1.0, float(value))


def new_canvas(
    width: int,
    height: int,
    *,
    dpr: float = 1.0,
    color: QColor | Qt.GlobalColor = Qt.GlobalColor.transparent,
) -> QPixmap:
    """Create a pixmap whose logical size remains ``width`` by ``height``."""

    ratio = effective_dpr(dpr=dpr)
    pixmap = QPixmap(max(1, round(width * ratio)), max(1, round(height * ratio)))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(color)
    return pixmap


def cover_pixmap(source: QPixmap, width: int, height: int, *, dpr: float = 1.0) -> QPixmap:
    """Scale and center-crop without distorting the source aspect ratio."""

    if source.isNull():
        raise ValueError("图片为空")
    ratio = effective_dpr(dpr=dpr)
    target = QSize(max(1, round(width * ratio)), max(1, round(height * ratio)))
    raw = QPixmap(source)
    raw.setDevicePixelRatio(1.0)
    scaled = raw.scaled(
        target,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = max(0, (scaled.width() - target.width()) // 2)
    y = max(0, (scaled.height() - target.height()) // 2)
    result = scaled.copy(QRect(x, y, target.width(), target.height()))
    result.setDevicePixelRatio(ratio)
    return result


def copy_logical(pixmap: QPixmap, x: float, y: float, width: float, height: float) -> QPixmap:
    """Copy a rectangle expressed in device-independent coordinates."""

    ratio = effective_dpr(dpr=pixmap.devicePixelRatioF())
    result = pixmap.copy(
        QRect(
            round(x * ratio),
            round(y * ratio),
            max(1, round(width * ratio)),
            max(1, round(height * ratio)),
        )
    )
    result.setDevicePixelRatio(ratio)
    return result
