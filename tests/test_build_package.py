from build_package import copy_skill_pages


def test_copy_skill_pages_places_local_skill_data_under_target_data(tmp_path):
    project_root = tmp_path / "project"
    source_dir = project_root / "data" / "skill_pages" / "职业" / "转职"
    source_dir.mkdir(parents=True)
    (source_dir / "skill-data.js").write_text("window.BERSERKER_SKILL_DATA = {};", encoding="utf-8")

    target_root = tmp_path / "staged" / "tool" / "bin" / "app"

    copy_skill_pages(project_root, target_root)

    assert (target_root / "data" / "skill_pages" / "职业" / "转职" / "skill-data.js").exists()
