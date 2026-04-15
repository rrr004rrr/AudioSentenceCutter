# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run the application:**
```bash
python main.py
```

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Build Windows executable:**
```bash
build.bat
```
Produces `dist\AI音檔分割工具.exe` via PyInstaller. Requires `pip install pyinstaller` beforehand.

**External dependency:** ffmpeg must be installed separately (`winget install ffmpeg`). The app auto-detects it or allows manual path configuration via `utils/ffmpeg_helper.py`.

There is no test suite.

## Architecture

**Purpose:** Windows desktop tool for splitting audio files into sentences using AI speech recognition (faster-whisper), with interactive waveform editing and batch export.

### Data Flow

1. User queues audio files → `QueueWorker` background thread processes them sequentially
2. `core/audio_loader.py` loads audio as mono float32 numpy arrays
3. `core/transcriber.py` runs faster-whisper with VAD; caches results as `<file>.segments.json` alongside the audio file
4. `ui/waveform_widget.py` renders the waveform via pyqtgraph with draggable `LinearRegionItem` boundaries
5. User edits segment boundaries, merges/splits segments in `ui/main_window.py`
6. `core/exporter.py` exports selected segments as individual audio files + `metadata.json` + `timestamps.txt`

### Key Modules

| File | Role |
|------|------|
| `main.py` | Entry point; configures pyqtgraph, launches `MainWindow` |
| `ui/main_window.py` | Central logic (1432 lines): file list, queue management, table UI, playback, cross-file selection, export |
| `ui/waveform_widget.py` | Waveform display; exposes editable `LinearRegionItem` for segment boundaries |
| `core/transcriber.py` | faster-whisper wrapper; VAD settings; reads/writes `.segments.json` cache |
| `core/audio_loader.py` | Format-agnostic audio loading via pydub → numpy float32 |
| `core/exporter.py` | Batch export segments; writes `metadata.json` and `timestamps.txt` |
| `utils/ffmpeg_helper.py` | ffmpeg binary detection and manual path config |
| `utils/filename_cleaner.py` | Sanitizes transcribed text for use as filenames (max 50 chars) |

### Important Design Details

- **Caching:** Transcription results are persisted as `.segments.json` files next to the audio files. The app skips re-transcription if this file exists. Deleting it forces re-processing.
- **Whisper model sizes:** `tiny`, `base`, `small` (default), `medium` — configurable in the UI. Larger models give better accuracy but are slower.
- **Cross-file selection:** `main_window.py` tracks selected segments across multiple loaded files for batch export.
- **Playback tracking:** Uses wall-clock time vs. audio start offset (not a Qt media position) to track playback progress on the waveform.
- **Thread safety:** Audio processing happens in `QueueWorker` (QThread); UI updates use Qt signals/slots.

### Supported Audio Formats

MP3, WAV, M4A, FLAC, OGG (MP3 and M4A require ffmpeg).
