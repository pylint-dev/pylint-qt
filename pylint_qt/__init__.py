"""Pylint plugin for Qt signal inference."""

from __future__ import annotations

import astroid
from astroid import nodes

from pylint_qt.transforms import register_transforms

__all__ = ["register"]


def _unregister_brain_qt() -> None:
    """Unregister astroid's brain_qt transforms.

    brain_qt is being phased out in favor of this plugin. To support older
    astroid versions that still ship it, we remove its transforms here since
    both cannot coexist as they transform the same nodes.
    """
    registry = astroid.MANAGER._transform.transforms
    if nodes.FunctionDef not in registry:
        return
    registry[nodes.FunctionDef] = [
        (fn, pred)
        for fn, pred in registry[nodes.FunctionDef]
        if "brain_qt" not in getattr(fn, "__module__", "")
    ]


# Qt C bindings are extension modules; astroid skips them by default.
astroid.MANAGER.always_load_extensions = True
_unregister_brain_qt()
register_transforms()


def register(_linter) -> None:  # pylint: disable=unused-argument
    """Required by pylint plugin interface."""
