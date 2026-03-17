"""Utilities for detecting and configuring ffmpeg for pydub."""

import os
import shutil
from typing import Optional


def find_ffmpeg() -> Optional[str]:
    """Return the path to ffmpeg.exe, or None if not found."""
    # 1. Check PATH
    found = shutil.which("ffmpeg")
    if found:
        return found

    # 2. Common installation locations on Windows
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

    # Also set ffprobe (same directory, different name)
    ffprobe_path = os.path.join(os.path.dirname(ffmpeg_path), "ffprobe.exe")
    if os.path.isfile(ffprobe_path):
        AudioSegment.ffprobe = ffprobe_path


def is_winerror2(exc: Exception) -> bool:
    """Return True if the exception is WinError 2 (file not found)."""
    return (
        isinstance(exc, FileNotFoundError)
        or (isinstance(exc, OSError) and getattr(exc, "winerror", None) == 2)
    )


FFMPEG_HELP = (
    "找不到 ffmpeg，無法處理 mp3 / m4a 格式。\n\n"
    "解決方式：\n"
    "① 安裝 ffmpeg 並加入 PATH\n"
    "   winget install ffmpeg\n\n"
    "② 或點擊「設定 ffmpeg 路徑」手動指定 ffmpeg.exe\n\n"
    "ffmpeg 下載：https://ffmpeg.org/download.html"
)
