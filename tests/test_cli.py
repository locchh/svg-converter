"""Tests for svg_converter.cli using Click's CliRunner."""

import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner
from PIL import Image

from svg_converter.cli import cli


def _make_png(path: Path, size: tuple = (4, 4), color: tuple = (255, 0, 0)) -> Path:
    Image.new("RGB", size, color=color).save(path)
    return path


class TestConvertCommand:
    def test_embed_mode(self, tmp_path):
        src = tmp_path / "img.png"
        _make_png(src)
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(src), "-m", "embed"])
        assert result.exit_code == 0
        assert (tmp_path / "img.svg").exists()

    def test_pixel_mode(self, tmp_path):
        src = tmp_path / "img.png"
        _make_png(src)
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(src), "-m", "pixel"])
        assert result.exit_code == 0
        assert (tmp_path / "img.svg").exists()

    def test_vectorize_mode(self, tmp_path):
        src = tmp_path / "img.png"
        img = Image.new("L", (20, 20), color=255)
        for y in range(5, 15):
            for x in range(5, 15):
                img.putpixel((x, y), 0)
        img.save(src)
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(src), "-m", "vectorize"])
        assert result.exit_code == 0

    def test_custom_output(self, tmp_path):
        src = tmp_path / "img.png"
        out = tmp_path / "custom.svg"
        _make_png(src)
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(src), "-o", str(out)])
        assert result.exit_code == 0
        assert out.exists()

    def test_no_overwrite_skips(self, tmp_path):
        src = tmp_path / "img.png"
        out = tmp_path / "img.svg"
        _make_png(src)
        out.write_text("existing")
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(src), "--no-overwrite"])
        assert result.exit_code == 0
        assert out.read_text() == "existing"

    def test_invalid_file_exit_code(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(tmp_path / "missing.png")])
        assert result.exit_code != 0

    def test_unsupported_format(self, tmp_path):
        src = tmp_path / "file.xyz"
        src.write_text("not an image")
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(src)])
        # File is unsupported so no valid inputs → exit 1
        assert result.exit_code != 0

    def test_pixel_color_mode(self, tmp_path):
        src = tmp_path / "img.png"
        _make_png(src)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["convert", str(src), "-m", "pixel", "--color-mode", "--num-colors", "4"],
        )
        assert result.exit_code == 0

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", "--help"])
        assert result.exit_code == 0
        assert "vectorize" in result.output


class TestFormatsCommand:
    def test_lists_formats(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["formats"])
        assert result.exit_code == 0
        assert ".png" in result.output


class TestInfoCommand:
    def test_shows_info(self, tmp_path):
        src = tmp_path / "img.png"
        _make_png(src)
        runner = CliRunner()
        result = runner.invoke(cli, ["info", str(src)])
        assert result.exit_code == 0
        assert "Size" in result.output
