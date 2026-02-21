"""Interactive Terminal UI for svg-converter using Rich."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional

from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich import box

from .converter import (
    SUPPORTED_FORMATS,
    ConversionResult,
    convert_image,
)
from .exceptions import SVGConverterError
from .options import ConversionMode, ConversionOptions
from .utils import format_bytes, resolve_output_path

console = Console()

BANNER = """
[bold blue]
  ███████╗██╗   ██╗ ██████╗      ██████╗ ██████╗ ███╗   ██╗██╗   ██╗███████╗██████╗ ████████╗███████╗██████╗ 
  ██╔════╝██║   ██║██╔════╝     ██╔════╝██╔═══██╗████╗  ██║██║   ██║██╔════╝██╔══██╗╚══██╔══╝██╔════╝██╔══██╗
  ███████╗██║   ██║██║  ███╗    ██║     ██║   ██║██╔██╗ ██║██║   ██║█████╗  ██████╔╝   ██║   █████╗  ██████╔╝
  ╚════██║╚██╗ ██╔╝██║   ██║    ██║     ██║   ██║██║╚██╗██║╚██╗ ██╔╝██╔══╝  ██╔══██╗   ██║   ██╔══╝  ██╔══██╗
  ███████║ ╚████╔╝ ╚██████╔╝    ╚██████╗╚██████╔╝██║ ╚████║ ╚████╔╝ ███████╗██║  ██║   ██║   ███████╗██║  ██║
  ╚══════╝  ╚═══╝   ╚═════╝      ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝
[/bold blue]"""

SMALL_BANNER = "[bold blue]  SVG Converter[/bold blue]  [dim]— Raster to Vector[/dim]"


def _clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _print_header() -> None:
    width = console.width
    if width >= 110:
        console.print(BANNER)
    else:
        console.print()
        console.print(Align.center(SMALL_BANNER))
        console.print()
    console.print(Rule(style="blue"))


def _mode_panel() -> Panel:
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Key", style="bold yellow", width=4)
    table.add_column("Mode", style="bold cyan", width=10)
    table.add_column("Description")
    table.add_row("1", "embed", "Embed raster as base64 inside SVG [dim](lossless, fast, larger file)[/dim]")
    table.add_row("2", "trace", "Vectorize via bitmap tracing [dim](true vector, requires potrace)[/dim]")
    table.add_row("3", "pixel", "Each pixel becomes an SVG <rect> [dim](true vector, very large files)[/dim]")
    table.add_row("4", "vectorize", "Contour tracing + Douglas-Peucker [dim](true vector, color support)[/dim]")
    return Panel(table, title="[bold]Conversion Modes[/bold]", border_style="blue")


def _pick_mode() -> ConversionMode:
    console.print(_mode_panel())
    while True:
        choice = Prompt.ask(
            "[bold yellow]Select mode[/bold yellow]",
            choices=["1", "2", "3", "4"],
            default="1",
        )
        return {
            "1": ConversionMode.EMBED,
            "2": ConversionMode.TRACE,
            "3": ConversionMode.PIXEL,
            "4": ConversionMode.VECTORIZE,
        }[choice]


def _pick_inputs() -> List[Path]:
    console.print()
    console.print(
        Panel(
            f"[dim]Supported formats: {', '.join(sorted(SUPPORTED_FORMATS.keys()))}[/dim]\n"
            "[dim]Enter a file path, directory path, or multiple paths separated by spaces.[/dim]",
            title="[bold]Input Files[/bold]",
            border_style="blue",
        )
    )
    while True:
        raw = Prompt.ask("[bold yellow]Input path(s)[/bold yellow]")
        parts = raw.strip().split()
        paths: List[Path] = []
        for part in parts:
            p = Path(part.strip())
            if p.is_dir():
                found = [c for c in p.rglob("*") if c.is_file() and c.suffix.lower() in SUPPORTED_FORMATS]
                if found:
                    paths.extend(found)
                    console.print(f"  [green]✓[/] Found [cyan]{len(found)}[/] image(s) in [cyan]{p}[/]")
                else:
                    console.print(f"  [yellow]⚠[/] No supported images found in [cyan]{p}[/]")
            elif p.is_file():
                if p.suffix.lower() in SUPPORTED_FORMATS:
                    paths.append(p)
                    console.print(f"  [green]✓[/] [cyan]{p}[/]")
                else:
                    console.print(f"  [red]✗[/] Unsupported format: [cyan]{p.suffix}[/]")
            else:
                console.print(f"  [red]✗[/] Not found: [cyan]{p}[/]")

        if paths:
            return paths
        console.print("[red]No valid input files. Please try again.[/red]")


def _pick_output(inputs: List[Path]) -> Optional[Path]:
    console.print()
    is_multi = len(inputs) > 1
    hint = "directory for output SVGs" if is_multi else "output .svg file path"
    default_hint = (
        f"same directory as input(s)" if is_multi
        else str(inputs[0].with_suffix(".svg"))
    )
    console.print(
        Panel(
            f"[dim]Leave blank to save {default_hint}[/dim]",
            title=f"[bold]Output ({hint})[/bold]",
            border_style="blue",
        )
    )
    raw = Prompt.ask("[bold yellow]Output path[/bold yellow]", default="")
    if not raw.strip():
        return None
    return Path(raw.strip())


def _pick_trace_options() -> tuple[int, bool]:
    console.print()
    console.print(Panel(
        "[dim]Threshold: pixels brighter than this value are treated as foreground (0-255).[/dim]",
        title="[bold]Trace Options[/bold]",
        border_style="blue",
    ))
    threshold = IntPrompt.ask("[bold yellow]Threshold[/bold yellow]", default=128)
    threshold = max(0, min(255, threshold))
    invert = Confirm.ask("[bold yellow]Invert bitmap?[/bold yellow]", default=False)
    return threshold, invert


def _pick_pixel_options() -> int:
    console.print()
    console.print(Panel(
        "[dim]Large images will be downscaled to this pixel count before conversion.[/dim]",
        title="[bold]Pixel Mode Options[/bold]",
        border_style="blue",
    ))
    max_px = IntPrompt.ask("[bold yellow]Max pixels[/bold yellow]", default=65536)
    return max(1, max_px)


def _pick_vectorize_options() -> tuple:
    """Prompt for vectorize-mode parameters."""
    console.print()
    console.print(Panel(
        "[dim]Contour tracing with Douglas-Peucker simplification.\n"
        "Color mode quantizes the image before tracing.[/dim]",
        title="[bold]Vectorize Options[/bold]",
        border_style="blue",
    ))
    tolerance_str = Prompt.ask("[bold yellow]Tolerance (simplification)[/bold yellow]", default="1.0")
    try:
        tolerance = max(0.0, float(tolerance_str))
    except ValueError:
        tolerance = 1.0
    scale_str = Prompt.ask("[bold yellow]Scale factor[/bold yellow]", default="1.0")
    try:
        scale = max(0.01, float(scale_str))
    except ValueError:
        scale = 1.0
    color_mode = Confirm.ask("[bold yellow]Enable color mode?[/bold yellow]", default=False)
    num_colors = 8
    if color_mode:
        num_colors = IntPrompt.ask("[bold yellow]Number of colors[/bold yellow]", default=8)
        num_colors = max(2, min(256, num_colors))
    fill_color = Prompt.ask("[bold yellow]Fill color (B&W mode)[/bold yellow]", default="#000000")
    background_color_raw = Prompt.ask(
        "[bold yellow]Background color (leave blank for transparent)[/bold yellow]", default=""
    )
    background_color = background_color_raw.strip() or None
    stroke_color_raw = Prompt.ask(
        "[bold yellow]Stroke color (leave blank for none)[/bold yellow]", default=""
    )
    stroke_color = stroke_color_raw.strip() or None
    stroke_width = 0.0
    if stroke_color:
        sw_str = Prompt.ask("[bold yellow]Stroke width[/bold yellow]", default="1.0")
        try:
            stroke_width = max(0.0, float(sw_str))
        except ValueError:
            stroke_width = 1.0
    return tolerance, scale, fill_color, background_color, stroke_color, stroke_width, color_mode, num_colors


def _run_conversion(
    inputs: List[Path],
    output: Optional[Path],
    options: ConversionOptions,
    overwrite: bool = True,
) -> tuple[List[ConversionResult], List[tuple[Path, str]]]:
    results: List[ConversionResult] = []
    errors: List[tuple[Path, str]] = []
    is_multi = len(inputs) > 1

    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Converting...[/cyan]", total=len(inputs))
        for src in inputs:
            dest = resolve_output_path(src, output, is_multi)

            if dest.exists() and not overwrite:
                console.print(f"  [yellow]\u26a0 Skipping (exists):[/] {dest}")
                progress.advance(task)
                continue

            progress.update(task, description=f"[cyan]{src.name}[/cyan]")
            try:
                result = convert_image(src, dest, options=options)
                results.append(result)
            except SVGConverterError as exc:
                errors.append((src, str(exc)))
            except Exception as exc:
                errors.append((src, f"Unexpected error: {exc}"))
            progress.advance(task)

    return results, errors


def _show_results(results: List[ConversionResult], errors: List[tuple[Path, str]]) -> None:
    console.print()
    console.print(Rule("[bold green]Results[/bold green]"))

    if results:
        table = Table(box=box.ROUNDED, header_style="bold magenta", show_lines=True)
        table.add_column("Input", style="cyan")
        table.add_column("Output", style="green")
        table.add_column("Mode", style="yellow")
        table.add_column("In Size", justify="right")
        table.add_column("Out Size", justify="right")
        table.add_column("Ratio", justify="right")

        for r in results:
            ratio = r.compression_ratio
            ratio_str = f"{ratio:.2f}x"
            ratio_style = "green" if ratio <= 1.0 else "yellow"
            table.add_row(
                r.input_path.name,
                str(r.output_path),
                r.mode.value,
                format_bytes(r.file_size_in),
                format_bytes(r.file_size_out),
                f"[{ratio_style}]{ratio_str}[/{ratio_style}]",
            )
        console.print(table)

    if errors:
        console.print()
        err_table = Table(box=box.ROUNDED, header_style="bold red", title="[bold red]Errors[/bold red]")
        err_table.add_column("File", style="cyan")
        err_table.add_column("Error", style="red")
        for path, msg in errors:
            err_table.add_row(path.name, msg)
        console.print(err_table)

    console.print()
    console.print(
        Panel(
            f"[green]✓ Converted:[/green] {len(results)}   "
            f"[red]✗ Failed:[/red] {len(errors)}",
            title="[bold]Summary[/bold]",
            border_style="green" if not errors else "yellow",
            expand=False,
        )
    )


def run_tui() -> None:
    """Entry point for the interactive TUI."""
    _clear()
    _print_header()

    console.print(
        Align.center(
            "[dim]Interactive mode — follow the prompts to convert images to SVG[/dim]"
        )
    )
    console.print()

    while True:
        try:
            inputs = _pick_inputs()
            mode = _pick_mode()

            threshold = 128
            invert = False
            max_pixels = 65536
            tolerance = 1.0
            scale = 1.0
            fill_color = "#000000"
            background_color = None
            stroke_color = None
            stroke_width = 0.0
            color_mode = False
            num_colors = 8

            if mode == ConversionMode.TRACE:
                threshold, invert = _pick_trace_options()
            elif mode == ConversionMode.PIXEL:
                max_pixels = _pick_pixel_options()
            elif mode == ConversionMode.VECTORIZE:
                tolerance, scale, fill_color, background_color, stroke_color, stroke_width, color_mode, num_colors = _pick_vectorize_options()

            output = _pick_output(inputs)

            overwrite = True
            if any(
                resolve_output_path(src, output, len(inputs) > 1).exists()
                for src in inputs
            ):
                overwrite = Confirm.ask(
                    "[bold yellow]Some output files already exist. Overwrite?[/bold yellow]",
                    default=True,
                )

            opts = ConversionOptions(
                mode=mode,
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

            console.print()
            console.print(Rule("[bold blue]Starting Conversion[/bold blue]"))

            results, errors = _run_conversion(inputs, output, opts, overwrite)
            _show_results(results, errors)

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")
            break

        console.print()
        again = Confirm.ask("[bold yellow]Convert more files?[/bold yellow]", default=False)
        if not again:
            break
        _clear()
        _print_header()

    console.print()
    console.print(Align.center("[bold blue]Goodbye![/bold blue]"))
    console.print()
