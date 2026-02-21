"""Shared utility functions for svg-converter."""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def format_bytes(n: int) -> str:
    """Format a byte count as a human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def resolve_output_path(
    src: Path,
    output: Optional[Path],
    is_multi: bool,
) -> Path:
    """Determine the output path for a single file conversion.

    Parameters
    ----------
    src:
        The source image path.
    output:
        User-supplied output path (file or directory), or ``None`` for
        same-directory-as-input default.
    is_multi:
        Whether the current batch contains more than one input file.
    """
    if is_multi and output:
        return output / src.with_suffix(".svg").name
    elif not is_multi and output:
        return output if output.suffix else output / src.with_suffix(".svg").name
    else:
        return src.with_suffix(".svg")
