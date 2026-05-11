from dataclasses import dataclass
from typing import Optional


@dataclass
class Segment:
    id: int
    start: float   # seconds
    end: float     # seconds
    text: str
    # Custom export filename override. When empty, exporter derives the name
    # from `text`. Lets users name files independently of the transcript.
    filename: str = ""


class Transcriber:
    def __init__(self, model_size: str = "small"):
        self.model_size = model_size
        self.model = None

    def load_model(self):
        if self.model is None:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8",
            )

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        min_silence_ms: int = 500,
        vad_threshold: float = 0.5,
    ) -> list:
        """Transcribe audio file and return list of Segment objects."""
        self.load_model()
        kwargs = {
            "beam_size": 5,
            "vad_filter": True,
            "vad_parameters": {
                "min_silence_duration_ms": min_silence_ms,
                "threshold": vad_threshold,
            },
        }
        if language:
            kwargs["language"] = language

        raw_segments, info = self.model.transcribe(audio_path, **kwargs)

        result = []
        for i, seg in enumerate(raw_segments):
            text = seg.text.strip()
            if not text:
                continue
            result.append(Segment(
                id=i,
                start=round(seg.start, 3),
                end=round(seg.end, 3),
                text=text,
            ))

        # Re-index after filtering empty segments
        for i, seg in enumerate(result):
            seg.id = i

        return result
