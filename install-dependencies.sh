#!/bin/sh
set -eu

APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV="$APP_DIR/.venv"
REQ="$APP_DIR/app/requirements.txt"
MARKER="$VENV/.appearance-copier-requirements"
RUNTIME="$APP_DIR/runtime/linux"
RUNTIME_PYTHON="$RUNTIME/bin/python3"
PY_NAME='cpython-3.12.14+20260901-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz'
PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20260901/cpython-3.12.14%2B20260901-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
PY_SHA256='72748da13197c1fb161e3afeef20a6a385ff24f2165e6e2758e47008e7faba4c'

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }

find_python() {
    for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" >/dev/null 2>&1 &&
           "$candidate" -c 'import sys; raise SystemExit(not ((3, 10) <= sys.version_info[:2] < (3, 15)))' >/dev/null 2>&1; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

download() {
    if command -v curl >/dev/null 2>&1; then
        curl --fail --location --progress-bar "$1" --output "$2"
    elif command -v wget >/dev/null 2>&1; then
        wget --output-document="$2" "$1"
    else
        log "ERROR: curl or wget is required to download Python."
        return 1
    fi
}

install_python() {
    [ "$(uname -s)" = Linux ] && [ "$(uname -m)" = x86_64 ] || {
        log "ERROR: Automatic Python installation supports 64-bit x86 Linux only."
        return 1
    }
    bootstrap="$APP_DIR/.bootstrap"
    archive="$bootstrap/$PY_NAME"
    staging="$bootstrap/extract"
    mkdir -p "$bootstrap"
    log "Python will be installed at: $RUNTIME"
    log "Downloading the private Python 3.12.14 runtime..."
    download "$PY_URL" "$archive"
    actual=$(sha256sum "$archive" | cut -d ' ' -f 1)
    [ "$actual" = "$PY_SHA256" ] || {
        log "ERROR: Python download checksum verification failed."
        rm -f "$archive"
        return 1
    }
    rm -rf "$staging"
    mkdir -p "$staging"
    log "Extracting Python..."
    tar -xzf "$archive" -C "$staging"
    mkdir -p "$APP_DIR/runtime"
    rm -rf "$RUNTIME"
    mv "$staging/python/install" "$RUNTIME"
    rm -rf "$bootstrap"
}

if PYTHON=$(find_python); then
    log "Using system Python: $PYTHON"
elif [ -x "$RUNTIME_PYTHON" ]; then
    PYTHON=$RUNTIME_PYTHON
    log "Using private Python: $PYTHON"
else
    install_python
    PYTHON=$RUNTIME_PYTHON
fi

log "Dependencies will be installed at: $VENV"
if [ ! -x "$VENV/bin/python" ]; then
    log "Creating the local Python environment with $PYTHON..."
    "$PYTHON" -m venv "$VENV"
fi

if [ ! -f "$MARKER" ] || ! cmp -s "$REQ" "$MARKER" ||
   ! "$VENV/bin/python" -c 'import PySide6' >/dev/null 2>&1; then
    log "Installing the packages listed in: $REQ"
    "$VENV/bin/python" -m pip install --disable-pip-version-check --no-input --requirement "$REQ"
    cp "$REQ" "$MARKER"
else
    log "The local dependencies are already installed and current."
fi

log "Dependency installation complete: $VENV"
