import tempfile
from pathlib import Path

import streamlit as st

from ingest import extract_audio, get_video_metadata, check_ffmpeg_available
from transcribe import load_model, transcribe
from highlights import select_top_highlights, flatten_words
from refine import refine_highlights
from clip import cut_clip
from reframe import reframe_vertical
from captions import add_captions, words_in_range
from package import package_clip


st.set_page_config(page_title="AI Shorts Clipper", layout="wide")
st.title("AI Shorts Clipper")
st.caption("Upload a long video. It finds the best 10-20s moments and turns them into ready-to-post vertical shorts.")

try:
    check_ffmpeg_available()
except RuntimeError as e:
    st.error(str(e))
    st.stop()


# ---- cached, expensive resources ----

@st.cache_resource
def get_whisper_model(model_size: str):
    return load_model(model_size)


# ---- session state setup ----

if "work_dir" not in st.session_state:
    st.session_state.work_dir = tempfile.mkdtemp(prefix="shorts_")
if "analyzed" not in st.session_state:
    st.session_state.analyzed = False
if "highlights" not in st.session_state:
    st.session_state.highlights = []
if "generated_clips" not in st.session_state:
    st.session_state.generated_clips = []


# ---- sidebar options ----

with st.sidebar:
    st.header("Settings")
    model_size = st.selectbox("Whisper model size", ["tiny", "base", "small", "medium"], index=1)
    top_k = st.slider("Number of highlights to detect", 1, 10, 5)
    clip_range = st.slider("Clip length range (sec)", 5, 30, (15, 20))
    reframe_mode = st.radio("Reframe to vertical (9:16)", ["none", "center", "face"], index=1)
    add_caption_burn = st.checkbox("Burn in captions", value=True)


# ---- step 1: upload + analyze ----

uploaded = st.file_uploader("Upload a video", type=["mp4", "mov", "mkv"])

if uploaded is not None:
    video_path = str(Path(st.session_state.work_dir) / uploaded.name)
    if not Path(video_path).exists():
        Path(video_path).write_bytes(uploaded.read())

    meta = get_video_metadata(video_path)
    st.write(f"**{meta.duration_sec:.1f}s** &nbsp;|&nbsp; {meta.width}x{meta.height} &nbsp;|&nbsp; {meta.fps:.1f} fps")

    if st.button("Analyze video", type="primary"):
        with st.spinner("Extracting audio..."):
            audio_path = extract_audio(video_path)

        with st.spinner(f"Transcribing (model: {model_size})... this can take a while on CPU"):
            model = get_whisper_model(model_size)
            segments = transcribe(audio_path, model=model)

        with st.spinner("Scoring and selecting highlights..."):
            highlights = select_top_highlights(
                segments, top_k=top_k, min_dur=clip_range[0], max_dur=clip_range[1]
            )
            highlights = refine_highlights(audio_path, highlights)

        st.session_state.video_path = video_path
        st.session_state.audio_path = audio_path
        st.session_state.all_words = flatten_words(segments)
        st.session_state.highlights = highlights
        st.session_state.analyzed = True
        st.session_state.generated_clips = []


# ---- step 2: pick highlights ----

if st.session_state.analyzed and st.session_state.highlights:
    st.subheader("Detected highlights")
    selected_idxs = []
    for i, h in enumerate(st.session_state.highlights):
        checked = st.checkbox(
            f"[{h.start:.1f}s - {h.end:.1f}s]  (score: {h.score:.1f})  \u2014 \u201c{h.text}\u201d",
            value=True,
            key=f"select_{i}",
        )
        if checked:
            selected_idxs.append(i)

    if st.button("Generate shorts", type="primary") and selected_idxs:
        video_path = st.session_state.video_path
        all_words = st.session_state.all_words
        out_dir = Path(st.session_state.work_dir) / "output"
        out_dir.mkdir(exist_ok=True)

        progress = st.progress(0.0)
        results = []

        for n, idx in enumerate(selected_idxs):
            h = st.session_state.highlights[idx]

            raw_clip = str(out_dir / f"raw_{idx}.mp4")
            cut_clip(video_path, h.start, h.end, raw_clip)

            working = raw_clip
            if reframe_mode != "none":
                reframed = str(out_dir / f"reframed_{idx}.mp4")
                reframe_vertical(working, reframed, mode=reframe_mode)
                working = reframed

            if add_caption_burn:
                clip_words = words_in_range(all_words, h.start, h.end)
                captioned = str(out_dir / f"captioned_{idx}.mp4")
                # target dims match what reframe produced (1080x1920-ish);
                # package() below normalizes to the exact final resolution anyway
                add_captions(working, clip_words, captioned, video_width=1080, video_height=1920)
                working = captioned

            packaged = package_clip(working, str(out_dir), f"short_{idx + 1}")
            results.append({"highlight": h, **packaged})

            progress.progress((n + 1) / len(selected_idxs))

        st.session_state.generated_clips = results


# ---- step 3: show results ----

if st.session_state.generated_clips:
    st.subheader("Your shorts")
    cols = st.columns(min(3, len(st.session_state.generated_clips)))
    for i, result in enumerate(st.session_state.generated_clips):
        with cols[i % len(cols)]:
            st.video(result["video"])
            st.caption(result["highlight"].text)
            with open(result["video"], "rb") as f:
                st.download_button(
                    "Download",
                    f.read(),
                    file_name=Path(result["video"]).name,
                    mime="video/mp4",
                    key=f"dl_{i}",
                )
