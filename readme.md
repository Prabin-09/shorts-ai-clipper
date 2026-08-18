# AI Shorts Clipper

Turns a long video into ready-to-post vertical shorts. Upload a podcast,
lecture, or any long-form video — it transcribes it, finds the best
10-20 second moments, cuts them, reframes to 9:16, and burns in captions,
fully automatically.

**Live demo:** [ai-shorts-clipper01.streamlit.app](https://ai-shorts-clipper01.streamlit.app/)

## How it works

The pipeline combines three AI capabilities into one system:

- **Speech** — [Whisper](https://github.com/openai/whisper) (via `faster-whisper`) transcribes the video with word-level timestamps
- **NLP** — a scoring pass ranks transcript segments by punctuation, keyword density, and pace to find the most "clip-worthy" moments
- **Vision** — OpenCV face detection tracks the speaker so the vertical crop follows them instead of just center-cropping

ffmpeg handles all the actual media work underneath — cutting, cropping,
caption burn-in, and final encoding — driven by the decisions the models
above make.

## Architecture

The pipeline is nine small, single-responsibility modules, split into two phases:

**Phase A — analysis (runs once per video):**

| # | File | What it does |
|---|---|---|
| 1 | `ingest.py` | Extracts audio from the video, reads duration/resolution/fps |
| 2 | `transcribe.py` | Runs Whisper on the audio, returns word-level timestamps |
| 3 | `highlights.py` | Scores transcript windows and picks the best non-overlapping set |
| 4 | `refine.py` | Snaps each highlight's start/end to the nearest silence, so cuts land cleanly |

**Phase B — rendering (runs once per selected highlight):**

| # | File | What it does |
|---|---|---|
| 5 | `clip.py` | Cuts that exact window into a standalone clip (frame-accurate) |
| 6 | `reframe.py` | Converts to vertical 9:16 — center crop, or face-tracking crop |
| 7 | `captions.py` | Groups words into on-screen chunks and burns them in |
| 8 | `package.py` | Normalizes to final 1080x1920 / H.264+AAC, generates a thumbnail |

**Orchestration:**

| File | What it does |
|---|---|
| `pipeline.py` | CLI — runs the full chain end to end from the terminal |
| `app.py` | Streamlit UI — same chain, with a highlight picker and preview/download step |
| `config.py` | Central ffmpeg/ffprobe binary config, shared error handling used by every module that shells out to ffmpeg |

Both `pipeline.py` and `app.py` are thin orchestrators — neither duplicates
pipeline logic, they just call the same eight functions in order. A fix to
any one module automatically applies whether you're using the terminal or
the browser.

## Running locally

**1. Clone the repository**
```
git clone https://github.com/<your-username>/ai-shorts-clipper.git
cd ai-shorts-clipper
```

**2. Create and activate a virtual environment**

Keeps this project's Python packages isolated from your system Python.

macOS/Linux:
```
python3 -m venv venv
source venv/bin/activate
```
Windows (PowerShell):
```
python -m venv venv
.\venv\Scripts\activate
```
You'll know it worked if your terminal prompt now starts with `(venv)`.

**3. Install ffmpeg**

The project shells out to `ffmpeg`/`ffprobe` for every video/audio
operation, so this has to be installed separately from the Python
packages — `pip` can't install it for you.

- **Windows:** download the "essentials" build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/), extract it somewhere permanent (e.g. `C:\ffmpeg`), then add the inner `bin` folder (the one that directly contains `ffmpeg.exe`) to your PATH via Environment Variables. **Close and reopen your terminal completely afterward** — PATH changes don't apply to already-open terminal windows, which is the single most common thing that trips people up here.
- **macOS:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg` (Debian/Ubuntu) or your distro's equivalent

Verify it worked before moving on:
```
ffmpeg -version
ffprobe -version
```
Both should print version info, not a "command not found" error.

**4. Install the Python dependencies**
```
pip install -r requirements.txt
```
This pulls in `faster-whisper`, `pydub`, `opencv-contrib-python`, and
`streamlit`. On the first run of the app, `faster-whisper` will also
separately download the Whisper model weights from Hugging Face —
that happens automatically the first time you transcribe something, not
during this install step.

**5. (Windows only, if needed) Fix `pydub`'s missing `audioop` module**

Python 3.13+ removed the built-in `audioop` module that `pydub` depends
on, which breaks `pydub` with an import error. If you hit this:
```
pip install audioop-lts
```

**6. Run the app**
```
streamlit run app.py
```
This opens the app in your browser automatically (usually at
`http://localhost:8501`). See [Usage](#usage) below for what to do next.

**If ffmpeg keeps getting lost across terminals/IDEs:** open `config.py`
and hardcode `FFMPEG_BIN` / `FFPROBE_BIN` to the exact `.exe` paths
(find them with `where.exe ffmpeg` on Windows or `which ffmpeg` on
Mac/Linux). Every module reads from this one place, so it fixes the
problem everywhere at once instead of per-file.

## Usage

**Interactive app (recommended):**
```
streamlit run app.py
```
Upload a video, click **Analyze video**, review the detected highlights
(each shown with its score and transcript text), uncheck any you don't
want, click **Generate shorts**, then preview and download each one.

**CLI (no UI):**
```
python pipeline.py path/to/video.mp4
python pipeline.py path/to/video.mp4 --reframe face --no-captions
python pipeline.py path/to/video.mp4 --model small --top-k 3 --min-dur 15 --max-dur 20
```

| Flag | Default | Description |
|---|---|---|
| `--model` | `base` | Whisper model size: `tiny`, `base`, `small`, `medium` |
| `--top-k` | `5` | Number of highlights to select |
| `--min-dur` / `--max-dur` | `15` / `20` | Target clip length range, in seconds |
| `--reframe` | `center` | `none`, `center`, or `face` |
| `--no-captions` | off | Skip burning in captions |
| `--output-dir` | `output` | Where to save final shorts |

Start with `--model tiny` (or the "tiny" option in the app's sidebar) on
your first run to confirm everything works end to end quickly — it
downloads and runs much faster than `base`/`small`, which is worth doing
before committing to a slower model on a long video.

## Troubleshooting

A few real issues hit while building this, documented here since they'll
likely trip up anyone else running it fresh:

- **`cv2` has no attribute `CascadeClassifier`** — OpenCV 5.0 moved
  Haar-cascade face detection into `opencv-contrib-python`. Fixed by
  installing that package instead of plain `opencv-python`
  (`requirements.txt` already reflects this).
- **`CascadeClassifier::detectMultiScale` empty() assertion** — a separate,
  currently-open packaging bug ([opencv-python#1244](https://github.com/opencv/opencv-python/issues/1244))
  where some OpenCV 5.x wheels ship with an empty data directory, so the
  bundled cascade file never loads. Fixed by bundling
  `haarcascade_frontalface_default.xml` directly in this repo instead of
  relying on the package's own copy.
- **ffmpeg "not recognized" / WinError 2** — almost always a stale
  terminal/IDE session that started before PATH was updated. Close and
  reopen the terminal (or IDE) completely, not just the tab.
- **`pydub`/`pyaudioop` import error on Python 3.13+** — Python removed
  the `audioop` module that `pydub` depends on. Fixed with
  `pip install audioop-lts`.
- **Transcription seems stuck** — check CPU usage first: if it's actively
  busy (not 0%), it's genuinely working, just slow on CPU. If it's been
  stuck for 15+ minutes with low/no CPU activity, it's most likely the
  Whisper model download being blocked by a firewall — run `diagnose.py`
  for a fast, isolated test with debug logging that pinpoints exactly
  where it's stalling.

## Notes on the AI components

**Highlight scoring (`highlights.py`)** is currently a rule-based
heuristic — punctuation, keyword hits, numbers, and speaking pace — not a
pretrained model. There's a `score_windows_llm()` stub for swapping in an
actual LLM-based scorer, which is the more "AI" version of this step if
you want to extend it further.

**Face tracking (`reframe.py`)** uses classic Haar-cascade detection
rather than a modern DNN-based detector — fast and dependency-light, but
less robust on angled faces or busy backgrounds than something like a
YuNet or MediaPipe-based detector would be.

## License

MIT