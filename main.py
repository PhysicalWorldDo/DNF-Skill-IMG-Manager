from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app.main_window import MainWindow


def main() -> int:
    if "--smoke-test" in sys.argv:
        from app.dnflib_io import DnflibNpkIO
        from app.skill_db import SkillDatabase

        db = SkillDatabase()
        db.init()
        DnflibNpkIO()
        print(f"smoke ok: {len(db.professions())} professions, {db.total_skill_rows} rows")
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName("DNF 角色技能 IMG 管理器")
    try:
        window = MainWindow()
    except Exception as exc:
        QMessageBox.critical(None, "启动失败", str(exc))
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
