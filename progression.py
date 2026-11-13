"""Unit catalog and lobby progression rules."""

from bisect import bisect_right
import random

from settings import TOWER_TYPES

ROLL_COST = 10
FIRST_UPGRADE_COST = 200
UPGRADE_COST_MULTIPLIER = 1.2
UPGRADE_STAT_MULTIPLIER = 1.1

RARITY_COLORS = {
    "Base": (174, 190, 177),
    "Common": (188, 198, 185),
    "Uncommon": (104, 210, 135),
    "Rare": (88, 174, 239),
    "Epic": (190, 116, 246),
    "Legendary": (255, 174, 74),
    "Mythic": (255, 92, 119),
    "Crate": (232, 90, 72),
    "Secret": (244, 224, 120),
}

RARITY_CHANCES = (
    ("Common", 48.87),
    ("Uncommon", 30.0),
    ("Rare", 20.0),
    ("Epic", 1.0),
    ("Legendary", 0.1),
    ("Mythic", 0.03),
)

RARITY_UNIT_NAMES = {
    "Common": (
        "Guardian", "Sentinel", "Ranger", "Vanguard", "Bulwark",
        "Pathfinder", "Marksman", "Striker", "Lookout", "Defender",
        "Warden", "Sharpshot", "Outrider", "Sentry", "Trailblazer",
        "Keeper", "Pioneer", "Aegis", "Scoutmaster", "Ironclad",
    ),
    "Uncommon": (
        "Raider", "Blazewing", "Frostbite", "Stormrunner", "Wildshot",
        "Emberguard", "Riftstalker", "Thornbow", "Duskblade", "Skyfire",
    ),
    "Rare": (
        "Tempest", "Nightfall", "Venomheart", "Thunderstrike",
        "Glacier", "Starfall", "Ironstorm", "Moonpiercer",
    ),
    "Epic": ("Voidweaver", "Soulflame", "Aetherion", "Dreadnought", "Spellbreaker"),
    "Legendary": ("Sunwarden", "Eternity", "Dragonheart"),
    "Mythic": ("Worldbreaker", "Celestial"),
}
RARITY_STARTER_IDS = {
    "Common": "common-guardian",
    "Uncommon": "uncommon-raider",
    "Rare": "rare-tempest",
    "Epic": "epic-voidweaver",
    "Legendary": "legendary-sunwarden",
    "Mythic": "mythic-worldbreaker",
}

RARITY_BASE_STATS = {
    "Common": (20, 130, 21, 0.72, (188, 198, 185), ("standard",)),
    "Uncommon": (34, 150, 34, 0.60, (104, 210, 135), ("bleed", "slow")),
    "Rare": (50, 170, 52, 0.91, (88, 174, 239), ("chain", "slow", "poison")),
    "Epic": (70, 190, 73, 0.88, (190, 116, 246), ("burn", "poison", "slow", "splash")),
    "Legendary": (95, 205, 98, 0.82, (255, 174, 74), ("burn", "poison", "slow", "splash", "execute", "pierce")),
    "Mythic": (135, 225, 140, 0.76, (255, 92, 119), ("burn", "poison", "slow", "splash", "income", "pierce")),
}


def _create_gacha_units() -> tuple[dict[str, object], ...]:
    units: list[dict[str, object]] = []
    for rarity, names in RARITY_UNIT_NAMES.items():
        base_cost, attack_range, damage, fire_rate, color, abilities = RARITY_BASE_STATS[rarity]
        for ordinal, name in enumerate(names, start=1):
            scale = 1 + (ordinal - 1) * 0.025
            unit_id = (
                RARITY_STARTER_IDS[rarity]
                if ordinal == 1
                else f"{rarity.lower()}-{ordinal:02d}"
            )
            unit: dict[str, object] = {
                "id": unit_id,
                "name": name,
                "role": f"{rarity} specialist",
                "icon": name[0],
                "cost": round(base_cost * scale),
                "range": round(attack_range * scale),
                "damage": round(damage * scale),
                "fire_rate": fire_rate,
                "projectile_speed": 440 + (ordinal % 5) * 18,
                "ability": next((ability for ability in abilities if ability != "income"), "standard"),
                "abilities": abilities,
                "color": color,
                "rarity": rarity,
            }
            if "burn" in abilities:
                unit.update(burn_dps=10 + ordinal, burn_duration=3.0 + ordinal * 0.05)
            if "poison" in abilities:
                unit.update(poison_dps=5 + ordinal, poison_duration=3.5 + ordinal * 0.05)
            if "slow" in abilities:
                unit.update(slow_factor=max(0.35, 0.8 - ordinal * 0.01), slow_duration=2.0 + ordinal * 0.05)
            if "splash" in abilities:
                unit["splash_radius"] = 42 + ordinal * 2
            if "income" in abilities:
                unit.update(income=10 + ordinal, income_interval=5.0)
            if "pierce" in abilities:
                unit.update(pierce_width=18, pierce_targets=3 + ordinal)
            if "bleed" in abilities:
                unit.update(bleed_dps=8 + ordinal, bleed_duration=3.0 + ordinal * 0.05)
            if "chain" in abilities:
                unit.update(chain_radius=80 + ordinal * 3, chain_targets=2 + ordinal, chain_damage_factor=0.7)
            if "execute" in abilities:
                unit.update(execute_threshold=0.25, execute_multiplier=1.75)
            units.append(unit)
    return tuple(units)


GACHA_UNITS = _create_gacha_units()
CRATE_UNIT = {
    "id": "crate-hitler",
    "name": "Hitler",
    "role": "Stacking fire damage",
    "icon": "H",
    "cost": 250,
    "range": 250,
    "damage": 500,
    "fire_rate": 0.5,
    "projectile_speed": 500,
    "ability": "stacking_burn",
    "abilities": ("stacking_burn",),
    "color": (232, 90, 72),
    "rarity": "Crate",
    "burn_fraction": 0.5,
    "burn_duration": 5.0,
}
SECRET_UNIT = {
    "id": "secret-accelerator",
    "name": "Apocalypse ender",
    "role": "Accelerating empowered status specialist",
    "icon": "E",
    "cost": 5000,
    "range": 250,
    "damage": 1000,
    "fire_rate": 0.4,
    "projectile_speed": 620,
    "ability": "empower",
    "abilities": (
        "burn",
        "slow",
        "poison",
        "accelerate",
        "empower",
        "stacking_burn",
        "pierce",
    ),
    "color": (244, 224, 120),
    "rarity": "Secret",
    "burn_dps": 200,
    "burn_duration": 3.0,
    "burn_fraction": 0.5,
    "slow_factor": 0.6,
    "slow_duration": 2.5,
    "poison_dps": 150,
    "poison_duration": 4.0,
    "pierce_width": 18,
    "pierce_targets": 8,
}
UNIT_COUNT_BY_RARITY = {rarity: len(names) for rarity, names in RARITY_UNIT_NAMES.items()}
GACHA_UNITS_BY_RARITY = {
    rarity: tuple(unit for unit in GACHA_UNITS if unit["rarity"] == rarity)
    for rarity in RARITY_UNIT_NAMES
}
LEVEL_DUPLICATE_COST = {
    "Common": 10,
    "Uncommon": 8,
    "Rare": 6,
    "Epic": 4,
    "Legendary": 2,
    "Mythic": 1,
    "Crate": 1,
    "Secret": 1,
}
STARTER_UNIT_ID = RARITY_STARTER_IDS["Common"]
_UNIT_INDEX_BY_ID = {
    f"base-{str(tower['name']).lower().replace(' ', '-')}": index
    for index, tower in enumerate(TOWER_TYPES)
}
_UNIT_INDEX_BY_ID.update(
    {str(unit["id"]): len(TOWER_TYPES) + index for index, unit in enumerate(GACHA_UNITS)}
)
_UNIT_INDEX_BY_ID[str(CRATE_UNIT["id"])] = len(TOWER_TYPES) + len(GACHA_UNITS)
_UNIT_INDEX_BY_ID[str(SECRET_UNIT["id"])] = len(TOWER_TYPES) + len(GACHA_UNITS) + 1
_GACHA_INDICES_BY_RARITY = {
    rarity: tuple(
        len(TOWER_TYPES) + index
        for index, unit in enumerate(GACHA_UNITS)
        if unit["rarity"] == rarity
    )
    for rarity in RARITY_UNIT_NAMES
}

TRAITS = (
    {"id": "keen", "name": "Keen", "damage_multiplier": 1.10, "attack_speed_multiplier": 1.10, "chance": 40.0},
    {"id": "eager", "name": "Eager", "damage_multiplier": 1.20, "attack_speed_multiplier": 1.25, "chance": 25.0},
    {"id": "trained", "name": "Trained", "damage_multiplier": 1.50, "attack_speed_multiplier": 1.50, "chance": 15.0},
    {"id": "veteran", "name": "Veteran", "damage_multiplier": 2.00, "attack_speed_multiplier": 2.00, "chance": 10.0},
    {"id": "elite", "name": "Elite", "damage_multiplier": 2.25, "attack_speed_multiplier": 2.50, "chance": 5.0},
    {"id": "master", "name": "Master", "damage_multiplier": 2.80, "attack_speed_multiplier": 3.00, "chance": 2.5},
    {"id": "champion", "name": "Champion", "damage_multiplier": 3.50, "attack_speed_multiplier": 3.50, "chance": 1.5},
    {"id": "mythical", "name": "Mythical", "damage_multiplier": 4.00, "attack_speed_multiplier": 4.00, "chance": 0.7},
    {"id": "celestial", "name": "Celestial", "damage_multiplier": 5.00, "attack_speed_multiplier": 5.00, "chance": 0.25},
    {"id": "apex", "name": "Apex", "damage_multiplier": 7.50, "attack_speed_multiplier": 6.00, "chance": 0.049},
    {"id": "overlord", "name": "Overlord", "damage_multiplier": 25.0, "attack_speed_multiplier": 10.0, "chance": 0.001},
)
ULTIMATE_TRAIT_ID = "overlord"
ULTIMATE_TRAIT_CHANCE = 0.001
TRAIT_ROLL_COSTS = {1: 25, 10: 250, 100: 2500}
TRAIT_BATCH_COUNTS = (5, 10, 25, 100)
TRAIT_BASE_CHANCE = 0.01
CRATE_TYPES = {
    "standard": {
        "name": "Supply Crate",
        "credit_chance": 99.99,
        "unit_chance": 0.01,
        "credit_min": 1000,
        "credit_max": 5000,
        "unit_id": "crate-hitler",
        "description": "99.99%: 1,000-5,000 credits | 0.01%: secret unit",
    },
    "story": {
        "name": "Story Crate",
        "unit_chance": 100.0,
        "description": "One unit: Common 70% | Rare 20% | Epic 7% | Legendary 2.5% | Mythic 0.49% | Secret 0.01%",
    },
}
BATTLE_PASS_XP_PER_WAVE = 20
BATTLE_PASS_LEVEL_CAP = 100
BATTLE_PASS_EXTRA_LEVEL_XP = 1500
BATTLE_PASS_MAX_XP = 9_000_000_000_000_000_000_00
BATTLE_PASS_LEVEL_THRESHOLDS = tuple(
    50 * level * (level - 1)
    for level in range(1, BATTLE_PASS_LEVEL_CAP + 2)
)
BATTLE_PASS_UNIT_IDS = (
    "uncommon-raider",
    "rare-tempest",
    "epic-voidweaver",
    "legendary-sunwarden",
    "mythic-worldbreaker",
)


def battle_pass_xp_for_next_level(level: int) -> int:
    """Return the XP required to advance from the given level."""
    if level < 1:
        raise ValueError("Battle pass level must be at least 1.")
    if level <= BATTLE_PASS_LEVEL_CAP:
        return level * 100
    return BATTLE_PASS_EXTRA_LEVEL_XP


def battle_pass_level(total_xp: int) -> tuple[int, int, int]:
    """Return current level, XP earned within it, and XP needed to advance."""
    if total_xp < 0:
        raise ValueError("Battle pass XP cannot be negative.")
    xp_for_extra_levels = BATTLE_PASS_LEVEL_THRESHOLDS[-1]
    if total_xp >= xp_for_extra_levels:
        extra_levels, xp_remaining = divmod(
            total_xp - xp_for_extra_levels,
            BATTLE_PASS_EXTRA_LEVEL_XP,
        )
        level = BATTLE_PASS_LEVEL_CAP + 1 + extra_levels
        return level, xp_remaining, BATTLE_PASS_EXTRA_LEVEL_XP

    level = bisect_right(BATTLE_PASS_LEVEL_THRESHOLDS, total_xp)
    xp_into_level = total_xp - BATTLE_PASS_LEVEL_THRESHOLDS[level - 1]
    return level, xp_into_level, battle_pass_xp_for_next_level(level)


def battle_pass_reward(level: int) -> dict[str, object]:
    """Build the recurring reward for a battle-pass level."""
    if level < 1:
        raise ValueError("Battle pass level must be at least 1.")
    reward: dict[str, object] = {
        "credits": level * 100,
        "crate_id": None,
        "unit_id": None,
    }
    if level % 5 == 0:
        reward["unit_id"] = BATTLE_PASS_UNIT_IDS[(level // 5 - 1) % len(BATTLE_PASS_UNIT_IDS)]
    elif level % 3 == 0:
        reward["crate_id"] = "story" if level % 2 == 0 else "standard"
    return reward


STORY_CRATE_RARITY_CHANCES = (
    ("Common", 70.0),
    ("Rare", 20.0),
    ("Epic", 7.0),
    ("Legendary", 2.5),
    ("Mythic", 0.49),
    ("Secret", 0.01),
)


def random_trait(include_ultimate: bool = False) -> dict[str, object]:
    candidates = [
        trait
        for trait in TRAITS
        if include_ultimate or trait["id"] != ULTIMATE_TRAIT_ID
    ]
    roll = random.random() * sum(float(trait["chance"]) for trait in candidates)
    for trait in candidates:
        roll -= float(trait["chance"])
        if roll < 0:
            return dict(trait)
    return dict(candidates[-1])


def roll_trait(ordinary_chance: float) -> dict[str, object] | None:
    if random.random() < ULTIMATE_TRAIT_CHANCE / 100:
        return dict(next(trait for trait in TRAITS if trait["id"] == ULTIMATE_TRAIT_ID))
    if random.random() < ordinary_chance:
        return random_trait()
    return None


def roll_traits(count: int, luck: int) -> list[dict[str, object]]:
    ordinary_chance = TRAIT_BASE_CHANCE * (luck ** 0.5)
    return [
        trait
        for _ in range(count)
        if (trait := roll_trait(ordinary_chance)) is not None
    ]


def all_unit_indices() -> range:
    return range(len(TOWER_TYPES) + len(GACHA_UNITS) + 2)


def unit_stats(unit_index: int) -> dict[str, object]:
    if 0 <= unit_index < len(TOWER_TYPES):
        tower = dict(TOWER_TYPES[unit_index])
        tower["id"] = f"base-{tower['name'].lower().replace(' ', '-')}"
        tower["rarity"] = "Base"
        tower["abilities"] = (tower["ability"],)
        return tower
    bonus_index = unit_index - len(TOWER_TYPES)
    if 0 <= bonus_index < len(GACHA_UNITS):
        return dict(GACHA_UNITS[bonus_index])
    if bonus_index == len(GACHA_UNITS):
        return dict(CRATE_UNIT)
    if bonus_index == len(GACHA_UNITS) + 1:
        return dict(SECRET_UNIT)
    raise ValueError(f"Unknown unit index: {unit_index}")


def unit_index_for_id(unit_id: str) -> int | None:
    return _UNIT_INDEX_BY_ID.get(unit_id)


def unit_upgrade_cost(level: int) -> int:
    return round(FIRST_UPGRADE_COST * UPGRADE_COST_MULTIPLIER ** (level - 1))


def duplicate_cost(unit_index: int) -> int:
    rarity = str(unit_stats(unit_index)["rarity"])
    return LEVEL_DUPLICATE_COST.get(rarity, 10)


def rarity_gacha_indices(rarity: str) -> tuple[int, ...]:
    return _GACHA_INDICES_BY_RARITY.get(rarity, ())


def roll_story_crate_unit() -> dict[str, object]:
    roll = random.random() * 100
    total = 0.0
    for rarity, chance in STORY_CRATE_RARITY_CHANCES:
        total += chance
        if roll < total:
            if rarity == "Secret":
                return dict(SECRET_UNIT)
            candidates = GACHA_UNITS_BY_RARITY.get(rarity, ())
            if not candidates:
                raise RuntimeError(f"No units are configured for {rarity} rarity.")
            return dict(random.choice(candidates))
    raise RuntimeError("The story crate rarity chances must total 100%.")


def combat_upgrade_cap(unit_index: int) -> int:
    return {
        "Base": 3,
        "Common": 3,
        "Uncommon": 4,
        "Rare": 5,
        "Epic": 6,
        "Legendary": 8,
        "Mythic": 10,
        "Crate": 10,
        "Secret": 20,
    }[str(unit_stats(unit_index)["rarity"])]


def roll_unit() -> dict[str, object] | None:
    if random.random() < 1 / 1_000_000:
        return dict(SECRET_UNIT)
    roll = random.random() * 100
    total = 0.0
    rarity = "Mythic"
    for candidate, chance in RARITY_CHANCES:
        total += chance
        if roll < total:
            rarity = candidate
            break
    candidates = GACHA_UNITS_BY_RARITY.get(rarity, ())
    return random.choice(candidates) if candidates else None
