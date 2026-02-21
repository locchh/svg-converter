"""Custom exception hierarchy for svg-converter."""


class SVGConverterError(Exception):
    """Base exception for all svg-converter errors."""


class UnsupportedFormatError(SVGConverterError):
    """Raised when the input file extension is not supported."""


class ConversionError(SVGConverterError):
    """Raised when a conversion operation fails."""


class ImageLoadError(SVGConverterError):
    """Raised when PIL cannot open or decode an image."""


class ValidationError(SVGConverterError):
    """Raised when conversion options fail validation."""
