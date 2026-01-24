"""Pylint plugin for Qt signal inference."""

from __future__ import annotations

from pylint_qt.transforms import register_transforms

__all__ = ["register"]

register_transforms()


def register(_linter) -> None:  # pylint: disable=unused-argument
    """Required by pylint plugin interface."""
