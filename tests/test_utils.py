"""Tests for svg_converter.utils."""

from pathlib import Path

import pytest

from svg_converter.utils import format_bytes, resolve_output_path


class TestFormatBytes:
    def test_bytes(self):
        assert format_bytes(512) == "512.0 B"

    def test_kilobytes(self):
        assert format_bytes(2048) == "2.0 KB"

    def test_megabytes(self):
        assert format_bytes(3 * 1024 * 1024) == "3.0 MB"

    def test_gigabytes(self):
        assert format_bytes(2 * 1024 ** 3) == "2.0 GB"

    def test_terabytes(self):
        assert format_bytes(5 * 1024 ** 4) == "5.0 TB"

    def test_zero(self):
        assert format_bytes(0) == "0.0 B"


class TestResolveOutputPath:
    def test_single_no_output(self):
        src = Path("/tmp/photo.png")
        result = resolve_output_path(src, None, is_multi=False)
        assert result == Path("/tmp/photo.svg")

    def test_single_with_svg_output(self):
        src = Path("/tmp/photo.png")
        out = Path("/tmp/out.svg")
        result = resolve_output_path(src, out, is_multi=False)
        assert result == Path("/tmp/out.svg")

    def test_single_with_dir_output(self):
        src = Path("/tmp/photo.png")
        out = Path("/some/dir")
        result = resolve_output_path(src, out, is_multi=False)
        assert result == Path("/some/dir/photo.svg")

    def test_multi_no_output(self):
        src = Path("/tmp/photo.png")
        result = resolve_output_path(src, None, is_multi=True)
        assert result == Path("/tmp/photo.svg")

    def test_multi_with_dir_output(self):
        src = Path("/tmp/photo.png")
        out = Path("/out/dir")
        result = resolve_output_path(src, out, is_multi=True)
        assert result == Path("/out/dir/photo.svg")
