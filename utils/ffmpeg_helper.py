"""Utilities for detecting and configuring ffmpeg for pydub."""

import os
import sys
import shutil
from typing import Optional


def _bundled_ffmpeg_dir() -> Optional[str]:
    """Return the directory holding the bundled ffmpeg binaries, or None.

    Resolves to <bundle>/vendor/ffmpeg when running as a frozen PyInstaller
    app, or <project>/vendor/ffmpeg when running from source.
    """
    # PyInstaller stores bundled files under sys._MEIPASS in onefile mode.
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidate = os.path.join(base, "vendor", "ffmpeg")
        if os.path.isdir(candidate):
            return candidate
    # Source-tree fallback for `python main.py` runs.
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(here)
    candidate = os.path.join(project_root, "vendor", "ffmpeg")
    if os.path.isdir(candidate):
        return candidate
    return None


def find_ffmpeg() -> Optional[str]:
    """Return the path to ffmpeg.exe, or None if not found.

    Lookup order: bundled vendor/ffmpeg, PATH, common install locations.
    The bundled copy wins so distributing the .exe doesn't require the PM
    to install ffmpeg separately.
    """
    bundled = _bundled_ffmpeg_dir()
    if bundled:
        path = os.path.join(bundled, "ffmpeg.exe")
        if os.path.isfile(path):
            return path

    found = shutil.which("ffmpeg")
    if found:
        return found

    candidates = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        os.path.join(os.path.expanduser("~"), "ffmpeg", "bin", "ffmpeg.exe"),
        # winget default
        r"C:\Users\Public\ffmpeg\bin\ffmpeg.exe",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path

    return None


def apply_ffmpeg_path(ffmpeg_path: str):
    """Tell pydub to use a specific ffmpeg binary."""
    from pydub import AudioSegment

    ffmpeg_path = os.path.normpath(ffmpeg_path)
    AudioSegment.converter = ffmpeg_path

    bin_dir = os.path.dirname(ffmpeg_path)
    ffprobe_path = os.path.join(bin_dir, "ffprobe.exe")
    if os.path.isfile(ffprobe_path):
        AudioSegment.ffprobe = ffprobe_path

    # Prepend the ffmpeg dir to PATH so any pydub code path that resolves
    # "ffmpeg" by name (rather than via AudioSegment.converter) also finds
    # the right binary.
    if bin_dir:
        current = os.environ.get("PATH", "")
        if bin_dir.lower() not in (p.lower() for p in current.split(os.pathsep) if p):
            os.environ["PATH"] = bin_dir + os.pathsep + current


def is_winerror2(exc) -> bool:
    """Return True if the exception (or its stringified form) indicates
    Windows error 2 — i.e. the file/program could not be found.

    Accepts either an exception instance or a string repr of one, since the
    worker thread passes the failure across signal/slot as `str(exc)`.
    """
    if isinstance(exc, FileNotFoundError):
        return True
    if isinstance(exc, OSError) and getattr(exc, "winerror", None) == 2:
        return True
    text = str(exc) if exc is not None else ""
    return "WinError 2" in text or "[Errno 2]" in text


FFMPEG_HELP = (
    "找不到 ffmpeg，無法處理 mp3 / m4a 格式。\n\n"
    "解決方式：\n"
    "① 安裝 ffmpeg 並加入 PATH\n"
    "   winget install ffmpeg\n\n"
    "② 或點擊「設定 ffmpeg 路徑」手動指定 ffmpeg.exe\n\n"
    "ffmpeg 下載：https://ffmpeg.org/download.html"
)
