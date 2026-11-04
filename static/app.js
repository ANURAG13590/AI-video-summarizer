/* ─── DOM refs ─── */
const urlForm      = document.getElementById("urlForm");
const fileForm     = document.getElementById("fileForm");
const progressWrap = document.getElementById("progressWrap");
const progress     = document.getElementById("progress");
const errorEl      = document.getElementById("error");
const result       = document.getElementById("result");
const engineStatus = document.getElementById("engineStatus");
const dropZone     = document.getElementById("dropZone");
const fileInput    = document.getElementById("file");

let lastPayload = null;

/* ─── Tab switching ─── */
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    const isUrl = tab.dataset.tab === "url";
    urlForm.classList.toggle("hidden", !isUrl);
    fileForm.classList.toggle("hidden", isUrl);
  });
});

/* ─── Hamburger menu ─── */
const hamburger = document.getElementById("navHamburger");
const navLinks  = document.querySelector(".nav-links");
if (hamburger && navLinks) {
  hamburger.addEventListener("click", () => {
    const open = navLinks.style.display === "flex";
    navLinks.style.cssText = open
      ? ""
      : "display:flex;flex-direction:column;position:absolute;top:60px;left:0;right:0;background:rgba(0,0,0,.95);backdrop-filter:blur(20px);padding:16px 24px 24px;gap:4px;border-bottom:1px solid rgba(255,255,255,.08);z-index:99";
  });
}

/* ─── Smooth nav shadow on scroll ─── */
const nav = document.getElementById("nav");
window.addEventListener("scroll", () => {
  nav.style.background = window.scrollY > 10
    ? "rgba(0,0,0,.88)"
    : "rgba(0,0,0,.72)";
}, { passive: true });

/* ─── Scroll reveal ─── */
const observer = new IntersectionObserver(
  (entries) => entries.forEach((e) => {
    if (e.isIntersecting) { e.target.classList.add("visible"); observer.unobserve(e.target); }
  }),
  { threshold: 0.12 }
);
document.querySelectorAll(".feature-card, .step, .card-mock").forEach((el) => {
  el.classList.add("reveal");
  observer.observe(el);
});

/* ─── Drag & drop on file drop zone ─── */
if (dropZone) {
  ["dragenter","dragover"].forEach((evt) => {
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropZone.classList.add("dragover");
    });
  });
  ["dragleave","drop"].forEach((evt) => {
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropZone.classList.remove("dragover");
    });
  });
  dropZone.addEventListener("drop", (e) => {
    const dt = e.dataTransfer;
    if (dt && dt.files.length) {
      const transfer = new DataTransfer();
      transfer.items.add(dt.files[0]);
      fileInput.files = transfer.files;
      updateFileLabel(dt.files[0].name);
    }
  });
}

fileInput && fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) updateFileLabel(fileInput.files[0].name);
});
function updateFileLabel(name) {
  const lbl = document.getElementById("fileLabel");
  if (lbl) lbl.textContent = name;
}

/* ─── 24/7 Cloud API URL Resolution ─── */
const CLOUD_BACKENDS = [
  "https://ai-video-summarizer-qx.vercel.app",
  "https://ai-video-summarizer-zv8y.vercel.app"
];
let activeBackend = CLOUD_BACKENDS[0];

function getApiUrl(endpoint) {
  // If opened directly on Vercel or localhost, use relative path
  if (!window.location.hostname.endsWith("github.io")) {
    return endpoint;
  }
  const custom = localStorage.getItem("ai_backend_url");
  if (custom) return custom.replace(/\/+$/, "") + endpoint;
  return activeBackend + endpoint;
}

/* ─── Engine health ─── */
async function loadHealth() {
  // If not on GitHub Pages, just check local/relative
  if (!window.location.hostname.endsWith("github.io")) {
    try {
      const res = await fetch("/api/health");
      const data = await res.json();
      updateHealthUI(data);
      return;
    } catch (e) {
      // fallback
    }
  }

  // If custom backend set
  const custom = localStorage.getItem("ai_backend_url");
  if (custom) {
    try {
      const res = await fetch(custom.replace(/\/+$/, "") + "/api/health");
      const data = await res.json();
      updateHealthUI(data);
      return;
    } catch (e) {}
  }

  // Try cloud backends with auto-failover
  for (const b of CLOUD_BACKENDS) {
    try {
      const res = await fetch(b + "/api/health", { signal: AbortSignal.timeout(4000) });
      if (res.ok) {
        const data = await res.json();
        activeBackend = b;
        updateHealthUI(data);
        return;
      }
    } catch (err) {}
  }

  showOfflineUI();
}

function updateHealthUI(data) {
  const whisper = data.whisper
    ? "Whisper ready"
    : "instant-clarity";
  engineStatus.textContent = `Cloud Engine: ${data.llm} · 24/7 Active`;
  const navBadge = document.getElementById("navStatusBadge");
  if (navBadge) navBadge.textContent = `24/7 Cloud Active`;
}

function showOfflineUI() {
  engineStatus.innerHTML = `Engine: offline — <a href="javascript:void(0)" id="setBackendLink" style="color:var(--apple-cyan);text-decoration:underline;cursor:pointer;">Connect backend URL</a>`;
  const navBadge = document.getElementById("navStatusBadge");
  if (navBadge) navBadge.textContent = "Engine Offline";
  const link = document.getElementById("setBackendLink");
  if (link) {
    link.onclick = (e) => {
      e.preventDefault();
      const current = localStorage.getItem("ai_backend_url") || "";
      const entered = prompt("Enter your live backend URL (leave blank for default 24/7 cloud):", current);
      if (entered !== null) {
        if (entered.trim()) {
          localStorage.setItem("ai_backend_url", entered.trim());
        } else {
          localStorage.removeItem("ai_backend_url");
        }
        loadHealth();
      }
    };
  }
}
loadHealth();

/* ─── Busy state ─── */
function setBusy(busy, message) {
  progressWrap.classList.toggle("hidden", !busy);
  progress.textContent = message || "Working — fetching captions and writing the summary.";
  errorEl.classList.add("hidden");
  document.querySelectorAll(".go").forEach((b) => (b.disabled = busy));
}

/* ─── Error ─── */
function showError(message) {
  errorEl.textContent = message;
  errorEl.classList.remove("hidden");
  result.classList.add("hidden");
  errorEl.scrollIntoView({ behavior: "smooth", block: "center" });
}

/* ─── List helper ─── */
function fillList(el, items, mapper) {
  el.innerHTML = "";
  (items || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = mapper ? mapper(item) : String(item);
    el.appendChild(li);
  });
}

/* ─── Render result ─── */
function render(data) {
  lastPayload = data;
  result.classList.remove("hidden");

  document.getElementById("title").textContent = data.title || "Summary";
  const bits = [
    data.author,
    data.source  ? `source: ${data.source}`  : "",
    data.engine  ? `model: ${data.engine}`   : "",
  ].filter(Boolean);
  document.getElementById("sub").textContent = bits.join(" · ");

  const thumb = document.getElementById("thumb");
  if (data.thumbnail) { thumb.src = data.thumbnail; thumb.hidden = false; }
  else { thumb.hidden = true; }

  document.getElementById("overview").textContent = data.overview || "";
  fillList(document.getElementById("bullets"), data.bullets);

  const chaptersWrap = document.getElementById("chaptersWrap");
  const chapters     = data.chapters || [];
  chaptersWrap.classList.toggle("hidden", chapters.length === 0);
  fillList(document.getElementById("chapters"), chapters, (ch) => {
    const ts     = ch.timestamp || ch.start || "";
    const title  = ch.title || "";
    const detail = ch.detail || ch.description || "";
    return [ts, title, detail].filter(Boolean).join(" — ");
  });

  const quotesWrap = document.getElementById("quotesWrap");
  const quotes     = data.quotes || [];
  quotesWrap.classList.toggle("hidden", quotes.length === 0);
  fillList(document.getElementById("quotes"), quotes);

  document.getElementById("transcript").textContent = data.transcript || "";
  result.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ─── Markdown export ─── */
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

/* ─── Error helpers ─── */
function formatDetail(detail) {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((i) => i.msg || JSON.stringify(i)).join("; ");
  return String(detail);
}

function friendlyError(err) {
  const msg = err && err.message ? err.message : String(err);
  if (/bot|sign in to confirm|rate-limit/i.test(msg)) {
    return "YouTube is temporarily rate-limiting this video on cloud servers. Try another video, or upload the audio/video file directly.";
  }
  if (
    msg === "Failed to fetch" ||
    msg === "Load failed" ||
    msg.includes("NetworkError")
  ) {
    return "Connection to AI backend failed. Please wait a moment and try again.";
  }
  if (/403|access denied|network settings/i.test(msg)) {
    return "AI engine access error (403). Falling back to extractive summary.";
  }
  if (/valid YouTube URL/i.test(msg)) {
    return msg + " Paste the full link from the address bar or Share button.";
  }
  return msg;
}

/* ─── URL normalisation ─── */
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
  if (/^(?:www\.)?(?:youtube(?:-nocookie)?\.com|youtu\.be)\//i.test(text))
    return `https://${text.replace(/^\/+/, "")}`;
  return text;
}

function looksLikeYouTubeUrl(value) {
  const normalized = normalizeYouTubeInput(value);
  if (/^[A-Za-z0-9_-]{11}$/.test(normalized)) return true;
  return /(?:youtube(?:-nocookie)?\.com|youtu\.be)/i.test(normalized);
}

/* ─── API call ─── */
async function postJson(url, body) {
  const target = getApiUrl(url);
  const res  = await fetch(target, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {

    const data = await res.json().catch(() => ({}));
    throw new Error(formatDetail(data.detail) || `Request failed (${res.status})`);
  }
  const data = await res.json().catch(() => ({}));
  return data;
}

/* ─── Direct Google Gemini Multimodal Cloud Summarizer ─── */
async function summarizeWithGemini(apiKey, videoUrl, style) {
  const prompt = `You are an expert video summarizer.
Analyze this YouTube video: ${videoUrl}

Provide a comprehensive, high-quality structured summary in JSON format with exactly these keys:
{
  "title": "Exact or inferred title of the video",
  "author": "Channel or speaker name",
  "overview": "A clear, well-written executive summary paragraph capturing the essence of the video.",
  "bullets": [
    "Key insight or takeaway 1",
    "Key insight or takeaway 2",
    "Key insight or takeaway 3",
    "Key insight or takeaway 4",
    "Key insight or takeaway 5"
  ],
  "chapters": [
    {"timestamp": "0:00", "title": "Introduction & Context", "detail": "Summary of this section"},
    {"timestamp": "02:15", "title": "Core Discussion", "detail": "Key points discussed here"}
  ],
  "quotes": [
    "Memorable, impactful remark or quote from the video 1",
    "Important quote 2"
  ],
  "transcript": "Key excerpts or outline of spoken content."
}
Style requested: ${style}. Return ONLY valid parseable JSON. Do not include markdown code block markers or extra explanation.`;

  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`;
  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }]
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error?.message || `Gemini API error (${res.status})`);
  }
  const data = await res.json();
  const rawText = data.candidates?.[0]?.content?.parts?.[0]?.text || "";
  const cleaned = rawText.replace(/```(?:json)?\s*/gi, "").replace(/```\s*$/g, "").trim();
  const parsed = JSON.parse(cleaned);
  parsed.engine = "Google Gemini 1.5 Flash (Direct Cloud)";
  parsed.source = "gemini-cloud";
  parsed.url = videoUrl;
  return parsed;
}

function updateKeyBannerUI() {
  const key = localStorage.getItem("gemini_api_key");
  const keyStatusText = document.getElementById("keyStatusText");
  const btnKeyLabel = document.getElementById("btnKeyLabel");
  if (key) {
    if (keyStatusText) keyStatusText.textContent = "Google Gemini 24/7 Cloud Key Active! Summaries run instantly with zero delays.";
    if (btnKeyLabel) btnKeyLabel.textContent = "Change Key";
  } else {
    if (keyStatusText) keyStatusText.textContent = "Using Instant Cloud Engine. (Add free Gemini key for 100% fail-proof YouTube understanding anywhere).";
    if (btnKeyLabel) btnKeyLabel.textContent = "Add Free Key";
  }
}
updateKeyBannerUI();

const btnConfigKey = document.getElementById("btnConfigureKey");
if (btnConfigKey) {
  btnConfigKey.addEventListener("click", () => {
    const current = localStorage.getItem("gemini_api_key") || "";
    const entered = prompt(
      "Enter your free Google Gemini API Key (get one free at https://aistudio.google.com/apikey in 1 click):\n\nLeave blank to remove key.",
      current
    );
    if (entered !== null) {
      if (entered.trim()) {
        localStorage.setItem("gemini_api_key", entered.trim());
      } else {
        localStorage.removeItem("gemini_api_key");
      }
      updateKeyBannerUI();
      loadHealth();
    }
  });
}

/* ─── URL form submit ─── */
urlForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const rawUrl = document.getElementById("url").value;
  const url    = normalizeYouTubeInput(rawUrl);
  if (!looksLikeYouTubeUrl(url)) {
    showError(
      "Paste a YouTube link (watch, shorts, or youtu.be). Example: https://www.youtube.com/watch?v=…"
    );
    return;
  }
  const style = urlForm.querySelector('input[name="style"]:checked').value;
  const geminiKey = localStorage.getItem("gemini_api_key");

  setBusy(true, "Analyzing video and generating structured intelligence…");
  try {
    let data;
    if (geminiKey) {
      data = await summarizeWithGemini(geminiKey, url, style);
    } else {
      try {
        data = await postJson("/api/summarize-url", { url, style });
      } catch (backendErr) {
        const ask = confirm(
          "Cloud datacenter IP is temporarily rate-limited by YouTube for this video.\n\nWould you like to enter a free Google Gemini API Key to summarize this video instantly with zero blocks? (Free at aistudio.google.com)"
        );
        if (ask) {
          const key = prompt("Enter your free Google Gemini API Key (from https://aistudio.google.com/apikey):");
          if (key && key.trim()) {
            localStorage.setItem("gemini_api_key", key.trim());
            updateKeyBannerUI();
            data = await summarizeWithGemini(key.trim(), url, style);
          } else {
            throw backendErr;
          }
        } else {
          throw backendErr;
        }
      }
    }
    render(data);
  } catch (err) {
    showError(friendlyError(err));
  } finally {
    setBusy(false);
  }
});

/* ─── File form submit ─── */
fileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = document.getElementById("file").files[0];
  if (!file) return;
  setBusy(true, "Transcribing audio, then writing the brief…");
  try {
    const style = fileForm.querySelector('input[name="fileStyle"]:checked').value;
    const form  = new FormData();
    form.append("file", file);
    form.append("style", style);
    const res  = await fetch(getApiUrl("/api/summarize-file"), { method: "POST", body: form });
    if (!res.ok) {

      const data = await res.json().catch(() => ({}));
      throw new Error(formatDetail(data.detail) || `Upload failed (${res.status})`);
    }
    const data = await res.json().catch(() => ({}));
    render(data);
  } catch (err) {
    showError(friendlyError(err));
  } finally {
    setBusy(false);
  }
});

/* ─── Copy ─── */
document.getElementById("copyBtn").addEventListener("click", async () => {
  if (!lastPayload) return;
  await navigator.clipboard.writeText(toMarkdown(lastPayload));
  const btn = document.getElementById("copyBtn");
  btn.textContent = "Copied!";
  setTimeout(() => {
    btn.innerHTML = `<svg viewBox="0 0 20 20" fill="none" style="width:16px;height:16px"><path d="M8 4H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-3M8 4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V4z" stroke="currentColor" stroke-width="1.5"/></svg> Copy summary`;
  }, 1800);
});

/* ─── Download ─── */
document.getElementById("downloadBtn").addEventListener("click", () => {
  if (!lastPayload) return;
  const blob = new Blob([toMarkdown(lastPayload)], { type: "text/markdown" });
  const a    = document.createElement("a");
  a.href     = URL.createObjectURL(blob);
  a.download = `${(lastPayload.title || "summary").replace(/[^\w\-]+/g, "_").slice(0, 60)}.md`;
  a.click();
  URL.revokeObjectURL(a.href);
});
