"""Transforms for Qt signal inference."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Literal

from astroid import nodes
from astroid.bases import Instance
from astroid.builder import parse
from astroid.context import InferenceContext
from astroid.exceptions import InferenceError, UseInferenceDefault
from astroid.inference_tip import inference_tip
from astroid.manager import AstroidManager
from astroid.typing import InferenceResult

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

QtBinding = Literal["pyqt", "pyside"]

_PYQT_ROOTS: frozenset[str] = frozenset({"PyQt5", "PyQt6"})
_PYSIDE_ROOTS: frozenset[str] = frozenset({"PySide2", "PySide6"})
_ALL_QT_ROOTS: frozenset[str] = _PYQT_ROOTS | _PYSIDE_ROOTS

_PYQT_SIGNAL_QNAMES: frozenset[str] = frozenset(
    {
        "PyQt5.QtCore.pyqtSignal",
        "PyQt6.QtCore.pyqtSignal",
    }
)

_PYSIDE_SIGNAL_QNAMES: frozenset[str] = frozenset(
    {
        "PySide2.QtCore.Signal",
        "PySide6.QtCore.Signal",
    }
)

_ALL_SIGNAL_QNAMES: frozenset[str] = _PYQT_SIGNAL_QNAMES | _PYSIDE_SIGNAL_QNAMES

# Cache key for storing Qt binding detection result on module nodes
_QT_BINDING_CACHE_KEY = "__pylint_qt_binding__"

# -----------------------------------------------------------------------------
# Signal Templates
#
# PyQt signals have a `.signal` attribute that returns the C++ signature string.
# PySide signals do not have this attribute.
# -----------------------------------------------------------------------------

_SIGNAL_TEMPLATE_CODE = """
_UNSET = object()

class _PyQtSignalTemplate:
    signal: str = ""
    def connect(self, slot, type=None, no_receiver_check=False): pass
    def disconnect(self, slot=_UNSET): pass
    def emit(self, *args): pass
    def __getitem__(self, key): return self

class _PySideSignalTemplate:
    def connect(self, slot, type=None): pass
    def disconnect(self, slot=_UNSET): pass
    def emit(self, *args): pass
    def __getitem__(self, key): return self
"""

_TEMPLATES_MODULE = parse(_SIGNAL_TEMPLATE_CODE)
_PYQT_SIGNAL_TEMPLATE: nodes.ClassDef = _TEMPLATES_MODULE["_PyQtSignalTemplate"]
_PYSIDE_SIGNAL_TEMPLATE: nodes.ClassDef = _TEMPLATES_MODULE["_PySideSignalTemplate"]


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _get_qt_binding(node: nodes.NodeNG) -> QtBinding | None:
    """Detect which Qt binding is used in the module containing node.

    Results are cached on the module node for performance.
    """
    module = node.root()

    # Check cache
    cached = getattr(module, _QT_BINDING_CACHE_KEY, None)
    if cached is not None:
        return cached if cached != "none" else None

    binding: QtBinding | None = None
    for imp in module.nodes_of_class((nodes.Import, nodes.ImportFrom)):
        if isinstance(imp, nodes.ImportFrom):
            names = [imp.modname] if imp.modname else []
        else:
            names = [name for name, _ in imp.names]

        for name in names:
            if name and name.startswith("PyQt"):
                binding = "pyqt"
                break
            if name and name.startswith("PySide"):
                binding = "pyside"
                break
        if binding:
            break

    # Cache result (use "none" string to distinguish from uncached None)
    setattr(module, _QT_BINDING_CACHE_KEY, binding if binding else "none")
    return binding


def _get_signal_template(node: nodes.NodeNG) -> nodes.ClassDef:
    """Get the appropriate signal template based on Qt binding."""
    binding = _get_qt_binding(node)
    return _PYQT_SIGNAL_TEMPLATE if binding == "pyqt" else _PYSIDE_SIGNAL_TEMPLATE


def _infer_signal_instance(node: nodes.NodeNG) -> Iterator[InferenceResult]:
    """Return an iterator yielding a signal template instance."""
    template = _get_signal_template(node)
    return iter([template.instantiate_class()])


# -----------------------------------------------------------------------------
# Predicates
# -----------------------------------------------------------------------------


def _looks_like_pyqt_signal_classdef(node: nodes.ClassDef) -> bool:
    """Check if node is a PyQt signal class definition."""
    return node.qname() in _PYQT_SIGNAL_QNAMES


def _looks_like_pyside_signal_classdef(node: nodes.ClassDef) -> bool:
    """Check if node is a PySide signal class definition."""
    return node.qname() in _PYSIDE_SIGNAL_QNAMES


def _looks_like_qt_signal_functiondef(node: nodes.FunctionDef) -> bool:
    """Check if node is a Qt signal represented as a FunctionDef.

    Qt signals in C++ extension modules are represented as FunctionDef nodes
    with a __class__ instance attribute pointing to the signal class.
    """
    root = node.qname().partition(".")[0]
    if root not in _ALL_QT_ROOTS:
        return False

    klasses = node.instance_attrs.get("__class__", [])
    for cls in klasses:
        name = getattr(cls, "name", "")
        if name == "pyqtSignal" and root in _PYQT_ROOTS:
            return True
        if name == "Signal" and root in _PYSIDE_ROOTS:
            return True
    return False


def _looks_like_subscripted_signal(node: nodes.Attribute) -> bool:
    """Check if node is a signal being subscripted (e.g., signal[int]).

    This handles overloaded signals where the type is selected via subscript:
        button.clicked[bool].connect(handler)
    """
    if not isinstance(node.parent, nodes.Subscript):
        return False
    if node.parent.value is not node:
        return False
    return _get_qt_binding(node) is not None


def _looks_like_signal_class_attribute(node: nodes.Attribute) -> bool:
    """Check if node might be accessing a signal defined as a class attribute.

    This is a lightweight check that only verifies:
    1. The expression can be inferred to an Instance
    2. The attribute name exists in some ancestor's locals
    3. The module uses a Qt binding

    The actual signal type verification happens in the inference function.
    """
    # Skip signal[type] subscript access
    if isinstance(node.parent, nodes.Subscript) and node.parent.value is node:
        return False

    # Check for Qt imports
    if _get_qt_binding(node) is None:
        return False

    attrname = node.attrname

    try:
        for val in node.expr.infer():
            if not isinstance(val, Instance):
                continue

            cls = val._proxied  # pylint: disable=protected-access
            if not isinstance(cls, nodes.ClassDef):
                continue

            # Check if attribute exists in class or ancestors
            try:
                mro = cls.mro()
            except (NotImplementedError, TypeError):
                mro = [cls]

            for ancestor in mro:
                if not isinstance(ancestor, nodes.ClassDef):
                    continue
                if attrname in ancestor.locals:
                    return True
    except InferenceError:
        pass

    return False


# -----------------------------------------------------------------------------
# Transform Functions
# -----------------------------------------------------------------------------


def _attach_signal_instance_attrs(node: nodes.NodeNG, template: nodes.ClassDef) -> None:
    """Attach signal methods from template to node's instance_attrs."""
    node.instance_attrs["connect"] = [template["connect"]]
    node.instance_attrs["disconnect"] = [template["disconnect"]]
    node.instance_attrs["emit"] = [template["emit"]]
    node.instance_attrs["__getitem__"] = [template["__getitem__"]]
    if "signal" in template:
        node.instance_attrs["signal"] = [template["signal"]]


def _transform_pyqt_signal(node: nodes.NodeNG) -> None:
    """Transform a PyQt signal node to have signal methods."""
    _attach_signal_instance_attrs(node, _PYQT_SIGNAL_TEMPLATE)


def _transform_pyside_signal(node: nodes.NodeNG) -> None:
    """Transform a PySide signal node to have signal methods."""
    _attach_signal_instance_attrs(node, _PYSIDE_SIGNAL_TEMPLATE)


def _transform_signal_functiondef(node: nodes.FunctionDef) -> None:
    """Transform a FunctionDef node that represents a Qt signal."""
    root = node.qname().partition(".")[0]
    if root in _PYQT_ROOTS:
        _transform_pyqt_signal(node)
    else:
        _transform_pyside_signal(node)


# -----------------------------------------------------------------------------
# Inference Functions
# -----------------------------------------------------------------------------


def _infer_subscripted_signal(
    node: nodes.Attribute,
    ctx: InferenceContext | None = None,  # pylint: disable=unused-argument
) -> Iterator[InferenceResult]:
    """Infer signal[type] subscript to return a signal instance.

    Handles overloaded signal selection:
        spinbox.valueChanged[int].connect(handler)
    """
    return _infer_signal_instance(node)


def _infer_signal_class_attribute(  # pylint: disable=too-many-branches,too-many-nested-blocks
    node: nodes.Attribute,
    ctx: InferenceContext | None = None,  # pylint: disable=unused-argument
) -> Iterator[InferenceResult]:
    """Infer a signal defined as a class attribute.

    Handles the descriptor protocol case where a signal is defined as a class
    attribute and accessed on an instance:

        class MyWidget(QObject):
            my_signal = pyqtSignal(int)

        obj = MyWidget()
        obj.my_signal.connect(...)

    Astroid normally returns Uninferable for descriptors because it can't
    understand the descriptor protocol. This function provides a SignalTemplate
    instance instead.
    """
    attrname = node.attrname

    try:
        for val in node.expr.infer():
            if not isinstance(val, Instance):
                continue

            cls = val._proxied  # pylint: disable=protected-access
            if not isinstance(cls, nodes.ClassDef):
                continue

            # Check the full MRO for the signal attribute (handles inheritance)
            try:
                mro = cls.mro()
            except (NotImplementedError, TypeError):
                mro = [cls]

            for ancestor in mro:
                if not isinstance(ancestor, nodes.ClassDef):
                    continue
                if attrname not in ancestor.locals:
                    continue

                for attr_node in ancestor.locals[attrname]:
                    if not isinstance(attr_node, nodes.AssignName):
                        continue

                    # Handle both Assign and AnnAssign
                    parent = attr_node.parent
                    if isinstance(parent, nodes.Assign):
                        value_node = parent.value
                    elif isinstance(parent, nodes.AnnAssign) and parent.value:
                        value_node = parent.value
                    else:
                        continue

                    # Verify this is actually a Qt signal
                    try:
                        for attr_val in value_node.infer():
                            if isinstance(attr_val, Instance):
                                # pylint: disable-next=protected-access
                                if attr_val._proxied.qname() in _ALL_SIGNAL_QNAMES:
                                    return _infer_signal_instance(node)
                    except InferenceError:
                        pass

    except InferenceError:
        pass

    # Fall back to default inference
    raise UseInferenceDefault


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


def register_transforms(manager: AstroidManager) -> None:
    """Register all Qt signal transforms with astroid."""
    # Transform FunctionDef nodes representing Qt signals (from C++ bindings)
    manager.register_transform(
        nodes.FunctionDef,
        _transform_signal_functiondef,
        _looks_like_qt_signal_functiondef,
    )

    # Transform ClassDef nodes for direct signal class references
    manager.register_transform(
        nodes.ClassDef,
        _transform_pyqt_signal,
        _looks_like_pyqt_signal_classdef,
    )
    manager.register_transform(
        nodes.ClassDef,
        _transform_pyside_signal,
        _looks_like_pyside_signal_classdef,
    )

    # Inference tip for subscripted signals: signal[type].connect(...)
    manager.register_transform(
        nodes.Attribute,
        inference_tip(_infer_subscripted_signal),
        _looks_like_subscripted_signal,
    )

    # Inference tip for class attribute signals
    manager.register_transform(
        nodes.Attribute,
        inference_tip(_infer_signal_class_attribute),
        _looks_like_signal_class_attribute,
    )
