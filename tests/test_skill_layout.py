import json
from pathlib import Path

from app.models import SkillRecord
from app.settings import skill_pages_dir
from app.skill_layout import SkillLayoutRepository, match_layout_skill


def _write_page(root: Path) -> Path:
    page_dir = root / "光职者(女)" / "光明骑士(女)"
    icon_dir = page_dir / "assets" / "icons"
    icon_dir.mkdir(parents=True)
    (icon_dir / "156_WeaponGuard.png").write_bytes(b"png")
    (root / "generation-report.json").write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "major": "光职者(女)",
                        "sub": "光明骑士(女)",
                        "href": "光职者(女)/光明骑士(女)/index.html",
                        "learnSlots": 1,
                        "vpSkills": 0,
                        "iconOk": 1,
                        "iconMissing": 0,
                        "links": 1,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (page_dir / "skill-data.js").write_text(
        "window.BERSERKER_SKILL_DATA = "
        + json.dumps(
            {
                "profession": "光明骑士(女)",
                "classFamily": "光职者(女)",
                "cell": {"width": 47, "height": 67},
                "stats": {"learnSlots": 1, "vpSkills": 0, "iconOk": 1, "iconMissing": 0, "links": 1},
                "skills": [
                    {
                        "index": 156,
                        "english": "WeaponGuard",
                        "name": "武器格挡",
                        "x": 94,
                        "y": 201,
                        "icon": "assets/icons/156_WeaponGuard.png",
                    }
                ],
                "links": [{"from": 1, "to": 156, "x1": 10, "y1": 20, "x2": 30, "y2": 40}],
                "vpSkills": [],
            },
            ensure_ascii=False,
        )
        + ";",
        encoding="utf-8",
    )
    return page_dir


def test_skill_layout_repository_loads_pages_and_resolves_icons(tmp_path):
    page_dir = _write_page(tmp_path)

    repo = SkillLayoutRepository(tmp_path)
    pages = repo.pages()
    layout = repo.load_page("光职者(女)", "光明骑士(女)")

    assert pages[0].major == "光职者(女)"
    assert pages[0].sub == "光明骑士(女)"
    assert layout.class_family == "光职者(女)"
    assert layout.profession == "光明骑士(女)"
    assert layout.skills[0].english == "WeaponGuard"
    assert layout.skills[0].icon_path == page_dir / "assets" / "icons" / "156_WeaponGuard.png"
    assert layout.links[0].from_index == 1


def test_match_layout_skill_prefers_same_index_and_english_name():
    layout = SkillLayoutRepository.parse_skill_node(
        {
            "index": 156,
            "english": "WeaponGuard",
            "name": "武器格挡",
            "x": 0,
            "y": 0,
            "icon": "",
        },
        Path("."),
    )
    records = [
        SkillRecord(156, "光职者(男)", "光明骑士(男)", "武器格挡", "WeaponGuard", "vp1", "", 0, ()),
        SkillRecord(156, "光职者(男)", "光明骑士(男)", "武器格挡", "WeaponGuard", "原版", "", 0, ("a.img",)),
        SkillRecord(999, "光职者(男)", "光明骑士(男)", "武器格挡", "WeaponGuard", "原版", "", 0, ("b.img",)),
    ]

    assert match_layout_skill(layout, records) is records[1]


def test_default_skill_pages_dir_is_inside_tool_data_dir():
    path = skill_pages_dir()

    assert path.name == "skill_pages"
    assert path.parent.name == "data"
