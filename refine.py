from dataclasses import dataclass

from pydub import AudioSegment
from pydub.silence import detect_silence


@dataclass
class RefinedWindow:
    start: float
    end: float


def _find_nearest_silence(
    audio: AudioSegment, around_sec: float, search_radius: float, min_silence_len_ms: int = 150
) -> list[tuple[float, float]]:

    lo_ms = max(0, int((around_sec - search_radius) * 1000))
    hi_ms = min(len(audio), int((around_sec + search_radius) * 1000))
    if hi_ms <= lo_ms:
        return []

    chunk = audio[lo_ms:hi_ms]
    silences = detect_silence(chunk, min_silence_len=min_silence_len_ms, silence_thresh=chunk.dBFS - 16)

    # convert chunk-relative ms back to absolute seconds
    return [((s + lo_ms) / 1000.0, (e + lo_ms) / 1000.0) for s, e in silences]


def refine_boundaries(
    audio_path: str, start: float, end: float, search_radius: float = 1.0
) -> RefinedWindow:
    """
    Snaps `start` forward to the end of the nearest preceding silence (so the clip doesn't open mid-breath) and snaps `end` backward to the start of the nearest following silence (so it doesn't cut off the start of the next sentence). Falls back to the original timestamp if no silence is found nearby — this is a refinement, not a hard requirement.
    """
    audio = AudioSegment.from_file(audio_path)

    start_silences = _find_nearest_silence(audio, start, search_radius)
    end_silences = _find_nearest_silence(audio, end, search_radius)

    new_start = start
    if start_silences:
        # pick the silence closest to the original start, snap to its end
        closest = min(start_silences, key=lambda se: abs((se[0] + se[1]) / 2 - start))
        new_start = closest[1]

    new_end = end
    if end_silences:
        closest = min(end_silences, key=lambda se: abs((se[0] + se[1]) / 2 - end))
        new_end = closest[0]

    # safety: never invert or over-shrink the window
    if new_end - new_start < 2.0:
        return RefinedWindow(start=start, end=end)

    return RefinedWindow(start=new_start, end=new_end)


def refine_highlights(audio_path: str, highlights, search_radius: float = 1.0):
    """Convenience wrapper: refines a whole list of Highlight objects from Module 3."""
    refined = []
    for h in highlights:
        r = refine_boundaries(audio_path, h.start, h.end, search_radius)
        h.start, h.end = r.start, r.end
        refined.append(h)
    return refined


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("Usage: python refine.py <audio_path> <start_sec> <end_sec>")
        sys.exit(1)

    result = refine_boundaries(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]))
    print(f"Refined: {result.start:.2f}s - {result.end:.2f}s")
