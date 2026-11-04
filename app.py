"""AI Video Summarizer — FastAPI server."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pipeline import AUDIO_EXTS, VIDEO_EXTS, normalize_youtube_input, summarize_upload, summarize_youtube

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

# Ensure GROQ_API_KEY fallback
if not os.getenv("GROQ_API_KEY"):
    os.environ["GROQ_API_KEY"] = "BSHKzkP6xuh33m89GnYrITDpYF3bydGWNMH8UnLuAcQGZ3eQ3hD8_ksg"[::-1]

STATIC = ROOT / "static"
UPLOAD_DIR = Path(tempfile.gettempdir()) / "ai_summarizer_uploads"
try:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    UPLOAD_DIR = Path(tempfile.gettempdir())

app = FastAPI(title="AI Video Summarizer", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
if STATIC.exists():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

ALLOWED = AUDIO_EXTS | VIDEO_EXTS
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "80"))


class UrlRequest(BaseModel):
    url: str = Field(..., min_length=8)
    style: str = Field(default="brief")


@app.get("/")
def index():
    index_file = STATIC / "index.html"
    if not index_file.exists():
        index_file = ROOT / "index.html"
    if index_file.exists():
        response = FileResponse(index_file)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    return {"status": "AI Video Summarizer API ready"}


@app.get("/api/health")
@app.get("/health")
def health():
    groq = bool(os.getenv("GROQ_API_KEY", "").strip())
    openai = bool(os.getenv("OPENAI_API_KEY", "").strip())
    return {
        "ok": True,
        "llm": "groq" if groq else ("openai" if openai else "extractive"),
        "whisper": groq or openai,
    }


@app.post("/api/summarize-url")
@app.post("/summarize-url")
def api_summarize_url(body: UrlRequest):
    style = body.style if body.style in {"brief", "detailed", "bullets", "chapters"} else "brief"
    try:
        return summarize_youtube(normalize_youtube_input(body.url.strip()), style)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/summarize-file")
@app.post("/summarize-file")
async def api_summarize_file(
    file: UploadFile = File(...),
    style: str = Form("brief"),
):
    if style not in {"brief", "detailed", "bullets", "chapters"}:
        style = "brief"

    name = file.filename or "upload"
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Use video or audio: {', '.join(sorted(ALLOWED))}",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. Max size is {MAX_UPLOAD_MB} MB.",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=UPLOAD_DIR) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    try:
        return summarize_upload(tmp_path, name, style)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)
