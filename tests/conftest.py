"""Test configuration for pylint-qt."""

import astroid
from astroid import nodes

# Enable extension module loading for Qt C bindings inference
astroid.MANAGER.always_load_extensions = True

# Disable brain_qt transforms so this plugin handles signals
# Will be removed once this plugin replaces brain_qt
_transform_visitor = astroid.MANAGER._transform
_transform_visitor.transforms[nodes.FunctionDef] = [
    (f, p)
    for f, p in _transform_visitor.transforms.get(nodes.FunctionDef, [])
    if "brain_qt" not in getattr(f, "__module__", "")
]

# Register pylint-qt transforms
import pylint_qt  # noqa: F401, E402
