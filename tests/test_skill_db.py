from pathlib import Path

from app.skill_db import DEFAULT_SKILL_DB_DLL, SKILL_DB_DLL_NAME, SkillDatabase


def test_skill_db_uses_renamed_skill_img_db_dll():
    assert SKILL_DB_DLL_NAME == "SkillImgDb.dll"
    assert DEFAULT_SKILL_DB_DLL.name == "SkillImgDb.dll"


def test_skill_db_can_enumerate_professions_and_find_known_skill():
    assert DEFAULT_SKILL_DB_DLL.exists()

    db = SkillDatabase(DEFAULT_SKILL_DB_DLL)
    db.init()

    professions = db.professions()
    assert len(professions) >= 70
    assert ("光职者(女)", "蓝拳使者(女)") in professions

    skills = db.skills_for_profession("光职者(女)", "蓝拳使者(女)")
    known = [
        item
        for item in skills
        if item.chinese_name == "治愈祈祷" and item.skill_type == "原版"
    ]
    assert len(known) == 1
    assert known[0].icon_img_path == "sprite/character/priest/effect/atskillicon.img"
    assert known[0].icon_frame_index == 80
    assert "sprite/character/priest/effect/atprayerofheal/effect.img" in known[0].img_paths
