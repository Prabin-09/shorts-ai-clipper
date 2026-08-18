import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from config import FFMPEG_BIN, FFPROBE_BIN, run_ffmpeg

def _is_available(bin_path: str) -> bool:
    """Bare command name -> resolve via PATH. Explicit path -> check it exists."""
    if os.path.sep in bin_path or (os.path.altsep and os.path.altsep in bin_path):
        return os.path.isfile(bin_path)
    return shutil.which(bin_path) is not None

def check_ffmpeg_available() -> None:

    missing = [name for name, bin_path in (("ffmpeg", FFMPEG_BIN), ("ffprobe", FFPROBE_BIN)) if not _is_available(bin_path)]
    if missing:
        raise RuntimeError(
            f"Required tool(s) not found: {', '.join(missing)} (looked for: "
            f"{FFMPEG_BIN!r}, {FFPROBE_BIN!r}).\n\n"
            "Common causes:\n"
            "  1. ffmpeg isn't installed yet -- see the README setup steps.\n"
            "  2. It's installed, but this terminal/IDE window was opened (or its\n"
            "     environment was cached) before you added it to PATH.\n"
            "  3. PATH keeps being unreliable across terminals -- the reliable fix is\n"
            "     to skip PATH entirely: open config.py in this project, and set\n"
            "     FFMPEG_BIN / FFPROBE_BIN to the exact .exe paths (find them by\n"
            "     running 'where.exe ffmpeg' in a terminal where it already works).\n\n"
            "After installing or editing config.py, fully restart this app (Ctrl+C,\n"
            "then 'streamlit run app.py' again) -- a browser refresh alone won't\n"
            "pick up the change."
        )

@dataclass
class VideoMetadata:
    duration_sec: float
    width: int
    height: int
    fps: float

def get_video_metadata(video_path: str) -> VideoMetadata:

    cmd = [
        FFPROBE_BIN, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate",
        "-show_entries", "format=duration",
        "-of", "json",
        video_path,
    ]
    result = run_ffmpeg(cmd)
    info = json.loads(result.stdout)

    stream = info["streams"][0]
    duration = float(info["format"]["duration"])
    width = int(stream["width"])
    height = int(stream["height"])

    # r_frame_rate comes back as a fraction string like "30000/1001"
    num, den = stream["r_frame_rate"].split("/")
    fps = float(num) / float(den)

    return VideoMetadata(duration_sec=duration, width=width, height=height, fps=fps)

def extract_audio(video_path: str, output_audio_path: str | None = None) -> str:

    video_path = Path(video_path)
    if output_audio_path is None:
        output_audio_path = str(video_path.with_suffix(".wav"))

    cmd = [
        FFMPEG_BIN, "-y",           # -y overwrites output if it already exists
        "-i", str(video_path),
        "-vn",                    # no video stream in the output
        "-acodec", "pcm_s16le",   # uncompressed PCM — safest for ASR input
        "-ar", "16000",           # 16kHz sample rate
        "-ac", "1",                # mono
        output_audio_path,
    ]
    run_ffmpeg(cmd)
    return output_audio_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python ingest.py <video_path>")
        sys.exit(1)

    path = sys.argv[1]
    meta = get_video_metadata(path)
    print(f"Duration: {meta.duration_sec:.1f}s | {meta.width}x{meta.height} | {meta.fps:.2f} fps")

    audio_path = extract_audio(path)
    print(f"Audio extracted to: {audio_path}")
