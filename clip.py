import subprocess
from pathlib import Path

from config import FFMPEG_BIN, run_ffmpeg


def cut_clip(video_path: str, start: float, end: float, output_path: str, frame_accurate: bool = True) -> str:
   
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if frame_accurate:
        cmd = [
            FFMPEG_BIN, "-y",
            "-i", video_path,
            "-ss", str(start),
            "-to", str(end),
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac",
            output_path,
        ]
    else:
        cmd = [
            FFMPEG_BIN, "-y",
            "-ss", str(start),
            "-to", str(end),
            "-i", video_path,
            "-c", "copy",
            output_path,
        ]

    run_ffmpeg(cmd)
    return output_path


def cut_highlights(video_path: str, highlights, output_dir: str, frame_accurate: bool = True) -> list[str]:
    """Cuts every Highlight in a list into its own numbered file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for i, h in enumerate(highlights, 1):
        out_path = output_dir / f"clip_{i}.mp4"
        cut_clip(video_path, h.start, h.end, str(out_path), frame_accurate=frame_accurate)
        paths.append(str(out_path))
    return paths


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("Usage: python clip.py <video_path> <start_sec> <end_sec>")
        sys.exit(1)

    out = cut_clip(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), "clip_output.mp4")
    print(f"Clip saved to {out}")