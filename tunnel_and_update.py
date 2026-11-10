"""
Tunnel starter + Gist updater.
Runs cloudflared, gets URL, updates GitHub Gist.
Runs independently of Antigravity.
"""
import subprocess
import time
import re
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLOUDFLARED = r"C:\Program Files (x86)\cloudflared\cloudflared.exe"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
GIST_ID = "ffa3aa3c705bc7e2d70c1a9c3a787f2f"


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
        print(f"Gist error: {e}")
        return False


def main():
    cf_log = LOG_DIR / "cloudflared.log"
    # Clear old log
    cf_log.write_text("")

    print("Starting Cloudflare tunnel...")
    proc = subprocess.Popen(
        [CLOUDFLARED, "tunnel", "--protocol", "http2", "--url", "http://127.0.0.1:8000"],
        stdout=open(cf_log, "w"),
        stderr=subprocess.STDOUT,
    )

    # Wait for URL
    tunnel_url = None
    start = time.time()
    while time.time() - start < 90:
        try:
            text = cf_log.read_text(errors="ignore")
            m = re.search(r'https://[a-z0-9\-]+\.trycloudflare\.com', text)
            if m:
                tunnel_url = m.group(0)
                break
        except Exception:
            pass
        time.sleep(1)

    if tunnel_url:
        print(f"Tunnel URL: {tunnel_url}")
        if update_gist(tunnel_url):
            print("Gist updated!")
        else:
            print("Gist update failed")
    else:
        print("Could not get tunnel URL")

    # Keep process alive (monitor cloudflared)
    print("Monitoring tunnel (Ctrl+C to stop)...")
    while True:
        time.sleep(30)
        if proc.poll() is not None:
            print("Cloudflared stopped! Restarting...")
            proc = subprocess.Popen(
                [CLOUDFLARED, "tunnel", "--protocol", "http2", "--url", "http://127.0.0.1:8000"],
                stdout=open(cf_log, "w"),
                stderr=subprocess.STDOUT,
            )
            # Get new URL and update Gist
            time.sleep(15)
            try:
                text = cf_log.read_text(errors="ignore")
                m = re.search(r'https://[a-z0-9\-]+\.trycloudflare\.com', text)
                if m:
                    new_url = m.group(0)
                    update_gist(new_url)
                    print(f"New tunnel: {new_url}")
            except Exception:
                pass


if __name__ == "__main__":
    main()
