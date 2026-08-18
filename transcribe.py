from dataclasses import dataclass, field


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class Segment:
    text: str
    start: float
    end: float
    words: list[Word] = field(default_factory=list)


def load_model(model_size: str = "base"):
    from faster_whisper import WhisperModel

    # compute_type="int8" keeps this usable on CPU-only machines.
    # Switch to device="cuda", compute_type="float16" if you have a GPU.
    return WhisperModel(model_size, device="cpu", compute_type="int8")


def transcribe(audio_path: str, model_size: str = "base", model=None) -> list[Segment]:
    """ Transcribes an audio file and returns a list of Segments. Pass a pre-loaded `model` (from load_model()) to avoid reloading the model on every call; otherwise one is loaded fresh for this call. """
    if model is None:
        model = load_model(model_size)

    raw_segments, info = model.transcribe(audio_path, word_timestamps=True)

    segments: list[Segment] = []
    for seg in raw_segments:
        words = [Word(text=w.word.strip(), start=w.start, end=w.end) for w in (seg.words or [])]
        segments.append(Segment(text=seg.text.strip(), start=seg.start, end=seg.end, words=words))

    return segments


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python transcribe.py <audio_path>")
        sys.exit(1)

    for seg in transcribe(sys.argv[1]):
        print(f"[{seg.start:6.1f}s - {seg.end:6.1f}s] {seg.text}")
