import sys
import os
import faulthandler
import tempfile
import traceback
from datetime import datetime

# ---------------------------------------------------------------------------
# Diagnostic logging
# ---------------------------------------------------------------------------
# Native-code crashes (segfaults from CTranslate2 / onnxruntime / Qt) kill the
# process before Python can print a traceback. faulthandler dumps a C stack
# trace to this file on any fatal signal; the sys.excepthook below captures
# unhandled Python exceptions to the same place. The file lives in %TEMP%
# so a packaged user can always find it after a crash.
_crash_log_path = os.path.join(tempfile.gettempdir(),
                               "AudioSentenceCutter_crash.log")
try:
    _crash_log = open(_crash_log_path, "w", encoding="utf-8", buffering=1)
    _crash_log.write(f"=== AudioSentenceCutter start: {datetime.now().isoformat()} ===\n")
    _crash_log.write(f"Python: {sys.version}\n")
    _crash_log.write(f"Executable: {sys.executable}\n")
    _crash_log.write(f"Frozen: {getattr(sys, 'frozen', False)}\n")
    _crash_log.write(f"MEIPASS: {getattr(sys, '_MEIPASS', None)}\n\n")
    _crash_log.flush()
    faulthandler.enable(file=_crash_log, all_threads=True)
except Exception:
    _crash_log = None


def _log(msg: str):
    if _crash_log is not None:
        try:
            _crash_log.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]}  {msg}\n")
            _crash_log.flush()
        except Exception:
            pass


def _excepthook(exc_type, exc_value, exc_tb):
    if _crash_log is not None:
        try:
            _crash_log.write("\n=== UNCAUGHT EXCEPTION ===\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=_crash_log)
            _crash_log.flush()
        except Exception:
            pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _excepthook

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# In a frozen onefile build, the native libs of ctranslate2 / onnxruntime /
# av live in subdirs of sys._MEIPASS. Register each as a DLL search dir so
# downstream `import ctranslate2._ext` etc. find their sibling DLLs even
# when Python loads the .pyd through unusual paths.
if getattr(sys, "frozen", False) and hasattr(os, "add_dll_directory"):
    _meipass = getattr(sys, "_MEIPASS", None)
    if _meipass:
        for _sub in ("ctranslate2", "onnxruntime/capi", "av.libs", "tokenizers",
                     "sounddevice", "PySide6"):
            _p = os.path.join(_meipass, _sub)
            if os.path.isdir(_p):
                try:
                    os.add_dll_directory(_p)
                    os.environ["PATH"] = _p + os.pathsep + os.environ.get("PATH", "")
                    _log(f"add_dll_directory: {_p}")
                except Exception as _e:
                    _log(f"add_dll_directory failed for {_p}: {_e}")

# Set up ffmpeg PATH BEFORE any module that imports pydub. pydub runs a
# shutil.which("ffmpeg") at import time and warns to stderr if it can't
# find one — annoying for our users since the warning shows even though
# the bundled ffmpeg works fine via AudioSegment.converter.
try:
    from utils.ffmpeg_helper import find_ffmpeg
    _ff_path = find_ffmpeg()
    if _ff_path:
        _ff_dir = os.path.dirname(_ff_path)
        if _ff_dir not in os.environ.get("PATH", "").split(os.pathsep):
            os.environ["PATH"] = _ff_dir + os.pathsep + os.environ.get("PATH", "")
        _log(f"Pre-import: ffmpeg dir on PATH -> {_ff_dir}")
    else:
        _log("Pre-import: ffmpeg not found")
except Exception as _e:
    _log(f"Pre-import ffmpeg setup failed: {_e}")

# Probe onnxruntime — faster_whisper masks the real ImportError, so do it
# ourselves to surface DLL / dependency issues clearly in the crash log.
try:
    _log("Probe: importing onnxruntime")
    import onnxruntime as _ort
    _log(f"Probe: onnxruntime OK, version={getattr(_ort, '__version__', '?')}")
    _log(f"Probe: providers={_ort.get_available_providers()}")
except Exception as _e:
    _log(f"Probe: onnxruntime import FAILED: {type(_e).__name__}: {_e}")
    import traceback as _tb
    _log(_tb.format_exc())

_log("Importing pyqtgraph")
import pyqtgraph as pg

# Configure pyqtgraph before creating QApplication
pg.setConfigOption("background", "#1a1a2e")
pg.setConfigOption("foreground", "#cdd6f4")
pg.setConfigOptions(antialias=False)

_log("Importing PySide6")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
_log("Importing MainWindow")
from ui.main_window import MainWindow
_log("Imports complete")


def main():
    _log("Entering main()")
    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("AI 音檔分割工具")
    app.setOrganizationName("AudioCutterAI")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
