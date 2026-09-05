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
        "targets": {
            "views": {},
            "likes": {}
        },
        "counts": {
            "views": {},
            "likes": {}
        },
        "hinder_mode": {
            "active": False,
            "current_date": "",
            "daily_target": 0,
            "today_views_count": 0
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
                        data["targets"]["views"].update(loaded.get("targets", {}).get("views", {}))
                        data["targets"]["likes"].update(loaded.get("targets", {}).get("likes", {}))
                        data["counts"]["views"].update(loaded.get("counts", {}).get("views", {}))
                        data["counts"]["likes"].update(loaded.get("counts", {}).get("likes", {}))
                        if "hinder_mode" in loaded and isinstance(loaded["hinder_mode"], dict):
                            data["hinder_mode"].update(loaded["hinder_mode"])
            except Exception:
                pass

        # Initialize missing reel links
        changed = False
        reels = list(config.REEL_WEIGHTS.keys())
        for r in reels:
            if r not in data["targets"]["views"]:
                data["targets"]["views"][r] = random.randint(*config.VIEW_CAP_RANGE)
                changed = True
            if r not in data["targets"]["likes"]:
                data["targets"]["likes"][r] = random.randint(*config.LIKE_CAP_RANGE)
                changed = True
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
            subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=SCRIPT_DIR, capture_output=True)
    except Exception:
        pass

def get_eligible_reel_for_views():
    data = load_state()
    hinder = data["hinder_mode"]
    reels = list(config.REEL_WEIGHTS.keys())

    # Check if hinder mode is active
    if hinder.get("active", False):
        today = time.strftime('%Y-%m-%d')
        if hinder.get("current_date") != today:
            hinder["current_date"] = today
            hinder["today_views_count"] = 0
            hinder["daily_target"] = random.randint(*config.HINDER_DAILY_VIEWS_RANGE)
            save_state(data)

        daily_target = hinder.get("daily_target", 15)
        current_views = hinder.get("today_views_count", 0)

        if current_views < daily_target:
            reel = random.choice(reels)
            remaining_today = daily_target - current_views
            return reel, "HINDER_RUN", remaining_today, daily_target
        else:
            return None, "HINDER_DAILY_LIMIT_REACHED", 0, daily_target

    # Normal mode: check per-reel caps (150-200)
    eligible = [
        r for r in reels
        if data["counts"]["views"].get(r, 0) < data["targets"]["views"].get(r, 150)
    ]

    if eligible:
        reel = random.choice(eligible)
        cur = data["counts"]["views"].get(reel, 0)
        target = data["targets"]["views"].get(reel, 150)
        remaining = target - cur
        return reel, "NORMAL_RUN", remaining, target

    # All reels have reached views targets
    # Check if all likes targets are also reached
    likes_remaining = any(
        data["counts"]["likes"].get(r, 0) < data["targets"]["likes"].get(r, 100)
        for r in reels
    )

    if not likes_remaining:
        # Both operations done: activate hinder mode!
        hinder["active"] = True
        hinder["current_date"] = time.strftime('%Y-%m-%d')
        hinder["today_views_count"] = 0
        hinder["daily_target"] = random.randint(*config.HINDER_DAILY_VIEWS_RANGE)
        save_state(data)
        reel = random.choice(reels)
        return reel, "HINDER_ACTIVATED", hinder["daily_target"], hinder["daily_target"]

    return None, "VIEWS_CAP_REACHED_WAITING_LIKES", 0, 0

def record_view_success(reel):
    data = load_state()
    hinder = data["hinder_mode"]

    if hinder.get("active", False):
        hinder["today_views_count"] = hinder.get("today_views_count", 0) + 1
    else:
        data["counts"]["views"][reel] = data["counts"]["views"].get(reel, 0) + 1
        # Check if this completed all views and all likes
        reels = list(config.REEL_WEIGHTS.keys())
        views_done = all(
            data["counts"]["views"].get(r, 0) >= data["targets"]["views"].get(r, 150)
            for r in reels
        )
        likes_done = all(
            data["counts"]["likes"].get(r, 0) >= data["targets"]["likes"].get(r, 100)
            for r in reels
        )
        if views_done and likes_done:
            hinder["active"] = True
            hinder["current_date"] = time.strftime('%Y-%m-%d')
            hinder["today_views_count"] = 0
            hinder["daily_target"] = random.randint(*config.HINDER_DAILY_VIEWS_RANGE)

    save_state(data)

def get_eligible_reel_for_likes():
    data = load_state()
    reels = list(config.REEL_WEIGHTS.keys())

    eligible = [
        r for r in reels
        if data["counts"]["likes"].get(r, 0) < data["targets"]["likes"].get(r, 100)
    ]

    if eligible:
        reel = random.choice(eligible)
        cur = data["counts"]["likes"].get(reel, 0)
        target = data["targets"]["likes"].get(reel, 100)
        remaining = target - cur
        return reel, remaining, target

    return None, 0, 0

def record_like_success(reel):
    data = load_state()
    data["counts"]["likes"][reel] = data["counts"]["likes"].get(reel, 0) + 1

    # Check if this completed all likes and views
    reels = list(config.REEL_WEIGHTS.keys())
    views_done = all(
        data["counts"]["views"].get(r, 0) >= data["targets"]["views"].get(r, 150)
        for r in reels
    )
    likes_done = all(
        data["counts"]["likes"].get(r, 0) >= data["targets"]["likes"].get(r, 100)
        for r in reels
    )

    if views_done and likes_done and not data["hinder_mode"].get("active", False):
        data["hinder_mode"]["active"] = True
        data["hinder_mode"]["current_date"] = time.strftime('%Y-%m-%d')
        data["hinder_mode"]["today_views_count"] = 0
        data["hinder_mode"]["daily_target"] = random.randint(*config.HINDER_DAILY_VIEWS_RANGE)

    save_state(data)

def get_status_summary():
    data = load_state()
    reels = list(config.REEL_WEIGHTS.keys())
    lines = []
    lines.append(f"Hinder Mode: {'ACTIVE' if data['hinder_mode'].get('active') else 'INACTIVE'}")
    if data['hinder_mode'].get('active'):
        lines.append(f"Daily Quota: {data['hinder_mode'].get('today_views_count', 0)} / {data['hinder_mode'].get('daily_target', 0)}")
    lines.append("Reels Status:")
    for r in reels:
        v_cur = data["counts"]["views"].get(r, 0)
        v_tgt = data["targets"]["views"].get(r, 0)
        l_cur = data["counts"]["likes"].get(r, 0)
        l_tgt = data["targets"]["likes"].get(r, 0)
        lines.append(f"  {r}: Views [{v_cur}/{v_tgt}], Likes [{l_cur}/{l_tgt}]")
    return "\n".join(lines)
