"""Vectorize mode — contour tracing + Douglas-Peucker simplification.

Ported from the 8df02113 worktree with adaptations:
- Accepts ``PIL.Image.Image`` instead of file paths.
- Accepts ``ConversionOptions`` for parameters.
- Always stores paths as ``(path_data, color)`` tuples (no DRY violation).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
from PIL import Image

from .options import ConversionOptions


# ---------------------------------------------------------------------------
# Image pre-processing
# ---------------------------------------------------------------------------

def image_to_grayscale(image: np.ndarray) -> np.ndarray:
    """Luminance-weighted conversion to grayscale."""
    if len(image.shape) == 2:
        return image
    if image.shape[2] == 4:  # RGBA
        return np.dot(image[..., :3], [0.299, 0.587, 0.114])
    if image.shape[2] == 3:  # RGB
        return np.dot(image, [0.299, 0.587, 0.114])
    return image


def apply_threshold(grayscale: np.ndarray, threshold: int = 128) -> np.ndarray:
    """Binary threshold — foreground pixels become 255."""
    return (grayscale > threshold).astype(np.uint8) * 255


# ---------------------------------------------------------------------------
# Contour tracing (Moore neighbourhood, 8-connectivity)
# ---------------------------------------------------------------------------

def find_contours(binary: np.ndarray) -> List[List[Tuple[int, int]]]:
    """Find contours in a binary image."""
    contours: List[List[Tuple[int, int]]] = []
    visited = np.zeros_like(binary, dtype=bool)
    height, width = binary.shape

    directions = [
        (0, 1), (1, 1), (1, 0), (1, -1),
        (0, -1), (-1, -1), (-1, 0), (-1, 1),
    ]

    def trace_contour(start_y: int, start_x: int) -> List[Tuple[int, int]]:
        contour: List[Tuple[int, int]] = []
        y, x = start_y, start_x
        direction = 0

        for i, (dy, dx) in enumerate(directions):
            ny, nx = y + dy, x + dx
            if 0 <= ny < height and 0 <= nx < width and binary[ny, nx] == 0:
                direction = (i + 4) % 8
                break

        start_point = (y, x)
        contour.append(start_point)
        visited[y, x] = True

        first_move = True
        while True:
            found = False
            search_dir = (direction + 5) % 8

            for _ in range(8):
                dy, dx = directions[search_dir]
                ny, nx = y + dy, x + dx

                if 0 <= ny < height and 0 <= nx < width and binary[ny, nx] == 255:
                    y, x = ny, nx
                    direction = search_dir
                    found = True

                    if (y, x) == start_point and not first_move:
                        return contour

                    if not visited[y, x]:
                        contour.append((y, x))
                        visited[y, x] = True
                    break

                search_dir = (search_dir + 1) % 8

            first_move = False
            if not found:
                break
            if len(contour) > height * width:
                break

        return contour

    for y in range(height):
        for x in range(width):
            if binary[y, x] == 255 and not visited[y, x]:
                is_edge = False
                for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    ny, nx = y + dy, x + dx
                    if ny < 0 or ny >= height or nx < 0 or nx >= width or binary[ny, nx] == 0:
                        is_edge = True
                        break
                if is_edge:
                    contour = trace_contour(y, x)
                    if len(contour) >= 3:
                        contours.append(contour)

    return contours


# ---------------------------------------------------------------------------
# Douglas-Peucker simplification
# ---------------------------------------------------------------------------

def simplify_contour(
    contour: List[Tuple[int, int]], tolerance: float = 1.0,
) -> List[Tuple[int, int]]:
    """Simplify a contour using the Douglas-Peucker algorithm."""
    if len(contour) <= 2:
        return contour

    def _perp_dist(
        point: Tuple[int, int],
        line_start: Tuple[int, int],
        line_end: Tuple[int, int],
    ) -> float:
        x0, y0 = point
        x1, y1 = line_start
        x2, y2 = line_end
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return float(np.sqrt((x0 - x1) ** 2 + (y0 - y1) ** 2))
        num = abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1)
        den = float(np.sqrt(dx ** 2 + dy ** 2))
        return num / den

    def _dp(points: List[Tuple[int, int]], tol: float) -> List[Tuple[int, int]]:
        if len(points) <= 2:
            return points
        max_dist = 0.0
        max_idx = 0
        for i in range(1, len(points) - 1):
            d = _perp_dist(points[i], points[0], points[-1])
            if d > max_dist:
                max_dist = d
                max_idx = i
        if max_dist > tol:
            left = _dp(points[: max_idx + 1], tol)
            right = _dp(points[max_idx:], tol)
            return left[:-1] + right
        return [points[0], points[-1]]

    return _dp(contour, tolerance)


# ---------------------------------------------------------------------------
# SVG generation helpers
# ---------------------------------------------------------------------------

def contour_to_svg_path(contour: List[Tuple[int, int]], scale: float = 1.0) -> str:
    """Convert contour points to an SVG path ``d`` attribute value."""
    if not contour:
        return ""
    parts: list[str] = []
    y, x = contour[0]
    parts.append(f"M {x * scale:.2f} {y * scale:.2f}")
    for y, x in contour[1:]:
        parts.append(f"L {x * scale:.2f} {y * scale:.2f}")
    parts.append("Z")
    return " ".join(parts)


def _generate_svg(
    width: float,
    height: float,
    paths: List[Tuple[str, str]],
    background_color: Optional[str],
    stroke_color: Optional[str],
    stroke_width: float,
) -> str:
    """Assemble a complete SVG document from ``(path_d, fill_color)`` tuples."""
    svg_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg"',
        f'     width="{width:.2f}"',
        f'     height="{height:.2f}"',
        f'     viewBox="0 0 {width:.2f} {height:.2f}">',
    ]
    if background_color:
        svg_parts.append(f'  <rect width="100%" height="100%" fill="{background_color}"/>')
    svg_parts.append("  <g>")
    for path_d, color in paths:
        elem = f'    <path d="{path_d}" fill="{color}"'
        if stroke_color:
            elem += f' stroke="{stroke_color}" stroke-width="{stroke_width}"'
        elem += "/>"
        svg_parts.append(elem)
    svg_parts.append("  </g>")
    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def convert_vectorize(img: Image.Image, options: ConversionOptions) -> str:
    """Vectorize *img* into an SVG string.

    Supports both black-and-white (default) and color mode.
    """
    arr = np.array(img.convert("RGB") if img.mode not in ("RGB", "RGBA", "L") else img)
    height, width = arr.shape[:2]
    scale = options.scale

    paths: List[Tuple[str, str]] = []

    if options.color_mode and len(arr.shape) == 3:
        quantized = img.convert("RGB").quantize(
            colors=options.num_colors, method=Image.Quantize.MEDIANCUT,
        ).convert("RGB")
        q_arr = np.array(quantized)
        unique_colors = np.unique(q_arr.reshape(-1, 3), axis=0)

        for color in unique_colors:
            mask = np.all(q_arr == color, axis=2).astype(np.uint8) * 255
            hex_color = "#{:02x}{:02x}{:02x}".format(*color)
            contours = find_contours(mask)
            for contour in contours:
                simplified = simplify_contour(contour, options.tolerance)
                path_d = contour_to_svg_path(simplified, scale)
                if path_d:
                    paths.append((path_d, hex_color))
    else:
        grayscale = image_to_grayscale(arr)
        binary = apply_threshold(grayscale, options.threshold)
        contours = find_contours(binary)
        for contour in contours:
            simplified = simplify_contour(contour, options.tolerance)
            path_d = contour_to_svg_path(simplified, scale)
            if path_d:
                paths.append((path_d, options.fill_color))

    return _generate_svg(
        width * scale,
        height * scale,
        paths,
        options.background_color,
        options.stroke_color,
        options.stroke_width,
    )
