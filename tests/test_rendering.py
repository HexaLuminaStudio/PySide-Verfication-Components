from PySide6.QtGui import QColor, QPixmap

from src.components.rendering import copy_logical, cover_pixmap, new_canvas
from src.iconClickVerification.image import Icon
from src.rotateSliderVerification import LocalVerificationImage
from src.tileOrderVerification import LocalVerificationImage as LocalTileOrderImage


def test_high_dpi_canvas_keeps_logical_size(qapp):
    canvas = new_canvas(300, 169, dpr=2.0, color=QColor("white"))
    assert canvas.width() == 600
    assert canvas.height() == 338
    assert canvas.devicePixelRatioF() == 2.0
    assert canvas.deviceIndependentSize().width() == 300
    assert canvas.deviceIndependentSize().height() == 169


def test_logical_copy_preserves_high_dpi_density(qapp):
    canvas = new_canvas(300, 169, dpr=2.0, color=QColor("white"))
    piece = copy_logical(canvas, 20, 30, 35, 35)
    assert piece.width() == 70
    assert piece.height() == 70
    assert piece.deviceIndependentSize().width() == 35
    assert piece.deviceIndependentSize().height() == 35


def test_cover_crop_preserves_target_size_without_stretching(qapp):
    source = QPixmap(400, 200)
    source.fill(QColor("#345678"))
    result = cover_pixmap(source, 300, 169, dpr=1.5)
    assert result.width() == 450
    assert result.height() == 254
    assert result.deviceIndependentSize().width() == 300


def test_all_icon_paths_are_valid_and_hit_testable(qapp):
    for icon_type in (
        "circle",
        "square",
        "triangle",
        "star",
        "cross",
        "diamond",
        "pentagon",
        "hexagon",
        "heart",
        "ellipse",
    ):
        icon = Icon(icon_type, 10, 10, 40)
        assert not icon.path().isEmpty()
        assert icon.contains(icon.bounds.center())


def test_rotate_image_preserves_high_dpi_source_density(qapp):
    source = QPixmap(420, 420)
    source.fill(QColor("#345678"))
    image = LocalVerificationImage(
        [source],
        initial_angle_degrees=180,
    )

    assert image.currentImage.deviceIndependentSize().width() == image._image_width
    assert image.currentImage.deviceIndependentSize().height() == image._image_height


def test_rotate_image_scale_is_bounded_and_preserves_aspect_ratio(qapp):
    source = QPixmap(600, 338)
    source.fill(QColor("#345678"))
    image = LocalVerificationImage([source], image_scale=0.9)

    assert image._image_width == 270
    assert image._image_height == 152
    assert image.currentImage.deviceIndependentSize().width() == 270
    assert image.currentImage.deviceIndependentSize().height() == 152


def test_tile_order_slices_keep_logical_dimensions(qapp):
    source = QPixmap(600, 338)
    source.fill(QColor("#345678"))
    image = LocalTileOrderImage(
        [source],
        tile_count=4,
        initial_order=[2, 0, 3, 1],
    )

    assert len(image.tiles) == 4
    assert all(tile.deviceIndependentSize().width() == 75 for tile in image.tiles)
    assert all(tile.deviceIndependentSize().height() == 169 for tile in image.tiles)
