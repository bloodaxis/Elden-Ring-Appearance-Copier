#!/bin/sh
set -eu

APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
LOCAL_PYTHON="$APP_DIR/.venv/bin/python"

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }

find_system_python() {
    for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" >/dev/null 2>&1 &&
           "$candidate" -c 'import sys, PySide6; raise SystemExit(not ((3, 10) <= sys.version_info[:2] < (3, 15)))' >/dev/null 2>&1; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

log "Elden Ring Appearance Copier starting..."

if PYTHON=$(find_system_python); then
    log "Using system Python and PySide6: $PYTHON"
elif [ -x "$LOCAL_PYTHON" ] && "$LOCAL_PYTHON" -c 'import PySide6' >/dev/null 2>&1; then
    PYTHON=$LOCAL_PYTHON
    log "Using locally installed dependencies: $APP_DIR/.venv"
else
    printf '\nPython with PySide6 was not found on the system.\n'
    printf 'A private Python runtime, if needed, will be installed at:\n  %s/runtime/linux\n' "$APP_DIR"
    printf 'The Python packages will be installed at:\n  %s/.venv\n' "$APP_DIR"
    printf 'This does not require administrator access or modify system packages.\n\n'
    printf 'Install the dependencies now? [y/N] '
    read -r answer || answer=
    case "$answer" in
        y|Y|yes|YES|Yes)
            "$APP_DIR/install-dependencies.sh"
            PYTHON=$LOCAL_PYTHON
            ;;
        *)
            log "Dependencies were not installed."
            log "Run $APP_DIR/install-dependencies.sh when you are ready."
            exit 1
            ;;
    esac
fi

log "Opening the application..."
ER_APPEARANCE_ROOT="$APP_DIR" PYTHONPATH="$APP_DIR/app" \
PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
exec "$PYTHON" "$APP_DIR/app/face_favorites_gui.py" "$@"
