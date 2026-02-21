# svg-converter

Convert raster images (JPEG, PNG, BMP, GIF, TIFF, WEBP, etc.) to SVG format with multiple vectorization modes.

## Features

- **4 conversion modes:**
  - `embed` — Embed raster as base64 inside SVG (lossless, fast, larger file)
  - `trace` — Vectorize via bitmap tracing using potrace (true vector, requires potrace)
  - `pixel` — Represent each pixel as SVG `<rect>` with run-length encoding (true vector, compact with color quantization)
  - `vectorize` — Contour tracing + Douglas-Peucker simplification (true vector, color support)

- **Rich CLI** — Beautiful terminal interface with progress bars and rich formatting
- **Interactive TUI** — Terminal UI for guided conversions with overwrite protection
- **Batch processing** — Convert single files or entire directories
- **Color quantization** — Reduce colors in pixel and vectorize modes for smaller SVGs
- **Typed API** — Frozen `ConversionOptions` dataclass with validation
- **Comprehensive tests** — 51 unit tests covering utils, options, converter, and CLI

## Installation

```bash
# Basic installation
pip install -e .

# With potrace support for trace mode
pip install -e ".[trace]"

# With test dependencies for development
pip install -e ".[dev]"
```

### Supported Input Formats

`.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`, `.tiff`, `.tif`, `.webp`, `.ico`, `.ppm`, `.pgm`, `.pbm`

**Output:** SVG (Scalable Vector Graphics)

## Quick Start

### CLI

```bash
# Convert a single image to SVG (embed mode by default)
svg-converter convert photo.jpg

# Specify output file
svg-converter convert photo.jpg -o output.svg

# Use pixel mode with color quantization
svg-converter convert photo.jpg -m pixel --color-mode --num-colors 8

# Use vectorize mode with custom tolerance
svg-converter convert photo.jpg -m vectorize --tolerance 1.5 --color-mode

# Batch convert directory
svg-converter convert images/ -o svgs/ -m trace

# Interactive terminal UI
svg-converter ui
```

### Python API

```python
from pathlib import Path
from svg_converter import convert_image, ConversionMode, ConversionOptions

# Simple usage with defaults (embed mode)
result = convert_image(Path("photo.jpg"))
print(f"Saved to {result.output_path}")

# Custom options
opts = ConversionOptions(
    mode=ConversionMode.VECTORIZE,
    tolerance=1.5,
    color_mode=True,
    num_colors=16,
    fill_color="#333333",
)
result = convert_image(Path("photo.jpg"), options=opts)
print(f"Compression ratio: {result.compression_ratio:.2f}x")

# With output path
result = convert_image(
    Path("photo.jpg"),
    Path("output.svg"),
    options=opts,
)
```

## Command-Line Reference

### `convert` command

```
Usage: svg-converter convert [OPTIONS] FILE_OR_DIR...

Options:
  -o, --output PATH                Output file (single) or directory (multiple)
  -m, --mode [embed|trace|pixel|vectorize]
                                   Conversion mode  [default: embed]
  -t, --threshold INTEGER (0-255) Grayscale threshold for trace/vectorize
                                   [default: 128]
  --invert                         Invert bitmap before tracing
  --max-pixels INTEGER             Max pixel count before downscaling in pixel
                                   mode  [default: 65536]
  --tolerance FLOAT                Contour simplification tolerance for
                                   vectorize  [default: 1.0]
  --scale FLOAT                    Output scale factor  [default: 1.0]
  --fill-color TEXT                Fill color for B&W vectorize
                                   [default: #000000]
  --background-color TEXT          Background color (vectorize)
  --stroke-color TEXT              Stroke color (vectorize)
  --stroke-width FLOAT             Stroke width  [default: 0.0]
  --color-mode                     Enable color quantization
  --num-colors INTEGER (2-256)     Number of colors with --color-mode
                                   [default: 8]
  -r, --recursive                  Recurse into subdirectories
  --overwrite/--no-overwrite       Overwrite existing files  [default: overwrite]
  -h, --help                       Show help
```

### Other commands

```bash
svg-converter formats           # List supported input formats
svg-converter info FILE         # Show image metadata
svg-converter ui                # Launch interactive TUI
```

## Conversion Modes Explained

### embed
Wraps the raster image as a base64-encoded data URI inside SVG. Fastest, lossless, but file size is ~33% larger than original.

```bash
svg-converter convert photo.jpg -m embed
```

### trace
Uses potrace for high-quality bitmap tracing. Converts pixels to vectorized paths. Requires `pip install -e ".[trace]"`.

```bash
svg-converter convert photo.jpg -m trace --threshold 128
```

### pixel
Represents each pixel as an SVG `<rect>`. With run-length encoding, consecutive same-color pixels are merged into wider rectangles. Supports color quantization.

```bash
# Basic pixel mode
svg-converter convert photo.jpg -m pixel

# With color quantization (10-100x smaller)
svg-converter convert photo.jpg -m pixel --color-mode --num-colors 8
```

### vectorize
Moore-neighborhood contour tracing followed by Douglas-Peucker simplification. Supports both B&W and color modes.

```bash
# B&W with custom simplification
svg-converter convert photo.jpg -m vectorize --tolerance 1.5

# Color mode with quantization
svg-converter convert photo.jpg -m vectorize --tolerance 1.5 --color-mode --num-colors 16
```

## Architecture

```
svg_converter/
├── __init__.py          # Public API exports
├── cli.py               # Click CLI with Rich formatting
├── tui.py               # Interactive terminal UI
├── converter.py         # Core conversion logic
├── options.py           # ConversionMode enum, ConversionOptions dataclass
├── exceptions.py        # Typed exception hierarchy
├── utils.py             # Shared utilities (format_bytes, resolve_output_path)
└── vectorize.py         # Vectorize mode implementation
tests/
├── test_utils.py        # Utils tests
├── test_options.py      # Options validation tests
├── test_converter.py    # Converter tests (all modes)
└── test_cli.py          # CLI integration tests
```

## Key Design Decisions

- **Frozen ConversionOptions**: Immutable dataclass ensures options can't be accidentally modified during conversion
- **Typed exceptions**: Specific exception types for proper error handling (not generic `Exception`)
- **Run-length encoding**: Pixel mode groups consecutive same-color pixels into single wide rects (10-100x size reduction)
- **Color quantization**: Reduce image colors before vectorization for dramatically smaller outputs
- **Moore-neighborhood tracing**: 8-connectivity contour detection for better accuracy than 4-connectivity
- **Douglas-Peucker simplification**: Recursive line simplification reduces path complexity

## Testing

Run all 51 tests:

```bash
pytest tests/ -v
```

Test coverage:
- ✅ Utilities (format_bytes, resolve_output_path)
- ✅ Options validation and immutability
- ✅ All 4 conversion modes
- ✅ CLI integration
- ✅ Error handling and edge cases

## Performance

| Mode | Speed | File Size | Quality |
|------|-------|-----------|---------|
| embed | ⚡⚡⚡ Fastest | ~133% of original | Lossless |
| pixel | ⚡⚡ Fast | Varies (10-100x with quantization) | Pixel-perfect |
| trace | ⚡ Slowest | Variable | High fidelity |
| vectorize | ⚡ Slowest | Variable | Simplified |

## Common Use Cases

### Web optimization
Convert PNG with color quantization for web-friendly small SVGs:
```bash
svg-converter convert icon.png -m pixel --color-mode --num-colors 4 -o icon.svg
```

### Logo vectorization
Trace existing raster logos:
```bash
svg-converter convert logo.png -m trace --threshold 128
```

### Poster/print artwork
Vectorize with simplification for clean outlines:
```bash
svg-converter convert artwork.jpg -m vectorize --tolerance 2.0 --color-mode
```

### Archive/backup
Embed original rasters as SVG for archival:
```bash
svg-converter convert archive/*.jpg -o archive_svgs/ -m embed
```

## License

See LICENSE file.

## Contributing

Contributions welcome! Please ensure tests pass before submitting PRs.

```bash
pip install -e ".[dev]"
pytest tests/ -v
```
