import subprocess
from pathlib import Path

import cv2

from config import FFMPEG_BIN, run_ffmpeg


def check_face_detection_available() -> None:
   
    if not hasattr(cv2, "CascadeClassifier"):
        raise RuntimeError(
            "cv2.CascadeClassifier is not available in this OpenCV install "
            f"(cv2 version: {getattr(cv2, '__version__', 'unknown')}).\n\n"
            "OpenCV 5.0 moved Haar-cascade face detection out of the base "
            "'opencv-python' package into 'opencv-contrib-python'. Fix:\n\n"
            "    pip uninstall opencv-python -y\n"
            "    pip install opencv-contrib-python\n\n"
            "opencv-contrib-python is a strict superset of opencv-python, so "
            "this is a safe upgrade. Restart the app afterward."
        )


def reframe_center(input_path: str, output_path: str, target_ratio: float = 9 / 16) -> str:
    """Fast path: single ffmpeg crop filter, centered, no per-frame analysis."""
    cmd = [
        FFMPEG_BIN, "-y",
        "-i", input_path,
        "-vf",
        f"crop='min(iw,ih*{target_ratio})':'min(ih,iw/{target_ratio})'",
        "-c:a", "copy",
        output_path,
    ]
    run_ffmpeg(cmd)
    return output_path


def _detect_face_center_x(frame, face_cascade, prev_x: float | None) -> float:
    """Returns the x-center (in pixels) of the most prominent detected face,
    or falls back to prev_x (or frame center) if no face is found."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))

    if len(faces) == 0:
        return prev_x if prev_x is not None else frame.shape[1] / 2

    # pick the largest detected face (most likely the main subject)
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return x + w / 2


def reframe_face_tracked(input_path: str, output_path: str, target_ratio: float = 9 / 16, smoothing: float = 0.15) -> str:
   
    check_face_detection_available()
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    cap = cv2.VideoCapture(input_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    crop_w = int(min(src_w, src_h * target_ratio))
    crop_w -= crop_w % 2  # keep even (required by most codecs)
    crop_h = src_h - (src_h % 2)

    silent_path = str(Path(output_path).with_name(Path(output_path).stem + "_noaudio.mp4"))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(silent_path, fourcc, fps, (crop_w, crop_h))

    smoothed_x = src_w / 2  # start centered
    prev_face_x = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        face_x = _detect_face_center_x(frame, face_cascade, prev_face_x)
        prev_face_x = face_x

        smoothed_x = smoothing * face_x + (1 - smoothing) * smoothed_x

        # clamp so the crop window never goes off-frame
        left = int(smoothed_x - crop_w / 2)
        left = max(0, min(left, src_w - crop_w))

        cropped = frame[0:crop_h, left:left + crop_w]
        writer.write(cropped)

    cap.release()
    writer.release()

    # OpenCV drops audio -- mux the original audio track back onto the cropped video
    mux_cmd = [
        FFMPEG_BIN, "-y",
        "-i", silent_path,
        "-i", input_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0", "-map", "1:a:0?",
        "-shortest",
        output_path,
    ]
    run_ffmpeg(mux_cmd)
    Path(silent_path).unlink(missing_ok=True)

    return output_path


def reframe_vertical(input_path: str, output_path: str, mode: str = "center") -> str:
    """Entry point used by the pipeline. mode: 'center' or 'face'."""
    if mode == "face":
        return reframe_face_tracked(input_path, output_path)
    return reframe_center(input_path, output_path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python reframe.py <video_path> <mode: center|face>")
        sys.exit(1)

    out = reframe_vertical(sys.argv[1], "reframed_output.mp4", mode=sys.argv[2])
    print(f"Reframed video saved to {out}")