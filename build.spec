# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for AudioSentenceCutter (AI 音檔分割工具).
# The recursion-limit bump is required because faster_whisper +
# ctranslate2 + onnxruntime have a deep transitive import graph that
# blows past the default 1000-frame stack.

import os
import sys
sys.setrecursionlimit(sys.getrecursionlimit() * 5)

# Windows Defender often locks the freshly-written 300 MB onefile exe
# while it scans, which makes PyInstaller's post-build PE timestamp update
# fail. The timestamp is purely cosmetic for our use, so disable it.
try:
    from PyInstaller.utils.win32 import winutils as _winutils
    _winutils.set_exe_build_timestamp = lambda *args, **kwargs: None
except Exception:
    pass

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

for pkg in (
    'pyqtgraph',
    'faster_whisper',
    'ctranslate2',
    'tokenizers',
    'onnxruntime',
    'huggingface_hub',
    'av',
    'sounddevice',
):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    # CTranslate2 4.5+ probes for CUDA during model init even when device='cpu'.
    # If we ship cuDNN but not the rest of the CUDA runtime (cudart/cublas),
    # that probe crashes with an access violation. Strip CUDA-related DLLs
    # for our CPU-only build.
    if pkg == 'ctranslate2':
        pkg_binaries = [
            (src, dest) for src, dest in pkg_binaries
            if not any(tok in os.path.basename(src).lower()
                       for tok in ('cudnn', 'cudart', 'cublas', 'cufft', 'curand', 'cusolver', 'cusparse'))
        ]
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=[
        ('ui', 'ui'),
        ('core', 'core'),
        ('utils', 'utils'),
        # Bundle ffmpeg + ffprobe so the .exe runs on machines without a
        # separate ffmpeg install. find_ffmpeg() resolves to vendor/ffmpeg
        # under sys._MEIPASS at runtime.
        ('vendor/ffmpeg/ffmpeg.exe', 'vendor/ffmpeg'),
        ('vendor/ffmpeg/ffprobe.exe', 'vendor/ffmpeg'),
    ] + datas,
    hiddenimports=[
        'pydub',
        'numpy',
        # pyqtgraph imports these through its Qt abstraction layer; PyInstaller
        # cannot detect them statically.
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'PySide6.QtSvg',
        'PySide6.QtPrintSupport',
    ] + hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # PyInstaller 6 refuses to bundle if multiple Qt bindings are visible.
    # We use PySide6 only — exclude the others (they're installed for
    # other projects on this machine).
    excludes=['PyQt6', 'PyQt5', 'PySide2'],
    noarchive=False,
)

# Note: earlier builds stripped cuDNN to dodge a suspected access-violation
# on model init. Turns out ctranslate2.dll links cuDNN as a hard dependency,
# so stripping it makes ctranslate2.dll fail to load at all. Keep cuDNN.

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AudioSentenceCutter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
