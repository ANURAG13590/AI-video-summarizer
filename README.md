# AI Video Summarizer

Paste a YouTube URL or upload a local video/audio file. The app grabs a transcript, then writes an overview, key points, chapters, and quotes.

## How it works

1. **YouTube captions first** — no download if the video has subtitles.
2. **Whisper fallback** — if captions are missing, or you upload a file, audio is transcribed with Groq or OpenAI.
3. **LLM summary** — Groq Llama (default) or OpenAI. Without an API key, YouTube captions still get a basic extractive summary.

## Setup

```bash
cd "c:\Users\avadh\OneDrive\Documents\anu\AI video Summarizer"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and add a [Groq](https://console.groq.com) API key (free tier works well).

For local **video** uploads, install [FFmpeg](https://ffmpeg.org/download.html) and keep `ffmpeg` on your PATH. Audio files (mp3/wav/m4a) do not need FFmpeg.

## Run

```bash
uvicorn app:app --reload --port 8000
```

Open http://127.0.0.1:8000

## Styles

- **Brief** — short overview
- **Detailed** — sectioned write-up
- **Bullets** — main ideas
- **Chapters** — timestamped outline
