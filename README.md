# Elden Ring Appearance Copier — System Edition

This package first uses Python and PySide6 already installed on the
system. If PySide6 is unavailable, the launchers offer to install it into a
private `.venv` inside this directory. If Python itself is unavailable, the
installer first downloads and verifies a private CPython runtime under
`runtime/linux` or `runtime/windows`, then installs the dependencies.

Requirements:

- Python 3.10 through 3.14
- PySide6 providing QtCore, QtGui, and QtWidgets

Install those through your operating system package manager when available.
Alternatively, install the pinned packages for your user account with:

```text
python3 -m pip install --user -r app/requirements.txt
```

Run `./run.sh` on Linux. To install the Linux dependencies separately, run:

```sh
./install-dependencies.sh
```

The installer prints every destination. Python packages go under `.venv`; a
downloaded Python runtime goes under `runtime`. 

On Windows, use `run.bat`. It follows the same process: system packages are
preferred, an existing local `.venv` is accepted, and installation is offered
when neither is available. To install Windows dependencies separately, run:

```bat
install-dependencies.bat
```

The last file-selector directory is stored in a generated
`EldenRingAppearanceCopier.conf` file beside the launchers.

The program stages changes in memory and writes only through **Save As**. Keep
a separate backup before placing an edited save in the game's save directory.
