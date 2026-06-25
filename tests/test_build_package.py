from build_package import (
    DNFLIB_DLL,
    DNFLIB_DLL_NAME,
    SKILL_DB_DLL,
    SKILL_DB_DLL_NAME,
    TOOLALL_ROOT,
    copy_skill_pages,
    pyinstaller_env,
)


def test_package_uses_renamed_skill_img_db_dll():
    assert SKILL_DB_DLL_NAME == "SkillImgDb.dll"
    assert SKILL_DB_DLL.name == "SkillImgDb.dll"


def test_package_prefers_local_dnflib_dll():
    assert DNFLIB_DLL_NAME == "dnflib.dll"
    assert DNFLIB_DLL.name == "dnflib.dll"


def test_pyinstaller_env_disables_user_site_packages():
    env = pyinstaller_env()

    assert env["PYTHONNOUSERSITE"] == "1"
    assert env["PYTHONUSERBASE"] == str(TOOLALL_ROOT / ".build-venvs" / "_pyuserbase")


def test_copy_skill_pages_places_local_skill_data_under_target_data(tmp_path):
    project_root = tmp_path / "project"
    source_dir = project_root / "data" / "skill_pages" / "职业" / "转职"
    source_dir.mkdir(parents=True)
    (source_dir / "skill-data.js").write_text("window.BERSERKER_SKILL_DATA = {};", encoding="utf-8")

    target_root = tmp_path / "staged" / "tool" / "bin" / "app"

    copy_skill_pages(project_root, target_root)

    assert (target_root / "data" / "skill_pages" / "职业" / "转职" / "skill-data.js").exists()
