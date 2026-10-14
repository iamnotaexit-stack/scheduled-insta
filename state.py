import json
import os
import random
import subprocess
import threading
import time

import config

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SCRIPT_DIR, "state.json")
_lock = threading.Lock()

def _default_state():
    return {
        "counts": {
            "views": {},
            "likes": {}
        }
    }

def load_state():
    with _lock:
        data = _default_state()
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        data["counts"]["views"].update(loaded.get("counts", {}).get("views", {}))
                        data["counts"]["likes"].update(loaded.get("counts", {}).get("likes", {}))
            except Exception:
                pass

        # Initialize missing reel links
        changed = False
        reels = list(config.REEL_WEIGHTS.keys())
        for r in reels:
            if r not in data["counts"]["views"]:
                data["counts"]["views"][r] = 0
                changed = True
            if r not in data["counts"]["likes"]:
                data["counts"]["likes"][r] = 0
                changed = True

        if changed or not os.path.exists(STATE_FILE):
            _save_state_unlocked(data)

        return data

def _save_state_unlocked(data):
    try:
        tmp_file = STATE_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(STATE_FILE):
            os.replace(tmp_file, STATE_FILE)
        else:
            os.rename(tmp_file, STATE_FILE)
    except Exception:
        pass

def save_state(data):
    with _lock:
        _save_state_unlocked(data)
    _async_git_sync()

def _async_git_sync():
    # Only sync to git when running in GitHub Actions with GH_PAT
    if os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GH_PAT"):
        threading.Thread(target=_git_sync_worker, daemon=True).start()

def _git_sync_worker():
    try:
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=SCRIPT_DIR, capture_output=True)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=SCRIPT_DIR, capture_output=True)
        subprocess.run(["git", "add", "state.json"], cwd=SCRIPT_DIR, capture_output=True)
        res = subprocess.run(["git", "commit", "-m", "Update automation state [skip ci]"], cwd=SCRIPT_DIR, capture_output=True)
        if res.returncode == 0:
            subprocess.run(["git", "pull", "--rebase"], cwd=SCRIPT_DIR, capture_output=True)
            push_res = subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=SCRIPT_DIR, capture_output=True, text=True)
            if push_res.returncode == 0:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Git Sync] Successfully pushed state.json to GitHub", flush=True)
            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Git Sync] Push error: {push_res.stderr.strip()}", flush=True)
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Git Sync] Exception: {e}", flush=True)

def get_eligible_reel_for_views():
    data = load_state()
    reels = list(config.REEL_WEIGHTS.keys())
    if not reels:
        return None, "NO_REELS", 0, 0
    weighted = [r for r in reels for _ in range(config.REEL_WEIGHTS.get(r, 1))]
    reel = random.choice(weighted)
    cur = data["counts"]["views"].get(reel, 0)
    return reel, "ALWAYS_RUN", cur, 0

def record_view_success(reel):
    data = load_state()
    data["counts"]["views"][reel] = data["counts"]["views"].get(reel, 0) + 1
    save_state(data)

def get_eligible_reel_for_likes():
    data = load_state()
    reels = list(config.REEL_WEIGHTS.keys())
    if not reels:
        return None, 0, 0
    weighted = [r for r in reels for _ in range(config.REEL_WEIGHTS.get(r, 1))]
    reel = random.choice(weighted)
    cur = data["counts"]["likes"].get(reel, 0)
    return reel, cur, 0

def record_like_success(reel):
    data = load_state()
    data["counts"]["likes"][reel] = data["counts"]["likes"].get(reel, 0) + 1
    save_state(data)

def get_status_summary():
    data = load_state()
    reels = list(config.REEL_WEIGHTS.keys())
    lines = []
    lines.append("Mode: CONTINUOUS (Always active, no expiration)")
    lines.append("Reels Status:")
    for r in reels:
        v_cur = data["counts"]["views"].get(r, 0)
        l_cur = data["counts"]["likes"].get(r, 0)
        lines.append(f"  {r}: Views [{v_cur}], Likes [{l_cur}]")
    return "\n".join(lines)
