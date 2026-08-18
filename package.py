import subprocess
from pathlib import Path

from config import FFMPEG_BIN, run_ffmpeg

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920


def normalize_output(input_path: str, output_path: str, width: int = TARGET_WIDTH, height: int = TARGET_HEIGHT) -> str:

    cmd = [
        FFMPEG_BIN, "-y",
        "-i", input_path,
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        output_path,
    ]
    run_ffmpeg(cmd)
    return output_path


def generate_thumbnail(video_path: str, output_path: str, timestamp: float = 1.0) -> str:
    """Grabs a single frame at `timestamp` seconds in as a thumbnail image."""
    cmd = [
        FFMPEG_BIN, "-y",
        "-ss", str(timestamp),
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        output_path,
    ]
    run_ffmpeg(cmd)
    return output_path


def package_clip(input_path: str, output_dir: str, name: str) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    final_video = str(output_dir / f"{name}.mp4")
    thumbnail = str(output_dir / f"{name}_thumb.jpg")

    normalize_output(input_path, final_video)
    generate_thumbnail(final_video, thumbnail, timestamp=min(1.0, 0.5))

    return {"video": final_video, "thumbnail": thumbnail}


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python package.py <video_path>")
        sys.exit(1)

    result = package_clip(sys.argv[1], "packaged_output", "clip")
    print(f"Final video: {result['video']}")
    print(f"Thumbnail:   {result['thumbnail']}")