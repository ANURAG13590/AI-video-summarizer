"""
AI Video Summarizer - Auto Start + Auto URL Updater
----------------------------------------------------
This script:
1. Kills any old uvicorn / cloudflared processes
2. Starts uvicorn (local server) on port 8000
3. Starts cloudflared quick tunnel
4. Reads the new tunnel URL from cloudflared output
5. Updates GitHub Gist with new URL (no git push needed!)
6. Optionally updates static/app.js and pushes to GitHub
7. Keeps monitoring and restarts if crashed
"""

import subprocess
import sys
import time
import re
import os
import urllib.request
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
CLOUDFLARED = Path("C:/Program Files (x86)/cloudflared/cloudflared.exe")
APP_JS = ROOT / "static" / "app.js"

GIST_ID = "ffa3aa3c705bc7e2d70c1a9c3a787f2f"
GIST_FILE = "backend.json"

def get_github_token():
    try:
        return subprocess.check_output("gh auth token", shell=True).decode().strip()
    except Exception:
        return None

def update_gist(tunnel_url: str, token: str):
    """Update the GitHub Gist with the new backend URL."""
    payload = json.dumps({
        "files": {
            GIST_FILE: {
                "content": json.dumps({
                    "backend_url": tunnel_url,
                    "updated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
                })
            }
        }
    }).encode()

    req = urllib.request.Request(
        f"https://api.github.com/gists/{GIST_ID}",
        data=payload,
        method="PATCH",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                print(f"[+] Gist updated: {tunnel_url}")
                return True
    except Exception as e:
        print(f"[!] Gist update failed: {e}")
    return False

def kill_old_processes():
    for name in ["uvicorn", "cloudflared"]:
        try:
            subprocess.run(["taskkill", "/F", "/IM", f"{name}.exe"],
                           capture_output=True, timeout=5)
        except Exception:
            pass
    # Kill port 8000
    try:
        result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=5)
        for line in result.stdout.splitlines():
            if ":8000 " in line and "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                subprocess.run(["taskkill", "/F", "/PID", pid],
                               capture_output=True, timeout=5)
    except Exception:
        pass
    time.sleep(2)

def start_uvicorn():
    print("[*] Starting uvicorn server on port 8000...")
    proc = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "app:app",
         "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        try:
            urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2)
            print("[+] Server UP!")
            return proc
        except Exception:
            time.sleep(1)
    print("[!] Server slow to start, continuing...")
    return proc

def start_cloudflared_and_get_url():
    print("[*] Starting Cloudflare tunnel...")
    proc = subprocess.Popen(
        [str(CLOUDFLARED), "tunnel", "--protocol", "http2",
         "--url", "http://127.0.0.1:8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    url = None
    start = time.time()
    while time.time() - start < 60:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.1)
            continue
        match = re.search(r'https://[a-z0-9\-]+\.trycloudflare\.com', line)
        if match:
            url = match.group(0)
            print(f"[+] Tunnel URL: {url}")
            break
    return proc, url

def monitor_processes(uvicorn_proc, cf_proc):
    print(f"\n{'='*60}")
    print(f"  WEBSITE IS LIVE!")
    print(f"  Open: https://anurag13590.github.io/AI-video-summarizer/")
    print(f"  Minimize this window - DO NOT CLOSE IT")
    print(f"{'='*60}\n")
    while True:
        try:
            time.sleep(15)
            if uvicorn_proc.poll() is not None:
                print("[!] Uvicorn crashed! Restarting...")
                return False
            if cf_proc.poll() is not None:
                print("[!] Cloudflared crashed! Restarting...")
                return False
        except KeyboardInterrupt:
            print("\n[*] Stopping...")
            uvicorn_proc.terminate()
            cf_proc.terminate()
            sys.exit(0)

def main():
    print("=" * 60)
    print("  AI Video Summarizer - Auto Start")
    print("=" * 60)
    token = get_github_token()
    if not token:
        print("[!] WARNING: Could not get GitHub token. Gist won't update.")

    while True:
        kill_old_processes()
        uvicorn_proc = start_uvicorn()
        cf_proc, tunnel_url = start_cloudflared_and_get_url()

        if tunnel_url and token:
            update_gist(tunnel_url, token)

        monitor_processes(uvicorn_proc, cf_proc)
        print("[*] Restarting in 5 seconds...")
        time.sleep(5)

if __name__ == "__main__":
    main()
