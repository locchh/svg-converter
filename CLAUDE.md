# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

This project uses `uv` as the package manager (no `pip` available).

```bash
# Install with all dev dependencies
uv pip install -e ".[dev]"

# With potrace support for trace mode
uv pip install -e ".[dev,trace]"

# Run all tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_converter.py -v

# Run a single test
uv run pytest tests/test_converter.py::TestConvertPixel::test_run_length_fewer_rects -v

# Run the CLI
uv run python -m svg_converter.cli convert --help
uv run python -m svg_converter.cli convert photo.jpg -m embed
```

## Architecture

The package has a clean layered structure:

**`options.py`** is the foundation — defines `ConversionMode` enum (EMBED, TRACE, PIXEL, VECTORIZE) and the frozen `ConversionOptions` dataclass with all parameters for every mode. `validate_options()` enforces range checks. **All other modules depend on this.**

**`exceptions.py`** defines the typed exception hierarchy rooted at `SVGConverterError`. Always raise specific subtypes (`UnsupportedFormatError`, `ConversionError`, `ImageLoadError`, `ValidationError`), never bare `Exception`.

**`converter.py`** is the core — `convert_image()` is the main entry point. It validates options, loads the image via `load_image()`, dispatches to `convert_embed()`, `convert_pixel()`, `convert_trace()`, or `convert_vectorize()` (imported lazily from `vectorize.py`), writes the SVG, and returns a `ConversionResult`. `ConversionResult` stores input/output paths, SVG content, and exposes `compression_ratio`.

**`vectorize.py`** is self-contained — Moore-neighborhood contour tracing (`find_contours`) → Douglas-Peucker simplification (`simplify_contour`) → SVG path assembly (`contour_to_svg_path`). Always stores paths as `(path_data, color)` tuples. Accepts `PIL.Image.Image` input to match the rest of the API.

**`utils.py`** — Two shared helpers used by both `cli.py` and `tui.py`: `format_bytes()` and `resolve_output_path(src, output, is_multi)` which encodes the output path resolution logic for single vs multi-file batches.

**`cli.py`** / **`tui.py`** — Both import from `converter.py`, `options.py`, `exceptions.py`, and `utils.py`. CLI uses Click + Rich. TUI is a prompt-driven loop (`run_tui()`). Both catch `SVGConverterError` specifically, with a fallback `except Exception` for unexpected errors.

## Key Design Constraints

- `ConversionOptions` is **frozen** — use `dataclasses.replace(opts, field=value)` to create modified copies.
- `convert_pixel()` uses run-length encoding: consecutive same-color pixels in a row become a single wide `<rect>`. When `options.color_mode=True`, PIL quantizes the image first before scanning rows.
- `vectorize.py` is imported lazily inside `convert_image()` to avoid import cost when vectorize mode is not used.
- The `--max-pixels` default in the CLI is `65536` (256×256) but `256*256` in `ConversionOptions`. Both are consistent.
