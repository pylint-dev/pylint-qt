# Changelog

## [0.1.0] - 2026-04-07

Initial release.

### Added

* Astroid inference for Qt signals across PyQt5, PyQt6, PySide2, and PySide6
* Support for `Signal()` instances exposing `connect`, `disconnect`, and `emit`
* Support for built-in widget signals (e.g. `QPushButton.clicked`, `QTimer.timeout`)
* Support for subscripted signals (e.g. `signal[int]`)
* Support for class-attribute signals accessed via `self` and via the class
