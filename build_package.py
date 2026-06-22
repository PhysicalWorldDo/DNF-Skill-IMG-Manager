from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


TOOL_ID = "dnf_skill_img_manager"
TOOL_NAME = "DNF 角色技能 IMG 管理器"
CATEGORY = "角色工具"
DESCRIPTION = "查看 DNF 角色技能 IMG 数据，并按技能整理关联 IMG 导出 NPK。"
VERSION = "1.1.1"
RELEASE_DATE = "2026-06-23"
EXE_NAME = "DNF_Skill_IMG_Manager"
PACKAGE_NAME = f"{TOOL_ID}-{VERSION}-win-x64.zip"

PROJECT_ROOT = Path(__file__).resolve().parent
TOOLALL_ROOT = PROJECT_ROOT.parents[1]
DNF_AUTOPLAY_ROOT = TOOLALL_ROOT.parent
STAGED_ROOT = TOOLALL_ROOT / "staged" / TOOL_ID
PACKAGES_ROOT = TOOLALL_ROOT / "packages"
INDEX_ROOT = TOOLALL_ROOT / "index"
REGISTRY_ROOT = TOOLALL_ROOT / "registry_repo"
SKILL_DB_DLL = DNF_AUTOPLAY_ROOT / "DNFPVF" / "summary" / "SkillImgNativeDll" / "dist" / "PvfSkillImgDb.dll"
DNFLIB_DLL = DNF_AUTOPLAY_ROOT / "DNFlibrary" / "dnflib" / "build" / "dnflib.dll"


def _assert_inside(child: Path, parent: Path) -> None:
    child.resolve().relative_to(parent.resolve())


def _remove_tree(path: Path, allowed_parent: Path) -> None:
    if not path.exists():
        return
    _assert_inside(path, allowed_parent)
    shutil.rmtree(path)


def _manifest(package_url: str, sha256: str, size: int) -> dict:
    return {
        "schemaVersion": 1,
        "id": TOOL_ID,
        "name": TOOL_NAME,
        "category": CATEGORY,
        "description": DESCRIPTION,
        "icon": "",
        "entry": "bin/run.cmd",
        "needAdmin": False,
        "latest": {"stable": VERSION},
        "versions": [
            {
                "version": VERSION,
                "channel": "stable",
                "releaseDate": RELEASE_DATE,
                "packageUrl": package_url,
                "sha256": sha256,
                "size": size,
                "changelog": [
                    "优化技能页布局：技能图谱收窄，中间独立显示 IMG 列表，右侧保留大尺寸预览",
                    "恢复技能图标悬停名称提示",
                    "技能进化页补充基础技能和进化选项图标",
                    "IMG 列表使用暗色样式并隐藏 NPK 文件名，动画预览默认暂停",
                    "保留按技能整理 IMG 导出 NPK",
                ],
                "minToolboxVersion": "0.1.0",
            }
        ],
        "permissions": [],
        "tags": ["技能", "IMG", "NPK", "导出"],
        "status": "active",
        "blockedVersions": [],
    }


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_pyinstaller() -> Path:
    if not SKILL_DB_DLL.exists():
        raise FileNotFoundError(SKILL_DB_DLL)
    if not DNFLIB_DLL.exists():
        raise FileNotFoundError(DNFLIB_DLL)
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        EXE_NAME,
        "--add-binary",
        f"{SKILL_DB_DLL};.",
        "--add-binary",
        f"{DNFLIB_DLL};.",
        str(PROJECT_ROOT / "main.py"),
    ]
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)
    dist_dir = PROJECT_ROOT / "dist" / EXE_NAME
    if not (dist_dir / f"{EXE_NAME}.exe").exists():
        raise FileNotFoundError(dist_dir / f"{EXE_NAME}.exe")
    return dist_dir


def stage_package(dist_dir: Path) -> None:
    _remove_tree(STAGED_ROOT, TOOLALL_ROOT / "staged")
    app_dir = STAGED_ROOT / "bin" / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(dist_dir, app_dir, dirs_exist_ok=True)

    (STAGED_ROOT / "bin" / "run.cmd").write_text(
        "\r\n".join(
            [
                "@echo off",
                "setlocal",
                'set "ROOT=%~dp0.."',
                'set "APPDIR=%ROOT%\\bin\\app"',
                'if not exist "%ROOT%\\config" mkdir "%ROOT%\\config"',
                'if not exist "%ROOT%\\data" mkdir "%ROOT%\\data"',
                'pushd "%APPDIR%"',
                f'start "" /wait "%APPDIR%\\{EXE_NAME}.exe"',
                "popd",
                "endlocal",
                "",
            ]
        ),
        encoding="utf-8",
    )
    copy_skill_pages(PROJECT_ROOT, STAGED_ROOT)
    _write_json(STAGED_ROOT / "tool.json", _manifest("", "", 0))


def copy_skill_pages(project_root: Path, staged_root: Path) -> None:
    source = project_root / "data" / "skill_pages"
    if not source.exists():
        raise FileNotFoundError(source)
    target = staged_root / "data" / "skill_pages"
    if target.exists():
        _assert_inside(target, staged_root)
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)


def zip_staged() -> Path:
    PACKAGES_ROOT.mkdir(parents=True, exist_ok=True)
    package_path = PACKAGES_ROOT / PACKAGE_NAME
    if package_path.exists():
        package_path.unlink()
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(STAGED_ROOT.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(STAGED_ROOT).as_posix())
    return package_path


def file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _ensure_index_entry(index_path: Path) -> None:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    tools = data.setdefault("tools", [])
    entry = {
        "id": TOOL_ID,
        "name": TOOL_NAME,
        "category": CATEGORY,
        "manifestUrl": f"tools/{TOOL_ID}.json",
    }
    for index, item in enumerate(tools):
        if item.get("id") == TOOL_ID:
            tools[index] = entry
            break
    else:
        tools.append(entry)
    _write_json(index_path, data)


def update_manifests(package_path: Path) -> None:
    sha256 = file_sha256(package_path)
    size = package_path.stat().st_size
    local_package_url = "file:///" + str(package_path).replace("\\", "/")
    release_package_url = (
        "https://github.com/PhysicalWorldDo/DNF-Skill-IMG-Manager/releases/download/"
        f"v{VERSION}/{PACKAGE_NAME}"
    )

    _write_json(INDEX_ROOT / "tools" / f"{TOOL_ID}.json", _manifest(local_package_url, sha256, size))
    _write_json(REGISTRY_ROOT / "tools" / f"{TOOL_ID}.json", _manifest(release_package_url, sha256, size))
    _ensure_index_entry(INDEX_ROOT / "index.json")
    _ensure_index_entry(REGISTRY_ROOT / "index.json")
    print(f"PACKAGE {package_path}")
    print(f"SIZE {size}")
    print(f"SHA256 {sha256}")


def main() -> int:
    dist_dir = run_pyinstaller()
    stage_package(dist_dir)
    package_path = zip_staged()
    update_manifests(package_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
