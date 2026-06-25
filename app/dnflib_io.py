from __future__ import annotations

import ctypes
import sys
from pathlib import Path
from typing import Iterable

from .models import DecodedFrame
from .npk_paths import normalize_img_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DNF_AUTOPLAY_ROOT = PROJECT_ROOT.parents[2]
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
DNFLIB_DLL_NAME = "dnflib.dll"
BUNDLED_DNFLIB_DLL = BUNDLE_DIR / DNFLIB_DLL_NAME
LOCAL_DNFLIB_DLL = PROJECT_ROOT / DNFLIB_DLL_NAME
SOURCE_DNFLIB_DLL = DNF_AUTOPLAY_ROOT / "DNFlibrary" / "dnflib" / "build" / "dnflib.dll"


def _default_dnflib_dll() -> Path:
    if getattr(sys, "frozen", False) and BUNDLED_DNFLIB_DLL.exists():
        return BUNDLED_DNFLIB_DLL
    if LOCAL_DNFLIB_DLL.exists():
        return LOCAL_DNFLIB_DLL
    return SOURCE_DNFLIB_DLL if SOURCE_DNFLIB_DLL.exists() else BUNDLED_DNFLIB_DLL


DEFAULT_DNFLIB_DLL = _default_dnflib_dll()

DNF_OK = 0
FMT_LINK = 0x11


class DnfError(Exception):
    pass


class NpkEntry(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char * 256),
        ("offset", ctypes.c_int32),
        ("size", ctypes.c_int32),
    ]

    @property
    def name_str(self) -> str:
        raw = bytes(self.name).split(b"\x00", 1)[0]
        for encoding in ("euc-kr", "cp949", "utf-8", "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("latin-1", errors="replace")


class NpkFile(ctypes.Structure):
    pass


NpkFile._fields_ = [
    ("entries", ctypes.POINTER(NpkEntry)),
    ("count", ctypes.c_int),
    ("_priv", ctypes.c_void_p),
]


class ImageFrame(ctypes.Structure):
    _fields_ = [
        ("format", ctypes.c_int32),
        ("compress", ctypes.c_int32),
        ("w", ctypes.c_int32),
        ("h", ctypes.c_int32),
        ("x", ctypes.c_int32),
        ("y", ctypes.c_int32),
        ("mw", ctypes.c_int32),
        ("mh", ctypes.c_int32),
        ("data", ctypes.POINTER(ctypes.c_uint8)),
        ("data_size", ctypes.c_int32),
        ("link_index", ctypes.c_int32),
    ]


class ImgFile(ctypes.Structure):
    pass


ImgFile._fields_ = [
    ("version", ctypes.c_int),
    ("frames", ctypes.POINTER(ImageFrame)),
    ("frame_count", ctypes.c_int),
    ("_priv", ctypes.c_void_p),
]


def find_entry_index(entries: Iterable[object], img_path: str) -> int | None:
    normalized = normalize_img_path(img_path)
    for index, entry in enumerate(entries):
        if normalize_img_path(entry.name_str) == normalized:
            return index
    return None


class DnflibNpkIO:
    def __init__(self, dll_path: Path | str = DEFAULT_DNFLIB_DLL):
        self.dll_path = Path(dll_path)
        if not self.dll_path.exists():
            raise FileNotFoundError(f"dnflib.dll not found: {self.dll_path}")
        self._dll = ctypes.CDLL(str(self.dll_path))
        self._configure()

    def _configure(self) -> None:
        dll = self._dll
        dll.dnf_npk_open_file.restype = ctypes.c_int
        dll.dnf_npk_open_file.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.POINTER(NpkFile))]
        dll.dnf_npk_open_mem.restype = ctypes.c_int
        dll.dnf_npk_open_mem.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.POINTER(NpkFile)),
        ]
        dll.dnf_npk_create.restype = ctypes.c_int
        dll.dnf_npk_create.argtypes = [ctypes.POINTER(ctypes.POINTER(NpkFile))]
        dll.dnf_npk_add_entry.restype = ctypes.c_int
        dll.dnf_npk_add_entry.argtypes = [
            ctypes.POINTER(NpkFile),
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_int32,
        ]
        dll.dnf_npk_save_file.restype = ctypes.c_int
        dll.dnf_npk_save_file.argtypes = [ctypes.c_char_p, ctypes.POINTER(NpkFile), ctypes.c_int]
        dll.dnf_npk_read_img.restype = ctypes.c_int
        dll.dnf_npk_read_img.argtypes = [
            ctypes.POINTER(NpkFile),
            ctypes.c_int,
            ctypes.POINTER(ctypes.POINTER(ImgFile)),
        ]
        dll.dnf_npk_free.restype = None
        dll.dnf_npk_free.argtypes = [ctypes.POINTER(NpkFile)]
        dll.dnf_img_free.restype = None
        dll.dnf_img_free.argtypes = [ctypes.POINTER(ImgFile)]
        dll.dnf_image_decode.restype = ctypes.c_int
        dll.dnf_image_decode.argtypes = [
            ctypes.POINTER(ImgFile),
            ctypes.c_int,
            ctypes.POINTER(ctypes.POINTER(ctypes.c_uint8)),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
        ]
        dll.dnf_free.restype = None
        dll.dnf_free.argtypes = [ctypes.c_void_p]

    def _check(self, rc: int, context: str) -> None:
        if rc != DNF_OK:
            raise DnfError(f"{context}: dnflib error {rc}")

    def _path_bytes(self, path: Path) -> bytes:
        return str(path).encode("mbcs")

    def _open_npk(self, path: Path):
        data = path.read_bytes()
        if not data:
            raise OSError(f"Empty NPK file: {path}")
        backing = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
        out = ctypes.POINTER(NpkFile)()
        self._check(
            self._dll.dnf_npk_open_mem(backing, len(data), ctypes.byref(out)),
            f"open NPK {path}",
        )
        return out, backing

    def read_entry(self, npk_path: Path, img_path: str) -> bytes:
        npk, _backing = self._open_npk(npk_path)
        try:
            entries = [npk.contents.entries[index] for index in range(npk.contents.count)]
            entry_index = find_entry_index(entries, img_path)
            if entry_index is None:
                raise FileNotFoundError(f"IMG {img_path} not found in {npk_path}")
            match = entries[entry_index]
            with npk_path.open("rb") as file:
                file.seek(int(match.offset))
                data = file.read(int(match.size))
            if len(data) != int(match.size):
                raise OSError(f"Short read from {npk_path}: expected {match.size}, got {len(data)}")
            return data
        finally:
            self._dll.dnf_npk_free(npk)

    def decode_entry_frames(self, npk_path: Path, img_path: str, max_frames: int = 300) -> list[DecodedFrame]:
        npk, _backing = self._open_npk(npk_path)
        img = ctypes.POINTER(ImgFile)()
        img_loaded = False
        try:
            entries = [npk.contents.entries[index] for index in range(npk.contents.count)]
            entry_index = find_entry_index(entries, img_path)
            if entry_index is None:
                raise FileNotFoundError(f"IMG {img_path} not found in {npk_path}")
            self._check(
                self._dll.dnf_npk_read_img(npk, entry_index, ctypes.byref(img)),
                f"read IMG {img_path}",
            )
            img_loaded = True
            frame_count = min(int(img.contents.frame_count), max_frames)
            decoded: list[DecodedFrame] = []
            for frame_index in range(frame_count):
                frame = img.contents.frames[frame_index]
                if int(frame.format) == FMT_LINK:
                    continue
                out_rgba = ctypes.POINTER(ctypes.c_uint8)()
                out_w = ctypes.c_int(0)
                out_h = ctypes.c_int(0)
                rc = self._dll.dnf_image_decode(
                    img,
                    frame_index,
                    ctypes.byref(out_rgba),
                    ctypes.byref(out_w),
                    ctypes.byref(out_h),
                )
                if rc != DNF_OK:
                    continue
                try:
                    width = int(out_w.value)
                    height = int(out_h.value)
                    rgba = bytes(out_rgba[: width * height * 4])
                    decoded.append(DecodedFrame(frame_index, rgba, width, height))
                finally:
                    self._dll.dnf_free(out_rgba)
            return decoded
        finally:
            if img_loaded:
                self._dll.dnf_img_free(img)
            self._dll.dnf_npk_free(npk)

    def write_npk(
        self,
        output_path: Path,
        entries: Iterable[tuple[str, bytes]],
        overwrite: bool = False,
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            if not overwrite:
                raise FileExistsError(f"Output already exists: {output_path}")
            output_path.unlink()

        npk = ctypes.POINTER(NpkFile)()
        self._check(self._dll.dnf_npk_create(ctypes.byref(npk)), "create output NPK")
        try:
            for img_path, data in entries:
                name = normalize_img_path(img_path)
                try:
                    name_bytes = name.encode("euc-kr")
                except UnicodeEncodeError:
                    name_bytes = name.encode("gbk", errors="replace")
                if len(name_bytes) > 255:
                    raise ValueError(f"NPK entry name is too long: {name}")
                buf = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
                self._check(
                    self._dll.dnf_npk_add_entry(npk, name_bytes, buf, len(data)),
                    f"add IMG {name}",
                )
            self._check(
                self._dll.dnf_npk_save_file(self._path_bytes(output_path), npk, 0),
                f"save NPK {output_path}",
            )
        finally:
            self._dll.dnf_npk_free(npk)
