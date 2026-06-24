from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SkillRecord:
    sequence: int
    big_profession: str
    small_profession: str
    chinese_name: str
    english_name: str
    skill_type: str
    icon_img_path: str
    icon_frame_index: int
    img_paths: tuple[str, ...]


@dataclass(frozen=True)
class ExportJob:
    skill: SkillRecord
    source_dir: Path
    output_dir: Path
    output_name: str | None = None
    overwrite: bool = False
    include_icon: bool = False
    include_body_templates: bool = False


@dataclass(frozen=True)
class ExportReport:
    skill: SkillRecord
    output_path: Path
    entry_count: int
    byte_count: int
    source_npks: tuple[Path, ...]
    missing_img_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class DecodedFrame:
    index: int
    rgba: bytes
    width: int
    height: int
    delay_ms: int = 90
