"""
Windows-native independent launcher using PowerShell Start-Process.
Processes are FULLY detached - survive even when Antigravity is closed.
"""
import subprocess
import sys
import time
import re
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PYTHON = str(ROOT / ".venv" / "Scripts" / "python.exe")
CLOUDFLARED = r"C:\Program Files (x86)\cloudflared\cloudflared.exe"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
GIST_ID = "ffa3aa3c705bc7e2d70c1a9c3a787f2f"


def kill_old():
    subprocess.run(["taskkill", "/F", "/IM", "cloudflared.exe"], capture_output=True)
    # Kill python on port 8000
    try:
        r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            if ":8000 " in line and "LISTENING" in line:
                pid = line.split()[-1]
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
    except Exception:
        pass
    time.sleep(2)


def start_with_powershell(exe, args, log_file):
    """Use PowerShell Start-Process to launch truly independent process."""
    args_str = " ".join(f'"{a}"' for a in args)
    ps_cmd = (
        f'Start-Process -FilePath "{exe}" '
        f'-ArgumentList {args_str} '
        f'-RedirectStandardOutput "{log_file}" '
        f'-RedirectStandardError "{log_file}.err" '
        f'-WindowStyle Hidden '
        f'-PassThru'
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_cmd],
        capture_output=True, text=True
    )
    # Extract PID from output
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
    return None


def wait_for_server(timeout=25):
    for _ in range(timeout):
        try:
            urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def get_tunnel_url(log_file, timeout=70):
    start = time.time()
    while time.time() - start < timeout:
        try:
            text = open(log_file, "r", errors="ignore").read()
            m = re.search(r'https://[a-z0-9\-]+\.trycloudflare\.com', text)
            if m:
                return m.group(0)
        except Exception:
            pass
        time.sleep(1)
    return None


def update_gist(tunnel_url):
    try:
        token = subprocess.check_output("gh auth token", shell=True).decode().strip()
    except Exception:
        return False
    payload = json.dumps({
        "files": {
            "backend.json": {
                "content": json.dumps({
                    "backend_url": tunnel_url,
                    "updated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
                })
            }
        }
    }).encode()
    req = urllib.request.Request(
        f"https://api.github.com/gists/{GIST_ID}",
        data=payload, method="PATCH",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[!] Gist error: {e}")
        return False


def main():
    print("=" * 55)
    print("  AI Video Summarizer - Independent Launcher")
    print("=" * 55)

    print("\n[1/4] Killing old processes...")
    kill_old()

    print("[2/4] Starting server in background...")
    uv_log = str(LOG_DIR / "uvicorn.log")
    start_with_powershell(
        VENV_PYTHON,
        ["-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8000"],
        uv_log
    )
    if wait_for_server():
        print("    ✓ Server is UP on port 8000")
    else:
        print("    ! Server slow - continuing anyway")

    print("[3/4] Starting Cloudflare tunnel in background...")
    cf_log = str(LOG_DIR / "cloudflared.log")
    # Clear old log
    try:
        open(cf_log, "w").close()
    except Exception:
        pass
    start_with_powershell(
        CLOUDFLARED,
        ["tunnel", "--protocol", "http2", "--url", "http://127.0.0.1:8000"],
        cf_log
    )
    print("    Waiting for tunnel URL (up to 70s)...")
    tunnel_url = get_tunnel_url(cf_log)

    if tunnel_url:
        print(f"    ✓ Tunnel: {tunnel_url}")
        # Save for reference
        (ROOT / "running.json").write_text(json.dumps({"tunnel_url": tunnel_url}))
        print("[4/4] Updating website (GitHub Gist)...")
        if update_gist(tunnel_url):
            print("    ✓ Website updated!")
        else:
            print("    ! Gist update failed - website may use old URL")
    else:
        print("    ! Tunnel URL not found in logs")
        print("    Check:", cf_log)

    print()
    print("=" * 55)
    print("  ALL DONE!")
    print("  Uvicorn + Cloudflared running INDEPENDENTLY.")
    print("  ✓ Close Antigravity - website stays LIVE")
    print("  ✓ Website: https://anurag13590.github.io/AI-video-summarizer/")
    print("=" * 55)


if __name__ == "__main__":
    main()
