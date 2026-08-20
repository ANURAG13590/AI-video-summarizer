const urlForm = document.getElementById("urlForm");
const fileForm = document.getElementById("fileForm");
const progress = document.getElementById("progress");
const errorEl = document.getElementById("error");
const result = document.getElementById("result");
const engineStatus = document.getElementById("engineStatus");

let lastPayload = null;

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    const isUrl = tab.dataset.tab === "url";
    urlForm.classList.toggle("hidden", !isUrl);
    fileForm.classList.toggle("hidden", isUrl);
  });
});

async function loadHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    const whisper = data.whisper ? "Whisper ready" : "captions-only (add API key for uploads)";
    engineStatus.textContent = `Engine: ${data.llm} · ${whisper}`;
  } catch {
    engineStatus.textContent = "Engine: offline — start the server, then refresh";
  }
}

loadHealth();

function setBusy(busy, message) {
  progress.classList.toggle("hidden", !busy);
        progress.textContent = message || "Working — fetching captions and writing the summary.";
  errorEl.classList.add("hidden");
  urlForm.querySelector(".go").disabled = busy;
  fileForm.querySelector(".go").disabled = busy;
}

function showError(message) {
  errorEl.textContent = message;
  errorEl.classList.remove("hidden");
  result.classList.add("hidden");
}

function fillList(el, items, mapper) {
  el.innerHTML = "";
  (items || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = mapper ? mapper(item) : String(item);
    el.appendChild(li);
  });
}

function render(data) {
  lastPayload = data;
  result.classList.remove("hidden");
  document.getElementById("title").textContent = data.title || "Summary";
  const bits = [data.author, data.source ? `source: ${data.source}` : "", data.engine ? `model: ${data.engine}` : ""]
    .filter(Boolean);
  document.getElementById("sub").textContent = bits.join(" · ");

  const thumb = document.getElementById("thumb");
  if (data.thumbnail) {
    thumb.src = data.thumbnail;
    thumb.hidden = false;
  } else {
    thumb.hidden = true;
  }

  document.getElementById("overview").textContent = data.overview || "";
  fillList(document.getElementById("bullets"), data.bullets);

  const chaptersWrap = document.getElementById("chaptersWrap");
  const chapters = data.chapters || [];
  chaptersWrap.classList.toggle("hidden", chapters.length === 0);
  fillList(document.getElementById("chapters"), chapters, (ch) => {
    const ts = ch.timestamp || ch.start || "";
    const title = ch.title || "";
    const detail = ch.detail || ch.description || "";
    return [ts, title, detail].filter(Boolean).join(" — ");
  });

  const quotesWrap = document.getElementById("quotesWrap");
  const quotes = data.quotes || [];
  quotesWrap.classList.toggle("hidden", quotes.length === 0);
  fillList(document.getElementById("quotes"), quotes);

  document.getElementById("transcript").textContent = data.transcript || "";
  result.scrollIntoView({ behavior: "smooth", block: "start" });
}

function toMarkdown(data) {
  const lines = [`# ${data.title || "Video summary"}`, ""];
  if (data.url) lines.push(`Source: ${data.url}`, "");
  lines.push("## Overview", data.overview || "", "");
  if (data.bullets?.length) {
    lines.push("## Key points");
    data.bullets.forEach((b) => lines.push(`- ${b}`));
    lines.push("");
  }
  if (data.chapters?.length) {
    lines.push("## Chapters");
    data.chapters.forEach((ch) => {
      lines.push(`- ${ch.timestamp || ""} ${ch.title || ""} — ${ch.detail || ch.description || ""}`.trim());
    });
    lines.push("");
  }
  if (data.quotes?.length) {
    lines.push("## Quotes");
    data.quotes.forEach((q) => lines.push(`> ${q}`, ""));
  }
  lines.push("## Transcript", "", data.transcript || "");
  return lines.join("\n");
}

function formatDetail(detail) {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
  }
  return String(detail);
}

function friendlyError(err) {
  const message = err && err.message ? err.message : String(err);
  if (
    message === "Failed to fetch" ||
    message === "Load failed" ||
    message === "NetworkError when attempting to fetch resource." ||
    message.includes("NetworkError")
  ) {
    return "Connection failed. The app server is not running. In this folder run: uvicorn app:app --host 127.0.0.1 --port 8000 then open http://127.0.0.1:8000";
  }
  if (/403|access denied|network settings/i.test(message)) {
    return "Groq/OpenAI blocked this request (403). Check your API key in .env, or try another network/VPN. Captions may still work if the server falls back to a basic summary.";
  }
  if (/valid YouTube URL/i.test(message)) {
    return message + " Paste the full link from the address bar or Share button.";
  }
  return message;
}

function normalizeYouTubeInput(raw) {
  let text = raw.trim().replace(/^[\s<(\[{]+|[\s>)\]}]+$/g, "");
  const httpMatch = text.match(
    /https?:\/\/(?:www\.)?(?:youtube(?:-nocookie)?\.com|youtu\.be)\/\S+/i
  );
  if (httpMatch) return httpMatch[0];

  const bareMatch = text.match(
    /(?:www\.)?(?:youtube(?:-nocookie)?\.com|youtu\.be)\/\S+/i
  );
  if (bareMatch) return `https://${bareMatch[0].replace(/^\/+/, "")}`;

  if (/^https?:\/\//i.test(text)) return text;
  if (/^(?:www\.)?(?:youtube(?:-nocookie)?\.com|youtu\.be)\//i.test(text)) {
    return `https://${text.replace(/^\/+/, "")}`;
  }
  return text;
}

function looksLikeYouTubeUrl(value) {
  const normalized = normalizeYouTubeInput(value);
  if (/^[A-Za-z0-9_-]{11}$/.test(normalized)) return true;
  return /(?:youtube(?:-nocookie)?\.com|youtu\.be)/i.test(normalized);
}

async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(formatDetail(data.detail) || "Request failed");
  return data;
}

urlForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const rawUrl = document.getElementById("url").value;
  const url = normalizeYouTubeInput(rawUrl);
  if (!looksLikeYouTubeUrl(url)) {
    showError("Paste a YouTube link (watch, shorts, or youtu.be). Example: https://www.youtube.com/watch?v=…");
    return;
  }
  setBusy(true, "Fetching captions and writing the summary — long videos without subtitles can take a few minutes…");
  try {
    const style = urlForm.querySelector('input[name="style"]:checked').value;
    const data = await postJson("/api/summarize-url", {
      url,
      style,
    });
    render(data);
  } catch (err) {
    showError(friendlyError(err));
  } finally {
    setBusy(false);
  }
});

fileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = document.getElementById("file").files[0];
  if (!file) return;
  setBusy(true, "Transcribing audio, then writing the brief…");
  try {
    const style = fileForm.querySelector('input[name="fileStyle"]:checked').value;
    const form = new FormData();
    form.append("file", file);
    form.append("style", style);
    const res = await fetch("/api/summarize-file", { method: "POST", body: form });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(formatDetail(data.detail) || "Upload failed");
    render(data);
  } catch (err) {
    showError(friendlyError(err));
  } finally {
    setBusy(false);
  }
});

document.getElementById("copyBtn").addEventListener("click", async () => {
  if (!lastPayload) return;
  await navigator.clipboard.writeText(toMarkdown(lastPayload));
  document.getElementById("copyBtn").textContent = "Copied";
  setTimeout(() => {
    document.getElementById("copyBtn").textContent = "Copy summary";
  }, 1400);
});

document.getElementById("downloadBtn").addEventListener("click", () => {
  if (!lastPayload) return;
  const blob = new Blob([toMarkdown(lastPayload)], { type: "text/markdown" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${(lastPayload.title || "summary").replace(/[^\w\-]+/g, "_").slice(0, 60)}.md`;
  a.click();
  URL.revokeObjectURL(a.href);
});
