"""
AI Video Summarizer - Auto Start + Auto URL Updater
----------------------------------------------------
This script:
1. Kills any old uvicorn / cloudflared processes
2. Starts uvicorn (local server) on port 8000
3. Starts cloudflared quick tunnel
4. Reads the new tunnel URL from cloudflared output
5. Updates static/app.js with the new URL
6. Commits & pushes to GitHub
7. Keeps running to monitor & restart if crashed
"""

import subprocess
import sys
import time
import re
import os
import signal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
CLOUDFLARED = Path("C:/Program Files (x86)/cloudflared/cloudflared.exe")
APP_JS = ROOT / "static" / "app.js"
GH = "gh"

VERCEL_BACKENDS = [
    "https://ai-video-summarizer-qx.vercel.app",
    "https://ai-video-summarizer-zv8y.vercel.app",
]

def kill_old_processes():
    """Kill any leftover uvicorn or cloudflared processes."""
    for name in ["uvicorn", "cloudflared"]:
        try:
            subprocess.run(["taskkill", "/F", "/IM", f"{name}.exe"], 
                         capture_output=True, timeout=5)
        except Exception:
            pass
    # Also kill by port 8000
    try:
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=5
        )
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
    """Start uvicorn server."""
    print("[*] Starting uvicorn server on port 8000...")
    proc = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "app:app",
         "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait for server to come up
    import urllib.request
    for _ in range(20):
        try:
            urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2)
            print("[+] Uvicorn server is UP!")
            return proc
        except Exception:
            time.sleep(1)
    print("[!] Uvicorn slow to start, continuing anyway...")
    return proc

def start_cloudflared_and_get_url():
    """Start cloudflared and extract the tunnel URL."""
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
    timeout = 60  # seconds
    start = time.time()
    
    while time.time() - start < timeout:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.1)
            continue
        print(f"  [cloudflared] {line.rstrip()}")
        match = re.search(r'https://[a-z0-9\-]+\.trycloudflare\.com', line)
        if match:
            url = match.group(0)
            print(f"[+] Tunnel URL: {url}")
            break
    
    return proc, url

def update_app_js(new_url: str):
    """Replace the first entry in CLOUD_BACKENDS with the new URL."""
    content = APP_JS.read_text(encoding="utf-8")
    
    # Replace any existing trycloudflare URL
    new_content = re.sub(
        r'"https://[a-z0-9\-]+\.trycloudflare\.com"',
        f'"{new_url}"',
        content,
        count=1
    )
    
    if new_content == content:
        # No existing trycloudflare URL found — insert at start of CLOUD_BACKENDS
        new_content = content.replace(
            "const CLOUD_BACKENDS = [",
            f'const CLOUD_BACKENDS = [\n  "{new_url}",'
        )
    
    APP_JS.write_text(new_content, encoding="utf-8")
    print(f"[+] app.js updated with: {new_url}")

def git_push(url: str):
    """Commit and push the updated app.js to GitHub."""
    try:
        subprocess.run(
            ["git", "add", "static/app.js"],
            cwd=str(ROOT), check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", f"Auto-update live tunnel: {url.split('//')[1].split('.')[0]}"],
            cwd=str(ROOT), capture_output=True  # don't check - may be no change
        )
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print("[+] Pushed to GitHub! Website is now live.")
        else:
            print(f"[!] Git push output: {result.stderr[:200]}")
    except Exception as e:
        print(f"[!] Git push error: {e}")

def monitor_processes(uvicorn_proc, cf_proc):
    """Monitor both processes and restart if either crashes."""
    print("\n[*] Monitoring processes... (Ctrl+C to stop)")
    print(f"[*] Website: https://anurag13590.github.io/AI-video-summarizer/")
    print(f"[*] Press Ctrl+C to stop the server\n")
    
    while True:
        try:
            time.sleep(10)
            
            u_alive = uvicorn_proc.poll() is None
            c_alive = cf_proc.poll() is None
            
            if not u_alive:
                print("[!] Uvicorn crashed! Restarting everything...")
                return False  # Signal to restart
            
            if not c_alive:
                print("[!] Cloudflared crashed! Restarting everything...")
                return False  # Signal to restart
                
        except KeyboardInterrupt:
            print("\n[*] Stopping servers...")
            uvicorn_proc.terminate()
            cf_proc.terminate()
            sys.exit(0)

def main():
    print("=" * 60)
    print("  AI Video Summarizer - Auto Start")
    print("=" * 60)
    
    while True:
        kill_old_processes()
        
        uvicorn_proc = start_uvicorn()
        cf_proc, tunnel_url = start_cloudflared_and_get_url()
        
        if tunnel_url:
            update_app_js(tunnel_url)
            git_push(tunnel_url)
            print(f"\n{'='*60}")
            print(f"  WEBSITE IS LIVE!")
            print(f"  Open: https://anurag13590.github.io/AI-video-summarizer/")
            print(f"{'='*60}\n")
        else:
            print("[!] Could not get tunnel URL. Server still running locally.")
        
        # Monitor until crash
        should_restart = monitor_processes(uvicorn_proc, cf_proc)
        
        if should_restart:
            print("[*] Restarting in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    main()
