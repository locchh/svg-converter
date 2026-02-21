"""Tests for svg_converter.options."""

import dataclasses

import pytest

from svg_converter.options import ConversionMode, ConversionOptions, validate_options
from svg_converter.exceptions import ValidationError


class TestConversionOptions:
    def test_defaults(self):
        opts = ConversionOptions()
        assert opts.mode == ConversionMode.EMBED
        assert opts.threshold == 128
        assert opts.invert is False
        assert opts.max_pixels == 256 * 256
        assert opts.tolerance == 1.0
        assert opts.scale == 1.0
        assert opts.fill_color == "#000000"
        assert opts.background_color is None
        assert opts.stroke_color is None
        assert opts.stroke_width == 0.0
        assert opts.color_mode is False
        assert opts.num_colors == 8

    def test_frozen_immutability(self):
        opts = ConversionOptions()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            opts.threshold = 64  # type: ignore[misc]

    def test_custom_values(self):
        opts = ConversionOptions(
            mode=ConversionMode.VECTORIZE,
            threshold=64,
            color_mode=True,
            num_colors=16,
        )
        assert opts.mode == ConversionMode.VECTORIZE
        assert opts.threshold == 64
        assert opts.color_mode is True
        assert opts.num_colors == 16

    def test_all_modes(self):
        for mode in ConversionMode:
            opts = ConversionOptions(mode=mode)
            assert opts.mode == mode


class TestValidateOptions:
    def test_valid_defaults(self):
        validate_options(ConversionOptions())  # should not raise

    def test_threshold_out_of_range_low(self):
        with pytest.raises(ValidationError, match="threshold"):
            validate_options(ConversionOptions(threshold=-1))

    def test_threshold_out_of_range_high(self):
        with pytest.raises(ValidationError, match="threshold"):
            validate_options(ConversionOptions(threshold=256))

    def test_max_pixels_zero(self):
        with pytest.raises(ValidationError, match="max_pixels"):
            validate_options(ConversionOptions(max_pixels=0))

    def test_tolerance_negative(self):
        with pytest.raises(ValidationError, match="tolerance"):
            validate_options(ConversionOptions(tolerance=-0.1))

    def test_scale_zero(self):
        with pytest.raises(ValidationError, match="scale"):
            validate_options(ConversionOptions(scale=0.0))

    def test_num_colors_too_low(self):
        with pytest.raises(ValidationError, match="num_colors"):
            validate_options(ConversionOptions(num_colors=1))

    def test_num_colors_too_high(self):
        with pytest.raises(ValidationError, match="num_colors"):
            validate_options(ConversionOptions(num_colors=257))

    def test_stroke_width_negative(self):
        with pytest.raises(ValidationError, match="stroke_width"):
            validate_options(ConversionOptions(stroke_width=-1.0))
