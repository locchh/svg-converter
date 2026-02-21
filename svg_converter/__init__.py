"""SVG Converter - Convert raster images to SVG format."""

__version__ = "1.0.0"
__author__ = "svg-converter"

from .converter import SUPPORTED_FORMATS, ConversionResult, convert_image
from .exceptions import (
    SVGConverterError,
    ConversionError,
    ImageLoadError,
    UnsupportedFormatError,
    ValidationError,
)
from .options import ConversionMode, ConversionOptions, validate_options

__all__ = [
    # Core
    "convert_image",
    "ConversionResult",
    "SUPPORTED_FORMATS",
    # Options
    "ConversionMode",
    "ConversionOptions",
    "validate_options",
    # Exceptions
    "SVGConverterError",
    "ConversionError",
    "ImageLoadError",
    "UnsupportedFormatError",
    "ValidationError",
]
