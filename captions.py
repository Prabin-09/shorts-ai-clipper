import subprocess
from dataclasses import dataclass
from pathlib import Path

from transcribe import Word
from config import FFMPEG_BIN, run_ffmpeg

@dataclass
class CaptionChunk:
    text: str
    start: float
    end: float

def words_in_range(words: list[Word], start: float, end: float) -> list[Word]:
    return [
        Word(text=w.text, start=w.start - start, end=w.end - start)
        for w in words
        if w.start >= start and w.end <= end
    ]

def chunk_words(words: list[Word], max_words: int = 3, max_gap: float = 0.6) -> list[CaptionChunk]:
    if not words:
        return []

    chunks: list[CaptionChunk] = []
    current: list[Word] = [words[0]]

    for prev, word in zip(words, words[1:]):
        gap = word.start - prev.end
        if len(current) >= max_words or gap > max_gap:
            chunks.append(CaptionChunk(
                text=" ".join(w.text for w in current),
                start=current[0].start,
                end=current[-1].end,
            ))
            current = [word]
        else:
            current.append(word)

    if current:
        chunks.append(CaptionChunk(
            text=" ".join(w.text for w in current),
            start=current[0].start,
            end=current[-1].end,
        ))

    return chunks

def _format_ass_time(seconds: float) -> str:
    """ASS timestamps look like H:MM:SS.CC (centiseconds)."""
    cs = int(round(seconds * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Outline, Shadow, Alignment, MarginV
Style: Caption,Arial,{fontsize},&H00FFFFFF,&H00000000,&H00000000,1,3,0,2,{marginv}

[Events]
Format: Layer, Start, End, Style, Text
"""

def generate_ass(chunks: list[CaptionChunk], output_path: str, video_width: int = 1080, video_height: int = 1920):
    fontsize = max(48, video_width // 18)
    marginv = video_height // 6  # distance from the bottom of the frame

    lines = [ASS_HEADER.format(width=video_width, height=video_height, fontsize=fontsize, marginv=marginv)]
    for chunk in chunks:
        start = _format_ass_time(chunk.start)
        end = _format_ass_time(chunk.end)
        # \b1 = bold; strip any literal braces in the text just in case
        text = chunk.text.replace("{", "").replace("}", "").upper()
        lines.append(f"Dialogue: 0,{start},{end},Caption,{text}")

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    return output_path

def burn_captions(video_path: str, ass_path: str, output_path: str) -> str:
    ass = Path(ass_path)
    video_in = str(Path(video_path).resolve())
    video_out = str(Path(output_path).resolve())

    cmd = [
        FFMPEG_BIN, "-y",
        "-i", video_in,
        "-vf", f"ass={ass.name}",
        "-c:a", "copy",
        video_out,
    ]
    run_ffmpeg(cmd, cwd=str(ass.parent))
    return output_path

def add_captions(video_path: str, words: list[Word], output_path: str, video_width: int, video_height: int) -> str:
    """Full Module 7 pipeline: words -> chunks -> .ass file -> burned-in video."""
    chunks = chunk_words(words)
    ass_path = str(Path(output_path).with_suffix(".ass"))
    generate_ass(chunks, ass_path, video_width, video_height)
    return burn_captions(video_path, ass_path, output_path)


if __name__ == "__main__":
    print("This module is meant to be called from the pipeline with real Word timestamps.")
    print("See pipeline.py for usage, or Module 2 (transcribe.py) for how Word objects are produced.")
    