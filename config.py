# Configuration for Instagram links
# Clean reel URLs without tracking parameters to prevent Zefame "Order error"

REEL_WEIGHTS = {
    "https://www.instagram.com/reel/Ded8tYZhXTn/": 1,
}

REEL_LINKS = [
    link for link, weight in REEL_WEIGHTS.items() for _ in range(weight)
]

def get_random_reel():
    import random
    return random.choice(REEL_LINKS)

PROFILE_LINK = "https://www.instagram.com/contentkaro.live/"

# Target endpoints on Zefame
VIEWS_URL = "https://zefame.com/en/free-instagram-views"
LIKES_URL = "https://zefame.com/en/free-instagram-likes"
FOLLOWERS_URL = "https://zefame.com/en/free-instagram-followers"

# Schedule intervals in seconds (runs continuously with no expiration date)
VIEWS_INTERVAL = 7 * 60                  # 7 minutes
LIKES_INTERVAL = 35 * 60                 # 35 minutes
FOLLOWERS_INTERVAL = 24 * 3600           # 24 hours

# Views to Likes Synchronization Settings
# Every 20 view cycles requires 4 like cycles (active for first 120 cycles)
SYNC_VIEW_INTERVAL = 20
SYNC_LIKES_PER_INTERVAL = 4
SYNC_MAX_CYCLES = 120
