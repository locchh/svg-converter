"""CLI interface for svg-converter using Click + Rich."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich import print as rprint

from .converter import (
    SUPPORTED_FORMATS,
    ConversionResult,
    convert_image,
)
from .exceptions import SVGConverterError
from .options import ConversionMode, ConversionOptions
from .utils import format_bytes, resolve_output_path

console = Console()

SUPPORTED_EXTS = ", ".join(sorted(SUPPORTED_FORMATS.keys()))


def _print_result(result: ConversionResult) -> None:
    ratio = result.compression_ratio
    ratio_color = "green" if ratio <= 1.0 else "yellow"
    console.print(
        f"  [bold green]✓[/] [cyan]{result.input_path.name}[/] → "
        f"[cyan]{result.output_path.name}[/]  "
        f"[dim]{format_bytes(result.file_size_in)} → {format_bytes(result.file_size_out)}[/]  "
        f"[{ratio_color}]({ratio:.2f}x)[/]"
    )


def _collect_inputs(inputs: tuple[str, ...], recursive: bool) -> List[Path]:
    """Expand directories and glob patterns into a flat list of image paths."""
    paths: List[Path] = []
    for raw in inputs:
        p = Path(raw)
        if p.is_dir():
            pattern = "**/*" if recursive else "*"
            for child in p.glob(pattern):
                if child.is_file() and child.suffix.lower() in SUPPORTED_FORMATS:
                    paths.append(child)
        elif p.is_file():
            if p.suffix.lower() in SUPPORTED_FORMATS:
                paths.append(p)
            else:
                console.print(f"[yellow]⚠ Skipping unsupported file:[/] {p}")
        else:
            console.print(f"[red]✗ Not found:[/] {raw}")
    return paths


@click.group(invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option("1.0.0", "-V", "--version")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """
    \b
    ╔══════════════════════════════╗
    ║   SVG Converter  v1.0.0      ║
    ║   Raster → SVG made easy     ║
    ╚══════════════════════════════╝

    Convert JPEG, PNG, BMP, GIF, TIFF, WEBP and more to SVG.

    Run 'svg-converter COMMAND --help' for command-specific help.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command("convert")
@click.argument("inputs", nargs=-1, required=True, metavar="FILE_OR_DIR...")
@click.option(
    "-o", "--output",
    default=None,
    help="Output file (single input) or output directory (multiple inputs).",
    metavar="PATH",
)
@click.option(
    "-m", "--mode",
    type=click.Choice([m.value for m in ConversionMode], case_sensitive=False),
    default=ConversionMode.EMBED.value,
    show_default=True,
    help=(
        "Conversion mode:\n\n"
        "  embed     – Embed raster as base64 inside SVG (lossless, fast).\n\n"
        "  trace     – Vectorize via bitmap tracing (requires potrace package).\n\n"
        "  pixel     – Represent each pixel as an SVG <rect> (true vector, large files).\n\n"
        "  vectorize – Contour tracing + Douglas-Peucker simplification."
    ),
)
@click.option(
    "-t", "--threshold",
    default=128,
    show_default=True,
    type=click.IntRange(0, 255),
    help="Grayscale threshold for trace mode (0-255).",
)
@click.option(
    "--invert",
    is_flag=True,
    default=False,
    help="Invert the bitmap before tracing (trace mode only).",
)
@click.option(
    "--max-pixels",
    default=256 * 256,
    show_default=True,
    type=int,
    help="Max pixel count before downscaling in pixel mode.",
)
@click.option(
    "-r", "--recursive",
    is_flag=True,
    default=False,
    help="Recurse into subdirectories when INPUT is a directory.",
)
@click.option(
    "--tolerance",
    default=1.0,
    show_default=True,
    type=float,
    help="Contour simplification tolerance (vectorize mode).",
)
@click.option(
    "--scale",
    default=1.0,
    show_default=True,
    type=float,
    help="Output scale factor (vectorize mode).",
)
@click.option(
    "--fill-color",
    default="#000000",
    show_default=True,
    help="Fill color for paths in B&W vectorize mode.",
)
@click.option(
    "--background-color",
    default=None,
    help="Background rectangle color (vectorize mode). Omit for transparent.",
)
@click.option(
    "--stroke-color",
    default=None,
    help="Stroke color for paths (vectorize mode). Omit for no stroke.",
)
@click.option(
    "--stroke-width",
    default=0.0,
    show_default=True,
    type=float,
    help="Stroke width (vectorize mode).",
)
@click.option(
    "--color-mode",
    is_flag=True,
    default=False,
    help="Enable color quantization (pixel and vectorize modes).",
)
@click.option(
    "--num-colors",
    default=8,
    show_default=True,
    type=click.IntRange(2, 256),
    help="Number of colors when --color-mode is active.",
)
@click.option(
    "--overwrite/--no-overwrite",
    default=True,
    show_default=True,
    help="Overwrite existing output files.",
)
def convert_cmd(
    inputs: tuple[str, ...],
    output: Optional[str],
    mode: str,
    threshold: int,
    invert: bool,
    max_pixels: int,
    recursive: bool,
    tolerance: float,
    scale: float,
    fill_color: str,
    background_color: Optional[str],
    stroke_color: Optional[str],
    stroke_width: float,
    color_mode: bool,
    num_colors: int,
    overwrite: bool,
) -> None:
    """Convert one or more images to SVG.

    \b
    Examples:
      svg-converter convert photo.jpg
      svg-converter convert photo.jpg -o out.svg -m embed
      svg-converter convert images/ -o svgs/ -m trace
      svg-converter convert *.png -m pixel --color-mode --num-colors 8
      svg-converter convert photo.png -m vectorize --tolerance 1.5 --color-mode
    """
    conv_mode = ConversionMode(mode)
    opts = ConversionOptions(
        mode=conv_mode,
        threshold=threshold,
        invert=invert,
        max_pixels=max_pixels,
        tolerance=tolerance,
        scale=scale,
        fill_color=fill_color,
        background_color=background_color,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
        color_mode=color_mode,
        num_colors=num_colors,
    )
    paths = _collect_inputs(inputs, recursive)

    if not paths:
        console.print("[red]No valid input files found.[/]")
        sys.exit(1)

    output_path: Optional[Path] = Path(output) if output else None
    is_multi = len(paths) > 1

    if is_multi and output_path and output_path.suffix.lower() == ".svg":
        console.print(
            "[red]Error:[/] When converting multiple files, --output must be a directory, not a .svg file."
        )
        sys.exit(1)

    console.print(
        Panel(
            f"[bold]Mode:[/] [cyan]{conv_mode.value}[/]  |  "
            f"[bold]Files:[/] [cyan]{len(paths)}[/]",
            title="[bold blue]SVG Converter[/]",
            expand=False,
        )
    )

    errors: List[tuple[Path, str]] = []
    results: List[ConversionResult] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Converting...", total=len(paths))

        for src in paths:
            dest = resolve_output_path(src, output_path, is_multi)

            if dest.exists() and not overwrite:
                console.print(f"[yellow]⚠ Skipping (exists):[/] {dest}")
                progress.advance(task)
                continue

            progress.update(task, description=f"[cyan]{src.name}[/]")
            try:
                result = convert_image(src, dest, options=opts)
                results.append(result)
                _print_result(result)
            except SVGConverterError as exc:
                errors.append((src, str(exc)))
                console.print(f"  [red]✗ {src.name}:[/] {exc}")
            except Exception as exc:
                errors.append((src, f"Unexpected error: {exc}"))
                console.print(f"  [red]✗ {src.name}:[/] Unexpected error: {exc}")
            progress.advance(task)

    _print_summary(results, errors)
    if errors:
        sys.exit(1)


def _print_summary(results: List[ConversionResult], errors: List[tuple[Path, str]]) -> None:
    table = Table(title="Summary", show_header=True, header_style="bold magenta")
    table.add_column("Stat", style="dim")
    table.add_column("Value", justify="right")
    table.add_row("Converted", f"[green]{len(results)}[/]")
    table.add_row("Failed", f"[red]{len(errors)}[/]" if errors else "0")
    if results:
        total_in = sum(r.file_size_in for r in results)
        total_out = sum(r.file_size_out for r in results)
        table.add_row("Total input size", format_bytes(total_in))
        table.add_row("Total output size", format_bytes(total_out))
    console.print(table)


@cli.command("info")
@click.argument("file", type=click.Path(exists=True))
def info_cmd(file: str) -> None:
    """Show metadata about an image file."""
    from PIL import Image as PILImage

    p = Path(file)
    try:
        img = PILImage.open(p)
    except Exception as exc:
        console.print(f"[red]Cannot open file:[/] {exc}")
        sys.exit(1)

    table = Table(title=f"Image Info: {p.name}", show_header=False)
    table.add_column("Property", style="bold cyan")
    table.add_column("Value")
    table.add_row("Path", str(p.resolve()))
    table.add_row("Format", img.format or "unknown")
    table.add_row("Mode", img.mode)
    table.add_row("Size", f"{img.width} × {img.height} px")
    table.add_row("File size", format_bytes(p.stat().st_size))
    if hasattr(img, "info") and img.info:
        for k, v in img.info.items():
            if isinstance(v, (str, int, float, tuple)):
                table.add_row(str(k), str(v))
    console.print(table)


@cli.command("formats")
def formats_cmd() -> None:
    """List all supported input image formats."""
    table = Table(title="Supported Input Formats", header_style="bold magenta")
    table.add_column("Extension", style="cyan")
    table.add_column("Format Name")
    for ext, name in sorted(SUPPORTED_FORMATS.items()):
        table.add_row(ext, name)
    console.print(table)
    console.print("\n[bold]Output format:[/] SVG (Scalable Vector Graphics)\n")


@cli.command("ui")
def ui_cmd() -> None:
    """Launch the interactive terminal UI."""
    from .tui import run_tui
    run_tui()


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
