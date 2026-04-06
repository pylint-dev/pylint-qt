"""Tests for plugin initialization."""

from astroid import MANAGER, nodes

from pylint_qt import _unregister_brain_qt


class TestUnregisterBrainQt:
    """Test brain_qt unregistration helper."""

    def test_handles_missing_functiondef_key(self):
        """No-op when FunctionDef has no registered transforms."""
        registry = MANAGER._transform.transforms
        saved = registry.pop(nodes.FunctionDef, None)
        try:
            _unregister_brain_qt()
            assert nodes.FunctionDef not in registry
        finally:
            if saved is not None:
                registry[nodes.FunctionDef] = saved
