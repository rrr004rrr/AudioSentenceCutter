import os
import json
from pydub import AudioSegment as PydubAudio
from utils.filename_cleaner import clean_filename


class Exporter:
    @staticmethod
    def export_segments(
        audio: PydubAudio,
        segments: list,
        output_dir: str,
        fmt: str = "mp3",
        pad_before: float = 0.0,   # seconds of silence before each segment
        pad_after: float = 0.0,    # seconds of silence after each segment
        bitrate: str = "192k",     # MP3 bitrate, e.g. "128k", "192k", "256k", "320k"
        progress_callback=None,
    ) -> list:
        """Export each segment as an audio file.

        Returns list of metadata dicts.
        """
        os.makedirs(output_dir, exist_ok=True)
        results = []
        used_names = set()

        # Build silence segments that match the source audio format
        pad_before_ms = int(pad_before * 1000)
        pad_after_ms  = int(pad_after  * 1000)
        silence_before = (
            PydubAudio.silent(duration=pad_before_ms, frame_rate=audio.frame_rate)
            if pad_before_ms > 0 else None
        )
        silence_after = (
            PydubAudio.silent(duration=pad_after_ms, frame_rate=audio.frame_rate)
            if pad_after_ms > 0 else None
        )

        for i, seg in enumerate(segments):
            if progress_callback:
                progress_callback(i, len(segments))

            start_ms = int(seg.start * 1000)
            end_ms   = int(seg.end   * 1000)
            chunk = audio[start_ms:end_ms]

            # Apply padding
            if silence_before:
                chunk = silence_before + chunk
            if silence_after:
                chunk = chunk + silence_after

            custom = getattr(seg, "filename", "")
            if custom and custom.strip():
                base_name = clean_filename(custom)
            elif seg.text.strip():
                base_name = clean_filename(seg.text)
            else:
                base_name = f"segment_{i + 1:04d}"
            filename = f"{base_name}.{fmt}"

            # Avoid duplicate filenames
            counter = 1
            while filename in used_names or os.path.exists(os.path.join(output_dir, filename)):
                filename = f"{base_name}_{counter}.{fmt}"
                counter += 1
            used_names.add(filename)

            output_path = os.path.join(output_dir, filename)
            export_kwargs = {}
            if fmt == "mp3":
                export_kwargs["bitrate"] = bitrate

            chunk.export(output_path, format=fmt, **export_kwargs)

            results.append({
                "text": seg.text,
                "start": seg.start,
                "end": seg.end,
                "duration": round(seg.end - seg.start, 3),
                "pad_before": pad_before,
                "pad_after": pad_after,
                "file": filename,
            })

        return results

    @staticmethod
    def export_json(results: list, output_dir: str):
        """Export metadata.json alongside audio files."""
        json_path = os.path.join(output_dir, "metadata.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    @staticmethod
    def export_timestamps_txt(results: list, output_dir: str):
        """Export timestamps.txt: start1,end1,start2,end2,... on one line."""
        values = []
        for r in results:
            values.append(str(r["start"]))
            values.append(str(r["end"]))
        txt_path = os.path.join(output_dir, "timestamps.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(",".join(values))
