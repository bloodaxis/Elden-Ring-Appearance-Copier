#!/usr/bin/env python3
"""Inspect or transfer Elden Ring PC save appearance data.

This follows the fixed PC-save layout used by ER Save Editor. It never edits
an input file; write operations always produce a separate output and
recalculate the affected MD5 checksums.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path


HEADER_SIZE = 0x300
SLOT_SIZE = 0x280010
SLOT_COUNT = 10
USER_DATA_10_SIZE = 0x60010
PROFILE_SIZE = 0x24C
FACE_BUFFER_SIZE = 0x120
FAVORITE_SIZE = 0x130
FAVORITE_COUNT = 10


def layout(data: bytes) -> dict[str, int]:
    if data[:4] != b"BND4":
        raise ValueError("input is not a PC BND4 save")

    user_data = HEADER_SIZE + SLOT_COUNT * SLOT_SIZE
    if len(data) < user_data + USER_DATA_10_SIZE:
        raise ValueError("input is shorter than the expected PC save layout")

    menu_header = user_data + 0x15C
    menu_unknown, menu_length = struct.unpack_from("<II", data, menu_header)
    if menu_unknown != 0 or menu_length < 0x1800:
        raise ValueError(
            f"unexpected CSMenuSystemSaveLoad header: {menu_unknown=}, "
            f"length=0x{menu_length:X}"
        )

    menu_data = menu_header + 8
    active_slots = menu_data + menu_length
    profiles = active_slots + SLOT_COUNT
    if profiles + SLOT_COUNT * PROFILE_SIZE > user_data + USER_DATA_10_SIZE:
        raise ValueError("profile summaries exceed UserData10")

    return {
        "user_data": user_data,
        "menu_data": menu_data,
        "active_slots": active_slots,
        "profiles": profiles,
    }


def face_offset_for_profile(offsets: dict[str, int], slot: int) -> int:
    return offsets["profiles"] + slot * PROFILE_SIZE + 0x3A


def favorite_offset(offsets: dict[str, int], slot: int) -> int:
    return offsets["menu_data"] + 0x18 + slot * FAVORITE_SIZE


def decode_name(data: bytes, offsets: dict[str, int], slot: int) -> str:
    start = offsets["profiles"] + slot * PROFILE_SIZE
    return data[start : start + 0x22].decode("utf-16-le").split("\0", 1)[0]


def face_is_valid(face: bytes) -> bool:
    return (
        len(face) == FACE_BUFFER_SIZE
        and face[:4] == b"FACE"
        and struct.unpack_from("<I", face, 4)[0] == 4
        and struct.unpack_from("<I", face, 8)[0] == FACE_BUFFER_SIZE
    )


def character_data_offset(slot: int) -> int:
    return HEADER_SIZE + slot * SLOT_SIZE + 0x10


def live_face_offset(data: bytes, slot: int) -> int:
    """Find the saved character's FaceDataBuffer.

    ER Save Editor parses this field after variable-length inventory data and
    stores it as SaveSlot::_face_data. It is the first structurally valid FACE
    buffer in the fixed-size character record; later FACE buffers belong to
    other serialized systems.
    """
    start = character_data_offset(slot)
    end = start + SLOT_SIZE - 0x10
    at = start
    while True:
        at = data.find(b"FACE", at, end)
        if at < 0:
            raise ValueError(f"character slot {slot} has no valid live FACE data")
        face = data[at : at + FACE_BUFFER_SIZE]
        if face_is_valid(face):
            return at
        at += 4


def parse_location(value: str) -> tuple[str, int]:
    try:
        kind, raw_slot = value.split(":", 1)
        slot = int(raw_slot)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "location must be character:N or favorite:N"
        ) from error
    if kind not in {"character", "favorite"} or not 0 <= slot < 10:
        raise argparse.ArgumentTypeError(
            "location must be character:N or favorite:N, with N from 0 to 9"
        )
    return kind, slot


def checksum_valid(data: bytes, offsets: dict[str, int]) -> bool:
    start = offsets["user_data"]
    expected = hashlib.md5(data[start + 0x10 : start + USER_DATA_10_SIZE]).digest()
    return data[start : start + 0x10] == expected


def slot_checksum_valid(data: bytes, slot: int) -> bool:
    start = HEADER_SIZE + slot * SLOT_SIZE
    expected = hashlib.md5(data[start + 0x10 : start + SLOT_SIZE]).digest()
    return data[start : start + 0x10] == expected


def read_appearance(
    data: bytes, offsets: dict[str, int], location: tuple[str, int]
) -> bytes:
    kind, slot = location
    if kind == "favorite":
        at = favorite_offset(offsets, slot)
    else:
        if data[offsets["active_slots"] + slot] != 1:
            raise ValueError(f"character slot {slot} is not active")
        at = live_face_offset(data, slot)
    face = data[at : at + FACE_BUFFER_SIZE]
    if not face_is_valid(face):
        raise ValueError(f"{kind} slot {slot} has invalid or empty FACE data")
    return face


def inspect(data: bytes, offsets: dict[str, int]) -> None:
    print(f"UserData10 checksum: {'valid' if checksum_valid(data, offsets) else 'INVALID'}")
    print("Characters:")
    for slot in range(SLOT_COUNT):
        active = data[offsets["active_slots"] + slot] == 1
        profile_at = face_offset_for_profile(offsets, slot)
        profile_face = data[profile_at : profile_at + FACE_BUFFER_SIZE]
        try:
            live_at = live_face_offset(data, slot)
            live_face = data[live_at : live_at + FACE_BUFFER_SIZE]
            live_description = f"0x{live_at:X}"
        except ValueError:
            live_face = bytes()
            live_description = "missing"
        print(
            f"  {slot}: {'active' if active else 'empty ':6} "
            f"{decode_name(data, offsets, slot)!r} "
            f"live={live_description} "
            f"profile_match={live_face == profile_face} "
            f"sha256={hashlib.sha256(live_face).hexdigest() if live_face else '-'}"
        )

    print("Favorites:")
    for slot in range(FAVORITE_COUNT):
        at = favorite_offset(offsets, slot)
        record = data[at : at + FAVORITE_SIZE]
        face = record[:FACE_BUFFER_SIZE]
        state = "occupied" if face_is_valid(face) else "empty" if not any(record) else "unknown"
        digest = hashlib.sha256(face).hexdigest() if state == "occupied" else "-"
        print(f"  {slot}: {state:8} offset=0x{at:X} sha256={digest}")


def write_appearance(
    data: bytes,
    offsets: dict[str, int],
    destination: tuple[str, int],
    appearance: bytes,
    overwrite_favorite: bool,
) -> bytes:
    kind, slot = destination
    result = bytearray(data)

    if kind == "favorite":
        at = favorite_offset(offsets, slot)
        existing = data[at : at + FAVORITE_SIZE]
        if any(existing) and not overwrite_favorite:
            raise ValueError(
                f"favorite slot {slot} is occupied; pass --overwrite-favorite "
                "to replace it"
            )
        result[at : at + FAVORITE_SIZE] = appearance + bytes(
            FAVORITE_SIZE - FACE_BUFFER_SIZE
        )
    else:
        if data[offsets["active_slots"] + slot] != 1:
            raise ValueError(f"destination character slot {slot} is not active")
        live_at = live_face_offset(data, slot)
        profile_at = face_offset_for_profile(offsets, slot)
        result[live_at : live_at + FACE_BUFFER_SIZE] = appearance
        result[profile_at : profile_at + FACE_BUFFER_SIZE] = appearance

        slot_start = HEADER_SIZE + slot * SLOT_SIZE
        result[slot_start : slot_start + 0x10] = hashlib.md5(
            result[slot_start + 0x10 : slot_start + SLOT_SIZE]
        ).digest()

    user_data = offsets["user_data"]
    result[user_data : user_data + 0x10] = hashlib.md5(
        result[user_data + 0x10 : user_data + USER_DATA_10_SIZE]
    ).digest()
    return bytes(result)


def delete_favorite(data: bytes, offsets: dict[str, int], slot: int) -> bytes:
    """Clear one favorite record and repair the UserData10 checksum."""
    if not 0 <= slot < FAVORITE_COUNT:
        raise ValueError("favorite slot must be from 0 to 9")
    at = favorite_offset(offsets, slot)
    if not any(data[at : at + FAVORITE_SIZE]):
        raise ValueError(f"favorite slot {slot} is already empty")
    result = bytearray(data)
    result[at : at + FAVORITE_SIZE] = bytes(FAVORITE_SIZE)
    user_data = offsets["user_data"]
    result[user_data : user_data + 0x10] = hashlib.md5(
        result[user_data + 0x10 : user_data + USER_DATA_10_SIZE]
    ).digest()
    return bytes(result)


def copy_appearance_files(
    source_save: Path,
    destination_save: Path,
    output: Path,
    source: tuple[str, int],
    destination: tuple[str, int],
    overwrite_favorite: bool = False,
) -> str:
    """Copy one appearance and return the output file's SHA-256 digest."""
    if output.resolve() in {source_save.resolve(), destination_save.resolve()}:
        raise ValueError("output must be separate from both input saves")

    source_data = source_save.read_bytes()
    source_offsets = layout(source_data)
    destination_data = destination_save.read_bytes()
    destination_offsets = layout(destination_data)
    if not checksum_valid(source_data, source_offsets):
        raise ValueError("source save has an invalid UserData10 checksum")
    if not checksum_valid(destination_data, destination_offsets):
        raise ValueError("destination save has an invalid UserData10 checksum")
    if source[0] == "character" and not slot_checksum_valid(source_data, source[1]):
        raise ValueError("source character slot has an invalid checksum")
    if destination[0] == "character" and not slot_checksum_valid(
        destination_data, destination[1]
    ):
        raise ValueError("destination character slot has an invalid checksum")

    appearance = read_appearance(source_data, source_offsets, source)
    result = write_appearance(
        destination_data,
        destination_offsets,
        destination,
        appearance,
        overwrite_favorite,
    )
    result_offsets = layout(result)
    if not checksum_valid(result, result_offsets):
        raise RuntimeError("output UserData10 checksum verification failed")
    if destination[0] == "character" and not slot_checksum_valid(
        result, destination[1]
    ):
        raise RuntimeError("output character-slot checksum verification failed")

    output.write_bytes(result)
    return hashlib.sha256(result).hexdigest()


def validate_save(data: bytes, offsets: dict[str, int], description: str) -> None:
    if not checksum_valid(data, offsets):
        raise ValueError(f"{description} has an invalid UserData10 checksum")


def apply_appearance_operation(
    destination_data: bytes,
    source_data: bytes,
    source: tuple[str, int],
    destination: tuple[str, int],
    overwrite_favorite: bool = False,
) -> bytes:
    """Apply one in-memory operation, including all affected checksums."""
    source_offsets = layout(source_data)
    destination_offsets = layout(destination_data)
    validate_save(source_data, source_offsets, "source save")
    validate_save(destination_data, destination_offsets, "destination save")
    if source[0] == "character" and not slot_checksum_valid(source_data, source[1]):
        raise ValueError("source character slot has an invalid checksum")
    if destination[0] == "character" and not slot_checksum_valid(
        destination_data, destination[1]
    ):
        raise ValueError("destination character slot has an invalid checksum")
    appearance = read_appearance(source_data, source_offsets, source)
    return write_appearance(
        destination_data,
        destination_offsets,
        destination,
        appearance,
        overwrite_favorite,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("save", type=Path)

    copy_parser = subparsers.add_parser("copy")
    copy_parser.add_argument("source_save", type=Path)
    copy_parser.add_argument("destination_save", type=Path)
    copy_parser.add_argument("output", type=Path)
    copy_parser.add_argument("--from", dest="source", type=parse_location, required=True)
    copy_parser.add_argument("--to", dest="destination", type=parse_location, required=True)
    copy_parser.add_argument("--overwrite-favorite", action="store_true")

    import_parser = subparsers.add_parser("import-json")
    import_parser.add_argument("json", type=Path)
    import_parser.add_argument("destination_save", type=Path)
    import_parser.add_argument("output", type=Path)
    import_parser.add_argument("--to", dest="destination", type=parse_location, required=True)
    import_parser.add_argument("--overwrite-favorite", action="store_true")

    export_parser = subparsers.add_parser("export-json")
    export_parser.add_argument("save", type=Path)
    export_parser.add_argument("output", type=Path)
    export_parser.add_argument("--from", dest="source", type=parse_location, required=True)
    export_parser.add_argument("--name")

    args = parser.parse_args()
    if args.command == "inspect":
        data = args.save.read_bytes()
        offsets = layout(data)
        inspect(data, offsets)
        return

    if args.command == "export-json":
        import elden_bling_json
        data = args.save.read_bytes()
        offsets = layout(data)
        validate_save(data, offsets, args.save.name)
        appearance = read_appearance(data, offsets, args.source)
        name = args.name
        if name is None and args.source[0] == "character":
            name = decode_name(data, offsets, args.source[1])
        elden_bling_json.save(args.output, appearance, name or "Exported")
        print(f"Wrote {args.output}")
        return

    if args.command == "import-json":
        import elden_bling_json
        if args.output.resolve() == args.destination_save.resolve():
            raise ValueError("output must be separate from the input save")
        data = args.destination_save.read_bytes()
        offsets = layout(data)
        validate_save(data, offsets, args.destination_save.name)
        appearance = elden_bling_json.load(args.json)
        result = write_appearance(
            data, offsets, args.destination, appearance, args.overwrite_favorite
        )
        validate_save(result, layout(result), "output save")
        args.output.write_bytes(result)
        print(f"Wrote {args.output}")
        print(f"SHA-256 {hashlib.sha256(result).hexdigest()}")
        return

    digest = copy_appearance_files(
        args.source_save,
        args.destination_save,
        args.output,
        args.source,
        args.destination,
        args.overwrite_favorite,
    )
    print(f"Wrote {args.output}")
    print(
        f"Copied {args.source[0]} {args.source[1]} from {args.source_save} "
        f"to {args.destination[0]} {args.destination[1]} in {args.destination_save}"
    )
    print(f"SHA-256 {digest}")


if __name__ == "__main__":
    main()
