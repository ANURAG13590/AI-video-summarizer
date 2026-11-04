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

STATIC = ROOT / "static"
UPLOAD_DIR = Path(tempfile.gettempdir()) / "ai_summarizer_uploads"
try:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    UPLOAD_DIR = Path(tempfile.gettempdir())

app = FastAPI(title="AI Video Summarizer", version="1.0.0")

@app.middleware("http")
async def fix_vercel_path(request, call_next):
    matched = request.headers.get("x-matched-path")
    if matched and not matched.startswith("/api/index"):
        request.scope["path"] = matched
    else:
        raw_path = request.scope.get("path", "")
        for prefix in ["/api/index.py", "/api/index"]:
            if raw_path == prefix:
                request.scope["path"] = "/"
                break
            elif raw_path.startswith(prefix + "/"):
                request.scope["path"] = raw_path[len(prefix):]
                break
    response = await call_next(request)
    response.headers["X-Debug-Path"] = request.scope.get("path", "")
    return response

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
    groq = bool(os.getenv("GROQ_API_KEY", "").strip()) and os.getenv("GROQ_API_KEY") != "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"
    gemini = bool(os.getenv("GEMINI_API_KEY", "").strip())
    openai = bool(os.getenv("OPENAI_API_KEY", "").strip())
    if groq:
        llm = "groq"
    elif gemini:
        llm = "gemini"
    elif openai:
        llm = "openai"
    else:
        llm = "instant-clarity"
    return {
        "ok": True,
        "llm": llm,
        "whisper": bool(groq or gemini or openai),
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
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{ext}'. Upload audio ({', '.join(sorted(AUDIO_EXTS))}) or video ({', '.join(sorted(VIDEO_EXTS))}).",
        )

    dest = UPLOAD_DIR / filename
    total = 0
    with dest.open("wb") as handle:
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_UPLOAD_MB * 1024 * 1024:
                handle.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds the {MAX_UPLOAD_MB} MB limit.",
                )
            handle.write(chunk)

    try:
        return summarize_upload(dest, filename, style)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        dest.unlink(missing_ok=True)
