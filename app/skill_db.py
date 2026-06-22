from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from .models import SkillRecord
from .npk_paths import normalize_img_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DNF_AUTOPLAY_ROOT = PROJECT_ROOT.parents[2]
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
BUNDLED_SKILL_DB_DLL = BUNDLE_DIR / "PvfSkillImgDb.dll"
SOURCE_SKILL_DB_DLL = (
    DNF_AUTOPLAY_ROOT
    / "DNFPVF"
    / "summary"
    / "SkillImgNativeDll"
    / "dist"
    / "PvfSkillImgDb.dll"
)


def _default_skill_db_dll() -> Path:
    if getattr(sys, "frozen", False) and BUNDLED_SKILL_DB_DLL.exists():
        return BUNDLED_SKILL_DB_DLL
    return SOURCE_SKILL_DB_DLL if SOURCE_SKILL_DB_DLL.exists() else BUNDLED_SKILL_DB_DLL


DEFAULT_SKILL_DB_DLL = _default_skill_db_dll()


class CSkillImg(ctypes.Structure):
    _fields_ = [
        ("sequence", ctypes.c_int),
        ("chinese_name", ctypes.c_char_p),
        ("english_name", ctypes.c_char_p),
        ("skill_type", ctypes.c_char_p),
        ("icon_img_path", ctypes.c_char_p),
        ("icon_frame_index", ctypes.c_int),
        ("all_unique_imgs", ctypes.c_char_p),
    ]


def _bytes(text: str | None) -> bytes | None:
    if text is None:
        return None
    return text.encode("utf-8")


def _text(value: bytes | None) -> str:
    return value.decode("utf-8") if value else ""


class SkillDatabase:
    def __init__(self, dll_path: Path | str = DEFAULT_SKILL_DB_DLL):
        self.dll_path = Path(dll_path)
        if not self.dll_path.exists():
            raise FileNotFoundError(f"PvfSkillImgDb.dll not found: {self.dll_path}")
        self._dll = ctypes.CDLL(str(self.dll_path))
        self._configure()
        self._initialized = False

    def _configure(self) -> None:
        dll = self._dll
        dll.pvf_skilldb_init.restype = ctypes.c_int
        dll.pvf_skilldb_last_error.restype = ctypes.c_char_p
        dll.pvf_skilldb_version.restype = ctypes.c_char_p
        dll.pvf_skilldb_build_info.restype = ctypes.c_char_p
        dll.pvf_skilldb_profession_count.restype = ctypes.c_int
        dll.pvf_skilldb_total_skill_rows.restype = ctypes.c_int
        dll.pvf_skilldb_profession_big.argtypes = [ctypes.c_int]
        dll.pvf_skilldb_profession_big.restype = ctypes.c_char_p
        dll.pvf_skilldb_profession_small.argtypes = [ctypes.c_int]
        dll.pvf_skilldb_profession_small.restype = ctypes.c_char_p
        dll.pvf_skilldb_skill_count.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        dll.pvf_skilldb_skill_count.restype = ctypes.c_int
        dll.pvf_skilldb_get_skill.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.POINTER(CSkillImg),
        ]
        dll.pvf_skilldb_get_skill.restype = ctypes.c_int
        dll.pvf_skilldb_find_skills.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.POINTER(CSkillImg),
            ctypes.c_int,
        ]
        dll.pvf_skilldb_find_skills.restype = ctypes.c_int

    def init(self) -> None:
        if self._initialized:
            return
        rc = self._dll.pvf_skilldb_init()
        if rc != 0:
            raise RuntimeError(_text(self._dll.pvf_skilldb_last_error()))
        self._initialized = True

    @property
    def version(self) -> str:
        return _text(self._dll.pvf_skilldb_version())

    @property
    def build_info(self) -> str:
        return _text(self._dll.pvf_skilldb_build_info())

    @property
    def total_skill_rows(self) -> int:
        self.init()
        return int(self._dll.pvf_skilldb_total_skill_rows())

    def professions(self) -> list[tuple[str, str]]:
        self.init()
        count = int(self._dll.pvf_skilldb_profession_count())
        return [
            (
                _text(self._dll.pvf_skilldb_profession_big(index)),
                _text(self._dll.pvf_skilldb_profession_small(index)),
            )
            for index in range(count)
        ]

    def skills_for_profession(self, big_profession: str, small_profession: str) -> list[SkillRecord]:
        self.init()
        count = int(
            self._dll.pvf_skilldb_skill_count(
                _bytes(big_profession),
                _bytes(small_profession),
            )
        )
        records: list[SkillRecord] = []
        for index in range(count):
            item = CSkillImg()
            rc = self._dll.pvf_skilldb_get_skill(
                _bytes(big_profession),
                _bytes(small_profession),
                index,
                ctypes.byref(item),
            )
            if rc != 0:
                raise RuntimeError(_text(self._dll.pvf_skilldb_last_error()))
            records.append(self._to_record(big_profession, small_profession, item))
        return records

    def _to_record(
        self,
        big_profession: str,
        small_profession: str,
        item: CSkillImg,
    ) -> SkillRecord:
        img_paths = tuple(
            path
            for path in (
                normalize_img_path(line)
                for line in _text(item.all_unique_imgs).replace("\r\n", "\n").replace("\r", "\n").split("\n")
            )
            if path
        )
        return SkillRecord(
            sequence=int(item.sequence),
            big_profession=big_profession,
            small_profession=small_profession,
            chinese_name=_text(item.chinese_name),
            english_name=_text(item.english_name),
            skill_type=_text(item.skill_type),
            icon_img_path=normalize_img_path(_text(item.icon_img_path)),
            icon_frame_index=int(item.icon_frame_index),
            img_paths=img_paths,
        )
