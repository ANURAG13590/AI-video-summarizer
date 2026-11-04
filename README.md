---
title: AI Video Summarizer
emoji: 🎬
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
---

# AI Video Summarizer

Paste a YouTube URL or upload a local video/audio file. The app grabs a transcript, then writes an overview, key points, chapters, and quotes.

## 🚀 100% Free 24/7 Hosting on Hugging Face Spaces (No Credit Card Required)

1. Open [huggingface.co/new-space](https://huggingface.co/new-space)
2. Choose a name: `ai-video-summarizer`
3. Under **Space SDK**, select **Docker**
4. Under **Space hardware**, select **Free (CPU basic · 2 vCPU · 16GB RAM)**
5. Connect your GitHub repository `ANURAG13590/AI-video-summarizer`
6. Add `GROQ_API_KEY` under **Settings** → **Variables and secrets**
7. Your permanent 24/7 URL will be: `https://<your-username>-ai-video-summarizer.hf.space`

---

## Local Setup

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Double click `start_public_tunnel.bat` to run locally with an instant public Cloudflare link.
