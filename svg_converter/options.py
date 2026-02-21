"""Conversion options and mode definitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .exceptions import ValidationError


class ConversionMode(str, Enum):
    EMBED = "embed"
    TRACE = "trace"
    PIXEL = "pixel"
    VECTORIZE = "vectorize"


@dataclass(frozen=True)
class ConversionOptions:
    """Immutable set of parameters for a conversion run."""

    mode: ConversionMode = ConversionMode.EMBED
    threshold: int = 128
    invert: bool = False
    max_pixels: int = 256 * 256

    # Vectorize / display options
    tolerance: float = 1.0
    scale: float = 1.0
    fill_color: str = "#000000"
    background_color: Optional[str] = None
    stroke_color: Optional[str] = None
    stroke_width: float = 0.0

    # Color quantization
    color_mode: bool = False
    num_colors: int = 8


def validate_options(opts: ConversionOptions) -> None:
    """Raise :class:`ValidationError` if *opts* contain invalid values."""
    if not 0 <= opts.threshold <= 255:
        raise ValidationError(f"threshold must be 0-255, got {opts.threshold}")
    if opts.max_pixels < 1:
        raise ValidationError(f"max_pixels must be >= 1, got {opts.max_pixels}")
    if opts.tolerance < 0:
        raise ValidationError(f"tolerance must be >= 0, got {opts.tolerance}")
    if opts.scale <= 0:
        raise ValidationError(f"scale must be > 0, got {opts.scale}")
    if opts.num_colors < 2 or opts.num_colors > 256:
        raise ValidationError(f"num_colors must be 2-256, got {opts.num_colors}")
    if opts.stroke_width < 0:
        raise ValidationError(f"stroke_width must be >= 0, got {opts.stroke_width}")
