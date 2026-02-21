"""Tests for svg_converter.converter using synthetic PIL images."""

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from svg_converter.converter import (
    ConversionResult,
    convert_embed,
    convert_image,
    convert_pixel,
    load_image,
)
from svg_converter.exceptions import ImageLoadError, UnsupportedFormatError
from svg_converter.options import ConversionMode, ConversionOptions


def _make_rgb_image(width: int = 4, height: int = 4) -> Image.Image:
    img = Image.new("RGB", (width, height), color=(255, 0, 0))
    return img


def _make_rgba_image(width: int = 4, height: int = 4) -> Image.Image:
    img = Image.new("RGBA", (width, height), color=(0, 128, 255, 200))
    return img


def _save_tmp(img: Image.Image, suffix: str = ".png") -> Path:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        path = Path(f.name)
    img.save(path)
    return path


class TestLoadImage:
    def test_loads_rgb(self):
        p = _save_tmp(_make_rgb_image())
        img = load_image(p)
        assert img.mode == "RGB"
        p.unlink()

    def test_missing_file_raises(self):
        with pytest.raises(ImageLoadError, match="not found|Cannot open"):
            load_image(Path("/nonexistent/path/image.png"))

    def test_palette_converted_to_rgba(self, tmp_path):
        img = Image.new("P", (4, 4))
        p = tmp_path / "pal.png"
        img.save(p)
        loaded = load_image(p)
        assert loaded.mode == "RGBA"


class TestConvertEmbed:
    def test_produces_svg_with_base64(self, tmp_path):
        src = tmp_path / "test.png"
        _make_rgb_image().save(src)
        img = load_image(src)
        svg = convert_embed(img, src)
        assert "<svg" in svg
        assert "data:image/png;base64," in svg

    def test_jpeg_mime(self, tmp_path):
        src = tmp_path / "test.jpg"
        _make_rgb_image().save(src, format="JPEG")
        img = load_image(src)
        svg = convert_embed(img, src)
        assert "data:image/jpeg;base64," in svg


class TestConvertPixel:
    def test_svg_contains_rects(self):
        img = _make_rgb_image(3, 3)
        svg = convert_pixel(img)
        assert "<rect" in svg
        assert "<svg" in svg

    def test_run_length_fewer_rects(self):
        """Solid-color image → one rect per row (run-length encoding)."""
        img = Image.new("RGB", (100, 10), color=(255, 0, 0))
        svg = convert_pixel(img)
        rect_count = svg.count("<rect")
        # With RLE each row is one rect → 10 rects, not 1000
        assert rect_count <= 10

    def test_transparent_pixels_skipped(self):
        img = Image.new("RGBA", (4, 4), color=(0, 0, 0, 0))
        svg = convert_pixel(img)
        assert "<rect" not in svg

    def test_downscale_when_exceeds_max(self):
        img = Image.new("RGB", (1000, 1000), color=(200, 100, 50))
        opts = ConversionOptions(max_pixels=100)
        svg = convert_pixel(img, opts)
        # Should not error; output is small
        assert "<svg" in svg

    def test_color_mode_quantizes(self):
        img = Image.new("RGB", (8, 8), color=(123, 45, 67))
        opts = ConversionOptions(color_mode=True, num_colors=4)
        svg = convert_pixel(img, opts)
        assert "<rect" in svg


class TestConvertImage:
    def test_embed_mode(self, tmp_path):
        src = tmp_path / "img.png"
        _make_rgb_image().save(src)
        out = tmp_path / "img.svg"
        result = convert_image(src, out, options=ConversionOptions(mode=ConversionMode.EMBED))
        assert isinstance(result, ConversionResult)
        assert out.exists()
        assert "<svg" in out.read_text()

    def test_pixel_mode(self, tmp_path):
        src = tmp_path / "img.png"
        _make_rgb_image(4, 4).save(src)
        out = tmp_path / "img.svg"
        result = convert_image(src, out, options=ConversionOptions(mode=ConversionMode.PIXEL))
        assert out.exists()
        assert "<rect" in out.read_text()

    def test_unsupported_format_raises(self, tmp_path):
        src = tmp_path / "file.xyz"
        src.write_text("not an image")
        with pytest.raises(UnsupportedFormatError):
            convert_image(src)

    def test_default_output_path(self, tmp_path):
        src = tmp_path / "img.png"
        _make_rgb_image().save(src)
        result = convert_image(src)
        expected = tmp_path / "img.svg"
        assert result.output_path == expected
        assert expected.exists()
        expected.unlink()

    def test_compression_ratio(self, tmp_path):
        src = tmp_path / "img.png"
        _make_rgb_image().save(src)
        result = convert_image(src, options=ConversionOptions(mode=ConversionMode.EMBED))
        assert result.compression_ratio > 0
        (tmp_path / "img.svg").unlink()

    def test_vectorize_mode(self, tmp_path):
        src = tmp_path / "img.png"
        img = Image.new("L", (20, 20), color=255)
        # Draw a black square in the middle to create a contour
        for y in range(5, 15):
            for x in range(5, 15):
                img.putpixel((x, y), 0)
        img.save(src)
        out = tmp_path / "img.svg"
        result = convert_image(src, out, options=ConversionOptions(mode=ConversionMode.VECTORIZE))
        assert out.exists()
        assert "<svg" in out.read_text()
