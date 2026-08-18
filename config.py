import os
import subprocess

FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN = os.environ.get("FFPROBE_BIN", "ffprobe")


def run_ffmpeg(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
   
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg command failed (exit code {result.returncode}):\n"
            f"  {' '.join(cmd)}\n\n"
            f"ffmpeg's error output:\n{result.stderr.strip() or '(ffmpeg produced no stderr output)'}"
        )
    return result