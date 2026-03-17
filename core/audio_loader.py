import os
import numpy as np
from pydub import AudioSegment as PydubAudio


class AudioLoader:
    @staticmethod
    def load(file_path: str) -> PydubAudio:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.mp3':
            audio = PydubAudio.from_mp3(file_path)
        elif ext == '.wav':
            audio = PydubAudio.from_wav(file_path)
        elif ext == '.m4a':
            audio = PydubAudio.from_file(file_path, format='m4a')
        elif ext == '.flac':
            audio = PydubAudio.from_file(file_path, format='flac')
        elif ext == '.ogg':
            audio = PydubAudio.from_ogg(file_path)
        else:
            audio = PydubAudio.from_file(file_path)
        return audio

    @staticmethod
    def to_numpy(audio: PydubAudio) -> tuple:
        """Convert pydub AudioSegment to mono float32 numpy array.
        Returns (samples, sample_rate).
        """
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
        if audio.channels == 2:
            samples = samples.reshape((-1, 2)).mean(axis=1)
        # Normalize to [-1, 1]
        if audio.sample_width == 1:
            max_val = 128.0
        elif audio.sample_width == 2:
            max_val = 32768.0
        elif audio.sample_width == 4:
            max_val = 2147483648.0
        else:
            max_val = float(2 ** (audio.sample_width * 8 - 1))
        samples = samples / max_val
        return samples, audio.frame_rate
