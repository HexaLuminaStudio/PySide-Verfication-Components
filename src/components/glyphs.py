"""Crisp vector glyph rendering for text-click challenges."""

from __future__ import annotations

import random
from dataclasses import dataclass

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QTransform


TEXT_COLORS = (
    QColor("#172033"),
    QColor("#b4232f"),
    QColor("#087a55"),
    QColor("#2358a6"),
    QColor("#7a3ea1"),
    QColor("#9b4d00"),
)


@dataclass(frozen=True, slots=True)
class GlyphPlacement:
    character: str
    bounds: QRectF


def draw_text_challenge(
    pixmap: QPixmap,
    *,
    width: int,
    height: int,
    characters: str,
    font_size_range: tuple[int, int] = (20, 34),
    count: int = 12,
) -> list[GlyphPlacement]:
    """Draw outlined vector glyphs and return their visual bounds."""

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    placements: list[GlyphPlacement] = []
    used: set[str] = set()

    for _ in range(240):
        if len(placements) >= count:
            break
        character = random.choice(characters)
        if character in used:
            continue

        font = QFont("Microsoft YaHei UI", random.randint(*font_size_range))
        font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
        path = QPainterPath()
        path.addText(0, 0, font, character)
        raw_bounds = path.boundingRect()
        normalized = QTransform.fromTranslate(-raw_bounds.left(), -raw_bounds.top()).map(path)
        glyph_bounds = normalized.boundingRect()
        if glyph_bounds.width() <= 0 or glyph_bounds.height() <= 0:
            continue

        max_x = int(width - glyph_bounds.width() - 12)
        max_y = int(height - glyph_bounds.height() - 12)
        if max_x <= 12 or max_y <= 12:
            continue
        x = random.randint(12, max_x)
        y = random.randint(12, max_y)
        translated = QTransform.fromTranslate(x, y).map(normalized)
        center = translated.boundingRect().center()
        transform = QTransform()
        transform.translate(center.x(), center.y())
        transform.rotate(random.randint(-12, 12))
        transform.translate(-center.x(), -center.y())
        final_path = transform.map(translated)
        final_bounds = final_path.boundingRect().adjusted(-4, -4, 4, 4)
        if any(final_bounds.intersects(item.bounds) for item in placements):
            continue

        color = random.choice(TEXT_COLORS)
        painter.setOpacity(random.uniform(0.88, 1.0))
        outline = QPen(QColor(255, 255, 255, 225), 2.4)
        outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        outline.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(outline)
        painter.setBrush(color)
        painter.drawPath(final_path)
        placements.append(GlyphPlacement(character, final_bounds))
        used.add(character)

    painter.end()
    return placements
