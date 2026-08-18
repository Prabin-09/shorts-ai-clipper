import re
from dataclasses import dataclass

from transcribe import Segment, Word

# Words that tend to show up in clips people actually share/watch.
# Tune this list for your content niche .
HOOK_KEYWORDS = {
    "amazing", "incredible", "insane", "crazy", "secret", "never", "always",
    "shocking", "important", "huge", "massive", "biggest", "first", "worst",
    "best", "mistake", "wrong", "truth", "actually", "literally", "wait",
    "stop", "imagine", "what if", "here's why", "nobody", "everyone",
}


@dataclass
class Highlight:
    start: float
    end: float
    text: str
    score: float


def flatten_words(segments: list[Segment]) -> list[Word]:
    """Combines word timestamps across all segments into one flat timeline."""
    words: list[Word] = []
    for seg in segments:
        if seg.words:
            words.extend(seg.words)
        else:
            # fallback if word-level timestamps weren't available for a segment
            words.append(Word(text=seg.text, start=seg.start, end=seg.end))
    return words


def score_window_heuristic(text: str, duration: float) -> float:
    """Rule-based score for a single candidate window. Higher = better clip."""
    if duration <= 0:
        return 0.0

    lower = text.lower()
    word_count = len(text.split())

    punctuation_score = text.count("!") * 1.5 + text.count("?") * 1.0
    keyword_score = sum(1 for kw in HOOK_KEYWORDS if kw in lower) * 2.0
    number_score = len(re.findall(r"\b\d+\b", text)) * 1.5
    pace_score = word_count / duration  # words per second

    return punctuation_score + keyword_score + number_score + pace_score


def score_windows_llm(candidate_windows: list[tuple[float, float, str]]) -> dict[tuple[float, float], float]:

    raise NotImplementedError("Wire this up to an LLM API once the heuristic version works end to end.")


def _generate_candidate_windows(
    words: list[Word], min_dur: float, max_dur: float, stride: float
) -> list[tuple[float, float, str]]:
    
    if not words:
        return []

    candidates = []
    total_end = words[-1].end
    t = words[0].start

    while t < total_end:
        window_end = t + max_dur
        window_words = [w for w in words if w.start >= t and w.start < window_end]
        if window_words:
            start = window_words[0].start
            end = window_words[-1].end
            duration = end - start
            if duration >= min_dur:
                text = " ".join(w.text for w in window_words)
                candidates.append((start, end, text))
        t += stride

    return candidates


def select_top_highlights(
    segments: list[Segment],
    top_k: int = 5,
    min_dur: float = 15.0,
    max_dur: float = 20.0,
    stride: float = 2.0,
) -> list[Highlight]:
    
    words = flatten_words(segments)
    candidates = _generate_candidate_windows(words, min_dur, max_dur, stride)

    scored = [
        Highlight(start=s, end=e, text=text, score=score_window_heuristic(text, e - s))
        for s, e, text in candidates
    ]
    scored.sort(key=lambda h: h.score, reverse=True)

    selected: list[Highlight] = []
    for h in scored:
        # skip if it overlaps any already-selected highlight
        overlaps = any(not (h.end <= s.start or h.start >= s.end) for s in selected)
        if not overlaps:
            selected.append(h)
        if len(selected) >= top_k:
            break

    # return in chronological order rather than score order — easier to review
    selected.sort(key=lambda h: h.start)
    return selected


if __name__ == "__main__":
    import sys
    from transcribe import transcribe

    if len(sys.argv) != 2:
        print("Usage: python highlights.py <audio_path>")
        sys.exit(1)

    segs = transcribe(sys.argv[1])
    for h in select_top_highlights(segs):
        print(f"[{h.start:6.1f}s - {h.end:6.1f}s] score={h.score:.1f}  {h.text}")
