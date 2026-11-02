"""Speedups must preserve every training bitmap, including translated edge ink."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from unittest.mock import Mock

from core.ocr_fonts import BUNDLED_FONTS
from games.patches_solver.src.image_parser import DIGIT_CANVAS_SIZE, _PatchesClueOcr
from games.zip_solver.src.image_parser import OCR_CANVAS_SIZE, _ZipClueOcr
from games.sudoku_solver.src.image_parser import _MiniSudokuOcr


def test_sudoku_cached_masks_preserve_glyph_pixels_at_all_training_sizes():
    ocr = _MiniSudokuOcr.__new__(_MiniSudokuOcr)
    ocr._digit_masks = {}
    for filename in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "NotoSans-Regular.ttf"):
        for size in (24, 28, 32, 36):
            font = ImageFont.truetype(str(BUNDLED_FONTS / filename), size)
            for digit in range(1, 7):
                for dx, dy, fill in ((-5, 5, 72), (0, 0, 110), (5, -5, 150)):
                    expected = Image.new("L", (64, 64), 255)
                    draw = ImageDraw.Draw(expected)
                    bbox = draw.textbbox((0, 0), str(digit), font=font)
                    draw.text(((64-(bbox[2]-bbox[0]))//2+dx, (64-(bbox[3]-bbox[1]))//2+dy), str(digit), fill=fill, font=font)
                    rng = Mock()
                    rng.randint.side_effect = [dx, dy, fill]
                    rng.random.return_value = 1.0  # Disable optional augmentations.
                    rng.uniform.side_effect = [0.0, 1.0, 0.0, 0.0]  # Identity affine transform.
                    actual = ocr._render_digit_canvas(digit, font, rng, np.random.default_rng(0))
                    np.testing.assert_array_equal(actual, np.asarray(expected))


def test_patches_translations_match_individually_rendered_templates():
    ocr = _PatchesClueOcr.__new__(_PatchesClueOcr)
    for filename in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf"):
        for size in (14, 16, 18, 20, 22, 24):
            font = ImageFont.truetype(str(BUNDLED_FONTS / filename), size)
            for digit in range(10):
                for stroke in (0, 1, 2):
                    padded = ocr._render_digit_template(str(digit), font, stroke, 0, 0, padding=1)
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            expected = ocr._render_digit_template(str(digit), font, stroke, dx, dy)
                            actual = padded[1-dy:1-dy+DIGIT_CANVAS_SIZE, 1-dx:1-dx+DIGIT_CANVAS_SIZE]
                            np.testing.assert_array_equal(actual, expected)


def test_zip_batch_packing_preserves_template_order_counts_and_edge_clipping():
    ocr = _ZipClueOcr.__new__(_ZipClueOcr)
    rng = np.random.default_rng(14)
    templates = {value: [rng.integers(0, 2, (OCR_CANVAS_SIZE, OCR_CANVAS_SIZE), dtype=np.uint8) * 255,
                         np.zeros((OCR_CANVAS_SIZE, OCR_CANVAS_SIZE), dtype=np.uint8)] for value in (1, 11, 64)}
    labels, counts, packed = [], [], []
    for value, images in templates.items():
        for image in images:
            padded = np.pad(image, 2)
            for dy in range(5):
                for dx in range(5):
                    shifted = padded[dy:dy+OCR_CANVAS_SIZE, dx:dx+OCR_CANVAS_SIZE] > 0
                    count = np.count_nonzero(shifted)
                    if count:
                        labels.append(value)
                        counts.append(count)
                        packed.append(np.packbits(shifted.reshape(-1)))
    actual = ocr._build_template_bank(templates)
    np.testing.assert_array_equal(actual.labels, labels)
    np.testing.assert_array_equal(actual.counts, counts)
    np.testing.assert_array_equal(actual.packed, packed)
    np.testing.assert_array_equal(actual.value_ends, np.searchsorted(labels, np.arange(65), side="right"))
