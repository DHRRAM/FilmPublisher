"""Command-line entry point for Film Publisher."""

from __future__ import annotations

from collections.abc import Sequence

from app.application import run


def main(argv: Sequence[str] | None = None) -> int:
    """Run the desktop application."""

    return run(argv)
