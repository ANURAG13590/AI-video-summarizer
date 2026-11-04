# AI Video Summarizer

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/ANURAG13590/AI-video-summarizer)

Paste a YouTube URL or upload a local video/audio file. The app grabs a transcript, then writes an overview, key points, chapters, and quotes.

## 🚀 24/7 Cloud Deployment (Always Online)

Click the **Deploy to Render** button above, or follow these 3 steps:

1. Sign up / log in to [Render.com](https://render.com) (100% free tier).
2. Click **New +** → **Blueprint** → Connect your GitHub repository `ANURAG13590/AI-video-summarizer`.
3. Enter your `GROQ_API_KEY` when prompted and click **Apply**.

Render will deploy the app and give you a permanent public URL (e.g. `https://ai-video-summarizer.onrender.com`) that runs 24/7 without needing your computer on.

---

## How it works

1. **YouTube captions first** — no download if the video has subtitles.
2. **Whisper fallback** — if captions are missing, or you upload a file, audio is transcribed with Groq or OpenAI Whisper.
3. **LLM summary** — Groq Llama (default) or OpenAI.

## Local Setup

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Double click `start_public_tunnel.bat` to run locally with an instant public Cloudflare link.
