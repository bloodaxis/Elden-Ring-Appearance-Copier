#!/usr/bin/env python3
"""Two-pane Qt GUI for Elden Ring appearance transfers."""

from __future__ import annotations

import hashlib
import shutil
import os
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (QApplication, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QSplitter, QTextEdit, QVBoxLayout, QWidget)

import elden_bling_json
import face_favorites as engine

SAVE_FILTER = "Elden Ring saves (*.sl2 *.co2 *.err);;All files (*)"
JSON_FILTER = "Elden Bling JSON (*.json);;All files (*)"
PACKAGE_ROOT = Path(
    os.environ.get("ER_APPEARANCE_ROOT", Path(__file__).resolve().parent)
).resolve()
CONFIG_PATH = PACKAGE_ROOT / "EldenRingAppearanceCopier.conf"
SETTINGS = QSettings(str(CONFIG_PATH), QSettings.IniFormat)


def next_backup_path(path: Path) -> Path:
    candidate = path.with_name(f"{path.name}.backup")
    number = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.backup.{number}")
        number += 1
    return candidate


def last_directory() -> Path:
    saved = SETTINGS.value("last_directory", str(Path.home()), type=str)
    path = Path(saved)
    return path if path.is_dir() else Path.home()


def remember_path(path: Path) -> None:
    directory = path if path.is_dir() else path.parent
    SETTINGS.setValue("last_directory", str(directory))


class SavePane(QGroupBox):
    operation_done = Signal(str)
    operation_undone = Signal()
    operations_reset = Signal()

    def __init__(self, title: str):
        super().__init__(title)
        self.path: Path | None = None
        self.data: bytes | None = None
        self.baseline_data: bytes | None = None
        self.dirty = False
        self.history: list[
            tuple[bytes, tuple[str, int] | None, dict[tuple[str, int], str]]
        ] = []
        self.appearance_sources: dict[tuple[str, int], str] = {}
        self.path_box = QLineEdit(readOnly=True)
        browse = QPushButton("Open save…")
        browse.clicked.connect(self.open_save)
        path_row = QHBoxLayout()
        path_row.addWidget(self.path_box, 1)
        path_row.addWidget(browse)
        self.entries = QListWidget()
        self.entries.setAlternatingRowColors(True)
        self.entries.setMinimumWidth(360)
        self.actions = QHBoxLayout()
        self.history_actions = QHBoxLayout()
        self.status = QLabel("No save loaded")
        self.save_button = QPushButton("Save As…")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_as)
        footer = QHBoxLayout()
        footer.addWidget(self.status, 1)
        footer.addWidget(self.save_button)
        layout = QVBoxLayout(self)
        layout.addLayout(path_row)
        layout.addWidget(self.entries, 1)
        layout.addLayout(self.actions)
        layout.addLayout(self.history_actions)
        layout.addLayout(footer)

        delete_button = QPushButton("Delete Favorite")
        delete_button.clicked.connect(self.delete_selected)
        self.undo_button = QPushButton("Undo")
        self.undo_button.setEnabled(False)
        self.undo_button.clicked.connect(self.undo)
        self.history_actions.addWidget(delete_button)
        self.history_actions.addWidget(self.undo_button)

    def add_action(self, label: str, callback) -> None:
        button = QPushButton(label)
        button.clicked.connect(callback)
        self.actions.addWidget(button)

    def open_save(self) -> None:
        start = str(self.path.parent if self.path else last_directory())
        filename, _ = QFileDialog.getOpenFileName(self, "Open Elden Ring save", start, SAVE_FILTER)
        if not filename:
            return
        try:
            data = Path(filename).read_bytes()
            offsets = engine.layout(data)
            engine.validate_save(data, offsets, Path(filename).name)
        except Exception as exception:
            QMessageBox.critical(self, "Cannot open save", str(exception))
            return
        self.path, self.data, self.baseline_data, self.dirty = Path(filename), data, data, False
        self.history.clear()
        self.appearance_sources.clear()
        self.operations_reset.emit()
        remember_path(self.path)
        self.path_box.setText(filename)
        self.refresh()

    def refresh(self, select: tuple[str, int] | None = None) -> None:
        self.entries.clear()
        if self.data is None:
            return
        offsets = engine.layout(self.data)
        for slot in range(engine.SLOT_COUNT):
            if self.data[offsets["active_slots"] + slot] != 1:
                continue
            try:
                engine.read_appearance(self.data, offsets, ("character", slot))
            except ValueError:
                continue
            name = engine.decode_name(self.data, offsets, slot) or "Unnamed"
            location = ("character", slot)
            text = f"Character {slot}: {name}"
            if source := self.appearance_sources.get(location):
                text += f" ({source})"
            self._add_item(text, location, select)
        for slot in range(engine.FAVORITE_COUNT):
            at = engine.favorite_offset(offsets, slot)
            face = self.data[at:at + engine.FACE_BUFFER_SIZE]
            state = "occupied" if engine.face_is_valid(face) else "empty"
            location = ("favorite", slot)
            text = f"Favorite {slot}: {state}"
            if source := self.appearance_sources.get(location):
                text += f" ({source})"
            self._add_item(text, location, select)
        marker = " — unsaved changes" if self.dirty else ""
        self.status.setText(f"{len(self.data):,} bytes{marker}")
        self.save_button.setEnabled(self.dirty)
        self.undo_button.setEnabled(bool(self.history))

    def _add_item(self, text: str, location: tuple[str, int], select) -> None:
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, location)
        if location[0] == "favorite" and text.endswith("empty"):
            item.setForeground(Qt.darkGray)
        self.entries.addItem(item)
        if location == select:
            self.entries.setCurrentItem(item)

    def selected_location(self) -> tuple[str, int] | None:
        item = self.entries.currentItem()
        return tuple(item.data(Qt.UserRole)) if item else None

    def selected_appearance(self) -> bytes:
        location = self.selected_location()
        if self.data is None or location is None:
            raise ValueError(f"Select an occupied character or favorite in {self.title()}")
        return engine.read_appearance(self.data, engine.layout(self.data), location)

    def selected_appearance_source(self) -> str:
        location = self.selected_location()
        if self.data is None or location is None:
            raise ValueError(f"Select an occupied character or favorite in {self.title()}")
        if source := self.appearance_sources.get(location):
            return source
        kind, slot = location
        if kind == "character":
            name = engine.decode_name(self.data, engine.layout(self.data), slot) or "Unnamed"
            return f"FaceData from {self.title()} slot {slot}: {name}"
        return f"FaceData from {self.title()} favorite {slot}"

    def apply(
        self, appearance: bytes, location: tuple[str, int], source: str | None = None
    ) -> None:
        if self.data is None:
            raise ValueError(f"Open a save in {self.title()} first")
        offsets = engine.layout(self.data)
        overwrite = False
        if location[0] == "favorite":
            at = engine.favorite_offset(offsets, location[1])
            overwrite = any(self.data[at:at + engine.FAVORITE_SIZE])
            if overwrite and QMessageBox.question(
                self, "Replace favorite?", f"Favorite {location[1]} is occupied. Replace it?"
            ) != QMessageBox.Yes:
                raise RuntimeError("Cancelled")
        self._remember(location)
        self.data = engine.write_appearance(self.data, offsets, location, appearance, overwrite)
        if source is None:
            self.appearance_sources.pop(location, None)
        else:
            self.appearance_sources[location] = source
        self.dirty = True
        self.refresh(location)

    def _remember(self, location: tuple[str, int] | None) -> None:
        if self.data is None:
            return
        self.history.append((self.data, location, self.appearance_sources.copy()))
        if len(self.history) > 20:
            del self.history[0]

    def delete_selected(self) -> None:
        location = self.selected_location()
        if self.data is None or location is None:
            QMessageBox.warning(self, "Select favorite", "Select a favorite to delete.")
            return
        if location[0] != "favorite":
            QMessageBox.warning(
                self, "Characters are not deleted",
                "Delete Favorite only clears favorite slots; it does not remove characters.",
            )
            return
        offsets = engine.layout(self.data)
        at = engine.favorite_offset(offsets, location[1])
        if not any(self.data[at:at + engine.FAVORITE_SIZE]):
            QMessageBox.information(self, "Already empty", f"Favorite {location[1]} is already empty.")
            return
        if QMessageBox.question(
            self, "Delete favorite?", f"Clear favorite {location[1]}?"
        ) != QMessageBox.Yes:
            return
        self._remember(location)
        self.data = engine.delete_favorite(self.data, offsets, location[1])
        self.appearance_sources.pop(location, None)
        self.dirty = True
        self.refresh(location)
        self.operation_done.emit(f"{self.title()}: deleted favorite {location[1]}")

    def undo(self) -> None:
        if not self.history:
            return
        self.data, location, self.appearance_sources = self.history.pop()
        self.dirty = self.data != self.baseline_data
        self.refresh(location)
        self.operation_undone.emit()

    def save_as(self) -> None:
        if self.data is None or self.path is None:
            return
        default = self.path.with_name(f"{self.path.stem}-appearance-copy{self.path.suffix}")
        filename, _ = QFileDialog.getSaveFileName(self, "Save edited copy", str(default), SAVE_FILTER)
        if not filename:
            return
        remember_path(Path(filename))
        output_path = Path(filename)
        backup_path: Path | None = None
        try:
            offsets = engine.layout(self.data)
            engine.validate_save(self.data, offsets, "edited save")
            if output_path.resolve() == self.path.resolve():
                backup_path = next_backup_path(self.path)
                shutil.copy2(self.path, backup_path)
            output_path.write_bytes(self.data)
            digest = hashlib.sha256(self.data).hexdigest()
        except Exception as exception:
            QMessageBox.critical(self, "Save failed", str(exception))
            return
        self.dirty = False
        self.baseline_data = self.data
        self.history.clear()
        self.operations_reset.emit()
        self.refresh(self.selected_location())
        backup_message = f"\n\nOriginal backup:\n{backup_path}" if backup_path else ""
        QMessageBox.information(
            self,
            "Save created",
            f"Created:\n{filename}{backup_message}\n\nSHA-256:\n{digest}",
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Elden Ring Appearance Copier")
        self.resize(1120, 760)
        self.left, self.right = SavePane("Left save"), SavePane("Right save")
        self.operations: list[tuple[SavePane, str]] = []
        for pane in (self.left, self.right):
            pane.operation_done.connect(lambda description, p=pane: self.record_operation(p, description))
            pane.operation_undone.connect(lambda p=pane: self.remove_last_operation(p))
            pane.operations_reset.connect(lambda p=pane: self.clear_operations(p))
        self.left.add_action("Import JSON…", lambda: self.import_json(self.left))
        self.left.add_action("Export JSON…", lambda: self.export_json(self.left))
        self.right.add_action("Import JSON…", lambda: self.import_json(self.right))
        self.right.add_action("Export JSON…", lambda: self.export_json(self.right))
        controls = QVBoxLayout()
        controls.addStretch()
        self._button(controls, "Copy  →", lambda: self.copy(self.left, self.right))
        self._button(controls, "←  Copy", lambda: self.copy(self.right, self.left))
        controls.addStretch()
        control_widget = QWidget()
        control_widget.setLayout(controls)
        top = QSplitter()
        top.addWidget(self.left)
        top.addWidget(control_widget)
        top.addWidget(self.right)
        top.setStretchFactor(0, 1)
        top.setStretchFactor(2, 1)
        self.log = QTextEdit(readOnly=True)
        self.log.setMaximumHeight(135)
        self.log.setPlaceholderText("Operations stay in memory until Save As is used.")
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(top, 1)
        layout.addWidget(QLabel("Operations in memory"))
        layout.addWidget(self.log)
        self.setCentralWidget(central)

    def _button(self, layout, label, callback):
        button = QPushButton(label)
        button.clicked.connect(callback)
        layout.addWidget(button)

    def record_operation(self, pane: SavePane, description: str) -> None:
        self.operations.append((pane, description))
        self.rebuild_log()

    def remove_last_operation(self, pane: SavePane) -> None:
        for index in range(len(self.operations) - 1, -1, -1):
            if self.operations[index][0] is pane:
                del self.operations[index]
                break
        self.rebuild_log()

    def clear_operations(self, pane: SavePane) -> None:
        self.operations = [operation for operation in self.operations if operation[0] is not pane]
        self.rebuild_log()

    def rebuild_log(self) -> None:
        self.log.setPlainText("\n".join(description for _, description in self.operations))

    def copy(self, source: SavePane, destination: SavePane) -> None:
        location = destination.selected_location()
        if location is None:
            QMessageBox.warning(self, "Select destination", f"Select a destination in {destination.title()}.")
            return
        try:
            appearance = source.selected_appearance()
            source_location = source.selected_location()
            source_description = source.selected_appearance_source()
            destination.apply(appearance, location, source_description)
        except RuntimeError:
            return
        except Exception as exception:
            QMessageBox.critical(self, "Copy failed", str(exception))
            return
        self.record_operation(
            destination,
            f"{source.title()} {source_location} → {destination.title()} {location}",
        )

    def import_json(self, destination: SavePane) -> None:
        location = destination.selected_location()
        if location is None:
            QMessageBox.warning(self, "Select destination", f"Select a destination in {destination.title()}.")
            return
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import Elden Bling JSON", str(last_directory()), JSON_FILTER
        )
        if not filename:
            return
        remember_path(Path(filename))
        try:
            destination.apply(
                elden_bling_json.load(Path(filename)),
                location,
                f"FaceData from JSON: {Path(filename).name}",
            )
        except RuntimeError:
            return
        except Exception as exception:
            QMessageBox.critical(self, "JSON import failed", str(exception))
            return
        self.record_operation(
            destination, f"JSON {Path(filename).name} → {destination.title()} {location}"
        )

    def export_json(self, source: SavePane) -> None:
        try:
            appearance = source.selected_appearance()
            location = source.selected_location()
        except Exception as exception:
            QMessageBox.warning(self, "Select source", str(exception))
            return
        default = last_directory() / f"elden_bling_{location[0]}_{location[1]}.json"
        filename, _ = QFileDialog.getSaveFileName(self, "Export Elden Bling JSON", str(default), JSON_FILTER)
        if not filename:
            return
        remember_path(Path(filename))
        try:
            name = "Exported"
            if location[0] == "character" and source.data is not None:
                name = engine.decode_name(source.data, engine.layout(source.data), location[1])
            elden_bling_json.save(Path(filename), appearance, name)
        except Exception as exception:
            QMessageBox.critical(self, "JSON export failed", str(exception))
            return
        self.log.append(f"{source.title()} {location} → JSON {Path(filename).name}")


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    if sys.platform == "win32":
        print("Elden Ring Appearance Copier window is ready.", flush=True)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
