import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtCore import QPoint, QPointF
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem, QGraphicsScene

from app.main_window import MainWindow, SkillNodeItem
from app.skill_layout import SkillLayoutSkill, SkillPageLayout, SkillVpOption


def _app():
    return QApplication.instance() or QApplication([])


def _write_icon(path: Path) -> Path:
    image = QImage(28, 28, QImage.Format.Format_RGBA8888)
    image.fill(0xFF22AAFF)
    image.save(str(path))
    return path


class _Owner:
    def _select_layout_skill(self, _skill):
        pass


class _HoverEvent:
    def __init__(self, point):
        self._point = point

    def screenPos(self):
        return self._point


def test_tooltip_position_accepts_qpoint_and_qpointf():
    assert SkillNodeItem._tooltip_position(_HoverEvent(QPoint(12, 34))) == QPoint(12, 34)
    assert SkillNodeItem._tooltip_position(_HoverEvent(QPointF(56.2, 78.8))) == QPoint(56, 79)


def test_skill_icon_pixmap_carries_skill_name_tooltip(tmp_path):
    _app()
    icon_path = _write_icon(tmp_path / "icon.png")
    skill = SkillLayoutSkill(156, "WeaponGuard", "武器格挡", 0, 0, "icon.png", icon_path)

    item = SkillNodeItem(_Owner(), skill)
    pixmap_children = [child for child in item.childItems() if isinstance(child, QGraphicsPixmapItem)]

    assert pixmap_children
    assert "武器格挡" in pixmap_children[0].toolTip()


def test_vp_page_renders_base_and_option_icons(tmp_path):
    _app()
    icon_path = _write_icon(tmp_path / "icon.png")
    skill = SkillLayoutSkill(
        24,
        "AriaOfCourage",
        "勇气颂歌",
        94,
        536,
        "icon.png",
        icon_path,
        (
            SkillVpOption("vp1", "圣音协奏"),
            SkillVpOption("vp2", "天堂进行曲"),
        ),
    )
    window = MainWindow.__new__(MainWindow)
    window.vp_scene = QGraphicsScene()
    window.current_layout = SkillPageLayout(
        "光职者(女)",
        "光明骑士(女)",
        47,
        67,
        {},
        (),
        (),
        (skill,),
        tmp_path / "skill-data.js",
    )

    MainWindow._render_vp_page(window)

    pixmap_count = sum(1 for item in window.vp_scene.items() if isinstance(item, QGraphicsPixmapItem))
    assert pixmap_count >= 3


def test_main_window_separates_img_list_from_preview_column():
    _app()
    window = MainWindow()

    assert window.work_splitter.count() == 2
    assert window.img_list.parentWidget() is window.img_panel
    assert window.preview_label.parentWidget() is not window.img_panel
    assert window.view_tabs.maximumWidth() <= 660
    assert "#0b0c0b" in window.img_list.styleSheet()

    window.close()


def test_main_window_loads_original_html_skill_page():
    _app()
    window = MainWindow()

    html_path = window.skill_page_web.url().toLocalFile().replace("\\", "/")

    assert html_path.endswith("/data/skill_pages/光职者(女)/光明骑士(女)/index.html")

    window.close()


def test_html_injection_uses_outer_page_scrollbar():
    script = MainWindow._skill_page_injection_script()

    assert "html, body" in script
    assert "overflow-y: auto" in script
    assert ".learn-scroll" in script
    assert ".vp-scroll" in script
    assert "overflow: visible" in script
    assert "html::-webkit-scrollbar" in script
    assert "body::-webkit-scrollbar" in script
    assert ".learn-scroll::-webkit-scrollbar" in script
    assert ".vp-scroll::-webkit-scrollbar" in script
    assert "display: none" in script
    assert "width: 0" in script
    assert "height: 0" in script
    assert "scrollbar-width: none" in script
    assert ".dnf-window" in script
    assert "syncOuterScrollHeight" in script


def test_main_window_uses_skill_page_palette_stylesheet():
    _app()
    window = MainWindow()

    stylesheet = window.styleSheet()

    assert "#161717" in stylesheet
    assert "#0b0c0b" in stylesheet
    assert "#d8caa5" in stylesheet
    assert "#f3d66f" in stylesheet
    assert "#5d4523" in stylesheet
    assert "#07111f" not in stylesheet
    assert "QPushButton" in stylesheet
    assert "QTabWidget" in stylesheet

    window.close()


def test_main_window_uses_dark_native_title_bar_palette():
    _app()
    window = MainWindow()

    assert window.native_title_bar_caption_color == "#0b0c0b"
    assert window.native_title_bar_text_color == "#f3d66f"
    assert window._windows_colorref("#f3d66f") == 0x6FD6F3

    window.close()


def test_html_skill_selection_updates_img_panel():
    _app()
    window = MainWindow()
    layout_skill = next(
        skill for skill in window.current_layout.skills if skill.english.lower() == "weaponguard"
    )

    window._select_html_skill(layout_skill.index, layout_skill.english, layout_skill.name)

    assert "武器格挡 / weaponguard" in window.detail_title.text()
    assert window.img_list.count() == 4

    window.close()
