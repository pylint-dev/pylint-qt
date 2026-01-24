"""Transforms for Qt inference."""

from __future__ import annotations

from astroid import MANAGER

from pylint_qt.transforms.signals import register_transforms as _register_signal_transforms

__all__ = ["register_transforms"]


def register_transforms() -> None:
    """Register all Qt transforms with astroid."""
    _register_signal_transforms(MANAGER)
