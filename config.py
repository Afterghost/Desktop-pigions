"""Configuration and constants for Desktop Pigeon."""

# Window settings
PIGEON_SIZE = 96  # pixels, including the hunger label
NEST_WIDTH = 600
NEST_HEIGHT = 400

# Pigeon behaviour
BASE_MOVEMENT_SPEED = 3  # pixels per frame
MOVEMENT_UPDATE_INTERVAL = 33  # ms
IDLE_DURATION_MIN = 3000  # ms
IDLE_DURATION_MAX = 8000  # ms
ROAM_RADIUS = 200  # pixels

# Hunger system
HUNGER_TICK_INTERVAL = 5000  # ms (5 seconds)
HUNGER_PER_TICK = 1  # hunger increases per tick
HUNGER_MAX = 100

HUNGER_STATES = {
    "full": (0, 20),
    "content": (21, 40),
    "hungry": (41, 70),
    "very_hungry": (71, 90),
    "angry": (91, 100),
}

# Feeding system
FOOD_TYPES = {
    "seed_mix": {"hunger_reduction": 15, "friendship": 5, "cost": 0},
    "sunflower_seeds": {"hunger_reduction": 20, "friendship": 8, "cost": 10},
    "french_fries": {"hunger_reduction": 10, "friendship": 12, "cost": 5},
    "mystery_crumbs": {"hunger_reduction": 8, "friendship": 3, "cost": 2},
    "golden_corn": {"hunger_reduction": 25, "friendship": 15, "cost": 25},
}

# Desktop detection
TREASURE_MIN_BRIGHTNESS = 100  # 0-255
TREASURE_MIN_COLOURFULNESS = 30  # 0-100
TREASURE_SCAN_INTERVAL = 3000  # ms
TREASURE_INTEREST_DECAY = 0.95  # Interest decreases over time

# Theft system
THEFT_ANIMATION_DURATION = 2000  # ms
THEFT_APPROACH_SPEED = 3.5  # pixels per frame
THEFT_ESCAPE_SPEED = 5.0  # pixels per frame

# File storage
NEST_DATA_FILE = "nest_data.json"
PIGEON_STATE_FILE = "pigeon_state.json"
MAX_STORED_ITEMS = 500
AUTO_FORAGE_INTERVAL = 30  # seconds
SAVE_INTERVAL = 10  # seconds

# Window detection (Windows-specific)
EXCLUDED_WINDOWS = {
    "Progman",  # Desktop
    "WorkerW",  # Desktop
}

EXCLUDED_PROCESSES = {
    "explorer.exe",
    "dwm.exe",
    "taskmgr.exe",
}
