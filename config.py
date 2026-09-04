# Configuration for Instagram links
# Clean reel URLs without tracking parameters to prevent Zefame "Order error"

REEL_WEIGHTS = {
    "https://www.instagram.com/reel/Dc0U9eCRyq4/": 1,
    "https://www.instagram.com/reel/Dc0Qg8WxenI/": 1,
    "https://www.instagram.com/reel/Dc3IwtNRZoi/": 2,
}

REEL_LINKS = [
    link for link, weight in REEL_WEIGHTS.items() for _ in range(weight)
]

def get_random_reel():
    import random
    return random.choice(REEL_LINKS)

PROFILE_LINK = "https://www.instagram.com/fluxiolive/"

# Schedule intervals in seconds
VIEWS_INTERVAL = 7 * 60                  # 7 minutes
LIKES_INTERVAL = 35 * 60                 # 35 minutes
FOLLOWERS_INTERVAL = 24 * 3600 + 3 * 60  # 24 hours 3 minutes
