pylint-qt
=========

``pylint-qt`` is a `Pylint <http://pylint.org>`__ plugin for improving code analysis when analysing code using Qt, supporting both PyQt and PySide.

Usage
-----

.. code-block:: bash

    pylint --load-plugins=pylint_qt <path_to_your_sources>

Or in ``pyproject.toml``:

.. code-block:: toml

    [tool.pylint.main]
    load-plugins = ["pylint_qt"]
