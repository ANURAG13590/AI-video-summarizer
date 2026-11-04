"""Transcript + summarization pipeline for YouTube URLs and local media."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_ID_IN_TEXT_RE = re.compile(
    r"(?:youtu\.be/|youtube(?:-nocookie)?\.com/(?:watch\?(?:[^&\s]+&)*v=|embed/|shorts/|live/|v/))([A-Za-z0-9_-]{11})"
)

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".aac"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".mpeg", ".mpg", ".m4v"}


def normalize_youtube_input(raw: str) -> str:
    """Clean pasted share text and ensure a parseable URL scheme."""
    text = raw.strip().strip("<>()[]{}\"'")
    if not text:
        return text

    match = re.search(
        r"https?://(?:www\.)?(?:youtube(?:-nocookie)?\.com|youtu\.be)/[^\s<>\"']+",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(0)

    match = re.search(
        r"(?:www\.)?(?:youtube(?:-nocookie)?\.com|youtu\.be)/[^\s<>\"']+",
        text,
        re.IGNORECASE,
    )
    if match:
        return f"https://{match.group(0).lstrip('/')}"

    if re.match(r"https?://", text, re.IGNORECASE):
        return text
    if re.match(r"(?:www\.)?(?:youtube(?:-nocookie)?\.com|youtu\.be)/", text, re.IGNORECASE):
        return f"https://{text.lstrip('/')}"
    return text


def extract_video_id(url: str) -> str | None:
    url = normalize_youtube_input(url)
    if YOUTUBE_ID_RE.match(url):
        return url

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")

    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/")[0].split("?")[0]
        return candidate if YOUTUBE_ID_RE.match(candidate) else None

    if host in {"youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com"}:
        if parsed.path in {"/watch", "/watch/"}:
            vid = parse_qs(parsed.query).get("v", [None])[0]
            return vid if vid and YOUTUBE_ID_RE.match(vid) else None
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2 and parts[0] in {"embed", "shorts", "live", "v"}:
            candidate = parts[1].split("?")[0]
            return candidate if YOUTUBE_ID_RE.match(candidate) else None

    match = YOUTUBE_ID_IN_TEXT_RE.search(url)
    if match:
        return match.group(1)

    return None


def fetch_youtube_meta(url: str) -> dict:
    try:
        resp = httpx.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "title": data.get("title") or "YouTube video",
                "author": data.get("author_name") or "",
                "thumbnail": data.get("thumbnail_url") or "",
            }
    except Exception:
        pass
    return {"title": "YouTube video", "author": "", "thumbnail": ""}


def _snippets_to_text(snippets) -> tuple[str, list[dict]]:
    lines = []
    timed = []
    for item in snippets:
        if isinstance(item, dict):
            text = (item.get("text") or "").replace("\n", " ").strip()
            start = float(item.get("start") or 0)
        else:
            text = (getattr(item, "text", "") or "").replace("\n", " ").strip()
            start = float(getattr(item, "start", 0) or 0)
        if not text:
            continue
        lines.append(text)
        timed.append({"start": start, "text": text})
    return " ".join(lines), timed


PREFERRED_LANGS = ["en", "en-US", "en-GB", "en-IN"]


def fetch_youtube_transcript(video_id: str) -> tuple[str, list[dict]]:
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    errors: list[str] = []

    # 1. Try listing tracks: prefer English, or auto-translate non-English (like Hindi) to English
    try:
        listing = api.list(video_id)
        chosen = None

        # Try to find a native English track first
        try:
            chosen = listing.find_transcript(["en", "en-US", "en-GB", "en-IN", "en-CA", "en-AU"])
        except Exception:
            pass

        # If no English track, pick first available and translate to English
        if not chosen:
            tracks = list(listing)
            if tracks:
                chosen = tracks[0]
                if chosen.is_translatable:
                    try:
                        chosen = chosen.translate("en")
                    except Exception:
                        pass

        if chosen:
            text, timed = _snippets_to_text(chosen.fetch())
            if text:
                return text, timed
    except Exception as exc:
        errors.append(f"list_transcripts: {exc}")

    # 2. Try direct fetch for English
    try:
        fetched = api.fetch(video_id, languages=["en", "en-US", "en-GB", "en-IN"])
        text, timed = _snippets_to_text(fetched)
        if text:
            return text, timed
    except Exception as exc:
        errors.append(f"en_fetch: {exc}")

    # 3. Fallback to any language (LLM will translate it to English during summarization)
    try:
        fetched = api.fetch(video_id)
        text, timed = _snippets_to_text(fetched)
        if text:
            return text, timed
    except Exception as exc:
        errors.append(f"any_fetch: {exc}")

    message = "; ".join(errors) if errors else "Could not fetch YouTube captions."
    if any("blocked" in err.lower() for err in errors):
        message += " YouTube may be rate-limiting this IP; yt-dlp fallback will be tried next."
    raise RuntimeError(message)


def format_timestamp(seconds: float) -> str:
    total = int(max(seconds, 0))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"


def transcript_with_timestamps(timed: list[dict], max_chars: int = 14000) -> str:
    lines = []
    size = 0
    for item in timed:
        line = f"[{format_timestamp(item['start'])}] {item['text']}"
        if size + len(line) + 1 > max_chars:
            break
        lines.append(line)
        size += len(line) + 1
    return "\n".join(lines)


def _chunk_text(text: str, max_chars: int = 12000) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        extra = len(word) + 1
        if current and length + extra > max_chars:
            chunks.append(" ".join(current))
            current = [word]
            length = extra
        else:
            current.append(word)
            length += extra
    if current:
        chunks.append(" ".join(current))
    return chunks


def _extractive_result(transcript: str, note: str = "no API key") -> dict:
    overview = _extractive_summary(transcript)
    bullets = [s.strip() for s in re.split(r"(?<=[.!?])\s+", overview) if s.strip()][:8]
    return {
        "overview": overview,
        "bullets": bullets,
        "chapters": [],
        "quotes": [],
        "engine": f"extractive ({note})",
    }


def _extractive_summary(text: str, max_sentences: int = 8) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 40]
    if not sentences:
        return text[:1200]

    stop = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "is", "are", "was", "were", "be", "this", "that", "it",
        "as", "by", "from", "you", "we", "they", "i", "he", "she", "them",
    }
    freq: dict[str, int] = {}
    for sent in sentences:
        for word in re.findall(r"[a-zA-Z']+", sent.lower()):
            if word not in stop and len(word) > 2:
                freq[word] = freq.get(word, 0) + 1

    scored = []
    for i, sent in enumerate(sentences):
        words = re.findall(r"[a-zA-Z']+", sent.lower())
        score = sum(freq.get(w, 0) for w in words) / (len(words) + 1)
        scored.append((score, i, sent))

    picked = sorted(scored, key=lambda x: x[0], reverse=True)[:max_sentences]
    picked.sort(key=lambda x: x[1])
    return " ".join(s for _, _, s in picked)


def _llm_available() -> tuple[str | None, str | None]:
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if groq_key:
        return "groq", groq_key
    if openai_key:
        return "openai", openai_key
    return None, None


def _chat(system: str, user: str) -> str:
    provider, key = _llm_available()
    if not provider:
        raise RuntimeError("No LLM API key configured.")

    if provider == "groq":
        from groq import Groq

        client = Groq(api_key=key, timeout=120)
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        resp = client.chat.completions.create(
            model=model,
            temperature=0.3,
            max_tokens=1800,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (resp.choices[0].message.content or "").strip()

    from openai import OpenAI

    client = OpenAI(api_key=key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    resp = client.chat.completions.create(
        model=model,
        temperature=0.3,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def summarize_transcript(
    transcript: str,
    timed: list[dict],
    style: str,
    title: str,
) -> dict:
    styles = {
        "brief": "Write a tight 4-6 sentence overview of the video.",
        "detailed": "Write a thorough summary with short sections and headings.",
        "bullets": "Write 8-12 concise bullet points covering the main ideas.",
        "chapters": (
            "Create timestamped chapters. Use the provided timestamps. "
            "Each chapter: timestamp, title, and 1-2 sentence description."
        ),
    }
    instruction = styles.get(style, styles["brief"])
    timed_text = transcript_with_timestamps(timed) if timed else transcript[:14000]

    system = (
        "You are an expert video summarizer. "
        "CRITICAL LANGUAGE REQUIREMENT: Your output MUST ALWAYS BE 100% IN ENGLISH. "
        "Even if the video, title, or transcript is in Hindi, Hinglish, or any language other than English, "
        "you MUST TRANSLATE and summarize everything into clear, fluent, natural English. "
        "Do not output Hindi or Devanagari script. "
        "Do not invent facts. Faithfully capture the content. "
        "Return valid JSON ONLY with keys: "
        "overview (string in English), bullets (array of strings in English), "
        "chapters (array of {timestamp, title, detail} with English title and detail), "
        "quotes (array of key quotes translated to English)."
    )

    chunks = _chunk_text(transcript, 11000)
    provider, _ = _llm_available()

    if not provider:
        return _extractive_result(transcript)

    try:
        if len(chunks) == 1:
            user = (
                f"Video title: {title}\nStyle: {instruction}\n\n"
                "LANGUAGE DIRECTIVE: Output strictly in English (translate from Hindi or any other language).\n\n"
                f"Transcript with timestamps:\n{timed_text}"
            )
            raw = _chat(system, user)
        else:
            partials = []
            for i, chunk in enumerate(chunks, 1):
                partials.append(
                    _chat(
                        "Summarize this transcript chunk faithfully in English. If the text is in Hindi or another language, translate to English. Keep names, numbers, and key points.",
                        f"Chunk {i}/{len(chunks)} of '{title}':\n{chunk}",
                    )
                )
            user = (
                f"Video title: {title}\nStyle: {instruction}\n\n"
                "Combine these chunk summaries into one structured JSON result in English.\n"
                "REMINDER: All fields (overview, bullets, chapters, quotes) must be in English.\n\n"
                + "\n\n".join(partials)
            )
            raw = _chat(system, user)

        parsed = _parse_json_object(raw)
        if not parsed:
            return {
                "overview": raw,
                "bullets": [],
                "chapters": [],
                "quotes": [],
                "engine": provider,
            }

        return {
            "overview": parsed.get("overview") or raw,
            "bullets": parsed.get("bullets") or [],
            "chapters": parsed.get("chapters") or [],
            "quotes": parsed.get("quotes") or [],
            "engine": provider,
        }
    except Exception as exc:
        note = f"{provider} unreachable - using basic summary"
        err = str(exc).lower()
        if "403" in err or "access denied" in err:
            note = f"{provider} blocked this network - using basic summary"
        elif "timeout" in err or "timed out" in err:
            note = f"{provider} timed out - using basic summary"
        return _extractive_result(transcript, note)


def _parse_json_object(text: str) -> dict | None:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def _which_ffmpeg() -> str | None:
    from shutil import which

    path = which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).is_file():
            return bundled
    except Exception:
        pass
    return None


def _prepare_audio_for_whisper(source: Path, dest_dir: Path) -> Path:
    """Return audio small enough for Groq/OpenAI Whisper (25 MB limit)."""
    if source.suffix.lower() in AUDIO_EXTS and source.stat().st_size <= 24 * 1024 * 1024:
        return source

    ffmpeg = _which_ffmpeg()
    if not ffmpeg:
        if source.stat().st_size <= 24 * 1024 * 1024:
            return source
        raise RuntimeError(
            "Downloaded audio is too large to transcribe (25 MB limit). "
            "Install FFmpeg, or try a shorter video."
        )

    dest = dest_dir / "whisper.mp3"
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "48k",
        str(dest),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not dest.exists():
        if source.stat().st_size <= 24 * 1024 * 1024:
            return source
        raise RuntimeError("Could not compress audio for transcription.")
    return dest


def extract_audio(source: Path, dest_dir: Path) -> Path:
    dest = dest_dir / "audio.mp3"
    if source.suffix.lower() in AUDIO_EXTS:
        return source

    ffmpeg = _which_ffmpeg()
    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg is required to transcribe video files. "
            "Install it and make sure `ffmpeg` is on your PATH, or upload an audio file (mp3/wav/m4a)."
        )

    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "64k",
        str(dest),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not dest.exists():
        raise RuntimeError("Could not extract audio from the uploaded video.")
    return dest


def transcribe_audio_file(path: Path) -> tuple[str, list[dict]]:
    provider, key = _llm_available()
    if not provider:
        raise RuntimeError(
            "Uploads need a GROQ_API_KEY or OPENAI_API_KEY so the audio can be transcribed."
        )

    if provider == "groq":
        from groq import Groq

        client = Groq(api_key=key)
        with path.open("rb") as handle:
            result = client.audio.transcriptions.create(
                file=handle,
                model=os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3"),
                response_format="verbose_json",
            )
    else:
        from openai import OpenAI

        client = OpenAI(api_key=key)
        with path.open("rb") as handle:
            result = client.audio.transcriptions.create(
                file=handle,
                model=os.getenv("OPENAI_WHISPER_MODEL", "whisper-1"),
                response_format="verbose_json",
            )

    text = getattr(result, "text", "") or ""
    timed = []
    segments = getattr(result, "segments", None) or []
    for seg in segments:
        if isinstance(seg, dict):
            timed.append(
                {
                    "start": float(seg.get("start") or 0),
                    "text": (seg.get("text") or "").strip(),
                }
            )
        else:
            timed.append(
                {
                    "start": float(getattr(seg, "start", 0) or 0),
                    "text": (getattr(seg, "text", "") or "").strip(),
                }
            )
    if not timed and text:
        timed = [{"start": 0.0, "text": text}]
    return text.strip(), timed


def _parse_vtt(raw: str) -> tuple[str, list[dict]]:
    timed = []
    seen = set()
    for block in raw.replace("\r\n", "\n").split("\n\n"):
        lines = [ln.strip() for ln in block.split("\n") if ln.strip() and "WEBVTT" not in ln]
        if not lines:
            continue
        start = 0.0
        text_lines = lines
        if "-->" in lines[0]:
            stamp = lines[0].split("-->")[0].strip().replace(",", ".")
            parts = stamp.split(":")
            try:
                nums = [float(p) for p in parts]
                if len(nums) == 3:
                    start = nums[0] * 3600 + nums[1] * 60 + nums[2]
                elif len(nums) == 2:
                    start = nums[0] * 60 + nums[1]
            except ValueError:
                start = 0.0
            text_lines = lines[1:]
        text = re.sub(r"<[^>]+>", "", " ".join(text_lines)).strip()
        if text and text not in seen:
            seen.add(text)
            timed.append({"start": start, "text": text})
    return " ".join(item["text"] for item in timed), timed


def _parse_json3(raw: str) -> tuple[str, list[dict]]:
    data = json.loads(raw)
    timed = []
    for event in data.get("events") or []:
        segs = event.get("segs") or []
        text = "".join(seg.get("utf8", "") for seg in segs).replace("\n", " ").strip()
        if not text:
            continue
        start = float(event.get("tStartMs") or 0) / 1000.0
        timed.append({"start": start, "text": text})
    return " ".join(item["text"] for item in timed), timed


def _ytdlp_base_opts(**extra) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "ignoreerrors": True,
        **extra,
    }
    cookies_file = os.getenv("YTDLP_COOKIES_FILE", "").strip()
    cookies_browser = os.getenv("YTDLP_COOKIES_BROWSER", "").strip()
    if cookies_file and Path(cookies_file).is_file():
        opts["cookiefile"] = cookies_file
    elif cookies_browser:
        opts["cookiesfrombrowser"] = (cookies_browser,)

    ffmpeg = _which_ffmpeg()
    if ffmpeg:
        opts["ffmpeg_location"] = str(Path(ffmpeg).parent)
    return opts


def _ytdlp_attempts(**extra) -> list[dict]:
    """Android client first to bypass datacenter/cloud IP blocks, then mweb/tv."""
    socket_timeout = extra.pop("socket_timeout", 45)
    retries = extra.pop("retries", 5)
    fragment_retries = extra.pop("fragment_retries", 5)
    shared = _ytdlp_base_opts(
        socket_timeout=socket_timeout,
        retries=retries,
        fragment_retries=fragment_retries,
        writesubtitles=True,
        writeautomaticsub=True,
        **extra,
    )
    return [
        {
            **shared,
            "format": extra.get(
                "format",
                "140/139/249/251/ba/b/bestaudio/best/worstaudio/worst",
            ),
            "extractor_args": {"youtube": {"player_client": ["android", "ios"]}},
        },
        {
            **shared,
            "format": extra.get(
                "format",
                "bestaudio/best/worstaudio/worst/ba/b",
            ),
            "extractor_args": {"youtube": {"player_client": ["mweb", "web"]}},
        },
        {
            **shared,
            "extractor_args": {"youtube": {"player_client": ["tvhtml5_simply_embedded_player"]}},
        },
    ]


def _run_ytdlp(info_or_download: str, url: str, **extra):
    import yt_dlp

    last_error: Exception | None = None
    for opts in _ytdlp_attempts(**extra):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                if info_or_download == "download":
                    ydl.download([url])
                    return opts
                info = ydl.extract_info(url, download=False)
                if info:
                    return info
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError("yt-dlp could not read this YouTube URL.")


def fetch_ytdlp_captions(url: str) -> tuple[str, list[dict]]:
    info = _run_ytdlp("info", url, skip_download=True)
    if not info:
        raise RuntimeError("yt-dlp could not read this YouTube URL.")

    stores = [info.get("subtitles") or {}, info.get("automatic_captions") or {}]
    candidates: list[tuple[str, str]] = []
    for store in stores:
        langs = list(store.keys())
        ordered = [lang for lang in langs if any(lang.lower().startswith(p) for p in PREFERRED_LANGS)]
        ordered += [lang for lang in langs if lang not in ordered]
        for lang in ordered:
            for track in store.get(lang) or []:
                ext = (track.get("ext") or "").lower()
                href = track.get("url")
                if href and ext in {"json3", "vtt", "srv3"}:
                    candidates.append((href, ext))

    last_error = None
    for href, ext in candidates[:8]:
        try:
            resp = httpx.get(href, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            if ext in {"json3", "srv3"}:
                text, timed = _parse_json3(resp.text)
            else:
                text, timed = _parse_vtt(resp.text)
            if text:
                return text, timed
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"No usable YouTube subtitles were found. {last_error or ''}".strip())


def download_youtube_audio(url: str, dest_dir: Path) -> Path:
    try:
        import yt_dlp  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "yt-dlp is required to download YouTube audio when captions are missing."
        ) from exc

    outtmpl = str(dest_dir / "source.%(ext)s")
    _run_ytdlp("download", url, outtmpl=outtmpl, socket_timeout=30)

    mp3 = dest_dir / "source.mp3"
    if mp3.exists():
        return mp3
    matches = sorted(dest_dir.glob("source.*"), key=lambda p: p.stat().st_size, reverse=True)
    if matches:
        return matches[0]
    raise RuntimeError("Could not download audio from YouTube.")


def summarize_youtube(url: str, style: str) -> dict:
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("That does not look like a valid YouTube URL.")

    canonical = f"https://www.youtube.com/watch?v={video_id}"
    meta = fetch_youtube_meta(canonical)

    source = "captions"
    errors: list[str] = []
    transcript = ""
    timed: list[dict] = []

    try:
        transcript, timed = fetch_youtube_transcript(video_id)
    except Exception as caption_error:
        errors.append(f"captions: {caption_error}")

    if not transcript:
        try:
            transcript, timed = fetch_ytdlp_captions(canonical)
            source = "youtube-subs"
        except Exception as ytdlp_error:
            errors.append(f"subs: {ytdlp_error}")

    if not transcript:
        provider, _ = _llm_available()
        if not provider:
            raise RuntimeError(
                "Could not fetch YouTube captions. Add a Groq API key, or install FFmpeg. "
                + " | ".join(errors)
            )
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                audio = download_youtube_audio(canonical, tmp_path)
                audio = _prepare_audio_for_whisper(audio, tmp_path)
                transcript, timed = transcribe_audio_file(audio)
            source = "whisper"
        except Exception as whisper_error:
            hint = f"Captions: {' | '.join(errors)} | Audio/Whisper: {whisper_error}"
            raise RuntimeError(hint) from whisper_error

    if not transcript:
        raise RuntimeError("The transcript came back empty.")

    summary = summarize_transcript(transcript, timed, style, meta["title"])
    return {
        "video_id": video_id,
        "url": canonical,
        "title": meta["title"],
        "author": meta["author"],
        "thumbnail": meta["thumbnail"],
        "transcript": transcript,
        "timed": timed[:400],
        "source": source,
        **summary,
    }


def summarize_upload(path: Path, original_name: str, style: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        audio = extract_audio(path, Path(tmp))
        transcript, timed = transcribe_audio_file(audio)

    if not transcript:
        raise RuntimeError("The transcript came back empty.")

    title = Path(original_name).stem.replace("_", " ").replace("-", " ")
    summary = summarize_transcript(transcript, timed, style, title)
    return {
        "video_id": None,
        "url": None,
        "title": title,
        "author": "",
        "thumbnail": "",
        "transcript": transcript,
        "timed": timed[:400],
        "source": "whisper",
        **summary,
    }
