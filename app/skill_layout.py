from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .models import SkillRecord


@dataclass(frozen=True)
class SkillPageInfo:
    major: str
    sub: str
    href: str
    learn_slots: int = 0
    vp_skills: int = 0
    icon_ok: int = 0
    icon_missing: int = 0
    links: int = 0

    @property
    def page_dir(self) -> Path:
        return Path(self.href).parent


@dataclass(frozen=True)
class SkillVpOption:
    option_type: str
    name: str


@dataclass(frozen=True)
class SkillLayoutSkill:
    index: int
    english: str
    name: str
    x: int
    y: int
    icon: str
    icon_path: Path | None
    vp: tuple[SkillVpOption, ...] = ()


@dataclass(frozen=True)
class SkillLayoutLink:
    from_index: int
    to_index: int
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class SkillPageLayout:
    class_family: str
    profession: str
    cell_width: int
    cell_height: int
    stats: dict[str, int]
    skills: tuple[SkillLayoutSkill, ...]
    links: tuple[SkillLayoutLink, ...]
    vp_skills: tuple[SkillLayoutSkill, ...]
    source_path: Path

    @property
    def canvas_width(self) -> int:
        return max((skill.x for skill in self.skills), default=0) + self.cell_width

    @property
    def canvas_height(self) -> int:
        return max((skill.y for skill in self.skills), default=0) + self.cell_height


class SkillLayoutRepository:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    def pages(self) -> list[SkillPageInfo]:
        report_path = self.root / "generation-report.json"
        if report_path.exists():
            data = json.loads(report_path.read_text(encoding="utf-8"))
            return [self._parse_page_info(item) for item in data.get("pages", [])]
        return self._scan_pages()

    def load_page(self, major: str, sub: str) -> SkillPageLayout:
        page = self._find_page(major, sub)
        skill_data_path = self.root / page.page_dir / "skill-data.js"
        if not skill_data_path.exists():
            raise FileNotFoundError(skill_data_path)
        data = self._read_skill_data(skill_data_path)
        page_dir = skill_data_path.parent
        cell = data.get("cell") or {}
        stats = {str(key): int(value) for key, value in (data.get("stats") or {}).items()}
        skills = tuple(self.parse_skill_node(item, page_dir) for item in data.get("skills", []))
        vp_skills = tuple(self.parse_skill_node(item, page_dir) for item in data.get("vpSkills", []))
        links = tuple(self._parse_link(item) for item in data.get("links", []))
        return SkillPageLayout(
            class_family=str(data.get("classFamily") or major),
            profession=str(data.get("profession") or sub),
            cell_width=int(cell.get("width") or 47),
            cell_height=int(cell.get("height") or 67),
            stats=stats,
            skills=skills,
            links=links,
            vp_skills=vp_skills,
            source_path=skill_data_path,
        )

    @staticmethod
    def parse_skill_node(item: dict, page_dir: Path) -> SkillLayoutSkill:
        icon = str(item.get("icon") or "")
        options = tuple(
            SkillVpOption(str(option.get("type") or ""), str(option.get("name") or ""))
            for option in item.get("vp", []) or []
        )
        return SkillLayoutSkill(
            index=int(item.get("index") or 0),
            english=str(item.get("english") or ""),
            name=str(item.get("name") or ""),
            x=int(item.get("x") or 0),
            y=int(item.get("y") or 0),
            icon=icon,
            icon_path=(page_dir / icon) if icon else None,
            vp=options,
        )

    def _find_page(self, major: str, sub: str) -> SkillPageInfo:
        for page in self.pages():
            if page.major == major and page.sub == sub:
                return page
        raise KeyError(f"Skill page not found: {major} / {sub}")

    def _scan_pages(self) -> list[SkillPageInfo]:
        pages: list[SkillPageInfo] = []
        for skill_data_path in sorted(self.root.rglob("skill-data.js")):
            rel_dir = skill_data_path.parent.relative_to(self.root)
            parts = rel_dir.parts
            if len(parts) < 2:
                continue
            pages.append(
                SkillPageInfo(
                    major=parts[-2],
                    sub=parts[-1],
                    href=(rel_dir / "index.html").as_posix(),
                )
            )
        return pages

    @staticmethod
    def _parse_page_info(item: dict) -> SkillPageInfo:
        return SkillPageInfo(
            major=str(item.get("major") or ""),
            sub=str(item.get("sub") or ""),
            href=str(item.get("href") or ""),
            learn_slots=int(item.get("learnSlots") or 0),
            vp_skills=int(item.get("vpSkills") or 0),
            icon_ok=int(item.get("iconOk") or 0),
            icon_missing=int(item.get("iconMissing") or 0),
            links=int(item.get("links") or 0),
        )

    @staticmethod
    def _parse_link(item: dict) -> SkillLayoutLink:
        return SkillLayoutLink(
            from_index=int(item.get("from") or 0),
            to_index=int(item.get("to") or 0),
            x1=int(item.get("x1") or 0),
            y1=int(item.get("y1") or 0),
            x2=int(item.get("x2") or 0),
            y2=int(item.get("y2") or 0),
        )

    @staticmethod
    def _read_skill_data(path: Path) -> dict:
        text = path.read_text(encoding="utf-8")
        match = re.search(r"=\s*(\{.*\})\s*;?\s*$", text, re.S)
        if not match:
            raise ValueError(f"Cannot parse skill-data.js: {path}")
        return json.loads(match.group(1))


def match_layout_skill(
    layout_skill: SkillLayoutSkill,
    records: Iterable[SkillRecord],
) -> SkillRecord | None:
    record_list = list(records)
    english = layout_skill.english.lower()

    def same_identity(record: SkillRecord) -> bool:
        return record.sequence == layout_skill.index and record.english_name.lower() == english

    for record in record_list:
        if same_identity(record) and record.skill_type == "原版":
            return record
    for record in record_list:
        if same_identity(record):
            return record
    for record in record_list:
        if record.english_name.lower() == english and record.skill_type == "原版":
            return record
    for record in record_list:
        if record.chinese_name == layout_skill.name and record.skill_type == "原版":
            return record
    return None
