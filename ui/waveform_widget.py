import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy


class WaveformWidget(QWidget):
    region_changed = Signal(float, float)   # start, end (seconds)
    region_drag_started = Signal()          # emitted on the first change of each user drag
    position_clicked = Signal(float)        # clicked position (seconds)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sample_rate = 44100
        self.duration = 0.0
        self.samples = None
        self._block_region_signal = False
        self._region_drag_active = False

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(140)

        # --- pyqtgraph setup ---
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("#1a1a2e")
        self.plot_widget.showGrid(x=False, y=False)
        self.plot_widget.getAxis("left").hide()
        self.plot_widget.getAxis("bottom").setTextPen(pg.mkPen("#a6adc8"))
        self.plot_widget.setMouseEnabled(x=True, y=False)
        self.plot_widget.setMenuEnabled(False)
        self.plot_widget.setLabel("bottom", text="", units="s")

        # Waveform curve
        self.curve = self.plot_widget.plot(
            pen=pg.mkPen("#89b4fa", width=1)
        )

        # Editable region for selected segment
        self.region = pg.LinearRegionItem(
            values=(0, 1),
            brush=pg.mkBrush(137, 180, 250, 50),
            pen=pg.mkPen("#cba6f7", width=2),
            movable=True,
        )
        self.region.setZValue(10)
        self.plot_widget.addItem(self.region)
        self.region.sigRegionChanged.connect(self._on_region_changed)
        self.region.sigRegionChangeFinished.connect(self._on_region_finished)

        # Playback position line
        self.position_line = pg.InfiniteLine(
            pos=0,
            angle=90,
            pen=pg.mkPen("#f38ba8", width=2),
            movable=False,
        )
        self.plot_widget.addItem(self.position_line)

        # Segment boundary lines (list)
        self.segment_lines: list = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot_widget)

    # ------------------------------------------------------------------
    def set_audio(self, samples: np.ndarray, sample_rate: int):
        self.samples = samples
        self.sample_rate = sample_rate
        self.duration = len(samples) / sample_rate

        # Downsample for performance
        max_points = 12000
        if len(samples) > max_points:
            factor = max(1, len(samples) // max_points)
            display = samples[::factor]
        else:
            display = samples

        x = np.linspace(0, self.duration, len(display))
        self.curve.setData(x, display)
        self.plot_widget.setXRange(0, self.duration, padding=0.01)
        self.plot_widget.setYRange(-1.1, 1.1, padding=0)

        # Reset region bounds
        self.region.setBounds((0, self.duration))
        self.region.setRegion((0, min(1.0, self.duration)))

    def set_region(self, start: float, end: float):
        self._block_region_signal = True
        self.region.setRegion((start, end))
        self._block_region_signal = False

        # Auto-scroll to show region with padding
        span = max(end - start, 0.1)
        pad = span * 0.8
        x_min = max(0, start - pad)
        x_max = min(self.duration, end + pad)
        self.plot_widget.setXRange(x_min, x_max, padding=0)

    def set_segments(self, segments: list):
        # Remove old boundary lines
        for line in self.segment_lines:
            self.plot_widget.removeItem(line)
        self.segment_lines.clear()

        # Add new boundary lines at segment starts
        for seg in segments:
            line = pg.InfiniteLine(
                pos=seg.start,
                angle=90,
                pen=pg.mkPen("#a6e3a1", width=1, style=Qt.PenStyle.DashLine),
                movable=False,
            )
            self.plot_widget.addItem(line)
            self.segment_lines.append(line)

    def set_playback_position(self, position: float):
        self.position_line.setValue(position)

    def clear(self):
        self.curve.setData([], [])
        self.region.setRegion((0, 1))
        for line in self.segment_lines:
            self.plot_widget.removeItem(line)
        self.segment_lines.clear()
        self.position_line.setValue(0)
        self.duration = 0.0

    # ------------------------------------------------------------------
    def _on_region_changed(self):
        if self._block_region_signal:
            return
        if not self._region_drag_active:
            self._region_drag_active = True
            self.region_drag_started.emit()
        start, end = self.region.getRegion()
        self.region_changed.emit(start, end)

    def _on_region_finished(self):
        self._region_drag_active = False
