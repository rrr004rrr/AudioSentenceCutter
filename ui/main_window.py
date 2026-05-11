import os
import json
import threading
import time
from typing import Optional

import sounddevice as sd
import numpy as np

from PySide6.QtCore import Qt, QThread, QObject, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QFileDialog, QProgressBar, QComboBox, QMessageBox,
    QAbstractItemView, QSizePolicy, QSpinBox, QDoubleSpinBox,
)
from PySide6.QtGui import QColor, QFont
from pydub import AudioSegment as PydubAudio

from core.audio_loader import AudioLoader
from core.transcriber import Transcriber, Segment
from core.exporter import Exporter
from utils.ffmpeg_helper import find_ffmpeg, apply_ffmpeg_path, is_winerror2, FFMPEG_HELP
from utils.time_format import format_seconds
from ui.waveform_widget import WaveformWidget


# ---------------------------------------------------------------------------
# File status definitions
# ---------------------------------------------------------------------------
# status -> (prefix, hex colour)
STATUS_DISPLAY = {
    "queued":       ("⏳", "#6c7086"),
    "loading":      ("📂", "#f9e2af"),
    "transcribing": ("🎙", "#fab387"),
    "ready":        ("✓ ", "#a6e3a1"),
    "error":        ("✗ ", "#f38ba8"),
}


# ---------------------------------------------------------------------------
# Queue worker — processes files one by one in a background thread
# ---------------------------------------------------------------------------
class QueueWorker(QObject):
    """Loads audio + transcribes files sequentially.

    Results are stored in audio_results / segment_results dicts.
    The main thread reads them after receiving file_ready.
    """
    file_status = Signal(str, str)   # path, status string
    file_ready  = Signal(str)        # path fully processed
    file_failed = Signal(str, str)   # path, error message

    def __init__(self):
        super().__init__()
        self._queue: list = []
        self._lock = threading.Lock()
        self._stop = False
        self._transcriber: Optional[Transcriber] = None
        self._transcriber_model: Optional[str] = None
        # Temporary storage until main thread picks up
        self.audio_results: dict = {}    # path -> PydubAudio
        self.segment_results: dict = {}  # path -> list[Segment]

    def enqueue(self, file_path: str, model_size: str, language,
                min_silence_ms: int = 500, vad_threshold: float = 0.5):
        with self._lock:
            # Remove duplicate entries (re-queue at end)
            self._queue = [item for item in self._queue if item[0] != file_path]
            self._queue.append((file_path, model_size, language,
                                min_silence_ms, vad_threshold))

    def stop(self):
        self._stop = True

    @Slot()
    def run(self):
        while not self._stop:
            item = None
            with self._lock:
                if self._queue:
                    item = self._queue.pop(0)

            if item is None:
                QThread.msleep(100)
                continue

            file_path, model_size, language, min_silence_ms, vad_threshold = item
            try:
                # 1. Load audio
                self.file_status.emit(file_path, "loading")
                audio = AudioLoader.load(file_path)

                # 2. Check disk cache
                segments = self._try_load_cache(file_path)

                # 3. Transcribe if no cache
                if segments is None:
                    self.file_status.emit(file_path, "transcribing")
                    if (self._transcriber is None
                            or self._transcriber_model != model_size):
                        self._transcriber = Transcriber(model_size)
                        self._transcriber.load_model()
                        self._transcriber_model = model_size
                    segments = self._transcriber.transcribe(
                        file_path, language, min_silence_ms, vad_threshold
                    )
                    self._save_cache(file_path, segments)

                # 4. Store results for main thread
                self.audio_results[file_path] = audio
                self.segment_results[file_path] = segments
                self.file_ready.emit(file_path)

            except Exception as exc:
                self.file_failed.emit(file_path, str(exc))

    # ------------------------------------------------------------------
    @staticmethod
    def _try_load_cache(file_path: str) -> Optional[list]:
        cache_path = file_path + ".segments.json"
        if not os.path.exists(cache_path):
            return None
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [
                Segment(id=i, start=d["start"], end=d["end"], text=d["text"])
                for i, d in enumerate(data)
            ]
        except Exception:
            return None

    @staticmethod
    def _save_cache(file_path: str, segments: list):
        try:
            cache_path = file_path + ".segments.json"
            data = [{"start": s.start, "end": s.end, "text": s.text}
                    for s in segments]
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Dark theme stylesheet (Catppuccin Mocha inspired)
# ---------------------------------------------------------------------------
STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-size: 13px;
}
QListWidget {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 4px;
    outline: none;
}
QListWidget::item { padding: 6px 8px; border-radius: 4px; }
QListWidget::item:selected { background-color: #313244; color: #cdd6f4; }
QListWidget::item:hover:!selected { background-color: #252535; }
QTableWidget {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    gridline-color: #2a2a3e;
    outline: none;
}
QTableWidget::item { padding: 4px 6px; }
QTableWidget::item:selected { background-color: #313244; color: #cdd6f4; }
QHeaderView::section {
    background-color: #1e1e2e;
    color: #a6adc8;
    border: none;
    border-right: 1px solid #313244;
    border-bottom: 1px solid #313244;
    padding: 5px 6px;
    font-weight: bold;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    padding: 6px 14px;
    border-radius: 5px;
}
QPushButton:hover { background-color: #45475a; }
QPushButton:pressed { background-color: #585b70; }
QPushButton:disabled { background-color: #1e1e2e; color: #585b70; border-color: #313244; }
QPushButton#add_btn { background-color: #a6e3a1; color: #1e1e2e; font-weight: bold; }
QPushButton#add_btn:hover { background-color: #94d3a2; }
QPushButton#merge_btn { background-color: #cba6f7; color: #1e1e2e; font-weight: bold; }
QPushButton#merge_btn:hover { background-color: #b4befe; }
QPushButton#export_btn { background-color: #89b4fa; color: #1e1e2e; font-weight: bold; }
QPushButton#export_btn:hover { background-color: #74c7ec; }
QPushButton#play_seg_btn {
    background-color: #a6e3a1;
    color: #1e1e2e;
    font-weight: bold;
    padding: 2px 6px;
    border-radius: 3px;
    border: none;
}
QPushButton#play_seg_btn:hover { background-color: #94d3a2; }
QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    padding: 4px 8px;
    border-radius: 5px;
    min-width: 70px;
}
QComboBox::drop-down { border: none; width: 16px; }
QComboBox QAbstractItemView {
    background-color: #313244;
    color: #cdd6f4;
    selection-background-color: #45475a;
    border: 1px solid #45475a;
}
QLabel { color: #cdd6f4; }
QLabel#section_label { color: #89b4fa; font-weight: bold; padding: 2px 0; }
QProgressBar {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk { background-color: #89b4fa; border-radius: 4px; }
QSplitter::handle { background-color: #313244; }
QStatusBar { background-color: #181825; color: #a6adc8; border-top: 1px solid #313244; }
QScrollBar:vertical { background: #181825; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #45475a; border-radius: 4px; min-height: 20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #181825; height: 8px; margin: 0; }
QScrollBar::handle:horizontal { background: #45475a; border-radius: 4px; min-width: 20px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; border: 1px solid #45475a; background: #313244; }
QCheckBox::indicator:checked { background: #89b4fa; border-color: #89b4fa; }
"""


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI 音檔分割工具")
        self.setMinimumSize(1100, 750)
        self.resize(1400, 900)

        # --- Application state ---
        self.file_paths: list = []
        self.current_file: Optional[str] = None
        self.audio_cache: dict = {}       # path -> PydubAudio
        self.segments_cache: dict = {}    # path -> list[Segment]
        self.current_segments: list = []
        self.selected_row: int = -1
        self._updating_table: bool = False
        self.file_status_map: dict = {}   # path -> status string
        # cross-file selection: file_path -> set of segment indices
        self.cross_file_selection: dict = {}

        # --- Queue worker (single persistent background thread) ---
        self.queue_worker = QueueWorker()
        self.queue_thread = QThread()
        self.queue_worker.moveToThread(self.queue_thread)
        self.queue_thread.started.connect(self.queue_worker.run)
        self.queue_worker.file_status.connect(self._on_file_status)
        self.queue_worker.file_ready.connect(self._on_file_ready)
        self.queue_worker.file_failed.connect(self._on_file_failed)
        self.queue_thread.start()

        # --- Audio playback (sounddevice) ---
        # numpy_cache stores (samples, sample_rate) per file to avoid re-converting
        self.numpy_cache: dict = {}
        self._play_start_wall: float = 0.0   # monotonic time when play() was called
        self._play_start_pos: float = 0.0    # audio offset at play start (seconds)
        self._play_duration: float = 0.0     # length of queued playback (seconds)

        self.position_timer = QTimer()
        self.position_timer.setInterval(80)
        self.position_timer.timeout.connect(self._update_playback_position)

        self._setup_ui()
        self.setStyleSheet(STYLESHEET)
        self._init_ffmpeg()

    # -----------------------------------------------------------------------
    # UI Layout
    # -----------------------------------------------------------------------
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # === Left panel: file list ===
        left_panel = QWidget()
        left_panel.setFixedWidth(220)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        lbl = QLabel("Audio List")
        lbl.setObjectName("section_label")
        left_layout.addWidget(lbl)

        self.file_list_widget = QListWidget()
        self.file_list_widget.currentItemChanged.connect(self._on_file_selected)
        left_layout.addWidget(self.file_list_widget)

        add_btn = QPushButton("＋ 匯入音檔")
        add_btn.setObjectName("add_btn")
        add_btn.clicked.connect(self.add_files)
        left_layout.addWidget(add_btn)

        remove_btn = QPushButton("移除選取")
        remove_btn.clicked.connect(self.remove_file)
        left_layout.addWidget(remove_btn)

        self.ffmpeg_btn = QPushButton("⚙ 設定 ffmpeg")
        self.ffmpeg_btn.clicked.connect(self._set_ffmpeg_path)
        self.ffmpeg_btn.setToolTip("手動指定 ffmpeg.exe 路徑（找不到 ffmpeg 時使用）")
        left_layout.addWidget(self.ffmpeg_btn)

        self.ffmpeg_status = QLabel("ffmpeg: 偵測中…")
        self.ffmpeg_status.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.ffmpeg_status.setWordWrap(True)
        left_layout.addWidget(self.ffmpeg_status)

        main_layout.addWidget(left_panel)

        # === Right panel ===
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top: waveform
        self.waveform = WaveformWidget()
        self.waveform.setFixedHeight(170)
        self.waveform.region_changed.connect(self._on_waveform_region_changed)
        right_splitter.addWidget(self.waveform)

        # Bottom: controls + table + action bar
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 4, 0, 0)
        bottom_layout.setSpacing(6)

        controls = self._build_controls_bar()
        bottom_layout.addWidget(controls)

        vad_bar = self._build_vad_bar()
        bottom_layout.addWidget(vad_bar)

        self._build_segment_table()
        bottom_layout.addWidget(self.table)

        action_bar = self._build_action_bar()
        bottom_layout.addWidget(action_bar)

        right_splitter.addWidget(bottom_widget)
        right_splitter.setSizes([170, 600])

        main_layout.addWidget(right_splitter, 1)

        self.statusBar().showMessage("就緒 — 請匯入音檔")

    def _build_controls_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.play_all_btn = QPushButton("▶ 播放全部")
        self.play_all_btn.setEnabled(False)
        self.play_all_btn.clicked.connect(self.play_all)
        layout.addWidget(self.play_all_btn)

        self.play_region_btn = QPushButton("▶ 播放區域")
        self.play_region_btn.setEnabled(False)
        self.play_region_btn.clicked.connect(self.play_region)
        self.play_region_btn.setToolTip("播放波形上紫色選取區域的音訊（空白鍵）")
        layout.addWidget(self.play_region_btn)

        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_playback)
        layout.addWidget(self.stop_btn)

        layout.addWidget(_sep())

        layout.addWidget(QLabel("模型："))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny", "base", "small", "medium"])
        self.model_combo.setCurrentText("small")
        layout.addWidget(self.model_combo)

        layout.addWidget(QLabel("語言："))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("自動偵測", None)
        self.lang_combo.addItem("中文", "zh")
        self.lang_combo.addItem("台語", "nan")
        self.lang_combo.addItem("英文", "en")
        self.lang_combo.addItem("日文", "ja")
        self.lang_combo.addItem("韓文", "ko")
        layout.addWidget(self.lang_combo)

        self.transcribe_btn = QPushButton("🎙 重新辨識")
        self.transcribe_btn.setEnabled(False)
        self.transcribe_btn.clicked.connect(self.retranscribe_current)
        layout.addWidget(self.transcribe_btn)

        layout.addStretch()

        # Queue progress indicator
        self.queue_label = QLabel("")
        self.queue_label.setStyleSheet("color: #fab387; font-size: 12px;")
        layout.addWidget(self.queue_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedWidth(120)
        layout.addWidget(self.progress_bar)

        return bar

    def _build_vad_bar(self) -> QWidget:
        """Second toolbar row: VAD segmentation parameters + re-analyze button."""
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(QLabel("分段參數："))

        layout.addWidget(QLabel("靜音長度"))
        self.silence_spin = QSpinBox()
        self.silence_spin.setRange(100, 3000)
        self.silence_spin.setSingleStep(50)
        self.silence_spin.setValue(500)
        self.silence_spin.setSuffix(" ms")
        self.silence_spin.setFixedWidth(90)
        self.silence_spin.setToolTip(
            "兩句之間的靜音至少要多長才算是一個分割點。\n"
            "數值越大 → 分段越少（句子較長）\n"
            "數值越小 → 分段越多（句子較短）"
        )
        layout.addWidget(self.silence_spin)

        layout.addWidget(QLabel("靈敏度"))
        self.vad_spin = QDoubleSpinBox()
        self.vad_spin.setRange(0.1, 0.95)
        self.vad_spin.setSingleStep(0.05)
        self.vad_spin.setValue(0.5)
        self.vad_spin.setDecimals(2)
        self.vad_spin.setFixedWidth(70)
        self.vad_spin.setToolTip(
            "VAD 偵測語音的門檻值（0.1 ~ 0.95）。\n"
            "數值越高 → 更嚴格，只有很確定是語音才算\n"
            "數值越低 → 更寬鬆，較小的聲音也會被視為語音"
        )
        layout.addWidget(self.vad_spin)

        self.reanalyze_btn = QPushButton("🔄 重新分析")
        self.reanalyze_btn.setEnabled(False)
        self.reanalyze_btn.setToolTip("以目前的分段參數重新切割當前音檔（不重新下載模型）")
        self.reanalyze_btn.clicked.connect(self.reanalyze_current)
        layout.addWidget(self.reanalyze_btn)

        layout.addStretch()

        # Parameter hint label
        hint = QLabel("調整後點「重新分析」套用")
        hint.setStyleSheet("color: #6c7086; font-size: 11px;")
        layout.addWidget(hint)

        return bar

    def _build_segment_table(self):
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["☑", "▶", "#", "開始", "結束", "長度", "文字"]
        )

        hh = self.table.horizontalHeader()
        for col in range(6):
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        self.table.setColumnWidth(0, 36)
        self.table.setColumnWidth(1, 40)
        self.table.setColumnWidth(2, 38)
        self.table.setColumnWidth(3, 75)
        self.table.setColumnWidth(4, 75)
        self.table.setColumnWidth(5, 65)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.table.verticalHeader().hide()

        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.table.itemChanged.connect(self._on_table_item_changed)

    def _build_action_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        select_all_btn = QPushButton("全選")
        select_all_btn.clicked.connect(self.select_all)
        layout.addWidget(select_all_btn)

        clear_sel_btn = QPushButton("清除所有選取")
        clear_sel_btn.clicked.connect(self.clear_all_selection)
        clear_sel_btn.setToolTip("清除所有音檔的勾選（包含其他音檔）")
        layout.addWidget(clear_sel_btn)

        layout.addWidget(_sep())

        self.selection_label = QLabel("")
        self.selection_label.setStyleSheet("color: #cba6f7; font-size: 12px;")
        layout.addWidget(self.selection_label)

        layout.addWidget(_sep())

        self.merge_btn = QPushButton("合併選取")
        self.merge_btn.setObjectName("merge_btn")
        self.merge_btn.clicked.connect(self.merge_selected)
        layout.addWidget(self.merge_btn)

        self.split_btn = QPushButton("在波形處分割")
        self.split_btn.clicked.connect(self.split_at_region)
        layout.addWidget(self.split_btn)

        self.add_seg_btn = QPushButton("＋ 新增段落")
        self.add_seg_btn.setObjectName("add_btn")
        self.add_seg_btn.setToolTip("以波形上紫色選取區域新增一個段落（自動依時間排序）")
        self.add_seg_btn.clicked.connect(self.add_segment_from_region)
        layout.addWidget(self.add_seg_btn)

        layout.addStretch()

        self.export_sel_btn = QPushButton("匯出選取")
        self.export_sel_btn.clicked.connect(self.export_selected)
        layout.addWidget(self.export_sel_btn)

        self.export_all_btn = QPushButton("匯出全部")
        self.export_all_btn.setObjectName("export_btn")
        self.export_all_btn.clicked.connect(self.export_all)
        layout.addWidget(self.export_all_btn)

        self.export_ts_btn = QPushButton("匯出時間戳 TXT")
        self.export_ts_btn.clicked.connect(self.export_timestamps)
        self.export_ts_btn.setToolTip("將當前音檔所有片段的開始/結束秒數匯出為 timestamps.txt")
        layout.addWidget(self.export_ts_btn)

        layout.addWidget(_sep())

        layout.addWidget(QLabel("格式："))
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["mp3", "wav", "m4a"])   # mp3 is default
        layout.addWidget(self.fmt_combo)

        layout.addWidget(QLabel("位元率："))
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.addItems(["128k", "192k", "256k", "320k"])
        self.bitrate_combo.setCurrentText("192k")
        self.bitrate_combo.setFixedWidth(65)
        self.bitrate_combo.setToolTip("MP3 輸出位元率（僅對 mp3 格式有效）")
        layout.addWidget(self.bitrate_combo)

        layout.addWidget(_sep())

        layout.addWidget(QLabel("前置靜音："))
        self.pad_before_spin = QDoubleSpinBox()
        self.pad_before_spin.setRange(0.0, 10.0)
        self.pad_before_spin.setSingleStep(0.1)
        self.pad_before_spin.setValue(0.3)
        self.pad_before_spin.setDecimals(1)
        self.pad_before_spin.setSuffix(" s")
        self.pad_before_spin.setFixedWidth(72)
        self.pad_before_spin.setToolTip("每段音檔開頭加入的靜音長度（秒）")
        layout.addWidget(self.pad_before_spin)

        layout.addWidget(QLabel("後置靜音："))
        self.pad_after_spin = QDoubleSpinBox()
        self.pad_after_spin.setRange(0.0, 10.0)
        self.pad_after_spin.setSingleStep(0.1)
        self.pad_after_spin.setValue(0.3)
        self.pad_after_spin.setDecimals(1)
        self.pad_after_spin.setSuffix(" s")
        self.pad_after_spin.setFixedWidth(72)
        self.pad_after_spin.setToolTip("每段音檔結尾加入的靜音長度（秒）")
        layout.addWidget(self.pad_after_spin)

        return bar

    # -----------------------------------------------------------------------
    # File management
    # -----------------------------------------------------------------------
    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "選擇音檔",
            "",
            "音檔 (*.mp3 *.wav *.m4a *.flac *.ogg);;所有檔案 (*.*)",
        )
        for path in files:
            if path not in self.file_paths:
                self.file_paths.append(path)
                self.file_status_map[path] = "queued"

                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, path)
                item.setToolTip(path)
                self.file_list_widget.addItem(item)
                self._update_file_item(path, "queued")

                # Immediately enqueue for background processing
                self.queue_worker.enqueue(
                    path,
                    self.model_combo.currentText(),
                    self.lang_combo.currentData(),
                    self.silence_spin.value(),
                    self.vad_spin.value(),
                )
        self._update_queue_label()

    def remove_file(self):
        row = self.file_list_widget.currentRow()
        if row < 0:
            return
        item = self.file_list_widget.takeItem(row)
        path = item.data(Qt.ItemDataRole.UserRole)
        if path in self.file_paths:
            self.file_paths.remove(path)
        self.audio_cache.pop(path, None)
        self.segments_cache.pop(path, None)
        self.file_status_map.pop(path, None)
        self.cross_file_selection.pop(path, None)
        if self.current_file == path:
            self.current_file = None
            self.current_segments = []
            self._refresh_table()
            self.waveform.clear()
            self.play_all_btn.setEnabled(False)
            self.play_region_btn.setEnabled(False)
            self.transcribe_btn.setEnabled(False)
            self.reanalyze_btn.setEnabled(False)
        self._update_queue_label()

    # -----------------------------------------------------------------------
    # Queue worker slots
    # -----------------------------------------------------------------------
    @Slot(str, str)
    def _on_file_status(self, path: str, status: str):
        self.file_status_map[path] = status
        self._update_file_item(path, status)
        name = os.path.basename(path)
        if status == "loading":
            self.queue_label.setText(f"載入: {name}")
            self.progress_bar.setVisible(True)
        elif status == "transcribing":
            self.queue_label.setText(f"辨識: {name}")

    @Slot(str)
    def _on_file_ready(self, path: str):
        # Pull results out of the worker into main-thread caches
        audio = self.queue_worker.audio_results.pop(path, None)
        segments = self.queue_worker.segment_results.pop(path, None)
        if audio is not None:
            self.audio_cache[path] = audio
        if segments is not None:
            self.segments_cache[path] = segments

        self.file_status_map[path] = "ready"
        self._update_file_item(path, "ready")
        self._update_queue_label()

        name = os.path.basename(path)
        n = len(segments) if segments else 0
        self.statusBar().showMessage(f"✓ {name}  —  {n} 段，可以選取")

        # If the user already clicked this file while it was processing,
        # display it now that it's ready.
        if path == self.current_file:
            self._display_file(path)

    @Slot(str, str)
    def _on_file_failed(self, path: str, error: str):
        self.file_status_map[path] = "error"
        self._update_file_item(path, "error")
        self._update_queue_label()
        self.statusBar().showMessage(f"✗ {os.path.basename(path)}: 處理失敗")

        if is_winerror2(Exception(error)):
            QMessageBox.critical(
                self, "找不到 ffmpeg",
                f"處理 {os.path.basename(path)} 時發生錯誤:\n\n{FFMPEG_HELP}",
            )
        # Don't show a popup for every error unless the user is looking at this file
        elif path == self.current_file:
            QMessageBox.critical(self, "處理失敗",
                                 f"{os.path.basename(path)}\n\n{error}")

    # -----------------------------------------------------------------------
    # File display (called only when status == "ready")
    # -----------------------------------------------------------------------
    def _on_file_selected(self, current, previous):
        if current is None:
            return
        path = current.data(Qt.ItemDataRole.UserRole)
        if path == self.current_file:
            return
        self.current_file = path
        status = self.file_status_map.get(path, "queued")

        if status != "ready":
            labels = {
                "queued":       "排隊等待處理中…",
                "loading":      "音檔載入中，請稍候…",
                "transcribing": "語音辨識中，請稍候…",
                "error":        "處理失敗，可點「重新辨識」重試",
            }
            self.statusBar().showMessage(
                f"{os.path.basename(path)}  —  {labels.get(status, status)}"
            )
            # Clear display without loading anything
            self.current_segments = []
            self._refresh_table()
            self.waveform.clear()
            self.play_all_btn.setEnabled(False)
            self.play_region_btn.setEnabled(False)
            self.transcribe_btn.setEnabled(status == "error")
            self.reanalyze_btn.setEnabled(status == "error")
            return

        self._display_file(path)

    def _display_file(self, path: str):
        """Render a fully-processed file. Always safe to call — no I/O."""
        audio = self.audio_cache.get(path)
        segments = self.segments_cache.get(path, [])
        if audio is None:
            return

        # Build / reuse numpy cache so playback has instant access
        if path not in self.numpy_cache:
            self.numpy_cache[path] = AudioLoader.to_numpy(audio)
        samples, sr = self.numpy_cache[path]
        self.waveform.set_audio(samples, sr)

        self.current_segments = list(segments)
        self._refresh_table()
        self.waveform.set_segments(self.current_segments)
        self.play_all_btn.setEnabled(True)
        self.play_region_btn.setEnabled(True)
        self.transcribe_btn.setEnabled(True)
        self.reanalyze_btn.setEnabled(True)

        count = len(self.cross_file_selection.get(path, set()))
        sel_str = f"，已勾選 {count} 句" if count > 0 else ""
        self.statusBar().showMessage(
            f"{os.path.basename(path)}  —  {len(self.current_segments)} 段{sel_str}"
        )

    # -----------------------------------------------------------------------
    # Re-transcription (user-triggered)
    # -----------------------------------------------------------------------
    def retranscribe_current(self):
        if not self.current_file:
            return
        path = self.current_file

        # Clear caches so worker re-runs transcription
        cache_path = path + ".segments.json"
        try:
            if os.path.exists(cache_path):
                os.remove(cache_path)
        except Exception:
            pass
        self.audio_cache.pop(path, None)
        self.segments_cache.pop(path, None)
        self.queue_worker.audio_results.pop(path, None)
        self.queue_worker.segment_results.pop(path, None)

        self.file_status_map[path] = "queued"
        self._update_file_item(path, "queued")
        self.current_segments = []
        self._refresh_table()
        self.waveform.clear()
        self.play_all_btn.setEnabled(False)
        self.play_region_btn.setEnabled(False)

        self.queue_worker.enqueue(
            path,
            self.model_combo.currentText(),
            self.lang_combo.currentData(),
            self.silence_spin.value(),
            self.vad_spin.value(),
        )
        self._update_queue_label()

    def reanalyze_current(self):
        """Re-segment current file with updated VAD parameters (skip model reload)."""
        if not self.current_file:
            return
        path = self.current_file

        # Delete only the segments cache — keep audio in memory (no reload needed)
        cache_path = path + ".segments.json"
        try:
            if os.path.exists(cache_path):
                os.remove(cache_path)
        except Exception:
            pass
        self.segments_cache.pop(path, None)
        self.queue_worker.segment_results.pop(path, None)

        # Audio is still in audio_cache — worker will skip re-loading
        # BUT QueueWorker always loads audio first, so we clear it too
        # and let it use the in-memory audio_results path
        # Simplest: just clear everything and re-enqueue (audio load is fast from cache)
        self.audio_cache.pop(path, None)
        self.numpy_cache.pop(path, None)
        self.queue_worker.audio_results.pop(path, None)

        self.file_status_map[path] = "queued"
        self._update_file_item(path, "queued")
        self.current_segments = []
        self._refresh_table()
        self.waveform.clear()
        self.play_all_btn.setEnabled(False)
        self.play_region_btn.setEnabled(False)
        self.reanalyze_btn.setEnabled(False)

        # Use current VAD params, keep same model and language
        self.queue_worker.enqueue(
            path,
            self.model_combo.currentText(),
            self.lang_combo.currentData(),
            self.silence_spin.value(),
            self.vad_spin.value(),
        )
        self._update_queue_label()

    # -----------------------------------------------------------------------
    # File list display helpers
    # -----------------------------------------------------------------------
    def _update_file_item(self, path: str, status: str):
        prefix, color = STATUS_DISPLAY.get(status, ("", "#cdd6f4"))
        base = os.path.basename(path)
        count = len(self.cross_file_selection.get(path, set()))
        count_str = f"  [{count}]" if count > 0 else ""

        for i in range(self.file_list_widget.count()):
            item = self.file_list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                item.setText(f"{prefix} {base}{count_str}")
                item.setForeground(QColor(color))
                break

    def _update_queue_label(self):
        pending = sum(
            1 for s in self.file_status_map.values()
            if s in ("queued", "loading", "transcribing")
        )
        if pending == 0:
            self.queue_label.setText("")
            self.progress_bar.setVisible(False)
        else:
            self.queue_label.setText(f"佇列：{pending} 個檔案待處理")
            self.progress_bar.setVisible(True)

    # -----------------------------------------------------------------------
    # Segment table
    # -----------------------------------------------------------------------
    def _refresh_table(self):
        self._updating_table = True
        self.table.setRowCount(0)

        for i, seg in enumerate(self.current_segments):
            self.table.insertRow(i)

            # Col 0: checkbox — restore cross-file selection state
            cb = QCheckBox()
            checked_indices = self.cross_file_selection.get(self.current_file, set())
            if i in checked_indices:
                cb.setChecked(True)
            cb.stateChanged.connect(
                lambda state, idx=i: self._on_checkbox_changed(idx, state)
            )
            cb_container = QWidget()
            cb_layout = QHBoxLayout(cb_container)
            cb_layout.addWidget(cb)
            cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(i, 0, cb_container)

            # Col 1: play button
            play_btn = QPushButton("▶")
            play_btn.setObjectName("play_seg_btn")
            play_btn.setFixedWidth(36)
            play_btn.clicked.connect(lambda _c, idx=i: self.play_segment(idx))
            self.table.setCellWidget(i, 1, play_btn)

            # Col 2: index
            idx_item = QTableWidgetItem(str(i + 1))
            idx_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            idx_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 2, idx_item)

            # Col 3: start
            start_item = QTableWidgetItem(format_seconds(seg.start))
            start_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 3, start_item)

            # Col 4: end
            end_item = QTableWidgetItem(format_seconds(seg.end))
            end_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 4, end_item)

            # Col 5: duration
            dur_item = QTableWidgetItem(f"{format_seconds(seg.end - seg.start)}s")
            dur_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 5, dur_item)

            # Col 6: text
            text_item = QTableWidgetItem(seg.text)
            self.table.setItem(i, 6, text_item)

            self.table.setRowHeight(i, 36)

        self._updating_table = False

    def _on_table_selection_changed(self):
        if self._updating_table:
            return
        row = self.table.currentRow()
        if 0 <= row < len(self.current_segments):
            self.selected_row = row
            seg = self.current_segments[row]
            self.waveform.set_region(seg.start, seg.end)

    def _on_table_item_changed(self, item):
        if self._updating_table:
            return
        row = item.row()
        col = item.column()
        if not (0 <= row < len(self.current_segments)):
            return
        seg = self.current_segments[row]

        if col == 3:
            try:
                seg.start = float(item.text())
                self._update_dur_cell(row, seg)
                self.waveform.set_region(seg.start, seg.end)
                self._persist_changes()
            except ValueError:
                pass
        elif col == 4:
            try:
                seg.end = float(item.text())
                self._update_dur_cell(row, seg)
                self.waveform.set_region(seg.start, seg.end)
                self._persist_changes()
            except ValueError:
                pass
        elif col == 6:
            seg.text = item.text()
            self._persist_changes()

    def _update_dur_cell(self, row: int, seg):
        self._updating_table = True
        dur_item = self.table.item(row, 5)
        if dur_item:
            dur_item.setText(f"{format_seconds(seg.end - seg.start)}s")
        self._updating_table = False

    # -----------------------------------------------------------------------
    # Waveform → table sync
    # -----------------------------------------------------------------------
    def _on_waveform_region_changed(self, start: float, end: float):
        if self.selected_row < 0 or self.selected_row >= len(self.current_segments):
            return
        seg = self.current_segments[self.selected_row]
        seg.start = round(start, 3)
        seg.end = round(end, 3)

        self._updating_table = True
        for col, val in [
            (3, format_seconds(seg.start)),
            (4, format_seconds(seg.end)),
            (5, f"{format_seconds(seg.end - seg.start)}s"),
        ]:
            item = self.table.item(self.selected_row, col)
            if item:
                item.setText(val)
        self._updating_table = False
        self._persist_changes()

    # -----------------------------------------------------------------------
    # Playback  (sounddevice — plays numpy arrays directly, no temp files)
    # -----------------------------------------------------------------------
    def _sd_play(self, samples: np.ndarray, sr: int,
                 audio_start_pos: float, duration: float):
        """Start sounddevice playback and arm the position timer."""
        sd.stop()
        sd.play(samples, sr)
        self._play_start_wall = time.monotonic()
        self._play_start_pos = audio_start_pos
        self._play_duration = duration
        self.position_timer.start()
        self.stop_btn.setEnabled(True)

    def play_segment(self, idx: int):
        if not self.current_file or idx >= len(self.current_segments):
            return
        samples_full, sr = self.numpy_cache.get(self.current_file, (None, None))
        if samples_full is None:
            return
        seg = self.current_segments[idx]
        start_f = int(seg.start * sr)
        end_f   = int(seg.end   * sr)
        chunk = np.ascontiguousarray(samples_full[start_f:end_f])
        self._sd_play(chunk, sr, seg.start, seg.end - seg.start)
        self.play_all_btn.setEnabled(False)
        self.play_region_btn.setEnabled(False)
        self.table.selectRow(idx)

    def play_all(self):
        samples, sr = self.numpy_cache.get(self.current_file, (None, None))
        if samples is None:
            return
        duration = len(samples) / sr
        self._sd_play(np.ascontiguousarray(samples), sr, 0.0, duration)
        self.play_all_btn.setEnabled(False)
        self.play_region_btn.setEnabled(False)

    def stop_playback(self):
        sd.stop()
        self.position_timer.stop()
        self.waveform.set_playback_position(0)
        self.stop_btn.setEnabled(False)
        if self.current_file:
            self.play_all_btn.setEnabled(True)
            self.play_region_btn.setEnabled(True)

    def play_region(self):
        """Play whatever region is currently shown on the waveform.

        Clears table selection first so dragging the region does not
        accidentally modify any segment's start/end times.
        """
        if not self.current_file:
            return
        samples_full, sr = self.numpy_cache.get(self.current_file, (None, None))
        if samples_full is None:
            return
        # Deselect table row so region drag is free from segment editing
        self.table.clearSelection()
        self.selected_row = -1
        r_start, r_end = self.waveform.region.getRegion()
        r_start = max(0.0, r_start)
        r_end = min(len(samples_full) / sr, r_end)
        if r_end <= r_start:
            return
        start_f = int(r_start * sr)
        end_f   = int(r_end   * sr)
        chunk = np.ascontiguousarray(samples_full[start_f:end_f])
        self._sd_play(chunk, sr, r_start, r_end - r_start)
        self.play_all_btn.setEnabled(False)
        self.play_region_btn.setEnabled(False)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            if self.stop_btn.isEnabled():
                self.stop_playback()
            elif self.play_region_btn.isEnabled():
                self.play_region()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _update_playback_position(self):
        elapsed = time.monotonic() - self._play_start_wall
        if elapsed >= self._play_duration:
            # Playback finished naturally
            self.position_timer.stop()
            self.waveform.set_playback_position(0)
            self.stop_btn.setEnabled(False)
            if self.current_file:
                self.play_all_btn.setEnabled(True)
                self.play_region_btn.setEnabled(True)
            return
        self.waveform.set_playback_position(self._play_start_pos + elapsed)

    # -----------------------------------------------------------------------
    # Cross-file selection
    # -----------------------------------------------------------------------
    def _get_checked_rows(self) -> list:
        checked = []
        for row in range(self.table.rowCount()):
            container = self.table.cellWidget(row, 0)
            if container:
                cb = container.findChild(QCheckBox)
                if cb and cb.isChecked():
                    checked.append(row)
        return checked

    def select_all(self):
        for row in range(self.table.rowCount()):
            container = self.table.cellWidget(row, 0)
            if container:
                cb = container.findChild(QCheckBox)
                if cb:
                    cb.setChecked(True)

    def deselect_all(self):
        for row in range(self.table.rowCount()):
            container = self.table.cellWidget(row, 0)
            if container:
                cb = container.findChild(QCheckBox)
                if cb:
                    cb.setChecked(False)

    def clear_all_selection(self):
        self.cross_file_selection.clear()
        self._updating_table = True
        for row in range(self.table.rowCount()):
            container = self.table.cellWidget(row, 0)
            if container:
                cb = container.findChild(QCheckBox)
                if cb:
                    cb.setChecked(False)
        self._updating_table = False
        self._update_selection_label()
        self._update_file_list_indicators()

    def _on_checkbox_changed(self, segment_idx: int, state: int):
        if self._updating_table or not self.current_file:
            return
        self.cross_file_selection.setdefault(self.current_file, set())
        if state == 2:  # Qt.CheckState.Checked
            self.cross_file_selection[self.current_file].add(segment_idx)
        else:
            self.cross_file_selection[self.current_file].discard(segment_idx)
        self._update_selection_label()
        self._update_file_list_indicators()

    def _get_all_selected_segments(self) -> list:
        result = []
        for i in range(self.file_list_widget.count()):
            path = self.file_list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            indices = self.cross_file_selection.get(path, set())
            if not indices:
                continue
            segments = self.segments_cache.get(path, [])
            for idx in sorted(indices):
                if idx < len(segments):
                    result.append((path, segments[idx]))
        return result

    def _update_selection_label(self):
        total = sum(len(v) for v in self.cross_file_selection.values())
        files_with_sel = sum(1 for v in self.cross_file_selection.values() if v)
        if total == 0:
            self.selection_label.setText("")
        elif files_with_sel > 1:
            self.selection_label.setText(
                f"已選取 {total} 句（跨 {files_with_sel} 個音檔）"
            )
        else:
            self.selection_label.setText(f"已選取 {total} 句")

    def _update_file_list_indicators(self):
        for path in self.file_paths:
            status = self.file_status_map.get(path, "queued")
            self._update_file_item(path, status)

    # -----------------------------------------------------------------------
    # Segment operations
    # -----------------------------------------------------------------------
    def merge_selected(self):
        rows = sorted(self._get_checked_rows())
        if len(rows) < 2:
            QMessageBox.information(self, "提示", "請至少勾選兩個句子進行合併。")
            return

        # Require consecutive rows
        for i in range(len(rows) - 1):
            if rows[i + 1] != rows[i] + 1:
                QMessageBox.warning(
                    self, "無法合併",
                    f"只能合併相鄰的句子。\n\n"
                    f"第 {rows[i] + 1} 句與第 {rows[i + 1] + 1} 句之間還有其他句子，"
                    f"請重新勾選連續的句子後再合併。",
                )
                return

        first_seg = self.current_segments[rows[0]]
        last_seg  = self.current_segments[rows[-1]]
        merged_text = " ".join(self.current_segments[r].text for r in rows)

        merged = Segment(
            id=rows[0],
            start=first_seg.start,
            end=last_seg.end,
            text=merged_text,
        )
        for row in reversed(rows):
            self.current_segments.pop(row)
        self.current_segments.insert(rows[0], merged)
        self._reindex()
        self._clear_current_file_selection()
        self._persist_changes()
        self._refresh_table()
        self.waveform.set_segments(self.current_segments)
        self.table.selectRow(rows[0])

    def add_segment_from_region(self):
        """Insert a new segment at the current waveform region, keeping the
        list sorted by start time."""
        if not self.current_file:
            QMessageBox.information(self, "提示", "請先選擇音檔。")
            return

        r_start, r_end = self.waveform.region.getRegion()
        r_start = round(max(0.0, r_start), 3)
        r_end = round(min(self.waveform.duration or r_end, r_end), 3)
        if r_end <= r_start:
            QMessageBox.information(
                self, "提示",
                "請先在波形上拖曳出一個有效的選取區域（起點需小於終點）。",
            )
            return

        new_seg = Segment(id=0, start=r_start, end=r_end, text="")

        # Insert and re-sort by start time
        self.current_segments.append(new_seg)
        self.current_segments.sort(key=lambda s: (s.start, s.end))
        new_row = self.current_segments.index(new_seg)

        # Shift cross-file selection indices that are >= new_row
        existing = self.cross_file_selection.get(self.current_file, set())
        if existing:
            self.cross_file_selection[self.current_file] = {
                (idx + 1 if idx >= new_row else idx) for idx in existing
            }

        self._reindex()
        self._persist_changes()
        self._refresh_table()
        self.waveform.set_segments(self.current_segments)
        self.table.selectRow(new_row)

    def split_at_region(self):
        if self.selected_row < 0 or self.selected_row >= len(self.current_segments):
            QMessageBox.information(self, "提示", "請先在句子列表中選取一個句子。")
            return

        seg = self.current_segments[self.selected_row]
        r_start, r_end = self.waveform.region.getRegion()
        split_point = round((r_start + r_end) / 2, 3)

        if split_point <= seg.start or split_point >= seg.end:
            QMessageBox.information(
                self, "提示",
                f"分割點 {split_point:.3f}s 必須在選取句子範圍內\n"
                f"({seg.start:.3f}s ~ {seg.end:.3f}s)。",
            )
            return

        seg1 = Segment(id=self.selected_row,
                       start=seg.start, end=split_point, text=seg.text)
        seg2 = Segment(id=self.selected_row + 1,
                       start=split_point, end=seg.end, text="")
        self.current_segments[self.selected_row] = seg1
        self.current_segments.insert(self.selected_row + 1, seg2)
        self._reindex()
        self._clear_current_file_selection()
        self._persist_changes()
        self._refresh_table()
        self.waveform.set_segments(self.current_segments)
        self.table.selectRow(self.selected_row)

    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------
    def export_selected(self):
        selected = self._get_all_selected_segments()
        if not selected:
            QMessageBox.information(self, "提示", "請勾選要匯出的句子（可跨音檔）。")
            return

        output_dir = QFileDialog.getExistingDirectory(self, "選擇輸出資料夾")
        if not output_dir:
            return

        fmt = self.fmt_combo.currentText()
        all_results = []
        try:
            by_file: dict = {}
            for path, seg in selected:
                by_file.setdefault(path, []).append(seg)

            for path, segs in by_file.items():
                audio = self.audio_cache.get(path)
                if audio is None:
                    audio = AudioLoader.load(path)
                    self.audio_cache[path] = audio
                results = Exporter.export_segments(
                    audio, segs, output_dir, fmt,
                    pad_before=self.pad_before_spin.value(),
                    pad_after=self.pad_after_spin.value(),
                    bitrate=self.bitrate_combo.currentText(),
                )
                all_results.extend(results)

            Exporter.export_json(all_results, output_dir)
            Exporter.export_timestamps_txt(all_results, output_dir)
            fc = len(by_file)
            detail = f"（來自 {fc} 個音檔）" if fc > 1 else ""
            QMessageBox.information(
                self, "匯出完成",
                f"成功匯出 {len(all_results)} 個音檔{detail}\n輸出位置：{output_dir}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "匯出錯誤", f"匯出失敗:\n{exc}")

    def export_all(self):
        if not self.current_file or not self.current_segments:
            QMessageBox.information(self, "提示", "沒有句子可以匯出。")
            return
        audio = self.audio_cache.get(self.current_file)
        if not audio:
            return

        output_dir = QFileDialog.getExistingDirectory(self, "選擇輸出資料夾")
        if not output_dir:
            return

        fmt = self.fmt_combo.currentText()
        try:
            results = Exporter.export_segments(
                audio, self.current_segments, output_dir, fmt,
                pad_before=self.pad_before_spin.value(),
                pad_after=self.pad_after_spin.value(),
                bitrate=self.bitrate_combo.currentText(),
            )
            Exporter.export_json(results, output_dir)
            Exporter.export_timestamps_txt(results, output_dir)
            QMessageBox.information(
                self, "匯出完成",
                f"成功匯出 {len(results)} 個音檔\n輸出位置：{output_dir}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "匯出錯誤", f"匯出失敗:\n{exc}")

    def export_timestamps(self):
        """Export timestamps.txt for the current file's segments."""
        if not self.current_file or not self.current_segments:
            QMessageBox.information(self, "提示", "沒有片段可以匯出。")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "儲存時間戳檔案", "timestamps.txt",
            "文字檔 (*.txt);;所有檔案 (*.*)",
        )
        if not path:
            return

        try:
            results = [
                {"start": seg.start, "end": seg.end}
                for seg in self.current_segments
            ]
            values = []
            for r in results:
                values.append(str(r["start"]))
                values.append(str(r["end"]))
            with open(path, "w", encoding="utf-8") as f:
                f.write(",".join(values))
            QMessageBox.information(self, "匯出完成", f"時間戳已儲存至：\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "匯出錯誤", f"匯出失敗:\n{exc}")

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    def _reindex(self):
        for i, seg in enumerate(self.current_segments):
            seg.id = i

    def _clear_current_file_selection(self):
        if self.current_file in self.cross_file_selection:
            self.cross_file_selection[self.current_file] = set()
        self._update_selection_label()
        self._update_file_list_indicators()

    def _persist_changes(self):
        if not self.current_file:
            return
        self.segments_cache[self.current_file] = list(self.current_segments)
        try:
            cache_path = self.current_file + ".segments.json"
            data = [{"start": s.start, "end": s.end, "text": s.text}
                    for s in self.current_segments]
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # ffmpeg detection & configuration
    # -----------------------------------------------------------------------
    def _init_ffmpeg(self):
        ffmpeg_path = find_ffmpeg()
        if ffmpeg_path:
            apply_ffmpeg_path(ffmpeg_path)
            self.ffmpeg_status.setText("ffmpeg: ✓")
            self.ffmpeg_status.setStyleSheet("color: #a6e3a1; font-size: 11px;")
            self.ffmpeg_status.setToolTip(ffmpeg_path)
        else:
            self.ffmpeg_status.setText("ffmpeg: ✗ 未找到")
            self.ffmpeg_status.setStyleSheet("color: #f38ba8; font-size: 11px;")
            self.ffmpeg_status.setToolTip("mp3/m4a 格式需要 ffmpeg，wav 格式可正常使用")

    def _set_ffmpeg_path(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇 ffmpeg.exe", r"C:\\",
            "ffmpeg 執行檔 (ffmpeg.exe);;所有檔案 (*.*)",
        )
        if not path or not os.path.isfile(path):
            return
        apply_ffmpeg_path(path)
        self.ffmpeg_status.setText("ffmpeg: ✓ (手動)")
        self.ffmpeg_status.setStyleSheet("color: #a6e3a1; font-size: 11px;")
        self.ffmpeg_status.setToolTip(path)
        self.statusBar().showMessage(f"ffmpeg 已設定：{path}")

    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------
    def closeEvent(self, event):
        sd.stop()
        self.position_timer.stop()
        self.queue_worker.stop()
        self.queue_thread.quit()
        self.queue_thread.wait(5000)
        event.accept()


# ---------------------------------------------------------------------------
def _sep() -> QWidget:
    sep = QWidget()
    sep.setFixedWidth(1)
    sep.setFixedHeight(20)
    sep.setStyleSheet("background-color: #45475a;")
    return sep
