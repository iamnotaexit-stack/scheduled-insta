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
            "likes": {},
            "followers": {}
        },
        "last_followers_run": ""
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
                        data["counts"]["followers"].update(loaded.get("counts", {}).get("followers", {}))
                        data["last_followers_run"] = loaded.get("last_followers_run", "")
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

        # Initialize profile link for followers
        profile = getattr(config, "PROFILE_LINK", "")
        if profile and profile not in data["counts"]["followers"]:
            data["counts"]["followers"][profile] = 0
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

def is_reel_views_blocked(reel, data):
    v = data["counts"]["views"].get(reel, 0)
    l = data["counts"]["likes"].get(reel, 0)
    max_sync = getattr(config, "SYNC_MAX_CYCLES", 120)
    interval = getattr(config, "SYNC_VIEW_INTERVAL", 20)
    likes_per = getattr(config, "SYNC_LIKES_PER_INTERVAL", 4)

    if v > max_sync:
        return False, 0
    if v >= interval:
        required_likes = (min(v, max_sync) // interval) * likes_per
        if l < required_likes:
            return True, required_likes
    return False, 0

def get_eligible_reel_for_views():
    data = load_state()
    reels = list(config.REEL_WEIGHTS.keys())
    if not reels:
        return None, "NO_REELS", 0, 0

    eligible = []
    blocked_info = []
    for r in reels:
        blocked, req_likes = is_reel_views_blocked(r, data)
        if blocked:
            v = data["counts"]["views"].get(r, 0)
            l = data["counts"]["likes"].get(r, 0)
            blocked_info.append(f"{r} (views: {v}, likes: {l}/{req_likes})")
        else:
            eligible.append(r)

    if not eligible:
        msg = "PAUSED_WAITING_LIKES: " + "; ".join(blocked_info)
        return None, msg, 0, 0

    # Prioritize reels with the lowest view count to keep all reels balanced
    min_views = min(data["counts"]["views"].get(r, 0) for r in eligible)
    lowest_reels = [r for r in eligible if data["counts"]["views"].get(r, 0) == min_views]

    weighted = [r for r in lowest_reels for _ in range(config.REEL_WEIGHTS.get(r, 1))]
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

    # Priority 1: Reels that are currently blocking views because they need likes
    blocked_reels = []
    for r in reels:
        blocked, _ = is_reel_views_blocked(r, data)
        if blocked:
            blocked_reels.append(r)
    if blocked_reels:
        min_likes = min(data["counts"]["likes"].get(r, 0) for r in blocked_reels)
        candidates = [r for r in blocked_reels if data["counts"]["likes"].get(r, 0) == min_likes]
        reel = random.choice(candidates)
        cur = data["counts"]["likes"].get(reel, 0)
        return reel, cur, 0

    # Priority 2: Reels in first 120 cycles that need likes for next 20-views milestone
    max_sync = getattr(config, "SYNC_MAX_CYCLES", 120)
    interval = getattr(config, "SYNC_VIEW_INTERVAL", 20)
    likes_per = getattr(config, "SYNC_LIKES_PER_INTERVAL", 4)
    lagging_reels = []
    for r in reels:
        v = data["counts"]["views"].get(r, 0)
        l = data["counts"]["likes"].get(r, 0)
        if v <= max_sync:
            next_target = ((v // interval) + 1) * likes_per
            if l < next_target:
                lagging_reels.append(r)
    if lagging_reels:
        min_likes = min(data["counts"]["likes"].get(r, 0) for r in lagging_reels)
        candidates = [r for r in lagging_reels if data["counts"]["likes"].get(r, 0) == min_likes]
        reel = random.choice(candidates)
        cur = data["counts"]["likes"].get(reel, 0)
        return reel, cur, 0

    # Priority 3: Lowest likes count first among all reels
    min_likes = min(data["counts"]["likes"].get(r, 0) for r in reels)
    lowest_reels = [r for r in reels if data["counts"]["likes"].get(r, 0) == min_likes]
    weighted = [r for r in lowest_reels for _ in range(config.REEL_WEIGHTS.get(r, 1))]
    reel = random.choice(weighted)
    cur = data["counts"]["likes"].get(reel, 0)
    return reel, cur, 0

def record_like_success(reel):
    data = load_state()
    data["counts"]["likes"][reel] = data["counts"]["likes"].get(reel, 0) + 1
    save_state(data)

def record_follower_success(profile_link):
    data = load_state()
    if "followers" not in data["counts"]:
        data["counts"]["followers"] = {}
    data["counts"]["followers"][profile_link] = data["counts"]["followers"].get(profile_link, 0) + 1
    data["last_followers_run"] = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
    save_state(data)

def get_status_summary():
    data = load_state()
    reels = list(config.REEL_WEIGHTS.keys())
    lines = []
    lines.append("Mode: CONTINUOUS (Views-to-likes sync active for first 120 view cycles)")
    lines.append("Reels Status:")
    for r in reels:
        v_cur = data["counts"]["views"].get(r, 0)
        l_cur = data["counts"]["likes"].get(r, 0)
        blocked, req_likes = is_reel_views_blocked(r, data)
        if v_cur <= 120:
            if blocked:
                status_str = f"Views PAUSED at {v_cur} (needs {req_likes} likes, currently {l_cur}/{req_likes})"
            else:
                next_check = ((v_cur // 20) + 1) * 20
                next_req = (next_check // 20) * 4
                status_str = f"Views ACTIVE ({v_cur}/120 milestone, next check at {next_check} views needs {next_req} likes)"
        else:
            status_str = "Views UNRESTRICTED (>120 cycles complete)"
        lines.append(f"  {r}: Views [{v_cur}], Likes [{l_cur}] : {status_str}")

    profile = getattr(config, "PROFILE_LINK", "")
    f_cur = data["counts"].get("followers", {}).get(profile, 0)
    last_f = data.get("last_followers_run", "Not yet recorded")
    lines.append(f"Followers Status: {profile} : Submissions [{f_cur}], Last run: {last_f}")
    return "\n".join(lines)
