# Zefame Instagram Multi-Service Automation

Automated service submission script for Zefame free tools:
- **Instagram Views**: Submits random reel link every 7 minutes (site minimum 5 min).
- **Instagram Likes**: Submits random reel link every 35 minutes (site minimum 30 min).
- **Instagram Followers**: Submits profile link every 24 hours 3 minutes (site minimum 24 hours).

---

## Configuration (`config.py`)

- **Reel Links**:
  - `https://www.instagram.com/reel/Dc0U9eCRyq4/`
  - `https://www.instagram.com/reel/Dc0Qg8WxenI/`
- **Profile Link**:
  - `https://www.instagram.com/fluxiolive/`
- **Service Intervals**:
  - Views: 7 minutes (`420` seconds)
  - Likes: 35 minutes (`2100` seconds)
  - Followers: 24 hours 3 minutes (`86580` seconds)

---

## Key Features

1. **Cloudflare Turnstile Handling**: Uses `undetected_chromedriver` with headful mode to pass verification challenges automatically.
2. **Dynamic Cooldown Detection**: Parses both English and French cooldown timers returned by Zefame and dynamically pauses the service task until the cooldown period expires.
3. **Async Concurrency Lock**: Runs all three services concurrently using Python's `asyncio` while using an `asyncio.Lock()` to ensure only one browser runs at a time.
4. **URL Normalization**: Strips URL query parameters (`?utm_source=...`) and standardizes trailing slashes before submitting.

---

## How to Run

### Automatic / Background
Run the launcher script:
```cmd
start_automation.bat
```
Or directly in Python:
```cmd
python zefame_automation.py
```

### Manual Single Run
To test any individual service once:
```cmd
python run_single.py views
python run_single.py likes
python run_single.py followers
```
