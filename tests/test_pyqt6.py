"""Tests for PyQt6 signal inference."""

import pytest

pytest.importorskip("PyQt6")

from astroid import Uninferable, extract_node
from astroid.nodes import FunctionDef

import pylint_qt  # noqa: F401


class TestUserDefinedSignals:
    """Tests for user-defined pyqtSignal() inference."""

    def test_signal_has_connect(self):
        """Test pyqtSignal() instances expose connect."""
        node = extract_node("""
        from PyQt6.QtCore import pyqtSignal
        sig = pyqtSignal()
        sig.connect  #@
        """)
        inferred = node.inferred()[0]
        assert inferred is not Uninferable
        assert isinstance(inferred, FunctionDef)

    def test_signal_has_disconnect(self):
        """Test pyqtSignal() instances expose disconnect."""
        node = extract_node("""
        from PyQt6.QtCore import pyqtSignal
        sig = pyqtSignal()
        sig.disconnect  #@
        """)
        inferred = node.inferred()[0]
        assert inferred is not Uninferable
        assert isinstance(inferred, FunctionDef)

    def test_signal_has_emit(self):
        """Test pyqtSignal() instances expose emit."""
        node = extract_node("""
        from PyQt6.QtCore import pyqtSignal
        sig = pyqtSignal()
        sig.emit  #@
        """)
        inferred = node.inferred()[0]
        assert inferred is not Uninferable
        assert isinstance(inferred, FunctionDef)

    def test_signal_with_arguments(self):
        """Test pyqtSignal(int, str) works."""
        node = extract_node("""
        from PyQt6.QtCore import pyqtSignal
        sig = pyqtSignal(int, str)
        sig.emit  #@
        """)
        inferred = node.inferred()[0]
        assert inferred is not Uninferable
        assert isinstance(inferred, FunctionDef)


class TestBuiltinWidgetSignals:
    """Tests for built-in Qt widget signals."""

    def test_qpushbutton_clicked(self):
        """Test QPushButton.clicked.connect."""
        node = extract_node("""
        from PyQt6.QtWidgets import QPushButton
        btn = QPushButton()
        btn.clicked.connect  #@
        """)
        inferred = node.inferred()[0]
        assert inferred is not Uninferable
        assert isinstance(inferred, FunctionDef)

    def test_qlineedit_text_changed(self):
        """Test QLineEdit.textChanged.connect."""
        node = extract_node("""
        from PyQt6.QtWidgets import QLineEdit
        edit = QLineEdit()
        edit.textChanged.connect  #@
        """)
        inferred = node.inferred()[0]
        assert inferred is not Uninferable
        assert isinstance(inferred, FunctionDef)

    def test_qcombobox_current_index_changed(self):
        """Test QComboBox.currentIndexChanged.connect."""
        node = extract_node("""
        from PyQt6.QtWidgets import QComboBox
        combo = QComboBox()
        combo.currentIndexChanged.connect  #@
        """)
        inferred = node.inferred()[0]
        assert inferred is not Uninferable
        assert isinstance(inferred, FunctionDef)

    def test_qcheckbox_state_changed(self):
        """Test QCheckBox.stateChanged.connect."""
        node = extract_node("""
        from PyQt6.QtWidgets import QCheckBox
        cb = QCheckBox()
        cb.stateChanged.connect  #@
        """)
        inferred = node.inferred()[0]
        assert inferred is not Uninferable
        assert isinstance(inferred, FunctionDef)

    def test_qslider_value_changed(self):
        """Test QSlider.valueChanged.connect."""
        node = extract_node("""
        from PyQt6.QtWidgets import QSlider
        slider = QSlider()
        slider.valueChanged.connect  #@
        """)
        inferred = node.inferred()[0]
        assert inferred is not Uninferable
        assert isinstance(inferred, FunctionDef)

    def test_qtimer_timeout(self):
        """Test QTimer.timeout.connect."""
        node = extract_node("""
        from PyQt6.QtCore import QTimer
        timer = QTimer()
        timer.timeout.connect  #@
        """)
        inferred = node.inferred()[0]
        assert inferred is not Uninferable
        assert isinstance(inferred, FunctionDef)


class TestSignalSubscript:
    """Tests for signal[type] subscript pattern."""

    def test_subscript_connect(self):
        """Test signal[int].connect works."""
        node = extract_node("""
        from PyQt6.QtWidgets import QSpinBox
        spin = QSpinBox()
        spin.valueChanged[int].connect  #@
        """)
        inferred = node.inferred()[0]
        assert inferred is not Uninferable

    def test_subscript_with_bare_import(self):
        """Test subscript with bare import statement."""
        node = extract_node("""
        import PyQt6.QtWidgets
        spin = PyQt6.QtWidgets.QSpinBox()
        spin.valueChanged[int].connect  #@
        """)
        inferred = node.inferred()[0]
        assert inferred is not Uninferable


class TestClassAttributeSignals:
    """Tests for user-defined class attribute signals (descriptor protocol)."""

    def test_class_attribute_signal_via_self(self):
        """Test class attribute signal accessed via self."""
        node = extract_node("""
        from PyQt6.QtCore import pyqtSignal, QObject
        class MyWidget(QObject):
            my_signal = pyqtSignal()
            def setup(self):
                self.my_signal.connect  #@
        """)
        inferred = node.inferred()[0]
        assert inferred is not Uninferable
        # Returns BoundMethod (method on Instance) rather than FunctionDef
        assert hasattr(inferred, "name") and inferred.name == "connect"

    def test_class_attribute_signal_external_access(self):
        """Test class attribute signal accessed from external instance."""
        node = extract_node("""
        from PyQt6.QtCore import pyqtSignal, QObject
        class MyWidget(QObject):
            my_signal = pyqtSignal(int)
        obj = MyWidget()
        obj.my_signal.connect  #@
        """)
        inferred = node.inferred()[0]
        assert inferred is not Uninferable
        assert hasattr(inferred, "name") and inferred.name == "connect"

    def test_inherited_signal_via_mro(self):
        """Test signal inherited from parent class."""
        node = extract_node("""
        from PyQt6.QtCore import pyqtSignal, QObject
        class Parent(QObject):
            parent_signal = pyqtSignal()
        class Child(Parent):
            pass
        obj = Child()
        obj.parent_signal.connect  #@
        """)
        inferred = node.inferred()[0]
        assert inferred is not Uninferable
        assert hasattr(inferred, "name") and inferred.name == "connect"

    def test_annotated_assignment_signal(self):
        """Test signal with type annotation (AnnAssign)."""
        node = extract_node("""
        from PyQt6.QtCore import pyqtSignal, QObject
        class MyWidget(QObject):
            my_signal: pyqtSignal = pyqtSignal(int)
        obj = MyWidget()
        obj.my_signal.emit  #@
        """)
        inferred = node.inferred()[0]
        assert inferred is not Uninferable
        assert hasattr(inferred, "name") and inferred.name == "emit"
