from __future__ import annotations

import re
from pathlib import Path

WINDOWS_FILENAME_TRANSLATION = str.maketrans(
    {
        "<": "＜",
        ">": "＞",
        ":": "：",
        '"': "＂",
        "/": "／",
        "\\": "＼",
        "|": "｜",
        "?": "？",
        "*": "＊",
    }
)

BODY_TEMPLATE_RE = re.compile(r"_body(?:%04d|\d{4})\.img$", re.IGNORECASE)


def normalize_img_path(value: object) -> str:
    return str(value or "").strip().replace("\\", "/").lower()


def img_path_to_npk_name(img_path: str) -> str:
    normalized = normalize_img_path(img_path)
    if "/" not in normalized:
        raise ValueError(f"IMG path has no parent directory: {img_path}")
    parent = normalized.rsplit("/", 1)[0]
    return parent.replace("/", "_") + ".NPK"


def sanitize_windows_filename(value: str) -> str:
    cleaned = str(value or "").strip().translate(WINDOWS_FILENAME_TRANSLATION)
    cleaned = "".join("_" if ord(ch) < 32 else ch for ch in cleaned)
    cleaned = cleaned.rstrip(" .")
    return cleaned or "unnamed"


def skill_output_filename(skill_name: str) -> str:
    return f"%{sanitize_windows_filename(skill_name)}.npk"


def should_skip_export_img(
    img_path: str,
    *,
    include_icon: bool = False,
    include_body_templates: bool = False,
) -> bool:
    normalized = normalize_img_path(img_path)
    leaf = normalized.rsplit("/", 1)[-1]
    if not include_icon and leaf == "skillicon.img":
        return True
    if not include_body_templates and BODY_TEMPLATE_RE.search(leaf):
        return True
    return False


def resolve_source_npk(source_dir: Path, img_path: str) -> Path:
    npk_name = img_path_to_npk_name(img_path)
    direct = source_dir / npk_name
    if direct.exists():
        return direct

    lower_name = npk_name.lower()
    try:
        for item in source_dir.iterdir():
            if item.is_file() and item.name.lower() == lower_name:
                return item
    except OSError:
        pass
    return direct

