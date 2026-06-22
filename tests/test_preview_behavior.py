import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from app.main_window import MainWindow
from app.models import DecodedFrame


def _app():
    return QApplication.instance() or QApplication([])


def test_set_preview_frames_keeps_multi_frame_img_paused_by_default():
    _app()
    window = MainWindow.__new__(MainWindow)
    window.preview_timer = QTimer()
    window.preview_frames = []
    window.preview_frame_index = 0
    window.preview_label = QLabel()
    window.preview_label.resize(120, 120)
    window.preview_info_label = QLabel()
    window.preview_play_btn = QPushButton()

    frames = [
        DecodedFrame(0, b"\xff\x00\x00\xff" * 4, 2, 2, 90),
        DecodedFrame(1, b"\x00\xff\x00\xff" * 4, 2, 2, 90),
    ]

    window._set_preview_frames(frames)

    assert window.preview_frame_index == 0
    assert not window.preview_timer.isActive()
    assert window.preview_play_btn.text() == "播放"
    assert window.preview_info_label.text().startswith("1/2")
