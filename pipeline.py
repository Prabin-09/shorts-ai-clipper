import argparse
from pathlib import Path

from ingest import extract_audio, get_video_metadata, check_ffmpeg_available
from transcribe import transcribe
from highlights import select_top_highlights, flatten_words
from refine import refine_highlights
from clip import cut_clip
from reframe import reframe_vertical
from captions import add_captions, words_in_range
from package import package_clip


def run_pipeline(
    video_path: str,
    model_size: str = "base",
    top_k: int = 5,
    min_dur: float = 15.0,
    max_dur: float = 20.0,
    reframe_mode: str = "center",
    burn_captions: bool = True,
    output_dir: str = "output",
):
    check_ffmpeg_available()

    print("Reading video metadata...")
    meta = get_video_metadata(video_path)
    print(f"  Duration: {meta.duration_sec:.1f}s | {meta.width}x{meta.height} | {meta.fps:.2f} fps\n")

    print("Extracting audio (Module 1)...")
    audio_path = extract_audio(video_path)

    print(f"Transcribing (Module 2, model='{model_size}', this is the slow step)...")
    segments = transcribe(audio_path, model_size=model_size)
    all_words = flatten_words(segments)
    print(f"  -> {len(segments)} segments transcribed\n")

    print("Scoring and selecting highlights (Module 3)...")
    highlights = select_top_highlights(segments, top_k=top_k, min_dur=min_dur, max_dur=max_dur)

    print("Refining boundaries to natural pauses (Module 4)...")
    highlights = refine_highlights(audio_path, highlights)

    print("=" * 60)
    for i, h in enumerate(highlights, 1):
        print(f"Highlight {i}: [{h.start:.1f}s - {h.end:.1f}s]  (score={h.score:.1f})")
        print(f"   \"{h.text}\"")
    print("=" * 60)

    out_dir = Path(output_dir)
    out_dir.mkdir(exist_ok=True)
    final_paths = []

    for i, h in enumerate(highlights, 1):
        print(f"\nProcessing highlight {i}/{len(highlights)}...")

        print("  Cutting clip (Module 5)...")
        raw_clip = str(out_dir / f"_raw_{i}.mp4")
        cut_clip(video_path, h.start, h.end, raw_clip)
        working = raw_clip

        if reframe_mode != "none":
            print(f"  Reframing to vertical, mode='{reframe_mode}' (Module 6)...")
            reframed = str(out_dir / f"_reframed_{i}.mp4")
            reframe_vertical(working, reframed, mode=reframe_mode)
            working = reframed

        if burn_captions:
            print("  Burning captions (Module 7)...")
            clip_words = words_in_range(all_words, h.start, h.end)
            captioned = str(out_dir / f"_captioned_{i}.mp4")
            add_captions(working, clip_words, captioned, video_width=1080, video_height=1920)
            working = captioned

        print("  Packaging final output (Module 8)...")
        result = package_clip(working, str(out_dir), f"short_{i}")
        final_paths.append(result)
        print(f"  -> {result['video']}")

    print(f"\nDone. {len(final_paths)} shorts saved to {out_dir}/")
    return final_paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI shorts clipper: full end-to-end pipeline")
    parser.add_argument("video_path")
    parser.add_argument("--model", default="base", help="Whisper model size (tiny/base/small/medium)")
    parser.add_argument("--top-k", type=int, default=5, help="number of highlights to select")
    parser.add_argument("--min-dur", type=float, default=15.0, help="minimum clip length in seconds")
    parser.add_argument("--max-dur", type=float, default=20.0, help="maximum clip length in seconds")
    parser.add_argument("--reframe", default="center", choices=["none", "center", "face"], help="vertical reframe mode")
    parser.add_argument("--no-captions", action="store_true", help="skip burning in captions")
    parser.add_argument("--output-dir", default="output", help="where to save final shorts")
    args = parser.parse_args()

    run_pipeline(
        args.video_path,
        model_size=args.model,
        top_k=args.top_k,
        min_dur=args.min_dur,
        max_dur=args.max_dur,
        reframe_mode=args.reframe,
        burn_captions=not args.no_captions,
        output_dir=args.output_dir,
    )