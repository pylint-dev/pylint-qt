<div align="center">
  <h1>pylint-qt</h1>
  <p>
    <a href="https://pypi.org/project/pylint-qt/"><img src="https://img.shields.io/pypi/v/pylint-qt.svg" alt="PyPI version"></a>
    <a href="https://pypi.org/project/pylint-qt/"><img src="https://img.shields.io/pypi/pyversions/pylint-qt.svg" alt="Python versions"></a>
    <a href="https://github.com/pylint-dev/pylint-qt/actions/workflows/ci.yml"><img src="https://github.com/pylint-dev/pylint-qt/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
    <a href="https://codecov.io/gh/pylint-dev/pylint-qt"><img src="https://codecov.io/gh/pylint-dev/pylint-qt/graph/badge.svg" alt="Coverage"></a>
  </p>
  <p>A <a href="https://pylint.org">Pylint</a> plugin for improving code analysis when using Qt, supporting both PyQt and PySide.</p>
</div>

## Installation

```bash
pip install pylint-qt
```

## Usage

```bash
pylint --load-plugins=pylint_qt <path_to_your_sources>
```

Or in `pyproject.toml`:

```toml
[tool.pylint.main]
load-plugins = ["pylint_qt"]
```
