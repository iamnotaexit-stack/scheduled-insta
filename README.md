# Scheduled Instagram Automation

Automated submission tool for Instagram views, likes, and followers.

## How to add more links in the future

Open `config.py` and add new links to the `REEL_LINKS` list:

```python
REEL_LINKS = [
    "https://www.instagram.com/reel/Dc0U9eCRyq4/",
    "https://www.instagram.com/reel/Dc0Qg8WxenI/",
    # Add your new reel links here
]
```

## Running locally

```bash
pip install playwright
playwright install
python zefame_automation.py
```

## GitHub Actions

GitHub Actions automatically runs `run_single.py` every 8 minutes using [.github/workflows/zefame.yml](.github/workflows/zefame.yml).
