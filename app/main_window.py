from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")

from PySide6.QtCore import QObject, QSignalBlocker, QTimer, QUrl, Qt, Slot
from PySide6.QtGui import QAction, QBrush, QColor, QImage, QPainterPath, QPen, QPixmap
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from .dnflib_io import DnflibNpkIO
from .exporter import ExportJob, NpkExporter
from .models import DecodedFrame, SkillRecord
from .npk_paths import normalize_img_path, resolve_source_npk, should_skip_export_img
from .settings import DEFAULT_SOURCE_DIR, Settings, data_dir, skill_pages_dir
from .skill_db import SkillDatabase
from .skill_layout import (
    SkillLayoutRepository,
    SkillLayoutSkill,
    SkillPageInfo,
    SkillPageLayout,
    match_layout_skill,
)


NODE_SIZE = 42
ICON_SIZE = 28


class SkillPageBridge(QObject):
    def __init__(self, owner: "MainWindow"):
        super().__init__(owner)
        self.owner = owner

    @Slot(int, str, str)
    def selectSkill(self, index: int, english: str, name: str) -> None:
        self.owner._select_html_skill(index, english, name)


class SkillNodeItem(QGraphicsRectItem):
    def __init__(self, owner: "MainWindow", skill: SkillLayoutSkill):
        super().__init__(0, 0, NODE_SIZE, NODE_SIZE)
        self.owner = owner
        self.skill = skill
        self.hover_text = f"{skill.name} / {skill.english}\nindex: {skill.index}"
        self.setPos(skill.x, skill.y)
        self.setBrush(QBrush(QColor("#101111")))
        self.setPen(QPen(QColor("#343837"), 2))
        self.setToolTip(self.hover_text)
        self.setAcceptHoverEvents(True)

        if skill.icon_path and skill.icon_path.exists():
            pixmap = QPixmap(str(skill.icon_path)).scaled(
                ICON_SIZE,
                ICON_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            icon = QGraphicsPixmapItem(pixmap, self)
            icon.setPos(5, 5)
            icon.setToolTip(self.hover_text)
        else:
            text = QGraphicsTextItem("?", self)
            text.setDefaultTextColor(QColor("#d8caa5"))
            text.setPos(14, 8)
            text.setToolTip(self.hover_text)

    def mousePressEvent(self, event) -> None:
        self.owner._select_layout_skill(self.skill)
        event.accept()

    def hoverEnterEvent(self, event) -> None:
        QToolTip.showText(self._tooltip_position(event), self.hover_text)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        QToolTip.hideText()
        super().hoverLeaveEvent(event)

    @staticmethod
    def _tooltip_position(event):
        point = event.screenPos()
        return point.toPoint() if hasattr(point, "toPoint") else point

    def set_selected(self, selected: bool) -> None:
        if selected:
            self.setPen(QPen(QColor("#66a6ff"), 2))
            self.setBrush(QBrush(QColor("#16243a")))
        else:
            self.setPen(QPen(QColor("#343837"), 2))
            self.setBrush(QBrush(QColor("#101111")))


class MainWindow(QMainWindow):
    native_title_bar_caption_color = "#0b0c0b"
    native_title_bar_text_color = "#f3d66f"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DNF 角色技能 IMG 管理器")
        self.resize(1460, 860)
        self._apply_skill_page_theme()
        self._apply_native_title_bar_theme()

        self.settings = Settings()
        self.layout_repo = SkillLayoutRepository(skill_pages_dir())
        self.db = SkillDatabase()
        self.db.init()
        self.npk_io = DnflibNpkIO()
        self.exporter = NpkExporter(self.npk_io)

        self.current_big = ""
        self.current_small = ""
        self.current_layout: SkillPageLayout | None = None
        self.current_skills: list[SkillRecord] = []
        self.visible_skills: list[SkillRecord] = []
        self.layout_pages: list[SkillPageInfo] = []
        self.pages_by_family: dict[str, list[SkillPageInfo]] = {}
        self.skill_node_items: dict[SkillLayoutSkill, SkillNodeItem] = {}
        self.selected_layout_skill: SkillLayoutSkill | None = None
        self.selected_skill_record: SkillRecord | None = None
        self.web_bridge: SkillPageBridge | None = None
        self.web_channel: QWebChannel | None = None

        self.preview_frames: list[DecodedFrame] = []
        self.preview_frame_index = 0
        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self._advance_preview_frame)

        self._build_ui()
        self._load_settings()
        self._load_professions()
        self.statusBar().showMessage(
            f"技能库: {len(self.db.professions())} 个职业, {self.db.total_skill_rows} 行技能"
        )

    @staticmethod
    def _windows_colorref(hex_color: str) -> int:
        color = hex_color.lstrip("#")
        red = int(color[0:2], 16)
        green = int(color[2:4], 16)
        blue = int(color[4:6], 16)
        return (blue << 16) | (green << 8) | red

    def _apply_native_title_bar_theme(self) -> None:
        if os.name != "nt":
            return

        try:
            import ctypes

            hwnd = int(self.winId())
            if not hwnd:
                return

            dwmapi = ctypes.windll.dwmapi
            enabled = ctypes.c_int(1)
            for attribute in (20, 19):
                result = dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    attribute,
                    ctypes.byref(enabled),
                    ctypes.sizeof(enabled),
                )
                if result == 0:
                    break

            caption = ctypes.c_int(self._windows_colorref(self.native_title_bar_caption_color))
            text = ctypes.c_int(self._windows_colorref(self.native_title_bar_text_color))
            dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption))
            dwmapi.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(text), ctypes.sizeof(text))
        except Exception:
            return

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_native_title_bar_theme()

    def _apply_skill_page_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #161717;
                color: #d8caa5;
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
                font-size: 12px;
            }
            QToolBar {
                background: #0b0c0b;
                border: 0;
                border-bottom: 1px solid #3d3526;
                spacing: 6px;
            }
            QGroupBox {
                color: #f3d66f;
                border: 1px solid #3d3526;
                border-radius: 4px;
                margin-top: 10px;
                background: #0f1110;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLabel {
                color: #d8caa5;
            }
            QLineEdit, QComboBox, QPlainTextEdit, QTableWidget {
                background: #0b0c0b;
                color: #d8caa5;
                selection-background-color: #4d3a1a;
                selection-color: #fff1a8;
                border: 1px solid #3d3526;
                border-radius: 3px;
                padding: 3px 5px;
            }
            QComboBox::drop-down {
                border-left: 1px solid #3d3526;
                width: 20px;
            }
            QPushButton {
                background: #1b1a14;
                color: #e2d3a0;
                border: 1px solid #5d4523;
                border-radius: 3px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background: #312a1d;
                border-color: #8b6f2c;
                color: #fff1a8;
            }
            QPushButton:pressed {
                background: #4d3a1a;
                color: #f3d66f;
            }
            QTabWidget::pane {
                border: 1px solid #3d3526;
                background: #0b0c0b;
            }
            QTabBar::tab {
                background: #151615;
                color: #bda77b;
                border: 1px solid #4a3d27;
                border-bottom: 0;
                padding: 5px 14px;
            }
            QTabBar::tab:selected {
                background: #4d3a1a;
                color: #f1d978;
                border-color: #8b6f2c;
            }
            QCheckBox {
                color: #d8caa5;
                spacing: 6px;
            }
            QSplitter::handle {
                background: #2d2b23;
            }
            QHeaderView::section {
                background: #151615;
                color: #f3d66f;
                border: 1px solid #3d3526;
                padding: 4px;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background: #161717;
                border: 1px solid #3d3526;
                width: 13px;
                height: 13px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #7b5727;
                border-radius: 4px;
                min-height: 28px;
                min-width: 28px;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                width: 0;
                height: 0;
            }
            QStatusBar {
                background: #0b0c0b;
                color: #d2af43;
                border-top: 1px solid #3d3526;
            }
            """
        )

    def _build_ui(self) -> None:
        toolbar = QToolBar("主工具栏", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        reload_action = QAction(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload),
            "重新加载",
            self,
        )
        reload_action.triggered.connect(self._reload_current_profession)
        toolbar.addAction(reload_action)

        copy_action = QAction(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton),
            "复制IMG列表",
            self,
        )
        copy_action.triggered.connect(self._copy_selected_img_list)
        toolbar.addAction(copy_action)

        root = QWidget(self)
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(8, 8, 8, 8)

        path_box = QGroupBox("路径")
        form = QFormLayout(path_box)
        self.source_dir_edit = QLineEdit()
        self.source_dir_edit.setPlaceholderText("选择包含源 NPK 的目录")
        self.source_dir_edit.textChanged.connect(self._refresh_missing_counts)
        source_browse = QPushButton("浏览")
        source_browse.clicked.connect(self._browse_source_dir)
        source_row = QHBoxLayout()
        source_row.addWidget(self.source_dir_edit, 1)
        source_row.addWidget(source_browse)
        form.addRow("源 NPK 目录", source_row)

        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("选择导出 NPK 的目录")
        output_browse = QPushButton("浏览")
        output_browse.clicked.connect(self._browse_output_dir)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_dir_edit, 1)
        output_row.addWidget(output_browse)
        form.addRow("导出目录", output_row)
        root_layout.addWidget(path_box)

        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("职业"))
        self.family_combo = QComboBox()
        self.family_combo.currentTextChanged.connect(self._on_family_combo_changed)
        selector_row.addWidget(self.family_combo)
        selector_row.addWidget(QLabel("转职"))
        self.profession_combo = QComboBox()
        self.profession_combo.currentTextChanged.connect(self._on_profession_combo_changed)
        selector_row.addWidget(self.profession_combo)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索中文 / 英文 / IMG路径")
        self.search_edit.textChanged.connect(self._apply_skill_filter)
        selector_row.addWidget(self.search_edit, 1)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["全部", "原版", "vp1", "vp2"])
        self.type_combo.currentTextChanged.connect(self._apply_skill_filter)
        selector_row.addWidget(self.type_combo)
        root_layout.addLayout(selector_row)

        self.layout_stats_label = QLabel("技能页: 0  VP: 0  图标: 0/0  IMG匹配: 0/0  缺失: 0")
        root_layout.addWidget(self.layout_stats_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter, 1)

        work_panel = QWidget()
        work_layout = QVBoxLayout(work_panel)
        work_layout.setContentsMargins(0, 0, 0, 0)
        self.work_splitter = QSplitter(Qt.Orientation.Horizontal)
        work_layout.addWidget(self.work_splitter, 1)

        self.skill_page_web = QWebEngineView()
        self.skill_page_web.setMinimumWidth(565)
        self.skill_page_web.setMaximumWidth(640)
        self.skill_page_web.setStyleSheet("background:#090a09; border:1px solid #2d2b23;")
        self.web_channel = QWebChannel(self.skill_page_web.page())
        self.web_bridge = SkillPageBridge(self)
        self.web_channel.registerObject("skillBridge", self.web_bridge)
        self.skill_page_web.page().setWebChannel(self.web_channel)
        self.skill_page_web.loadFinished.connect(self._inject_skill_page_bridge)

        self.view_tabs = QTabWidget()
        self.view_tabs.setMinimumWidth(565)
        self.view_tabs.setMaximumWidth(660)
        self.learn_scene = QGraphicsScene(self)
        self.learn_view = QGraphicsView(self.learn_scene)
        self.learn_view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.learn_view.setStyleSheet("background:#090a09; border:1px solid #2d2b23;")
        self.view_tabs.addTab(self.skill_page_web, "技能页")

        self.vp_scene = QGraphicsScene(self)
        self.vp_view = QGraphicsView(self.vp_scene)
        self.vp_view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.vp_view.setStyleSheet("background:#0b0c0b; border:1px solid #2d2b23;")

        self.skill_table = QTableWidget(0, 7)
        self.skill_table.setHorizontalHeaderLabels(
            ["序号", "中文技能名", "英文名", "类型", "图标帧", "IMG数", "缺失源"]
        )
        self.skill_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.skill_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.skill_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.skill_table.verticalHeader().setVisible(False)
        self.skill_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.skill_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.skill_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.skill_table.itemSelectionChanged.connect(self._on_skill_selection_changed)
        self.view_tabs.addTab(self.skill_table, "IMG表格")
        self.work_splitter.addWidget(self.view_tabs)

        self.img_panel = QWidget()
        self.img_panel.setStyleSheet(
            "QWidget { background:#0f1110; color:#d8caa5; } "
            "QLabel { color:#f3d66f; }"
        )
        img_layout = QVBoxLayout(self.img_panel)
        img_layout.setContentsMargins(8, 0, 0, 0)
        self.detail_title = QLabel("未选择技能")
        self.detail_title.setWordWrap(True)
        self.detail_title.setMinimumHeight(54)
        img_layout.addWidget(self.detail_title)
        img_layout.addWidget(QLabel("IMG 资源"))
        self.img_list = QListWidget()
        self.img_list.setStyleSheet(
            "QListWidget { background:#0b0c0b; color:#d8caa5; border:1px solid #3d3526; } "
            "QListWidget::item { padding:3px 5px; } "
            "QListWidget::item:selected { background:#4d3a1a; color:#fff1a8; }"
        )
        self.img_list.currentItemChanged.connect(self._on_img_item_changed)
        img_layout.addWidget(self.img_list, 1)
        self.work_splitter.addWidget(self.img_panel)
        self.work_splitter.setSizes([590, 360])
        splitter.addWidget(work_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        preview_box = QGroupBox("IMG 动画预览")
        preview_layout = QVBoxLayout(preview_box)
        self.preview_label = QLabel("选择 IMG")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(360)
        self.preview_label.setStyleSheet("background:#050605; color:#d8caa5; border:1px solid #5d4523;")
        preview_layout.addWidget(self.preview_label, 1)

        preview_controls = QHBoxLayout()
        self.preview_prev_btn = QPushButton("上一帧")
        self.preview_prev_btn.clicked.connect(self._prev_preview_frame)
        self.preview_play_btn = QPushButton("播放")
        self.preview_play_btn.clicked.connect(self._toggle_preview_playback)
        self.preview_next_btn = QPushButton("下一帧")
        self.preview_next_btn.clicked.connect(self._next_preview_frame)
        self.preview_info_label = QLabel("0/0")
        preview_controls.addWidget(self.preview_prev_btn)
        preview_controls.addWidget(self.preview_play_btn)
        preview_controls.addWidget(self.preview_next_btn)
        preview_controls.addWidget(self.preview_info_label, 1, Qt.AlignmentFlag.AlignRight)
        preview_layout.addLayout(preview_controls)
        right_layout.addWidget(preview_box, 4)

        options_box = QGroupBox("导出选项")
        options_layout = QVBoxLayout(options_box)
        self.include_icon_check = QCheckBox("包含图标 IMG")
        self.include_body_check = QCheckBox("包含 body 模板 IMG")
        self.overwrite_check = QCheckBox("覆盖已存在文件")
        self.include_icon_check.stateChanged.connect(self._on_export_options_changed)
        self.include_body_check.stateChanged.connect(self._on_export_options_changed)
        options_layout.addWidget(self.include_icon_check)
        options_layout.addWidget(self.include_body_check)
        options_layout.addWidget(self.overwrite_check)
        right_layout.addWidget(options_box)

        export_row = QHBoxLayout()
        self.export_selected_btn = QPushButton("导出当前技能")
        self.export_selected_btn.clicked.connect(self._export_selected_skills)
        self.export_visible_btn = QPushButton("导出当前列表")
        self.export_visible_btn.clicked.connect(self._export_visible_skills)
        export_row.addWidget(self.export_selected_btn)
        export_row.addWidget(self.export_visible_btn)
        right_layout.addLayout(export_row)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumBlockCount(600)
        right_layout.addWidget(self.log_edit, 1)
        splitter.addWidget(right_panel)

        splitter.setSizes([1000, 520])

    def _load_settings(self) -> None:
        default_source = str(DEFAULT_SOURCE_DIR) if DEFAULT_SOURCE_DIR.exists() else ""
        self.source_dir_edit.setText(self.settings.get_str("source_dir", default_source))
        default_output = str(data_dir() / "exports")
        self.output_dir_edit.setText(self.settings.get_str("output_dir", default_output))

    def _save_settings(self) -> None:
        self.settings.set_str("source_dir", self.source_dir_edit.text().strip())
        self.settings.set_str("output_dir", self.output_dir_edit.text().strip())
        self.settings.save()

    def _load_professions(self) -> None:
        try:
            self.layout_pages = self.layout_repo.pages()
        except Exception as exc:
            self.layout_pages = []
            self._log(f"技能页数据加载失败: {exc}")

        self.pages_by_family = {}
        if self.layout_pages:
            for page in self.layout_pages:
                self.pages_by_family.setdefault(page.major, []).append(page)
        else:
            for big, small in self.db.professions():
                self.pages_by_family.setdefault(big, []).append(SkillPageInfo(big, small, ""))

        with QSignalBlocker(self.family_combo):
            self.family_combo.clear()
            self.family_combo.addItems(list(self.pages_by_family))
        if self.family_combo.count():
            self.family_combo.setCurrentIndex(0)
            self._on_family_combo_changed(self.family_combo.currentText())

    def _on_family_combo_changed(self, family: str) -> None:
        pages = self.pages_by_family.get(family, [])
        with QSignalBlocker(self.profession_combo):
            self.profession_combo.clear()
            for page in pages:
                self.profession_combo.addItem(page.sub, page)
        if self.profession_combo.count():
            self.profession_combo.setCurrentIndex(0)
            self._on_profession_combo_changed(self.profession_combo.currentText())

    def _on_profession_combo_changed(self, profession: str) -> None:
        if not profession:
            return
        self.current_big = self.family_combo.currentText()
        self.current_small = profession
        self._reload_current_profession()

    def _browse_source_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择源 NPK 目录", self.source_dir_edit.text())
        if path:
            self.source_dir_edit.setText(path)
            self._save_settings()

    def _browse_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择导出目录", self.output_dir_edit.text())
        if path:
            self.output_dir_edit.setText(path)
            self._save_settings()

    def _reload_current_profession(self) -> None:
        if not self.current_big or not self.current_small:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.current_skills = self.db.skills_for_profession(self.current_big, self.current_small)
            try:
                self.current_layout = self.layout_repo.load_page(self.current_big, self.current_small)
            except Exception as exc:
                self.current_layout = None
                self._log(f"技能页布局缺失: {self.current_big} / {self.current_small} - {exc}")
        finally:
            QApplication.restoreOverrideCursor()
        self.selected_layout_skill = None
        self.selected_skill_record = None
        self._render_current_layout()
        self._apply_skill_filter()
        self._update_stats_label()
        self._log(f"已加载 {self.current_big} / {self.current_small}: {len(self.current_skills)} 行")

    def _apply_skill_filter(self) -> None:
        text = self.search_edit.text().strip().lower()
        selected_type = self.type_combo.currentText()
        self.visible_skills = []
        for skill in self.current_skills:
            if selected_type != "全部" and skill.skill_type != selected_type:
                continue
            haystack = f"{skill.chinese_name} {skill.english_name} {' '.join(skill.img_paths)}".lower()
            if text and text not in haystack:
                continue
            self.visible_skills.append(skill)
        self._populate_skill_table()
        self._update_skill_highlights()

    def _populate_skill_table(self) -> None:
        self.skill_table.setRowCount(len(self.visible_skills))
        source_dir = Path(self.source_dir_edit.text().strip()) if self.source_dir_edit.text().strip() else None
        for row, skill in enumerate(self.visible_skills):
            missing_count = ""
            if source_dir and source_dir.exists():
                missing = self.exporter.missing_source_npks(
                    skill,
                    source_dir,
                    include_icon=self.include_icon_check.isChecked(),
                    include_body_templates=self.include_body_check.isChecked(),
                )
                missing_count = str(len(missing)) if missing else ""
            values = [
                skill.sequence,
                skill.chinese_name,
                skill.english_name,
                skill.skill_type,
                skill.icon_frame_index,
                len(skill.img_paths),
                missing_count,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, skill)
                if col == 6 and missing_count:
                    item.setBackground(QColor(255, 235, 205))
                self.skill_table.setItem(row, col, item)
        self.skill_table.resizeRowsToContents()
        self.statusBar().showMessage(f"{self.current_big} / {self.current_small}: {len(self.visible_skills)} 行")
        if self.selected_skill_record is not None:
            self._sync_table_selection(self.selected_skill_record)
        else:
            self._on_skill_selection_changed()

    def _refresh_missing_counts(self) -> None:
        self._populate_skill_table()
        if self.selected_skill_record:
            self._populate_img_detail(self.selected_skill_record)

    def _on_export_options_changed(self) -> None:
        self._refresh_missing_counts()

    def _selected_skills(self) -> list[SkillRecord]:
        rows = sorted({index.row() for index in self.skill_table.selectionModel().selectedRows()})
        selected = [self.visible_skills[row] for row in rows if row < len(self.visible_skills)]
        if selected:
            return selected
        return [self.selected_skill_record] if self.selected_skill_record else []

    def _on_skill_selection_changed(self) -> None:
        rows = sorted({index.row() for index in self.skill_table.selectionModel().selectedRows()})
        if not rows:
            if self.selected_skill_record is None:
                self._show_empty_detail()
            return
        skill = self.visible_skills[rows[0]]
        self.selected_skill_record = skill
        self.selected_layout_skill = self._layout_for_record(skill)
        self._sync_graph_selection()
        self._show_skill_detail(skill, self.selected_layout_skill)

    def _show_empty_detail(self) -> None:
        self.detail_title.setText("未选择技能")
        self.img_list.clear()
        self._clear_preview("选择 IMG")

    def _show_skill_detail(self, skill: SkillRecord | None, layout_skill: SkillLayoutSkill | None) -> None:
        if skill is None:
            title = "未匹配 IMG 数据"
            if layout_skill:
                title = f"{layout_skill.name} / {layout_skill.english}\nindex:{layout_skill.index}  未匹配 IMG 数据"
            self.detail_title.setText(title)
            self.img_list.clear()
            self._clear_preview("没有 IMG 数据")
            return
        self.detail_title.setText(
            f"{skill.chinese_name} / {skill.english_name}\n"
            f"index:{skill.sequence}  类型:{skill.skill_type}  IMG:{len(skill.img_paths)}"
        )
        self._populate_img_detail(skill)

    def _populate_img_detail(self, skill: SkillRecord) -> None:
        self.img_list.clear()
        source_dir_text = self.source_dir_edit.text().strip()
        source_dir = Path(source_dir_text) if source_dir_text else None
        first_preview_row = -1
        for raw_path in skill.img_paths:
            img_path = normalize_img_path(raw_path)
            skipped = False
            if not self.include_icon_check.isChecked() and img_path == normalize_img_path(skill.icon_img_path):
                skipped = True
            if should_skip_export_img(
                img_path,
                include_icon=self.include_icon_check.isChecked(),
                include_body_templates=self.include_body_check.isChecked(),
            ):
                skipped = True
            status = "跳过" if skipped else "待导出"
            if source_dir is not None and not skipped:
                source_npk = resolve_source_npk(source_dir, img_path)
                status = "存在" if source_npk.exists() else "缺失"
            short_name = self._short_img_name(img_path)
            item = QListWidgetItem(f"[{status}] {short_name}")
            item.setToolTip(img_path)
            if status == "缺失":
                item.setBackground(QColor(255, 230, 230))
            elif status == "跳过":
                item.setForeground(QColor(120, 120, 120))
            item.setData(Qt.ItemDataRole.UserRole, img_path)
            item.setData(Qt.ItemDataRole.UserRole + 1, status)
            self.img_list.addItem(item)
            if first_preview_row < 0 and status != "跳过":
                first_preview_row = self.img_list.count() - 1
        if self.img_list.count():
            self.img_list.setCurrentRow(first_preview_row if first_preview_row >= 0 else 0)
        else:
            self._clear_preview("没有 IMG 数据")

    @staticmethod
    def _short_img_name(img_path: str) -> str:
        parts = normalize_img_path(img_path).split("/")
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
        return img_path

    def _on_img_item_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self._clear_preview("选择 IMG")
            return
        img_path = current.data(Qt.ItemDataRole.UserRole)
        if not img_path:
            self._clear_preview("未找到 IMG 路径")
            return
        self._load_img_preview(str(img_path))

    def _load_img_preview(self, img_path: str) -> None:
        self._clear_preview("加载中...")
        source_text = self.source_dir_edit.text().strip()
        if not source_text:
            self._clear_preview("请选择源 NPK 目录")
            return
        source_dir = Path(source_text)
        if not source_dir.exists():
            self._clear_preview("源 NPK 目录不存在")
            return
        source_npk = resolve_source_npk(source_dir, img_path)
        if not source_npk.exists():
            self._clear_preview("IMG 来源缺失")
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            frames = self.npk_io.decode_entry_frames(source_npk, img_path)
        except Exception as exc:
            self._clear_preview(f"预览失败: {exc}")
            self._log(f"预览失败: {img_path} - {exc}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        if not frames:
            self._clear_preview("没有可解码帧")
            return
        self._set_preview_frames(frames)

    def _set_preview_frames(self, frames: list[DecodedFrame]) -> None:
        self.preview_timer.stop()
        self.preview_frames = frames
        self.preview_frame_index = 0
        self.preview_play_btn.setText("播放")
        self._show_preview_frame()

    def _clear_preview(self, message: str = "") -> None:
        self.preview_timer.stop()
        self.preview_frames = []
        self.preview_frame_index = 0
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText(message)
        self.preview_info_label.setText("0/0")
        self.preview_play_btn.setText("播放")

    def _show_preview_frame(self) -> None:
        if not self.preview_frames:
            return
        frame = self.preview_frames[self.preview_frame_index]
        image = QImage(
            frame.rgba,
            frame.width,
            frame.height,
            frame.width * 4,
            QImage.Format.Format_RGBA8888,
        ).copy()
        pixmap = QPixmap.fromImage(image)
        target_size = self.preview_label.size()
        if target_size.width() > 1 and target_size.height() > 1:
            pixmap = pixmap.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self.preview_label.setText("")
        self.preview_label.setPixmap(pixmap)
        self.preview_info_label.setText(
            f"{self.preview_frame_index + 1}/{len(self.preview_frames)}  "
            f"帧{frame.index}  {frame.width}x{frame.height}"
        )

    def _advance_preview_frame(self) -> None:
        if not self.preview_frames:
            return
        self.preview_frame_index = (self.preview_frame_index + 1) % len(self.preview_frames)
        self._show_preview_frame()
        if self.preview_timer.isActive():
            self.preview_timer.start(max(1, self.preview_frames[self.preview_frame_index].delay_ms))

    def _toggle_preview_playback(self) -> None:
        if len(self.preview_frames) <= 1:
            return
        if self.preview_timer.isActive():
            self.preview_timer.stop()
            self.preview_play_btn.setText("播放")
        else:
            self.preview_timer.start(max(1, self.preview_frames[self.preview_frame_index].delay_ms))
            self.preview_play_btn.setText("暂停")

    def _prev_preview_frame(self) -> None:
        if not self.preview_frames:
            return
        self.preview_timer.stop()
        self.preview_play_btn.setText("播放")
        self.preview_frame_index = (self.preview_frame_index - 1) % len(self.preview_frames)
        self._show_preview_frame()

    def _next_preview_frame(self) -> None:
        if not self.preview_frames:
            return
        self.preview_timer.stop()
        self.preview_play_btn.setText("播放")
        self._advance_preview_frame()

    def _render_current_layout(self) -> None:
        self._load_current_html_page()

    def _load_current_html_page(self) -> None:
        if self.current_layout is None:
            self.skill_page_web.setHtml("<html><body>没有技能页布局数据</body></html>")
            return
        index_path = self.current_layout.source_path.parent / "index.html"
        if not index_path.exists():
            self.skill_page_web.setHtml(f"<html><body>技能页 HTML 缺失: {index_path}</body></html>")
            return
        self.skill_page_web.setUrl(QUrl.fromLocalFile(str(index_path)))

    def _inject_skill_page_bridge(self, ok: bool) -> None:
        if not ok:
            return
        self.skill_page_web.page().runJavaScript(self._skill_page_injection_script())

    @staticmethod
    def _skill_page_injection_script() -> str:
        return r"""
(() => {
  const style = document.getElementById("py-outer-scrollbar-fix") || document.createElement("style");
  style.id = "py-outer-scrollbar-fix";
  style.textContent = `
    html, body {
      height: auto !important;
      min-height: 100% !important;
      overflow-y: auto !important;
      overflow-x: hidden !important;
      scrollbar-width: none !important;
      -ms-overflow-style: none !important;
      background: #161717 !important;
    }
    body {
      display: block !important;
      margin: 0 !important;
      padding: 0 !important;
    }
    .dnf-window {
      height: auto !important;
      min-height: 1000px !important;
      overflow: visible !important;
      margin: 0 auto 28px auto !important;
      box-shadow: 0 0 0 1px rgba(209, 172, 75, 0.18), 0 18px 38px rgba(0, 0, 0, 0.45) !important;
    }
    .main-panel {
      position: relative !important;
      height: auto !important;
      min-height: 928px !important;
      overflow: visible !important;
    }
    .tab-page {
      position: relative !important;
      height: auto !important;
      min-height: 904px !important;
      overflow: visible !important;
    }
    .learn-scroll,
    .vp-scroll {
      position: relative !important;
      inset: auto !important;
      height: auto !important;
      overflow: visible !important;
      scrollbar-width: none !important;
      -ms-overflow-style: none !important;
    }
    .skill-canvas,
    .vp-canvas {
      height: auto !important;
      overflow: visible !important;
    }
    html::-webkit-scrollbar,
    body::-webkit-scrollbar,
    .learn-scroll::-webkit-scrollbar,
    .vp-scroll::-webkit-scrollbar,
    ::-webkit-scrollbar {
      display: none !important;
      width: 0 !important;
      height: 0 !important;
      background: transparent !important;
    }
    ::-webkit-scrollbar-thumb {
      background: transparent !important;
      border: 0 !important;
    }
  `;
  if (!style.parentNode) document.head.appendChild(style);

  function syncOuterScrollHeight() {
    const activePage = document.querySelector(".tab-page.is-active");
    if (!activePage) return;
    const content = activePage.querySelector(".skill-canvas, .vp-canvas");
    const scrollArea = activePage.querySelector(".learn-scroll, .vp-scroll");
    const panel = document.querySelector(".main-panel");
    const frame = document.querySelector(".dnf-window");
    const contentHeight = Math.max(content ? content.scrollHeight : 0, content ? content.offsetHeight : 0, 904);
    const pageHeight = contentHeight + 36;
    activePage.style.minHeight = `${pageHeight}px`;
    if (scrollArea) scrollArea.style.minHeight = `${pageHeight}px`;
    if (panel) panel.style.minHeight = `${pageHeight + 38}px`;
    if (frame) frame.style.minHeight = `${pageHeight + 98}px`;
  }
  window.syncOuterScrollHeight = syncOuterScrollHeight;
  window.setTimeout(syncOuterScrollHeight, 0);
  window.setTimeout(syncOuterScrollHeight, 120);
  window.addEventListener("resize", syncOuterScrollHeight);
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => window.setTimeout(syncOuterScrollHeight, 0));
  });

  function wire(channel) {
    const bridge = channel.objects.skillBridge;
    window.skillBridge = bridge;
    const data = window.BERSERKER_SKILL_DATA || {};
    const skills = data.skills || [];
    document.querySelectorAll(".skill-node").forEach((button, index) => {
      const skill = skills[index];
      if (!skill || button.dataset.pyBridgeReady === "1") return;
      button.dataset.pyBridgeReady = "1";
      button.addEventListener("click", () => {
        window.lastPySelectedSkill = skill;
        bridge.selectSkill(Number(skill.index || 0), String(skill.english || ""), String(skill.name || ""));
      });
    });
    document.querySelectorAll(".vp-base, .vp-option").forEach((node) => {
      if (node.dataset.pyBridgeReady === "1") return;
      node.dataset.pyBridgeReady = "1";
      const row = node.closest(".vp-row");
      const rows = Array.from(document.querySelectorAll(".vp-row"));
      const skill = (data.vpSkills || [])[rows.indexOf(row)];
      if (!skill) return;
      node.addEventListener("click", () => {
        window.lastPySelectedSkill = skill;
        bridge.selectSkill(Number(skill.index || 0), String(skill.english || ""), String(skill.name || ""));
      });
    });
  }
  function start() {
    if (!window.qt || !qt.webChannelTransport) {
      window.setTimeout(start, 50);
      return;
    }
    new QWebChannel(qt.webChannelTransport, wire);
  }
  if (window.QWebChannel) {
    start();
  } else {
    const script = document.createElement("script");
    script.src = "qrc:///qtwebchannel/qwebchannel.js";
    script.onload = start;
    document.head.appendChild(script);
  }
})();
"""

    def _select_html_skill(self, index: int, english: str, name: str) -> None:
        if self.current_layout is None:
            return
        english_lc = english.lower()
        candidates = list(self.current_layout.skills) + list(self.current_layout.vp_skills)
        for skill in candidates:
            if skill.index == index and skill.english.lower() == english_lc:
                self._select_layout_skill(skill)
                return
        for skill in candidates:
            if skill.english.lower() == english_lc or skill.name == name:
                self._select_layout_skill(skill)
                return

    def _render_learn_page(self) -> None:
        self.learn_scene.clear()
        self.skill_node_items = {}
        layout = self.current_layout
        if layout is None:
            self.learn_scene.addText("没有技能页布局数据")
            return
        width = max(532, layout.canvas_width + 20)
        height = max(900, layout.canvas_height + 20)
        self.learn_scene.setSceneRect(0, 0, width, height)
        self._add_skill_grid(self.learn_scene, width, height)
        for link in layout.links:
            mid_y = round((link.y1 + link.y2) / 2)
            path = QPainterPath()
            path.moveTo(link.x1, link.y1)
            path.lineTo(link.x1, mid_y)
            path.lineTo(link.x2, mid_y)
            path.lineTo(link.x2, link.y2)
            item = self.learn_scene.addPath(path, QPen(QColor(168, 96, 38, 190), 3))
            item.setZValue(1)
        for skill in layout.skills:
            node = SkillNodeItem(self, skill)
            node.setZValue(2)
            self.skill_node_items[skill] = node
            self.learn_scene.addItem(node)
        self._update_skill_highlights()

    def _render_vp_page(self) -> None:
        self.vp_scene.clear()
        layout = self.current_layout
        if layout is None:
            self.vp_scene.addText("没有技能进化布局数据")
            return
        row_step = 136
        top = 18
        width = 552
        height = max(900, top + len(layout.vp_skills) * row_step + 40)
        self.vp_scene.setSceneRect(0, 0, width, height)
        self.vp_scene.setBackgroundBrush(QBrush(QColor("#0b0c0b")))
        for index, skill in enumerate(layout.vp_skills):
            y = top + index * row_step
            self.vp_scene.addRect(11, y, 531, 124, QPen(QColor("#30291f")), QBrush(QColor("#101210")))
            icon_item = SkillNodeItem(self, SkillLayoutSkill(skill.index, skill.english, skill.name, 28, y + 7, skill.icon, skill.icon_path, skill.vp))
            icon_item.setZValue(2)
            self.vp_scene.addItem(icon_item)
            text = self.vp_scene.addText(skill.name)
            text.setDefaultTextColor(QColor("#d2af43"))
            text.setPos(78, y + 12)
            for option_index, option in enumerate(skill.vp[:2]):
                x = 217 + option_index * 154
                self.vp_scene.addRect(x, y + 4, 148, 46, QPen(QColor("#40372a")), QBrush(QColor("#161816")))
                self._add_vp_icon(self.vp_scene, skill, x + 7, y + 12, 26)
                opt_text = self.vp_scene.addText(option.name or option.option_type)
                opt_text.setDefaultTextColor(QColor("#b99e64"))
                opt_text.setPos(x + 40, y + 15)

    @staticmethod
    def _add_vp_icon(scene: QGraphicsScene, skill: SkillLayoutSkill, x: int, y: int, size: int) -> None:
        scene.addRect(x - 2, y - 2, size + 4, size + 4, QPen(QColor("#3d3e39")), QBrush(QColor("#101111")))
        if skill.icon_path and skill.icon_path.exists():
            pixmap = QPixmap(str(skill.icon_path)).scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            item = scene.addPixmap(pixmap)
            item.setPos(x, y)
            item.setToolTip(f"{skill.name} / {skill.english}")

    @staticmethod
    def _add_skill_grid(scene: QGraphicsScene, width: int, height: int) -> None:
        scene.setBackgroundBrush(QBrush(QColor("#080908")))
        for y in range(0, int(height), 67):
            row_brush = QBrush(QColor("#20221f") if (y // 67) % 2 == 0 else QColor("#0b0c0b"))
            scene.addRect(0, y, width, 67, QPen(Qt.PenStyle.NoPen), row_brush).setZValue(0)
        for x in range(0, int(width), 94):
            scene.addRect(x, 0, 47, height, QPen(Qt.PenStyle.NoPen), QBrush(QColor(255, 255, 255, 8))).setZValue(0)

    def _select_layout_skill(self, layout_skill: SkillLayoutSkill) -> None:
        self.selected_layout_skill = layout_skill
        self.selected_skill_record = self._record_for_layout(layout_skill)
        self._sync_graph_selection()
        if self.selected_skill_record:
            self._sync_table_selection(self.selected_skill_record)
        self._show_skill_detail(self.selected_skill_record, layout_skill)

    def _record_for_layout(self, layout_skill: SkillLayoutSkill) -> SkillRecord | None:
        return match_layout_skill(layout_skill, self.current_skills)

    def _layout_for_record(self, record: SkillRecord) -> SkillLayoutSkill | None:
        if self.current_layout is None:
            return None
        for skill in self.current_layout.skills:
            if skill.index == record.sequence and skill.english.lower() == record.english_name.lower():
                return skill
        for skill in self.current_layout.skills:
            if skill.english.lower() == record.english_name.lower():
                return skill
        return None

    def _sync_graph_selection(self) -> None:
        for skill, item in self.skill_node_items.items():
            item.set_selected(skill == self.selected_layout_skill)

    def _sync_table_selection(self, skill: SkillRecord) -> None:
        with QSignalBlocker(self.skill_table):
            self.skill_table.clearSelection()
            for row, visible in enumerate(self.visible_skills):
                if visible is skill:
                    self.skill_table.selectRow(row)
                    self.skill_table.scrollToItem(self.skill_table.item(row, 0))
                    break

    def _update_skill_highlights(self) -> None:
        text = self.search_edit.text().strip().lower()
        if not self.skill_node_items:
            return
        for skill, item in self.skill_node_items.items():
            record = self._record_for_layout(skill)
            if not text:
                item.setOpacity(1.0)
                continue
            haystack = f"{skill.name} {skill.english}"
            if record:
                haystack += f" {record.chinese_name} {record.english_name} {' '.join(record.img_paths)}"
            item.setOpacity(1.0 if text in haystack.lower() else 0.28)

    def _update_stats_label(self) -> None:
        layout = self.current_layout
        if layout is None:
            self.layout_stats_label.setText("技能页: 0  VP: 0  图标: 0/0  IMG匹配: 0/0  缺失: 0")
            return
        matched = sum(1 for skill in layout.skills if self._record_for_layout(skill) is not None)
        missing = max(0, len(layout.skills) - matched)
        icon_ok = int(layout.stats.get("iconOk", 0))
        icon_missing = int(layout.stats.get("iconMissing", 0))
        icon_total = icon_ok + icon_missing
        self.layout_stats_label.setText(
            f"技能页:{len(layout.skills)}  VP:{len(layout.vp_skills)}  "
            f"图标:{icon_ok}/{icon_total or len(layout.skills)}  "
            f"IMG匹配:{matched}/{len(layout.skills)}  缺失:{missing}"
        )

    def _export_selected_skills(self) -> None:
        self._export_skills(self._selected_skills())

    def _export_visible_skills(self) -> None:
        self._export_skills(self.visible_skills)

    def _export_skills(self, skills: list[SkillRecord]) -> None:
        if not skills:
            QMessageBox.information(self, "无技能", "没有可导出的技能。")
            return
        source_text = self.source_dir_edit.text().strip()
        output_text = self.output_dir_edit.text().strip()
        if not source_text:
            QMessageBox.warning(self, "源目录无效", "请选择有效的源 NPK 目录。")
            return
        if not output_text:
            QMessageBox.warning(self, "导出目录无效", "请选择导出目录。")
            return
        source_dir = Path(source_text)
        output_dir = Path(output_text)
        if not source_dir.exists():
            QMessageBox.warning(self, "源目录无效", "请选择有效的源 NPK 目录。")
            return

        self._save_settings()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        success = 0
        try:
            for skill in skills:
                try:
                    report = self.exporter.export_skill(
                        ExportJob(
                            skill=skill,
                            source_dir=source_dir,
                            output_dir=output_dir,
                            overwrite=self.overwrite_check.isChecked(),
                            include_icon=self.include_icon_check.isChecked(),
                            include_body_templates=self.include_body_check.isChecked(),
                        )
                    )
                except Exception as exc:
                    self._log(f"失败: {skill.chinese_name} - {exc}")
                    continue
                success += 1
                self._log(
                    f"导出: {report.output_path} ({report.entry_count} IMG, {report.byte_count} bytes)"
                )
                if report.missing_img_paths:
                    self._log(f"跳过缺失 IMG: {skill.chinese_name} - {len(report.missing_img_paths)} 项")
                    for img_path in report.missing_img_paths:
                        self._log(f"  缺失: {img_path}")
                if report.missing_source_npks:
                    self._log(f"跳过缺失源 NPK: {skill.chinese_name} - {len(report.missing_source_npks)} 项")
                    for missing in report.missing_source_npks:
                        self._log(f"  缺失源 NPK: {missing.npk_name} -> {missing.img_path}")
        finally:
            QApplication.restoreOverrideCursor()
        QMessageBox.information(self, "导出完成", f"成功导出 {success}/{len(skills)} 个 NPK。")
        self._refresh_missing_counts()

    def _copy_selected_img_list(self) -> None:
        selected = self._selected_skills()
        if not selected:
            return
        text = "\n".join(selected[0].img_paths)
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage("已复制 IMG 列表")

    def _log(self, message: str) -> None:
        self.log_edit.appendPlainText(message)

    def closeEvent(self, event) -> None:
        self._save_settings()
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.preview_frames:
            self._show_preview_frame()
