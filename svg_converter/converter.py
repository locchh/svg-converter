"""Core image-to-SVG conversion logic."""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from .exceptions import (
    ConversionError,
    ImageLoadError,
    UnsupportedFormatError,
)
from .options import ConversionMode, ConversionOptions, validate_options

SUPPORTED_FORMATS = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".bmp": "BMP",
    ".gif": "GIF",
    ".tiff": "TIFF",
    ".tif": "TIFF",
    ".webp": "WEBP",
    ".ico": "ICO",
    ".ppm": "PPM",
    ".pgm": "PGM",
    ".pbm": "PBM",
}


class ConversionResult:
    def __init__(self, svg_content: str, input_path: Path, output_path: Path, mode: ConversionMode):
        self.svg_content = svg_content
        self.input_path = input_path
        self.output_path = output_path
        self.mode = mode
        self.file_size_in = input_path.stat().st_size if input_path.exists() else 0
        self.file_size_out = len(svg_content.encode("utf-8"))

    @property
    def compression_ratio(self) -> float:
        if self.file_size_in == 0:
            return 0.0
        return self.file_size_out / self.file_size_in


def load_image(path: Path) -> Image.Image:
    """Load an image from disk, handling common quirks."""
    try:
        img = Image.open(path)
        if img.mode == "P":
            img = img.convert("RGBA")
        return img
    except FileNotFoundError:
        raise ImageLoadError(f"File not found: {path}")
    except Exception as exc:
        raise ImageLoadError(f"Cannot open image '{path}': {exc}") from exc


def _image_to_base64(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    save_fmt = fmt if fmt != "JPEG" else "JPEG"
    if save_fmt == "JPEG" and img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")
    img.save(buf, format=save_fmt)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def convert_embed(img: Image.Image, original_path: Path) -> str:
    """Wrap the raster image as a base64-embedded SVG."""
    ext = original_path.suffix.lower()
    fmt = SUPPORTED_FORMATS.get(ext, "PNG")
    mime = "image/jpeg" if fmt == "JPEG" else f"image/{fmt.lower()}"
    b64 = _image_to_base64(img, fmt)
    w, h = img.size
    svg = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
        f'  <image width="{w}" height="{h}" '
        f'xlink:href="data:{mime};base64,{b64}"/>\n'
        f'</svg>\n'
    )
    return svg


def convert_pixel(img: Image.Image, options: Optional[ConversionOptions] = None) -> str:
    """Convert each pixel to an SVG <rect> with run-length encoding.

    Consecutive same-color pixels on a row are merged into a single wider
    ``<rect>``, dramatically reducing SVG file size.  When
    ``options.color_mode`` is True the image is quantized first.
    """
    if options is None:
        options = ConversionOptions()
    max_pixels = options.max_pixels
    w, h = img.size
    total = w * h
    if total > max_pixels:
        scale = (max_pixels / total) ** 0.5
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)
        w, h = img.size

    if options.color_mode:
        img_rgb = img.convert("RGB")
        img_q = img_rgb.quantize(colors=options.num_colors, method=Image.Quantize.FASTOCTREE).convert("RGB")
        pixels = np.array(img_q)
        has_alpha = False
    else:
        img_rgba = img.convert("RGBA")
        pixels = np.array(img_rgba)
        has_alpha = True

    rects: list[str] = []
    for y in range(h):
        x = 0
        while x < w:
            if has_alpha:
                r, g, b, a = pixels[y, x]
                if a == 0:
                    x += 1
                    continue
            else:
                r, g, b = pixels[y, x]
                a = 255

            start = x
            color = (r, g, b, a)
            x += 1

            while x < w:
                if has_alpha:
                    nr, ng, nb, na = pixels[y, x]
                else:
                    nr, ng, nb = pixels[y, x]
                    na = 255
                if (nr, ng, nb, na) != color:
                    break
                x += 1

            run_len = x - start
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            opacity = f' opacity="{a / 255:.3f}"' if a < 255 else ""
            rects.append(
                f'  <rect x="{start}" y="{y}" width="{run_len}" height="1" '
                f'fill="{hex_color}"{opacity}/>'
            )

    svg = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'shape-rendering="crispEdges">\n'
        + "\n".join(rects)
        + "\n</svg>\n"
    )
    return svg


def convert_trace(img: Image.Image, threshold: int = 128, invert: bool = False) -> str:
    """Vectorize the image using potrace (bitmap tracing)."""
    try:
        import potrace
    except ImportError:
        raise ImportError(
            "The 'potrace' package is required for trace mode. "
            "Install it with: pip install potrace"
        )

    gray = img.convert("L")
    arr = np.array(gray)

    if invert:
        bitmap_arr = arr < threshold
    else:
        bitmap_arr = arr >= threshold

    bm = potrace.Bitmap(bitmap_arr)
    path = bm.trace()

    w, h = img.size
    paths_svg = []
    for curve in path:
        parts = [f"M {curve.start_point.x:.3f} {curve.start_point.y:.3f}"]
        for segment in curve:
            if segment.is_corner:
                parts.append(f"L {segment.c.x:.3f} {segment.c.y:.3f}")
                parts.append(f"L {segment.end_point.x:.3f} {segment.end_point.y:.3f}")
            else:
                parts.append(
                    f"C {segment.c1.x:.3f} {segment.c1.y:.3f} "
                    f"{segment.c2.x:.3f} {segment.c2.y:.3f} "
                    f"{segment.end_point.x:.3f} {segment.end_point.y:.3f}"
                )
        parts.append("Z")
        paths_svg.append(f'  <path d="{" ".join(parts)}" fill="black"/>')

    svg = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
        + "\n".join(paths_svg)
        + "\n</svg>\n"
    )
    return svg


def convert_image(
    input_path: Path,
    output_path: Optional[Path] = None,
    options: Optional[ConversionOptions] = None,
    *,
    # Legacy kwargs kept for backwards compat during transition
    mode: Optional[ConversionMode] = None,
    threshold: Optional[int] = None,
    invert: Optional[bool] = None,
    max_pixels: Optional[int] = None,
) -> ConversionResult:
    """Main conversion entry point.

    Prefer passing a :class:`ConversionOptions` instance.  Legacy keyword
    arguments are still accepted and will override the corresponding field.
    """
    if options is None:
        options = ConversionOptions()

    # Build override dict from legacy kwargs
    overrides = {}
    if mode is not None:
        overrides["mode"] = mode
    if threshold is not None:
        overrides["threshold"] = threshold
    if invert is not None:
        overrides["invert"] = invert
    if max_pixels is not None:
        overrides["max_pixels"] = max_pixels
    if overrides:
        from dataclasses import replace
        options = replace(options, **overrides)

    validate_options(options)

    input_path = Path(input_path)
    ext = input_path.suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        raise UnsupportedFormatError(
            f"Unsupported format '{ext}'. Supported: {', '.join(SUPPORTED_FORMATS)}"
        )

    if output_path is None:
        output_path = input_path.with_suffix(".svg")
    output_path = Path(output_path)

    img = load_image(input_path)

    if options.mode == ConversionMode.EMBED:
        svg = convert_embed(img, input_path)
    elif options.mode == ConversionMode.PIXEL:
        svg = convert_pixel(img, options)
    elif options.mode == ConversionMode.TRACE:
        svg = convert_trace(img, threshold=options.threshold, invert=options.invert)
    elif options.mode == ConversionMode.VECTORIZE:
        from .vectorize import convert_vectorize
        svg = convert_vectorize(img, options)
    else:
        raise ConversionError(f"Unknown mode: {options.mode}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")

    return ConversionResult(svg, input_path, output_path, options.mode)
