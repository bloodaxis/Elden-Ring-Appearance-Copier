#!/usr/bin/env python3
"""Convert Elden Bling Auto Sliders JSON to and from ER FaceDataBuffer."""

from __future__ import annotations

import json
import struct
from pathlib import Path


FACE_SIZE = 0x120
HAIR = [0, 113, 112, 1, 3, 100, 5, 10, 101, 9, 8, 6, 7, 115, 114, 2,
        4, 102, 103, 104, 105, 106, 107, 109, 108, 111, 110, 117, 119, 118,
        116, 121, 125, 122, 120, 123, 124]
BROW = list(range(17))
BEARD = list(range(12))
ACCESSORY = [0, 2, 1, 10]

STRUCTURE_FIELDS = [
    "apparent_age", "facial_aesthetic", "form_emphasis", "unknown_2f",
    "brow_ridge_height", "inner_brow_ridge", "outer_brow_ridge",
    "cheekbone_height", "cheekbone_depth", "cheekbone_width",
    "cheekbone_protrusion", "cheeks", "chin_tip_position", "chin_length",
    "chin_protrusion", "chin_depth", "chin_size", "chin_height", "chin_width",
    "eye_position", "eye_size", "eye_slant", "eye_spacing", "nose_size",
    "nose_forehead_ratio", "unknown_45", "face_protrusion",
    "vertical_face_ratio", "facial_feature_slant", "horizontal_face_ratio",
    "unknown_4a", "forehead_depth", "forehead_protrusion", "unknown_4d",
    "jaw_protrusion", "jaw_width", "lower_jaw", "jaw_contour", "lip_shape",
    "lip_size", "lip_fullness", "mouth_expression", "lip_protrusion",
    "lip_thickness", "mouth_protrusion", "mouth_slant", "occlusion",
    "mouth_position", "mouth_width", "mouth_chin_distance", "nose_ridge_depth",
    "nose_ridge_length", "nose_position", "nose_tip_height", "nostril_slant",
    "nostril_size", "nostril_width", "nose_protrusion", "nose_bridge_height",
    "bridge_protrusion1", "bridge_protrusion2", "nose_bridge_width",
    "nose_height", "nose_slant",
]

COSMETIC_FIELDS = [
    "skin_color_r", "skin_color_g", "skin_color_b", "skin_luster", "pores",
    "stubble", "dark_circles", "dark_circle_color_r", "dark_circle_color_g",
    "dark_circle_color_b", "cheeks_color_intensity", "cheek_color_r",
    "cheek_color_g", "cheek_color_b", "eye_liner", "eye_liner_color_r",
    "eye_liner_color_g", "eye_liner_color_b", "eye_shadow_lower",
    "eye_shadow_lower_color_r", "eye_shadow_lower_color_g",
    "eye_shadow_lower_color_b", "eye_shadow_upper", "eye_shadow_upper_color_r",
    "eye_shadow_upper_color_g", "eye_shadow_upper_color_b", "lip_stick",
    "lip_stick_color_r", "lip_stick_color_g", "lip_stick_color_b",
    "tattoo_mark_position_horizontal", "tattoo_mark_position_vertical",
    "tattoo_mark_angle", "tattoo_mark_expansion", "tattoo_mark_color_r",
    "tattoo_mark_color_g", "tattoo_mark_color_b", "unknown_d8",
    "tattoo_mark_flip", "body_hair", "body_hair_color_r", "body_hair_color_g",
    "body_hair_color_b", "right_iris_color_r", "right_iris_color_g",
    "right_iris_color_b", "right_iris_size", "right_eye_clouding",
    "right_eye_clouding_color_r", "right_eye_clouding_color_g",
    "right_eye_clouding_color_b", "right_eye_white_color_r",
    "right_eye_white_color_g", "right_eye_white_color_b", "right_eye_position",
    "left_iris_color_r", "left_iris_color_g", "left_iris_color_b",
    "left_iris_size", "left_eye_clouding", "left_eye_clouding_color_r",
    "left_eye_clouding_color_g", "left_eye_clouding_color_b",
    "left_eye_white_color_r", "left_eye_white_color_g", "left_eye_white_color_b",
    "left_eye_position", "hair_color_r", "hair_color_g", "hair_color_b",
    "hair_luster", "hair_root_darkness", "white_hairs", "beard_color_r",
    "beard_color_g", "beard_color_b", "beard_luster", "beard_root_darkness",
    "beard_white_hairs", "brow_color_r", "brow_color_g", "brow_color_b",
    "brow_luster", "brow_root_darkness", "brow_white_hairs",
    "eye_lash_color_r", "eye_lash_color_g", "eye_lash_color_b",
    "eye_patch_color_r", "eye_patch_color_g", "eye_patch_color_b",
]


def _integer(data: dict, section: str, key: str, default: int = 128) -> int:
    value = int(data.get(section, {}).get(key, default))
    if not 0 <= value <= 255:
        raise ValueError(f"{section}.{key} must be between 0 and 255")
    return value


def _model(table: list[int], display_index: int) -> int:
    index = display_index - 1
    return table[index] if 0 <= index < len(table) else 0


def _display_index(table: list[int], stored: int) -> int:
    try:
        return table.index(stored) + 1
    except ValueError:
        return 1


def _set(buffer: bytearray, fields: list[str], field: str, value: int, start: int) -> None:
    buffer[start + fields.index(field)] = value


def _get(buffer: bytes, fields: list[str], field: str, start: int) -> int:
    return buffer[start + fields.index(field)]


def from_dict(data: dict) -> bytes:
    if not isinstance(data, dict) or "base" not in data or "face_template" not in data:
        raise ValueError("not an Elden Bling Auto Sliders JSON object")
    result = bytearray(FACE_SIZE)
    result[:4] = b"FACE"
    struct.pack_into("<II", result, 4, 4, FACE_SIZE)
    result[0x6C:0xAC] = bytes([127, 0, 0, 0, 0] + [128] * 5 + [0] * 9 +
                                  [128] * 4 + [0] * 4 + [128] * 36 + [0])
    result[0xB1:0xB3] = bytes([128, 128])

    base = data.get("base", {})
    body_type = 1 if str(base.get("body_type", "A")).upper() == "B" else 0
    ft = data.get("face_template", {})
    result[0x0C] = max(0, min(255, (int(ft.get("structure", 1)) - 1) * 10))
    result[0x10] = _model(HAIR, _integer(data, "hair", "hair", 1))
    result[0x18] = _model(BROW, _integer(data, "eyebrows", "brow", 1))
    result[0x1C] = _model(BEARD, _integer(data, "facial_hair", "beard", 1))
    result[0x20] = _model(ACCESSORY, _integer(data, "tattoo_mark_eyepatch", "eyepatch", 1))
    result[0x28] = 1 if body_type else 3

    values = {
        "apparent_age": _integer(data, "face_template", "age"),
        "facial_aesthetic": _integer(data, "face_template", "aesthetic"),
        "form_emphasis": _integer(data, "face_template", "emphasis"),
    }
    sections = {
        "face_balance": {"size":"nose_size", "ratio":"nose_forehead_ratio", "protrusion":"face_protrusion", "vert":"vertical_face_ratio", "slant":"facial_feature_slant", "horiz":"horizontal_face_ratio"},
        "forehead": {"depth":"forehead_depth", "protrusion":"forehead_protrusion", "height":"nose_bridge_height", "prot1":"bridge_protrusion1", "prot2":"bridge_protrusion2", "width":"nose_bridge_width"},
        "brow_ridge": {"height":"brow_ridge_height", "inner":"inner_brow_ridge", "outer":"outer_brow_ridge"},
        "eyes": {"position":"eye_position", "size":"eye_size", "slant":"eye_slant", "spacing":"eye_spacing"},
        "nose_ridge": {"depth":"nose_ridge_depth", "length":"nose_ridge_length", "position":"nose_position", "tip_height":"nose_tip_height", "protrusion":"nose_protrusion", "height":"nose_height", "slant":"nose_slant"},
        "nostrils": {"slant":"nostril_slant", "size":"nostril_size", "width":"nostril_width"},
        "cheeks": {"height":"cheekbone_height", "depth":"cheekbone_depth", "width":"cheekbone_width", "protrusion":"cheekbone_protrusion", "cheeks":"cheeks"},
        "lips": {"shape":"lip_shape", "expression":"mouth_expression", "fullness":"lip_fullness", "size":"lip_size", "protrusion":"lip_protrusion", "thickness":"lip_thickness"},
        "mouth": {"protrusion":"mouth_protrusion", "slant":"mouth_slant", "occlusion":"occlusion", "position":"mouth_position", "width":"mouth_width", "distance":"mouth_chin_distance"},
        "chin": {"tip":"chin_tip_position", "length":"chin_length", "protrusion":"chin_protrusion", "depth":"chin_depth", "size":"chin_size", "height":"chin_height", "width":"chin_width"},
        "jaw": {"protrusion":"jaw_protrusion", "width":"jaw_width", "lower":"lower_jaw", "contour":"jaw_contour"},
    }
    for section, keys in sections.items():
        for key, field in keys.items():
            values[field] = _integer(data, section, key)
    for field, value in values.items():
        _set(result, STRUCTURE_FIELDS, field, value, 0x2C)

    body = data.get("body", {})
    for index, key in enumerate(("head", "chest", "abdomen", "arms", "legs")):
        result[0xAC + index] = _integer(data, "body", key)

    cosmetic_map = {
        "skin_color": {"skin_r":"skin_color_r", "skin_g":"skin_color_g", "skin_b":"skin_color_b"},
        "skin_features": {"luster":"skin_luster", "pores":"pores", "dark_circles":"dark_circles", "dark_circles_r":"dark_circle_color_r", "dark_circles_g":"dark_circle_color_g", "dark_circles_b":"dark_circle_color_b"},
        "cosmetics": {"eyeliner":"eye_liner", "eyeliner_r":"eye_liner_color_r", "eyeliner_g":"eye_liner_color_g", "eyeliner_b":"eye_liner_color_b", "upper":"eye_shadow_upper", "upper_r":"eye_shadow_upper_color_r", "upper_g":"eye_shadow_upper_color_g", "upper_b":"eye_shadow_upper_color_b", "lower":"eye_shadow_lower", "lower_r":"eye_shadow_lower_color_r", "lower_g":"eye_shadow_lower_color_g", "lower_b":"eye_shadow_lower_color_b", "cheeks":"cheeks_color_intensity", "cheeks_r":"cheek_color_r", "cheeks_g":"cheek_color_g", "cheeks_b":"cheek_color_b", "lipstick":"lip_stick", "lipstick_r":"lip_stick_color_r", "lipstick_g":"lip_stick_color_g", "lipstick_b":"lip_stick_color_b"},
        "hair": {"hair_r":"hair_color_r", "hair_g":"hair_color_g", "hair_b":"hair_color_b", "luster":"hair_luster", "roots":"hair_root_darkness", "white":"white_hairs"},
        "eyebrows": {"brow_r":"brow_color_r", "brow_g":"brow_color_g", "brow_b":"brow_color_b"},
        "eyelashes": {"lashes_r":"eye_lash_color_r", "lashes_g":"eye_lash_color_g", "lashes_b":"eye_lash_color_b"},
        "right_eye": {"iris_r":"right_iris_color_r", "iris_g":"right_iris_color_g", "iris_b":"right_iris_color_b", "iris_size":"right_iris_size", "clouding":"right_eye_clouding", "clouding_r":"right_eye_clouding_color_r", "clouding_g":"right_eye_clouding_color_g", "clouding_b":"right_eye_clouding_color_b", "white_r":"right_eye_white_color_r", "white_g":"right_eye_white_color_g", "white_b":"right_eye_white_color_b", "position":"right_eye_position"},
    }
    for section, keys in cosmetic_map.items():
        for key, field in keys.items():
            _set(result, COSMETIC_FIELDS, field, _integer(data, section, key, 0), 0xB3)
    _set(result, COSMETIC_FIELDS, "stubble", _integer(data, "facial_hair", "stubble", 0), 0xB3)
    _set(result, COSMETIC_FIELDS, "body_hair", _integer(data, "body", "body_hair", 0), 0xB3)

    hair_rgb = [_integer(data, "hair", key, 128) for key in ("hair_r", "hair_g", "hair_b")]
    for prefix in ("beard_color", "body_hair_color"):
        for channel, value in zip("rgb", hair_rgb):
            _set(result, COSMETIC_FIELDS, f"{prefix}_{channel}", value, 0xB3)
    _set(result, COSMETIC_FIELDS, "beard_luster", _integer(data, "hair", "luster"), 0xB3)
    _set(result, COSMETIC_FIELDS, "beard_root_darkness", _integer(data, "hair", "roots"), 0xB3)
    _set(result, COSMETIC_FIELDS, "beard_white_hairs", _integer(data, "hair", "white", 0), 0xB3)
    _set(result, COSMETIC_FIELDS, "brow_luster", _integer(data, "eyebrows", "luster"), 0xB3)
    right = data.get("right_eye", {})
    left = data.get("left_eye") or right
    left_fields = {"iris_r":"left_iris_color_r", "iris_g":"left_iris_color_g", "iris_b":"left_iris_color_b", "iris_size":"left_iris_size", "clouding":"left_eye_clouding", "clouding_r":"left_eye_clouding_color_r", "clouding_g":"left_eye_clouding_color_g", "clouding_b":"left_eye_clouding_color_b", "white_r":"left_eye_white_color_r", "white_g":"left_eye_white_color_g", "white_b":"left_eye_white_color_b", "position":"left_eye_position"}
    for json_key, field in left_fields.items():
        _set(result, COSMETIC_FIELDS, field, int(left.get(json_key, right.get(json_key, 128))), 0xB3)
    tattoo = data.get("tattoo_mark_eyepatch", {})
    tattoo_keys = {"horiz":"tattoo_mark_position_horizontal", "vert":"tattoo_mark_position_vertical", "angle":"tattoo_mark_angle", "expansion":"tattoo_mark_expansion", "tattoo_r":"tattoo_mark_color_r", "tattoo_g":"tattoo_mark_color_g", "tattoo_b":"tattoo_mark_color_b", "eyepatch_r":"eye_patch_color_r", "eyepatch_g":"eye_patch_color_g", "eyepatch_b":"eye_patch_color_b"}
    for key, field in tattoo_keys.items():
        _set(result, COSMETIC_FIELDS, field, int(tattoo.get(key, 128)), 0xB3)
    _set(result, COSMETIC_FIELDS, "tattoo_mark_flip", 0 if str(tattoo.get("flip", "OFF")).upper() == "OFF" else 1, 0xB3)
    return bytes(result)


def load(path: Path) -> bytes:
    return from_dict(json.loads(path.read_text(encoding="utf-8")))


def to_dict(face: bytes, name: str = "Exported") -> dict:
    if len(face) != FACE_SIZE or face[:4] != b"FACE":
        raise ValueError("invalid FaceDataBuffer")
    s = lambda field: str(_get(face, STRUCTURE_FIELDS, field, 0x2C))
    c = lambda field: str(_get(face, COSMETIC_FIELDS, field, 0xB3))
    section_maps = {
        "face_balance": {"size":"nose_size", "ratio":"nose_forehead_ratio", "protrusion":"face_protrusion", "vert":"vertical_face_ratio", "slant":"facial_feature_slant", "horiz":"horizontal_face_ratio"},
        "forehead": {"depth":"forehead_depth", "protrusion":"forehead_protrusion", "height":"nose_bridge_height", "prot1":"bridge_protrusion1", "prot2":"bridge_protrusion2", "width":"nose_bridge_width"},
        "brow_ridge": {"height":"brow_ridge_height", "inner":"inner_brow_ridge", "outer":"outer_brow_ridge"},
        "eyes": {"position":"eye_position", "size":"eye_size", "slant":"eye_slant", "spacing":"eye_spacing"},
        "nose_ridge": {"depth":"nose_ridge_depth", "length":"nose_ridge_length", "position":"nose_position", "tip_height":"nose_tip_height", "protrusion":"nose_protrusion", "height":"nose_height", "slant":"nose_slant"},
        "nostrils": {"slant":"nostril_slant", "size":"nostril_size", "width":"nostril_width"},
        "cheeks": {"height":"cheekbone_height", "depth":"cheekbone_depth", "width":"cheekbone_width", "protrusion":"cheekbone_protrusion", "cheeks":"cheeks"},
        "lips": {"shape":"lip_shape", "expression":"mouth_expression", "fullness":"lip_fullness", "size":"lip_size", "protrusion":"lip_protrusion", "thickness":"lip_thickness"},
        "mouth": {"protrusion":"mouth_protrusion", "slant":"mouth_slant", "occlusion":"occlusion", "position":"mouth_position", "width":"mouth_width", "distance":"mouth_chin_distance"},
        "chin": {"tip":"chin_tip_position", "length":"chin_length", "protrusion":"chin_protrusion", "depth":"chin_depth", "size":"chin_size", "height":"chin_height", "width":"chin_width"},
        "jaw": {"protrusion":"jaw_protrusion", "width":"jaw_width", "lower":"lower_jaw", "contour":"jaw_contour"},
    }
    out = {"base":{"name":name,"body_type":"B" if face[0x28] == 1 else "A","age":"Young","voice":"Young 1"},
           "skin_color":{"skin_r":c("skin_color_r"),"skin_g":c("skin_color_g"),"skin_b":c("skin_color_b")},
           "face_template":{"structure":str(face[0x0C] // 10 + 1),"emphasis":s("form_emphasis"),"age":s("apparent_age"),"aesthetic":s("facial_aesthetic")}}
    for section, mapping in section_maps.items(): out[section] = {key:s(field) for key,field in mapping.items()}
    out["hair"]={"hair":str(_display_index(HAIR,face[0x10])),"hair_r":c("hair_color_r"),"hair_g":c("hair_color_g"),"hair_b":c("hair_color_b"),"luster":c("hair_luster"),"roots":c("hair_root_darkness"),"white":c("white_hairs")}
    out["eyebrows"]={"brow":str(_display_index(BROW,face[0x18])),"brow_r":c("brow_color_r"),"brow_g":c("brow_color_g"),"brow_b":c("brow_color_b")}
    out["facial_hair"]={"beard":str(_display_index(BEARD,face[0x1C])),"stubble":c("stubble")}
    out["eyelashes"]={"lashes":"1","lashes_r":c("eye_lash_color_r"),"lashes_g":c("eye_lash_color_g"),"lashes_b":c("eye_lash_color_b")}
    def eye(prefix): return {"iris_size":c(f"{prefix}_iris_size"),"iris_r":c(f"{prefix}_iris_color_r"),"iris_g":c(f"{prefix}_iris_color_g"),"iris_b":c(f"{prefix}_iris_color_b"),"clouding":c(f"{prefix}_eye_clouding"),"clouding_r":c(f"{prefix}_eye_clouding_color_r"),"clouding_g":c(f"{prefix}_eye_clouding_color_g"),"clouding_b":c(f"{prefix}_eye_clouding_color_b"),"white_r":c(f"{prefix}_eye_white_color_r"),"white_g":c(f"{prefix}_eye_white_color_g"),"white_b":c(f"{prefix}_eye_white_color_b"),"position":c(f"{prefix}_eye_position")}
    out["right_eye"],out["left_eye"]=eye("right"),eye("left")
    out["skin_features"]={"pores":c("pores"),"luster":c("skin_luster"),"dark_circles":c("dark_circles"),"dark_circles_r":c("dark_circle_color_r"),"dark_circles_g":c("dark_circle_color_g"),"dark_circles_b":c("dark_circle_color_b")}
    out["cosmetics"]={"eyeliner":c("eye_liner"),"eyeliner_r":c("eye_liner_color_r"),"eyeliner_g":c("eye_liner_color_g"),"eyeliner_b":c("eye_liner_color_b"),"upper":c("eye_shadow_upper"),"upper_r":c("eye_shadow_upper_color_r"),"upper_g":c("eye_shadow_upper_color_g"),"upper_b":c("eye_shadow_upper_color_b"),"lower":c("eye_shadow_lower"),"lower_r":c("eye_shadow_lower_color_r"),"lower_g":c("eye_shadow_lower_color_g"),"lower_b":c("eye_shadow_lower_color_b"),"cheeks":c("cheeks_color_intensity"),"cheeks_r":c("cheek_color_r"),"cheeks_g":c("cheek_color_g"),"cheeks_b":c("cheek_color_b"),"lipstick":c("lip_stick"),"lipstick_r":c("lip_stick_color_r"),"lipstick_g":c("lip_stick_color_g"),"lipstick_b":c("lip_stick_color_b")}
    out["tattoo_mark_eyepatch"]={"tattoo":"1","tattoo_r":c("tattoo_mark_color_r"),"tattoo_g":c("tattoo_mark_color_g"),"tattoo_b":c("tattoo_mark_color_b"),"vert":c("tattoo_mark_position_vertical"),"horiz":c("tattoo_mark_position_horizontal"),"angle":c("tattoo_mark_angle"),"expansion":c("tattoo_mark_expansion"),"flip":"ON" if c("tattoo_mark_flip") != "0" else "OFF","eyepatch":str(_display_index(ACCESSORY,face[0x20])),"eyepatch_r":c("eye_patch_color_r"),"eyepatch_g":c("eye_patch_color_g"),"eyepatch_b":c("eye_patch_color_b")}
    out["body"]={"head":str(face[0xAC]),"chest":str(face[0xAD]),"abdomen":str(face[0xAE]),"arms":str(face[0xAF]),"legs":str(face[0xB0]),"body_hair":c("body_hair"),"muscle":"Standard"}
    out["armor"],out["weapons"]={},{}
    return out


def save(path: Path, face: bytes, name: str = "Exported") -> None:
    path.write_text(json.dumps(to_dict(face, name), indent=2) + "\n", encoding="utf-8")
