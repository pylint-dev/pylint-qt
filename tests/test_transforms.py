"""Tests for transform registration."""

from unittest.mock import MagicMock, patch

from astroid import MANAGER, Uninferable, extract_node, nodes
from astroid.exceptions import InferenceError

import pylint_qt  # noqa: F401
from pylint_qt.transforms.signals import (
    _looks_like_qt_signal_functiondef,
    _looks_like_signal_class_attribute,
    _looks_like_subscripted_signal,
)


class TestPredicates:
    """Test predicate functions."""

    def test_non_qt_functiondef_returns_false(self):
        """Test that non-Qt FunctionDefs are rejected by predicate."""
        node = extract_node("""
        def foo():  #@
            pass
        """)
        assert _looks_like_qt_signal_functiondef(node) is False

    def test_subscript_without_qt_import_returns_false(self):
        """Test that subscripted attributes without Qt imports are rejected."""
        from astroid import parse

        module = parse("""
        import os
        from pathlib import Path
        class Foo:
            bar = []
        x = Foo.bar[0]
        """)
        subscript = module.body[-1].value
        attr_node = subscript.value
        assert _looks_like_subscripted_signal(attr_node) is False

    def test_non_subscript_attribute_returns_false(self):
        """Test that non-subscripted attributes are rejected."""
        node = extract_node("""
        class Foo:
            bar = 1
        Foo.bar  #@
        """)
        assert _looks_like_subscripted_signal(node) is False

    def test_signal_class_attribute_with_regular_attr_returns_false(self):
        """Test that non-signal class attributes are rejected."""
        node = extract_node("""
        class Foo:
            bar = 1
        obj = Foo()
        obj.bar  #@
        """)
        assert _looks_like_signal_class_attribute(node) is False

    def test_signal_class_attribute_without_qt_import_returns_false(self):
        """Test that class attributes without Qt signal types are rejected."""
        node = extract_node("""
        class Signal:
            pass
        class Foo:
            my_signal = Signal()
        obj = Foo()
        obj.my_signal  #@
        """)
        assert _looks_like_signal_class_attribute(node) is False

    def test_signal_class_attribute_attr_not_in_class_returns_false(self):
        """Test accessing attribute not defined in class returns false."""
        node = extract_node("""
        class Foo:
            pass
        obj = Foo()
        obj.undefined_attr  #@
        """)
        assert _looks_like_signal_class_attribute(node) is False

    def test_signal_class_attribute_non_assign_returns_false(self):
        """Test class attribute that is not an assignment returns false."""
        node = extract_node("""
        class Foo:
            def bar(self): pass
        obj = Foo()
        obj.bar  #@
        """)
        assert _looks_like_signal_class_attribute(node) is False

    def test_signal_class_attribute_with_complex_mro(self):
        """Test signal with complex MRO (multiple inheritance)."""
        node = extract_node("""
        class A:
            pass
        class B:
            pass
        class C(A, B):
            pass
        obj = C()
        obj.some_attr  #@
        """)
        assert _looks_like_signal_class_attribute(node) is False

    def test_signal_class_attribute_expr_infers_to_uninferable(self):
        """Test when expr.infer() yields Uninferable."""
        node = extract_node("""
        unknown.attr  #@
        """)
        assert _looks_like_signal_class_attribute(node) is False

    def test_signal_class_attribute_proxied_not_classdef(self):
        """Test when Instance._proxied is not a ClassDef."""
        from astroid.bases import Instance

        # Create a mock node
        node = MagicMock()
        node.attrname = "test_attr"

        # Create mock instance with _proxied that's not a ClassDef
        mock_instance = MagicMock(spec=Instance)
        mock_instance._proxied = "not_a_classdef"

        # Mock expr.infer() to return the mock instance
        node.expr.infer.return_value = iter([mock_instance])

        assert _looks_like_signal_class_attribute(node) is False

    def test_signal_class_attribute_mro_fails(self):
        """Test when MRO computation fails and falls back to single class."""
        from astroid import nodes

        node = extract_node("""
        class Foo:
            attr = 1
        obj = Foo()
        obj.attr  #@
        """)

        with patch.object(nodes.ClassDef, "mro", side_effect=NotImplementedError):
            result = _looks_like_signal_class_attribute(node)
            assert result is False

    def test_signal_class_attribute_mro_contains_non_classdef(self):
        """Test when MRO contains non-ClassDef entries."""
        from astroid import nodes

        node = extract_node("""
        class Foo:
            attr = 1
        obj = Foo()
        obj.attr  #@
        """)

        with patch.object(nodes.ClassDef, "mro", return_value=[Uninferable, "not_classdef"]):
            result = _looks_like_signal_class_attribute(node)
            assert result is False

    def test_signal_class_attribute_excludes_subscripted_signals(self):
        """Test that subscripted signals are excluded from class attribute handling."""
        from astroid import parse

        # Parse code with a subscripted signal-like pattern
        module = parse("""
        from PyQt6.QtCore import pyqtSignal
        class Foo:
            sig = pyqtSignal()
        obj = Foo()
        x = obj.sig[int]
        """)
        # Get the attribute node (obj.sig) which is the value of the Subscript
        subscript = module.body[-1].value  # obj.sig[int]
        attr_node = subscript.value  # obj.sig

        result = _looks_like_signal_class_attribute(attr_node)
        assert result is False

    def test_subscripted_signal_parent_value_not_node(self):
        """Test _looks_like_subscripted_signal when parent.value is not node."""
        from astroid import parse

        # Parse code where the attribute is in the slice, not the value
        module = parse("""
        from PyQt6.QtCore import QTimer
        x = some_list[timer.timeout]
        """)
        # Get the attribute node (timer.timeout) which is in the slice
        subscript = module.body[-1].value  # some_list[timer.timeout]
        attr_in_slice = subscript.slice  # timer.timeout

        # Verify it's an Attribute with Subscript parent but not the value
        assert isinstance(attr_in_slice, nodes.Attribute)
        assert isinstance(attr_in_slice.parent, nodes.Subscript)
        assert attr_in_slice.parent.value is not attr_in_slice

        result = _looks_like_subscripted_signal(attr_in_slice)
        assert result is False


class TestInferenceFunctionEdgeCases:
    """Test edge cases in inference functions."""

    def test_infer_signal_class_attribute_non_instance_value(self):
        """Test when expr.infer() yields non-Instance values."""
        from astroid.exceptions import UseInferenceDefault

        from pylint_qt.transforms.signals import _infer_signal_class_attribute

        # Create a node where expr infers to a module, not an instance
        node = extract_node("""
        from PyQt6 import QtCore
        QtCore.someattr  #@
        """)

        import pytest

        with pytest.raises(UseInferenceDefault):
            list(_infer_signal_class_attribute(node))

    def test_infer_signal_class_attribute_proxied_not_classdef(self):
        """Test inference when _proxied is not a ClassDef."""
        from astroid.bases import Instance
        from astroid.exceptions import UseInferenceDefault

        from pylint_qt.transforms.signals import _infer_signal_class_attribute

        # Create a mock node
        node = MagicMock()
        node.attrname = "test_attr"

        # Create mock instance with _proxied that's not a ClassDef
        mock_instance = MagicMock(spec=Instance)
        mock_instance._proxied = "not_a_classdef"

        # Mock expr.infer() to return the mock instance
        node.expr.infer.return_value = iter([mock_instance])

        import pytest

        with pytest.raises(UseInferenceDefault):
            list(_infer_signal_class_attribute(node))

    def test_infer_signal_class_attribute_mro_fails(self):
        """Test inference when MRO computation fails (falls back to single class)."""
        from astroid.bases import Instance

        from pylint_qt.transforms.signals import _infer_signal_class_attribute

        # Create a mock node that simulates MRO failure
        mock_classdef = MagicMock(spec=nodes.ClassDef)
        mock_classdef.mro.side_effect = NotImplementedError()
        # Provide locals with a signal attribute
        mock_assignname = MagicMock(spec=nodes.AssignName)
        mock_assign = MagicMock(spec=nodes.Assign)
        mock_assignname.parent = mock_assign

        # Create a mock signal value
        mock_signal_instance = MagicMock(spec=Instance)
        mock_signal_proxied = MagicMock()
        mock_signal_proxied.qname.return_value = "PyQt6.QtCore.pyqtSignal"
        mock_signal_instance._proxied = mock_signal_proxied

        mock_value_node = MagicMock()
        mock_value_node.infer.return_value = iter([mock_signal_instance])
        mock_assign.value = mock_value_node

        mock_classdef.locals = {"attr": [mock_assignname]}

        # Create mock instance
        mock_instance = MagicMock(spec=Instance)
        mock_instance._proxied = mock_classdef

        # Create node
        node = MagicMock()
        node.attrname = "attr"
        node.expr.infer.return_value = iter([mock_instance])

        results = list(_infer_signal_class_attribute(node))
        assert len(results) == 1

    def test_infer_signal_class_attribute_mro_has_non_classdef(self):
        """Test inference skips non-ClassDef entries in MRO."""
        from astroid.bases import Instance

        from pylint_qt.transforms.signals import _infer_signal_class_attribute

        # Create a mock classdef with signal
        mock_classdef = MagicMock(spec=nodes.ClassDef)
        mock_assignname = MagicMock(spec=nodes.AssignName)
        mock_assign = MagicMock(spec=nodes.Assign)
        mock_assignname.parent = mock_assign

        # Create a mock signal value
        mock_signal_instance = MagicMock(spec=Instance)
        mock_signal_proxied = MagicMock()
        mock_signal_proxied.qname.return_value = "PyQt6.QtCore.pyqtSignal"
        mock_signal_instance._proxied = mock_signal_proxied

        mock_value_node = MagicMock()
        mock_value_node.infer.return_value = iter([mock_signal_instance])
        mock_assign.value = mock_value_node

        mock_classdef.locals = {"attr": [mock_assignname]}

        # MRO returns non-ClassDef entries followed by the real classdef
        mock_classdef.mro.return_value = [Uninferable, "not_classdef", mock_classdef]

        # Create mock instance
        mock_instance = MagicMock(spec=Instance)
        mock_instance._proxied = mock_classdef

        # Create node
        node = MagicMock()
        node.attrname = "attr"
        node.expr.infer.return_value = iter([mock_instance])

        results = list(_infer_signal_class_attribute(node))
        assert len(results) == 1

    def test_infer_signal_class_attribute_attr_not_assignname(self):
        """Test inference when attr_node is not an AssignName (e.g., method)."""
        from astroid.exceptions import UseInferenceDefault

        from pylint_qt.transforms.signals import _infer_signal_class_attribute

        # Create a node where the attribute is a method
        node = extract_node("""
        from PyQt6.QtCore import QObject
        class Foo(QObject):
            def method(self): pass
        obj = Foo()
        obj.method  #@
        """)

        import pytest

        with pytest.raises(UseInferenceDefault):
            list(_infer_signal_class_attribute(node))

    def test_infer_signal_class_attribute_not_signal_type(self):
        """Test inference when attribute value is not a signal type."""
        from astroid.exceptions import UseInferenceDefault

        from pylint_qt.transforms.signals import _infer_signal_class_attribute

        # Create a node where the attribute is not a signal
        node = extract_node("""
        from PyQt6.QtCore import QObject
        class Foo(QObject):
            attr = 42
        obj = Foo()
        obj.attr  #@
        """)

        import pytest

        with pytest.raises(UseInferenceDefault):
            list(_infer_signal_class_attribute(node))

    def test_infer_signal_class_attribute_inference_error_in_value(self):
        """Test when value_node.infer() raises InferenceError."""
        from astroid.exceptions import UseInferenceDefault

        from pylint_qt.transforms.signals import _infer_signal_class_attribute

        # Create a node where the value cannot be inferred
        node = extract_node("""
        from PyQt6.QtCore import QObject
        class Foo(QObject):
            attr = undefined_func()
        obj = Foo()
        obj.attr  #@
        """)

        import pytest

        with pytest.raises(UseInferenceDefault):
            list(_infer_signal_class_attribute(node))

    def test_infer_signal_class_attribute_outer_inference_error(self):
        """Test when expr.infer() raises InferenceError."""
        from astroid.exceptions import UseInferenceDefault

        from pylint_qt.transforms.signals import _infer_signal_class_attribute

        # Create a mock node
        node = MagicMock()
        node.attrname = "test"
        node.expr.infer.side_effect = InferenceError()

        import pytest

        with pytest.raises(UseInferenceDefault):
            list(_infer_signal_class_attribute(node))

    def test_infer_signal_class_attribute_attr_parent_not_assign(self):
        """Test when attr_node.parent is neither Assign nor AnnAssign."""
        from astroid.bases import Instance
        from astroid.exceptions import UseInferenceDefault

        from pylint_qt.transforms.signals import _infer_signal_class_attribute

        # Create a mock classdef
        mock_classdef = MagicMock(spec=nodes.ClassDef)
        mock_assignname = MagicMock(spec=nodes.AssignName)

        # Parent is something other than Assign/AnnAssign (e.g., For loop)
        mock_for = MagicMock(spec=nodes.For)
        mock_assignname.parent = mock_for

        mock_classdef.locals = {"attr": [mock_assignname]}
        mock_classdef.mro.return_value = [mock_classdef]

        # Create mock instance
        mock_instance = MagicMock(spec=Instance)
        mock_instance._proxied = mock_classdef

        # Create node
        node = MagicMock()
        node.attrname = "attr"
        node.expr.infer.return_value = iter([mock_instance])

        import pytest

        with pytest.raises(UseInferenceDefault):
            list(_infer_signal_class_attribute(node))

    def test_infer_signal_class_attribute_annassign_without_value(self):
        """Test AnnAssign without value (just annotation, no assignment)."""
        from astroid.bases import Instance
        from astroid.exceptions import UseInferenceDefault

        from pylint_qt.transforms.signals import _infer_signal_class_attribute

        # Create a mock classdef
        mock_classdef = MagicMock(spec=nodes.ClassDef)
        mock_assignname = MagicMock(spec=nodes.AssignName)

        # Parent is AnnAssign but without a value (just type annotation)
        mock_annassign = MagicMock(spec=nodes.AnnAssign)
        mock_annassign.value = None  # No value, just annotation
        mock_assignname.parent = mock_annassign

        mock_classdef.locals = {"attr": [mock_assignname]}
        mock_classdef.mro.return_value = [mock_classdef]

        # Create mock instance
        mock_instance = MagicMock(spec=Instance)
        mock_instance._proxied = mock_classdef

        # Create node
        node = MagicMock()
        node.attrname = "attr"
        node.expr.infer.return_value = iter([mock_instance])

        import pytest

        with pytest.raises(UseInferenceDefault):
            list(_infer_signal_class_attribute(node))


class TestTransformRegistration:
    """Test that transforms are properly registered."""

    def test_transforms_registered(self):
        """Verify transforms are registered with astroid."""
        transform_visitor = MANAGER._transform
        assert transform_visitor.transforms, "No transforms registered"

    def test_functiondef_transform_registered(self):
        """Verify FunctionDef transform is registered."""
        from astroid.nodes import FunctionDef

        transform_visitor = MANAGER._transform
        funcdefs = transform_visitor.transforms.get(FunctionDef, [])
        plugin_transforms = [f for f, _ in funcdefs if "pylint_qt" in getattr(f, "__module__", "")]
        assert plugin_transforms, "No FunctionDef transforms from pylint_qt"

    def test_classdef_transforms_registered(self):
        """Verify ClassDef transforms are registered."""
        from astroid.nodes import ClassDef

        transform_visitor = MANAGER._transform
        classdefs = transform_visitor.transforms.get(ClassDef, [])
        plugin_transforms = [f for f, _ in classdefs if "pylint_qt" in getattr(f, "__module__", "")]
        assert len(plugin_transforms) == 2, "Expected 2 ClassDef transforms (PyQt + PySide)"

    def test_attribute_transforms_registered(self):
        """Verify Attribute transforms are registered for subscript and class attr signals."""
        from astroid.nodes import Attribute

        transform_visitor = MANAGER._transform
        attrs = transform_visitor.transforms.get(Attribute, [])
        # Check predicates for pylint_qt transforms (inference_tip wraps the transform)
        plugin_transforms = [
            p for _, p in attrs if p and "pylint_qt" in getattr(p, "__module__", "")
        ]
        assert len(plugin_transforms) >= 2, "Expected at least 2 Attribute transforms"
