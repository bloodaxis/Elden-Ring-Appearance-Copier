# Third-party components

This application uses system-provided PySide6 and Shiboken6. Their package
metadata offers LGPL-3.0-only, GPL-2.0-only, GPL-3.0-only, or a commercial Qt
license. This application uses them under LGPL-3.0-only. Copies of LGPL-3.0
and GPL-3.0 accompany the application.

When compatible system Python is unavailable, the optional installer downloads
CPython 3.12.10 from Python.org on Windows or CPython 3.12.14 from
`python-build-standalone` on Linux. CPython uses the Python Software Foundation
License and bundled component licenses; `python-build-standalone` is MPL-2.0
licensed.

The appearance/save layout implementation was developed with reference to
ClayAmore's ER Save Editor, distributed under the MIT or Apache-2.0 license.
Its license texts and copyright notice accompany this application.

Sources:

- https://github.com/ClayAmore/ER-Save-Editor
- https://code.qt.io/cgit/pyside/pyside-setup.git/
- https://www.qt.io/licensing/
- https://github.com/astral-sh/python-build-standalone
