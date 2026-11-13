"""Shared game configuration."""

SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 700
FPS = 60
TOP_BAR_HEIGHT = 76
TOWER_BAR_TOP = 610

BACKGROUND = (39, 82, 65)
GRASS = (54, 105, 75)
PATH_COLOR = (190, 160, 112)
PATH_EDGE = (127, 105, 77)
PANEL = (29, 42, 47)
WHITE = (244, 241, 220)
MUTED = (174, 190, 177)
HUMAN_COLOR = (73, 179, 232)
ZOMBIE_COLOR = (119, 170, 83)
HEALTH_COLOR = (220, 75, 66)
GOLD_COLOR = (245, 204, 74)

TOWER_COST = 100
PROJECTILE_SPEED = 440
MAX_TOWER_LEVEL = 3
UPGRADE_COSTS = (120, 200)
MAX_EQUIPPED_TOWERS = 5
DEFAULT_GAME_SPEED = 10.0
GAME_SPEED_PRESETS = (1.0, 3.0, 10.0)
LOBBY_MOVE_SPEED = 3200
LOBBY_JUMP_VELOCITY = 60.0
LOBBY_GRAVITY = 1800.0

# Lobby coordinates are shared by the 2D menus and the 3D hub adapter.
LOBBY_STATION_RECTS = {
    "summon": (190, 200, 180, 110),
    "traits": (500, 180, 150, 120),
    "battle_pass": (790, 180, 170, 120),
    "crates": (280, 330, 170, 100),
    "collection": (600, 330, 170, 100),
    "start": (900, 300, 100, 90),
    "daily": (170, 390, 180, 70),
    "story": (430, 390, 180, 70),
    "admin": (700, 390, 180, 70),
}

GAME_MODES = (
    {
        "key": "normal",
        "name": "Normal",
        "drop_chance": 0.4,
        "credit_min": 1,
        "credit_max": 5,
        "enemy_power": 2,
        "movement_speed": 1.0,
        "crate_chance": 0.005,
        "crate_interval": 5,
    },
    {
        "key": "hard",
        "name": "Hard",
        "drop_chance": 0.5,
        "credit_min": 2,
        "credit_max": 7,
        "enemy_power": 5,
        "movement_speed": 1.15,
        "crate_chance": 0.005,
        "crate_interval": 1,
    },
    {
        "key": "insane",
        "name": "Insane",
        "drop_chance": 0.6,
        "credit_min": 4,
        "credit_max": 10,
        "enemy_power": 12,
        "movement_speed": 1.3,
        "crate_chance": 0.02,
        "crate_interval": 1,
    },
    {
        "key": "hell",
        "name": "Hell",
        "drop_chance": 1.0,
        "credit_min": 8,
        "credit_max": 30,
        "enemy_power": 25,
        "movement_speed": 1.5,
        "crate_chance": 0.1,
        "crate_interval": 1,
    },
    {
        "key": "forbidden",
        "name": "Forbidden",
        "drop_chance": 0.0,
        "credit_min": 0,
        "credit_max": 0,
        "enemy_power": 100,
        "movement_speed": 1.75,
        "crate_chance": 0.5,
        "crate_interval": 1,
    },
)
GAME_MODES_BY_KEY = {str(mode["key"]): mode for mode in GAME_MODES}

DAILY_CHALLENGES = {
    "normal": {"waves": 3, "credits": 500, "crates": 1},
    "hard": {"waves": 5, "credits": 1500, "crates": 2},
    "insane": {"waves": 8, "credits": 3000, "crates": 4},
    "hell": {"waves": 10, "credits": 6000, "crates": 7},
    "forbidden": {"waves": 15, "credits": 10000, "crates": 10},
}

STORY_BASE_CREDITS = 500
STORY_LEVEL_CREDIT_INCREMENT = 250
STORY_BASE_WAVES = 7
STORY_WAVES_PER_LEVEL = 2
STORY_MAX_WAVES = 50

TOWER_TYPES = (
    {
        "key": "1",
        "name": "Rifleman",
        "role": "Balanced",
        "icon": "R",
        "cost": 100,
        "range": 155,
        "damage": 20,
        "fire_rate": 0.65,
        "projectile_speed": 440,
        "ability": "standard",
        "color": (73, 179, 232),
    },
    {
        "key": "2",
        "name": "Scout",
        "role": "Rapid fire",
        "icon": "S",
        "cost": 125,
        "range": 125,
        "damage": 12,
        "fire_rate": 0.34,
        "projectile_speed": 500,
        "ability": "standard",
        "color": (111, 218, 164),
    },
    {
        "key": "3",
        "name": "Sniper",
        "role": "Long range",
        "icon": "N",
        "cost": 160,
        "range": 230,
        "damage": 42,
        "fire_rate": 1.4,
        "projectile_speed": 620,
        "ability": "standard",
        "color": (209, 157, 241),
    },
    {
        "key": "4",
        "name": "Quartermaster",
        "role": "Earns scrap",
        "icon": "$",
        "cost": 180,
        "range": 0,
        "damage": 0,
        "fire_rate": 99,
        "projectile_speed": 440,
        "ability": "income",
        "income": 24,
        "income_interval": 5.0,
        "color": (245, 204, 74),
    },
    {
        "key": "5",
        "name": "Brawler",
        "role": "Close damage",
        "icon": "B",
        "cost": 145,
        "range": 64,
        "damage": 52,
        "fire_rate": 0.72,
        "projectile_speed": 700,
        "ability": "standard",
        "color": (235, 119, 90),
    },
    {
        "key": "6",
        "name": "Gunner",
        "role": "Ranged DPS",
        "icon": "G",
        "cost": 190,
        "range": 185,
        "damage": 8,
        "fire_rate": 0.16,
        "projectile_speed": 590,
        "ability": "standard",
        "color": (245, 153, 79),
    },
    {
        "key": "7",
        "name": "Pyromancer",
        "role": "Burning",
        "icon": "F",
        "cost": 175,
        "range": 132,
        "damage": 10,
        "fire_rate": 0.82,
        "projectile_speed": 400,
        "ability": "burn",
        "burn_dps": 8,
        "burn_duration": 3.0,
        "color": (244, 97, 63),
    },
    {
        "key": "8",
        "name": "Frostkeeper",
        "role": "Slows zombies",
        "icon": "C",
        "cost": 185,
        "range": 150,
        "damage": 8,
        "fire_rate": 0.9,
        "projectile_speed": 410,
        "ability": "slow",
        "slow_factor": 0.45,
        "slow_duration": 2.8,
        "color": (96, 207, 231),
    },
    {
        "key": "9",
        "name": "Demolitionist",
        "role": "Splash damage",
        "icon": "E",
        "cost": 210,
        "range": 158,
        "damage": 30,
        "fire_rate": 1.35,
        "projectile_speed": 350,
        "ability": "splash",
        "splash_radius": 58,
        "color": (227, 197, 91),
    },
    {
        "key": "10",
        "name": "Toxicologist",
        "role": "Poisoning",
        "icon": "P",
        "cost": 195,
        "range": 162,
        "damage": 9,
        "fire_rate": 0.78,
        "projectile_speed": 390,
        "ability": "poison",
        "poison_dps": 5,
        "poison_duration": 4.5,
        "color": (164, 210, 92),
    },
)

PATH_POINTS = (
    (-30, 165),
    (205, 165),
    (205, 390),
    (430, 390),
    (430, 175),
    (665, 175),
    (665, 455),
    (1030, 455),
)
SCREEN_PATH_POINTS = tuple((x, y + TOP_BAR_HEIGHT) for x, y in PATH_POINTS)

MAPS = {
    "meadow": {
        "name": "Meadow",
        "path_points": SCREEN_PATH_POINTS,
    },
    "crossroads": {
        "name": "Crossroads",
        "path_points": (
            (-30, 180),
            (250, 180),
            (250, 500),
            (500, 500),
            (500, 300),
            (760, 300),
            (760, 480),
            (1030, 480),
        ),
    },
    "riverbend": {
        "name": "Riverbend",
        "path_points": (
            (-30, 470),
            (160, 470),
            (160, 250),
            (370, 250),
            (370, 520),
            (600, 520),
            (600, 155),
            (830, 155),
            (830, 410),
            (1030, 410),
        ),
    },
}
