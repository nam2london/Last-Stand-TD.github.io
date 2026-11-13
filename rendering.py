"""Drawing helpers for the game screen."""

from functools import lru_cache
import os
import random

import pygame

from entities import Defender, Projectile, Zombie, draw_circle_overlay
from progression import (
    CRATE_TYPES,
    duplicate_cost,
    ROLL_COST,
    RARITY_CHANCES,
    RARITY_COLORS,
    STARTER_UNIT_ID,
    TRAIT_BATCH_COUNTS,
    TRAIT_BASE_CHANCE,
    TRAIT_ROLL_COSTS,
    ULTIMATE_TRAIT_ID,
    UNIT_COUNT_BY_RARITY,
    UPGRADE_STAT_MULTIPLIER,
    all_unit_indices,
    battle_pass_level,
    battle_pass_reward,
    combat_upgrade_cap,
    unit_index_for_id,
    unit_stats,
    unit_upgrade_cost,
)
from settings import (
    BACKGROUND,
    DAILY_CHALLENGES,
    GAME_SPEED_PRESETS,
    GOLD_COLOR,
    GAME_MODES,
    GAME_MODES_BY_KEY,
    GRASS,
    HUMAN_COLOR,
    MAPS,
    LOBBY_STATION_RECTS,
    MUTED,
    PANEL,
    PATH_COLOR,
    PATH_EDGE,
    SCREEN_HEIGHT,
    SCREEN_PATH_POINTS,
    SCREEN_WIDTH,
    STORY_BASE_CREDITS,
    STORY_LEVEL_CREDIT_INCREMENT,
    STORY_BASE_WAVES,
    STORY_WAVES_PER_LEVEL,
    STORY_MAX_WAVES,
    TOP_BAR_HEIGHT,
    TOWER_BAR_TOP,
    TOWER_TYPES,
    UPGRADE_COSTS,
    WHITE,
)


def draw_text(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    color: tuple[int, int, int],
    position: tuple[int, int],
) -> None:
    surface.blit(font.render(text, True, color), position)


@lru_cache(maxsize=1)
def _menu_background_surface() -> pygame.Surface:
    background = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    background.fill((19, 34, 36))
    for y in range(0, SCREEN_HEIGHT, 4):
        shade = 23 + y * 12 // SCREEN_HEIGHT
        pygame.draw.line(background, (shade, shade + 16, shade + 13), (0, y), (SCREEN_WIDTH, y))
    for x, y, radius in ((890, 145, 130), (125, 570, 175), (720, 650, 95)):
        pygame.draw.circle(background, (27, 47, 45), (x, y), radius)
        pygame.draw.circle(background, (31, 52, 48), (x, y), radius, 1)
    return background


def _draw_menu_background(surface: pygame.Surface) -> None:
    surface.blit(_menu_background_surface(), (0, 0))


def _draw_panel(
    surface: pygame.Surface,
    rectangle: pygame.Rect,
    accent: tuple[int, int, int] = (84, 112, 101),
) -> None:
    shadow = rectangle.move(0, 4)
    pygame.draw.rect(surface, (12, 24, 27), shadow, border_radius=10)
    pygame.draw.rect(surface, (29, 45, 47), rectangle, border_radius=10)
    pygame.draw.rect(surface, accent, rectangle, 1, border_radius=10)


def _project_3d_point(
    x: float,
    y: float,
    z: float,
    center: tuple[int, int] = (SCREEN_WIDTH // 2, 440),
    scale: float = 58.0,
) -> tuple[int, int]:
    px = center[0] + (x - y) * scale
    py = center[1] - z * 38.0 + (x + y) * 14.0
    return int(px), int(py)


def _draw_3d_box(
    surface: pygame.Surface,
    x: float,
    y: float,
    z: float,
    width: float,
    depth: float,
    height: float,
    color: tuple[int, int, int],
    edge: tuple[int, int, int],
    center: tuple[int, int] = (SCREEN_WIDTH // 2, 440),
) -> None:
    corners = (
        (x - width / 2, y - depth / 2, z),
        (x + width / 2, y - depth / 2, z),
        (x + width / 2, y + depth / 2, z),
        (x - width / 2, y + depth / 2, z),
        (x - width / 2, y - depth / 2, z + height),
        (x + width / 2, y - depth / 2, z + height),
        (x + width / 2, y + depth / 2, z + height),
        (x - width / 2, y + depth / 2, z + height),
    )
    projected = [_project_3d_point(px, py, pz, center) for px, py, pz in corners]
    top = (projected[4], projected[5], projected[6], projected[7])
    left = (projected[0], projected[3], projected[7], projected[4])
    right = (projected[1], projected[2], projected[6], projected[5])
    front = (projected[0], projected[1], projected[2], projected[3])
    pygame.draw.polygon(surface, tuple(min(255, channel + 18) for channel in color), top)
    pygame.draw.polygon(surface, tuple(max(0, channel - 12) for channel in color), left)
    pygame.draw.polygon(surface, tuple(max(0, channel - 20) for channel in color), right)
    pygame.draw.polygon(surface, color, front)
    for points in (top, left, right, front):
        pygame.draw.polygon(surface, edge, points, 2)


def _draw_3d_player(
    surface: pygame.Surface,
    player: dict[str, float],
    center: tuple[int, int] = (SCREEN_WIDTH // 2, 440),
) -> None:
    body = _project_3d_point(player["x"], player["y"], player["z"], center)
    head = _project_3d_point(player["x"], player["y"], player["z"] + 0.95, center)
    pygame.draw.circle(surface, (235, 122, 82), body, 13)
    pygame.draw.circle(surface, (245, 214, 188), head, 9)
    pygame.draw.line(surface, (245, 214, 188), body, head, 3)


def _draw_3d_lobby_scene(
    surface: pygame.Surface,
    player: dict[str, float] | None,
) -> None:
    surface.fill((9, 17, 26))
    top_gradient = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    for y in range(SCREEN_HEIGHT):
        alpha = min(255, int((y / SCREEN_HEIGHT) * 180))
        pygame.draw.line(top_gradient, (12, 18, 30, alpha), (0, y), (SCREEN_WIDTH, y))
    surface.blit(top_gradient, (0, 0))

    _draw_3d_box(surface, 0, 0, -0.1, 8.5, 8.5, 0.4, (40, 82, 72), (18, 35, 33))
    _draw_3d_box(surface, -2.5, 2.0, 0.2, 2.2, 2.2, 0.8, (71, 115, 116), (32, 54, 52))
    _draw_3d_box(surface, 2.6, -2.0, 0.4, 2.6, 2.8, 1.1, (71, 95, 118), (34, 48, 58))
    _draw_3d_box(surface, 0.4, -3.4, 0.7, 2.5, 2.3, 1.5, (90, 124, 98), (38, 61, 44))
    _draw_3d_box(surface, -3.5, -1.8, 1.0, 2.2, 2.0, 1.8, (112, 88, 96), (54, 36, 35))
    if player is not None:
        _draw_3d_player(surface, player)


def _point_is_clear_of_path(
    point: tuple[int, int],
    path_points: tuple[tuple[int, int], ...],
    clearance: int,
) -> bool:
    x, y = point
    clearance_squared = clearance * clearance
    for start, end in zip(path_points, path_points[1:]):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length_squared = dx * dx + dy * dy
        progress = max(
            0.0,
            min(1.0, ((x - start[0]) * dx + (y - start[1]) * dy) / length_squared),
        )
        closest_x = start[0] + progress * dx
        closest_y = start[1] + progress * dy
        if (x - closest_x) ** 2 + (y - closest_y) ** 2 < clearance_squared:
            return False
    return True


@lru_cache(maxsize=8)
def _map_background(
    path_points: tuple[tuple[int, int], ...],
    map_name: str,
) -> pygame.Surface:
    surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    ground_colors = {
        "Meadow": ((52, 101, 71), (60, 111, 77)),
        "Crossroads": ((61, 91, 67), (69, 101, 72)),
        "Riverbend": ((49, 94, 78), (57, 104, 85)),
    }
    base_color, patch_color = ground_colors.get(
        map_name, ((54, 105, 75), (62, 114, 81))
    )
    surface.fill(base_color)
    rng = random.Random((map_name, path_points).__repr__())

    for _ in range(155):
        x = rng.randrange(12, SCREEN_WIDTH - 12)
        y = rng.randrange(TOP_BAR_HEIGHT + 10, TOWER_BAR_TOP - 10)
        point = (x, y)
        if not _point_is_clear_of_path(point, path_points, 42):
            continue
        width = rng.randrange(12, 45)
        height = rng.randrange(6, 21)
        color_shift = rng.randrange(-5, 6)
        color = tuple(max(0, min(255, channel + color_shift)) for channel in patch_color)
        pygame.draw.ellipse(surface, color, (x - width // 2, y - height // 2, width, height))

    for _ in range(45):
        x = rng.randrange(22, SCREEN_WIDTH - 22)
        y = rng.randrange(TOP_BAR_HEIGHT + 24, TOWER_BAR_TOP - 24)
        point = (x, y)
        if not _point_is_clear_of_path(point, path_points, 82):
            continue
        if map_name == "Riverbend" and rng.random() < 0.28:
            pond = pygame.Rect(x - 15, y - 7, rng.randrange(24, 42), rng.randrange(12, 20))
            pygame.draw.ellipse(surface, (57, 110, 117), pond)
            pygame.draw.ellipse(surface, (82, 139, 139), pond, 1)
            continue
        if map_name == "Crossroads" and rng.random() < 0.35:
            rock = pygame.Rect(x - 6, y - 4, 12, 8)
            pygame.draw.ellipse(surface, (105, 111, 87), rock)
            pygame.draw.ellipse(surface, (133, 134, 101), rock, 1)
            continue
        canopy = (40, 77, 54) if map_name != "Meadow" else (43, 88, 57)
        pygame.draw.ellipse(surface, (34, 59, 45), (x - 11, y + 5, 26, 10))
        pygame.draw.rect(surface, (91, 71, 48), (x - 3, y - 1, 7, 17), border_radius=2)
        pygame.draw.circle(surface, canopy, (x, y - 5), 13)
        pygame.draw.circle(surface, (67, 112, 67), (x - 4, y - 8), 6)
        if map_name == "Meadow" and rng.random() < 0.65:
            flower_color = rng.choice(((230, 205, 124), (205, 164, 184), (222, 222, 167)))
            pygame.draw.circle(surface, flower_color, (x + 15, y + 8), 2)

    pygame.draw.rect(
        surface,
        (36, 67, 53),
        (0, TOP_BAR_HEIGHT, SCREEN_WIDTH, TOWER_BAR_TOP - TOP_BAR_HEIGHT),
        2,
    )
    return surface


def _draw_map_thumbnail(
    surface: pygame.Surface,
    rectangle: pygame.Rect,
    path_points: tuple[tuple[int, int], ...],
    selected: bool,
    name: str,
    font: pygame.font.Font,
) -> None:
    pygame.draw.rect(surface, (22, 36, 38), rectangle, border_radius=6)
    pygame.draw.rect(
        surface,
        GOLD_COLOR if selected else (74, 98, 91),
        rectangle,
        2 if selected else 1,
        border_radius=6,
    )
    map_area = pygame.Rect(rectangle.x + 5, rectangle.y + 5, 48, rectangle.height - 10)
    pygame.draw.rect(surface, (58, 97, 70), map_area, border_radius=4)
    min_x = min(point[0] for point in path_points)
    max_x = max(point[0] for point in path_points)
    min_y = min(point[1] for point in path_points)
    max_y = max(point[1] for point in path_points)
    scale = min(
        (map_area.width - 8) / (max_x - min_x),
        (map_area.height - 8) / (max_y - min_y),
    )
    offset_x = map_area.centerx - (min_x + max_x) * scale / 2
    offset_y = map_area.centery - (min_y + max_y) * scale / 2
    points = [
        (round(offset_x + x * scale), round(offset_y + y * scale))
        for x, y in path_points
    ]
    pygame.draw.lines(surface, (88, 73, 55), False, points, 7)
    pygame.draw.lines(surface, PATH_COLOR, False, points, 4)
    label = font.render(name.upper(), True, WHITE if selected else MUTED)
    surface.blit(label, label.get_rect(midleft=(rectangle.x + 61, rectangle.centery)))


def draw_setup(
    surface: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    available_towers: set[int],
    game_speed: float,
    speed_input: str,
    username_input: str,
    password_input: str,
    grant_username_input: str,
    focused_field: str | None,
    account_name: str | None,
    is_admin: bool,
    has_custom_speed: bool,
    status: str,
) -> None:
    _draw_menu_background(surface)
    pygame.draw.rect(surface, PANEL, (0, 0, SCREEN_WIDTH, 76))
    pygame.draw.rect(surface, HUMAN_COLOR, (0, 74, SCREEN_WIDTH, 2))
    draw_text(surface, fonts["title"], "LAST STAND", WHITE, (38, 17))
    draw_text(surface, fonts["body"], "SET UP YOUR GAME", GOLD_COLOR, (238, 21))
    _draw_panel(surface, pygame.Rect(20, 78, 960, 220))
    _draw_panel(surface, pygame.Rect(20, 300, 670, 94), (83, 119, 122))
    _draw_panel(surface, pygame.Rect(20, 397, 960, 198))
    draw_text(
        surface,
        fonts["small"],
        f"Choose up to 5 towers ({len(available_towers)}/5 equipped)",
        WHITE,
        (38, 82),
    )

    for index, tower_type in enumerate(TOWER_TYPES):
        card = pygame.Rect(20 + (index % 5) * 192, 104 + (index // 5) * 98, 180, 90)
        chosen = index in available_towers
        fill = (53, 72, 73) if chosen else (37, 47, 48)
        border = tower_type["color"] if chosen else (94, 103, 99)
        pygame.draw.rect(surface, fill, card, border_radius=8)
        pygame.draw.rect(surface, border, card, 3 if chosen else 1, border_radius=8)
        draw_text(
            surface,
            fonts["body"],
            str(tower_type["name"]),
            tower_type["color"] if chosen else MUTED,
            (card.x + 10, card.y + 7),
        )
        draw_text(
            surface,
            fonts["tower"],
            f"${tower_type['cost']} | DMG {tower_type['damage']} | R {tower_type['range']}",
            WHITE,
            (card.x + 10, card.y + 30),
        )
        draw_text(
            surface,
            fonts["tower"],
            str(tower_type["role"]),
            MUTED,
            (card.x + 10, card.y + 51),
        )
        draw_text(
            surface,
            fonts["tower"],
            "EQUIPPED" if chosen else "CLICK TO EQUIP",
            GOLD_COLOR if chosen else MUTED,
            (card.x + 10, card.y + 70),
        )

    draw_text(surface, fonts["body"], "Game speed", WHITE, (38, 308))
    draw_text(surface, fonts["small"], "10x default; choose a standard speed", MUTED, (38, 326))
    for index, speed in enumerate(GAME_SPEED_PRESETS):
        button = pygame.Rect(40 + index * 112, 340, 100, 46)
        selected = game_speed == speed
        pygame.draw.rect(surface, (53, 72, 73) if selected else (38, 55, 57), button, border_radius=5)
        pygame.draw.rect(surface, GOLD_COLOR if selected else (88, 110, 106), button, 2, border_radius=5)
        label = fonts["body"].render(f"{speed:g}x", True, WHITE)
        surface.blit(label, label.get_rect(center=button.center))

    custom_button = pygame.Rect(400, 340, 150, 46)
    pygame.draw.rect(
        surface,
        (53, 72, 73) if has_custom_speed else (38, 45, 45),
        custom_button,
        border_radius=5,
    )
    pygame.draw.rect(
        surface,
        GOLD_COLOR if has_custom_speed else (88, 92, 88),
        custom_button,
        2,
        border_radius=5,
    )
    custom_label = "Custom speed" if has_custom_speed else "Custom: locked"
    label = fonts["body"].render(custom_label, True, WHITE if has_custom_speed else MUTED)
    surface.blit(label, label.get_rect(center=custom_button.center))
    _draw_input(
        surface,
        fonts,
        pygame.Rect(565, 340, 120, 46),
        "1-10x",
        speed_input,
        focused_field == "custom_speed",
        password=False,
    )

    draw_text(surface, fonts["body"], "Account (custom speeds require access)", WHITE, (38, 403))
    api_url = os.environ.get("GAME_API_URL", "http://127.0.0.1:5000")
    draw_text(surface, fonts["small"], f"API: {api_url}", MUTED, (490, 408))
    _draw_input(
        surface,
        fonts,
        pygame.Rect(40, 456, 245, 42),
        "Username",
        username_input,
        focused_field == "username",
        password=False,
    )
    _draw_input(
        surface,
        fonts,
        pygame.Rect(300, 456, 245, 42),
        "Password",
        password_input,
        focused_field == "password",
        password=True,
    )
    _draw_button(surface, fonts["small"], pygame.Rect(560, 456, 120, 42), "Register", HUMAN_COLOR)
    _draw_button(surface, fonts["small"], pygame.Rect(690, 456, 120, 42), "Sign in", GOLD_COLOR)
    _draw_button(surface, fonts["small"], pygame.Rect(820, 456, 140, 42), "Sign out", MUTED)

    account_line = (
        f"Signed in: {account_name} ({'admin' if is_admin else 'player'})"
        if account_name
        else "Guest: sign in or register for an account"
    )
    draw_text(surface, fonts["small"], account_line, HUMAN_COLOR if account_name else MUTED, (40, 508))
    if has_custom_speed:
        draw_text(
            surface,
            fonts["small"],
            "Click Custom and type a speed from 1 to 10, then press Enter.",
            GOLD_COLOR,
            (40, 529),
        )
        _draw_input(
            surface,
            fonts,
            pygame.Rect(40, 548, 245, 42),
            "Player to grant 10x",
            grant_username_input,
            focused_field == "grant_username",
            password=False,
        )
        if is_admin:
            _draw_button(
                surface,
                fonts["small"],
                pygame.Rect(300, 548, 180, 42),
                "Grant 10x access",
                GOLD_COLOR,
            )
        else:
            draw_text(surface, fonts["small"], "Admin only: grant 10x access to another account.", MUTED, (300, 561))
    else:
        draw_text(
            surface,
            fonts["small"],
            "The first registered account is admin. Admins can grant 10x access to other accounts.",
            MUTED,
            (40, 548),
        )

    if status:
        draw_text(surface, fonts["small"], status, WHITE, (40, 610))
    start_button = pygame.Rect(800, 610, 160, 62)
    pygame.draw.rect(surface, (53, 99, 78), start_button, border_radius=8)
    pygame.draw.rect(surface, HUMAN_COLOR, start_button, 2, border_radius=8)
    label = fonts["body"].render("OPEN LOBBY", True, WHITE)
    surface.blit(label, label.get_rect(center=start_button.center))
    draw_text(surface, fonts["small"], "Click up to 5 base units to equip | Enter opens lobby | Esc quits", MUTED, (40, 665))


def draw_lobby(
    surface: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    credits: int,
    owned_units: set[int],
    equipped_units: set[int],
    unit_levels: dict[str, int],
    selected_unit: int,
    selected_mode: str,
    status: str,
    account_name: str | None,
    is_admin: bool,
    crates: dict[str, int] | None = None,
    unit_traits: dict[str, dict[str, object]] | None = None,
    selected_map: str = "meadow",
    daily_claimed: bool = False,
    story_level: int = 1,
    battle_pass_xp: int = 0,
    battle_pass_claimed: set[int] | None = None,
    player: dict[str, float] | None = None,
) -> None:
    _draw_3d_lobby_scene(surface, player)
    pygame.draw.rect(surface, PANEL, (0, 0, SCREEN_WIDTH, 76))
    pygame.draw.rect(surface, GOLD_COLOR, (0, 74, SCREEN_WIDTH, 2))
    draw_text(surface, fonts["title"], "SUMMON LOBBY", WHITE, (25, 16))
    draw_text(surface, fonts["body"], f"Credits: {credits}", GOLD_COLOR, (390, 22))
    draw_text(
        surface,
        fonts["small"],
        f"Signed in: {account_name}" if account_name else "Guest progress is temporary",
        MUTED,
        (640, 27),
    )

    station_colors = {
        "summon": HUMAN_COLOR,
        "traits": GOLD_COLOR,
        "battle_pass": (136, 111, 185),
        "crates": (88, 111, 70),
        "collection": (80, 118, 138),
        "start": (53, 99, 78),
        "daily": (82, 90, 110),
        "story": (81, 119, 107),
        "admin": (98, 92, 72),
    }
    station_labels = {
        "summon": "SUMMON",
        "traits": "TRAITS",
        "battle_pass": "PASS",
        "crates": "CRATES",
        "collection": "UNITS",
        "start": "START",
        "daily": "DAILY",
        "story": "STORY",
        "admin": "ADMIN",
    }

    current_station: str | None = None
    if player is not None:
        x, y = player["x"], player["y"]
        for name, (px, py, pw, ph) in LOBBY_STATION_RECTS.items():
            dx = x - (px + pw / 2)
            dy = y - (py + ph / 2)
            if dx * dx + dy * dy <= 55**2:
                current_station = name
                break

    for station_name, (px, py, pw, ph) in LOBBY_STATION_RECTS.items():
        color = station_colors[station_name]
        label = station_labels[station_name]
        highlight = station_name == current_station
        pygame.draw.rect(surface, (38, 55, 57), pygame.Rect(px, py, pw, ph), border_radius=12)
        pygame.draw.rect(surface, color if highlight else (100, 112, 110), pygame.Rect(px, py, pw, ph), 2, border_radius=12)
        draw_text(surface, fonts["body"], label, WHITE, (px + 18, py + 18))
        draw_text(surface, fonts["tower"], "move here", MUTED, (px + 18, py + 58))

    if player is not None:
        pygame.draw.circle(surface, (250, 195, 120), (int(player["x"]), int(player["y"])), 14)
        pygame.draw.circle(surface, (255, 236, 200), (int(player["x"]), int(player["y"])), 7)
        pygame.draw.circle(surface, (54, 73, 82), (int(player["x"]) - 3, int(player["y"]) - 3), 3)
        pygame.draw.circle(surface, (54, 73, 82), (int(player["x"]) + 6, int(player["y"]) - 3), 3)

    info_panel = pygame.Rect(40, 90, 920, 120)
    pygame.draw.rect(surface, (19, 31, 36), info_panel, border_radius=12)
    pygame.draw.rect(surface, GOLD_COLOR, info_panel, 2, border_radius=12)
    draw_text(surface, fonts["small"], "Move with WASD. Stand on a platform and press Enter or E to activate it.", MUTED, (55, 104))
    station_label = current_station.upper() if current_station else "EXPLORING"
    draw_text(surface, fonts["body"], f"Current station: {station_label} | Credits: {credits}", WHITE, (55, 130))
    if status:
        draw_text(surface, fonts["small"], status, WHITE, (55, 160))

    if current_station == "summon":
        py = 220
        pygame.draw.rect(surface, (53, 72, 73), pygame.Rect(190, py, 180, 90), border_radius=8)
        draw_text(surface, fonts["body"], "SUMMON UNIT", WHITE, (205, 242))
        draw_text(surface, fonts["tower"], f"{len(owned_units)} owned", MUTED, (205, 272))
    if current_station == "traits":
        trait_name = str((unit_traits or {}).get(str(unit_stats(selected_unit)["id"]), {}).get("name", "No trait"))
        pygame.draw.rect(surface, (53, 72, 73), pygame.Rect(505, 220, 150, 80), border_radius=8)
        draw_text(surface, fonts["body"], "TRAITS", WHITE, (525, 242))
        draw_text(surface, fonts["tower"], trait_name[:18], MUTED, (525, 272))
    if current_station == "battle_pass":
        pass_level, _, _ = battle_pass_level(battle_pass_xp)
        pygame.draw.rect(surface, (53, 72, 73), pygame.Rect(810, 220, 160, 80), border_radius=8)
        draw_text(surface, fonts["body"], f"PASS {pass_level}", WHITE, (830, 242))
        draw_text(surface, fonts["tower"], "Claim rewards", MUTED, (830, 272))
    if current_station == "crates":
        crate_count = sum((crates or {}).values())
        pygame.draw.rect(surface, (53, 72, 73), pygame.Rect(275, 350, 170, 80), border_radius=8)
        draw_text(surface, fonts["body"], "CRATES", WHITE, (310, 372))
        draw_text(surface, fonts["tower"], f"{crate_count} ready", MUTED, (310, 402))
    if current_station == "collection":
        pygame.draw.rect(surface, (53, 72, 73), pygame.Rect(610, 350, 170, 80), border_radius=8)
        draw_text(surface, fonts["body"], "COLLECTION", WHITE, (625, 372))
        draw_text(surface, fonts["tower"], f"{len(owned_units)} units", MUTED, (625, 402))
    if current_station == "start":
        pygame.draw.rect(surface, (53, 99, 78), pygame.Rect(900, 310, 100, 70), border_radius=8)
        draw_text(surface, fonts["body"], "START", WHITE, (918, 332))
    if current_station == "daily":
        pygame.draw.rect(surface, (53, 72, 73), pygame.Rect(190, 510, 180, 60), border_radius=8)
        draw_text(surface, fonts["small"], "DAILY CHALLENGE", WHITE, (200, 528))
    if current_station == "story":
        pygame.draw.rect(surface, (53, 72, 73), pygame.Rect(440, 510, 180, 60), border_radius=8)
        draw_text(surface, fonts["small"], "STORY MODE", WHITE, (460, 528))
    if current_station == "admin" and is_admin:
        pygame.draw.rect(surface, (53, 72, 73), pygame.Rect(710, 510, 180, 60), border_radius=8)
        draw_text(surface, fonts["small"], "ADMIN PANEL", WHITE, (735, 528))

    hint = "Summon units, roll traits, open crates, claim battle pass, and launch the run from the platform stations."
    draw_text(surface, fonts["tower"], hint, MUTED, (70, 655))
    if current_station == "start":
        draw_text(surface, fonts["body"], "Stand here and press Enter to launch the wave run.", GOLD_COLOR, (610, 650))


def draw_battle_pass(
    surface: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    total_xp: int,
    claimed_levels: set[int],
    status: str,
) -> None:
    level, progress, required = battle_pass_level(total_xp)
    earned_level = level - 1
    available = [
        reward_level
        for reward_level in range(1, earned_level + 1)
        if reward_level not in claimed_levels
    ]
    surface.fill(BACKGROUND)
    pygame.draw.rect(surface, PANEL, (0, 0, SCREEN_WIDTH, 76))
    draw_text(surface, fonts["title"], "BATTLE PASS", WHITE, (25, 16))
    draw_text(surface, fonts["body"], f"Level {level}", GOLD_COLOR, (370, 20))
    draw_text(
        surface,
        fonts["small"],
        f"{progress} / {required} XP to next level",
        MUTED,
        (485, 25),
    )
    progress_width = round(420 * progress / required)
    pygame.draw.rect(surface, (53, 62, 57), (290, 65, 420, 8), border_radius=4)
    if progress_width:
        pygame.draw.rect(
            surface,
            GOLD_COLOR,
            (290, 65, progress_width, 8),
            border_radius=4,
        )

    draw_text(surface, fonts["body"], "Earn 20 XP for every successfully cleared wave.", WHITE, (40, 105))
    draw_text(
        surface,
        fonts["small"],
        "Levels 1-100 scale; extra levels need a fixed 1,500 XP each.",
        MUTED,
        (40, 137),
    )
    first_level = max(1, earned_level - 2)
    for row, reward_level in enumerate(range(first_level, first_level + 6)):
        reward = battle_pass_reward(reward_level)
        card = pygame.Rect(40, 180 + row * 56, 920, 48)
        is_claimed = reward_level in claimed_levels
        is_earned = reward_level <= earned_level
        fill = (44, 75, 58) if is_earned and not is_claimed else (38, 55, 57)
        pygame.draw.rect(surface, fill, card, border_radius=5)
        pygame.draw.rect(surface, GOLD_COLOR if is_earned else MUTED, card, 1, border_radius=5)
        detail = [f"{int(reward['credits']):,} credits"]
        crate_id = reward["crate_id"]
        if isinstance(crate_id, str):
            detail.append(str(CRATE_TYPES[crate_id]["name"]))
        unit_id = reward["unit_id"]
        if isinstance(unit_id, str):
            unit_index = unit_index_for_id(unit_id)
            unit_name = str(unit_stats(unit_index)["name"]) if unit_index is not None else unit_id
            detail.append(unit_name)
        state = "CLAIMED" if is_claimed else ("READY" if is_earned else "LOCKED")
        draw_text(surface, fonts["small"], f"Level {reward_level}", GOLD_COLOR, (58, card.y + 12))
        draw_text(surface, fonts["small"], " + ".join(detail), WHITE, (205, card.y + 12))
        draw_text(
            surface,
            fonts["tower"],
            state,
            HUMAN_COLOR if is_earned else MUTED,
            (850, card.y + 16),
        )

    if available:
        action = f"CLAIM LEVEL {min(available)}"
        action_color = HUMAN_COLOR
        draw_text(
            surface,
            fonts["tower"],
            "Claimable rewards are highlighted above.",
            WHITE,
            (390, 520),
        )
    else:
        action = "NO REWARD READY"
        action_color = MUTED
        draw_text(
            surface,
            fonts["tower"],
            f"Next level requires {required - progress} more XP.",
            WHITE,
            (390, 520),
        )
    _draw_button(surface, fonts["body"], pygame.Rect(390, 545, 220, 60), action, action_color)
    if status:
        draw_text(surface, fonts["tower"], status, WHITE, (220, 620))
    _draw_button(surface, fonts["body"], pygame.Rect(20, 620, 170, 55), "BACK", MUTED)


def draw_challenge_menu(
    surface: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    challenge_mode: str,
    selected_difficulty: str,
    story_level: int,
    daily_claimed: bool,
    status: str,
) -> None:
    surface.fill(BACKGROUND)
    pygame.draw.rect(surface, PANEL, (0, 0, SCREEN_WIDTH, 76))
    title = "DAILY CHALLENGE" if challenge_mode == "daily" else "STORY MODE"
    draw_text(surface, fonts["title"], title, WHITE, (25, 16))
    draw_text(surface, fonts["body"], "Select a challenge and deploy to begin.", MUTED, (25, 98))

    if challenge_mode == "daily":
        draw_text(
            surface,
            fonts["small"],
            "Clear every wave before your base falls. Rewards can be claimed once each day.",
            WHITE,
            (25, 154),
        )
        for index, mode in enumerate(GAME_MODES):
            key = str(mode["key"])
            reward = DAILY_CHALLENGES[key]
            rectangle = pygame.Rect(20 + index * 192, 230, 180, 150)
            selected = key == selected_difficulty
            pygame.draw.rect(
                surface,
                (53, 72, 73) if selected else (38, 55, 57),
                rectangle,
                border_radius=6,
            )
            pygame.draw.rect(
                surface,
                GOLD_COLOR if selected else (88, 110, 106),
                rectangle,
                2,
                border_radius=6,
            )
            draw_text(surface, fonts["body"], str(mode["name"]), WHITE, (rectangle.x + 12, rectangle.y + 12))
            draw_text(surface, fonts["small"], f"Clear {reward['waves']} waves", MUTED, (rectangle.x + 12, rectangle.y + 48))
            draw_text(surface, fonts["small"], f"{reward['credits']:,} credits", GOLD_COLOR, (rectangle.x + 12, rectangle.y + 76))
            draw_text(surface, fonts["small"], f"{reward['crates']} Supply Crate(s)", WHITE, (rectangle.x + 12, rectangle.y + 104))
    else:
        target_waves = min(
            STORY_BASE_WAVES + (story_level - 1) * STORY_WAVES_PER_LEVEL,
            STORY_MAX_WAVES,
        )
        reward = STORY_BASE_CREDITS + (story_level - 1) * STORY_LEVEL_CREDIT_INCREMENT
        panel = pygame.Rect(120, 205, 760, 250)
        pygame.draw.rect(surface, PANEL, panel, border_radius=10)
        pygame.draw.rect(surface, HUMAN_COLOR, panel, 2, border_radius=10)
        draw_text(surface, fonts["title"], f"CHAPTER {story_level}", GOLD_COLOR, (panel.x + 32, panel.y + 28))
        draw_text(surface, fonts["body"], f"Survive {target_waves} waves (maximum 50 per level).", WHITE, (panel.x + 32, panel.y + 86))
        draw_text(surface, fonts["body"], f"Reward: {reward:,} credits + 1 Story Crate", GOLD_COLOR, (panel.x + 32, panel.y + 132))
        draw_text(surface, fonts["small"], "Story Crates contain one unit: Common, Rare, Epic, Legendary, Mythic, or Secret.", MUTED, (panel.x + 32, panel.y + 182))
        draw_text(surface, fonts["small"], "Secret unit chance: 0.01%.", MUTED, (panel.x + 32, panel.y + 208))

    if status:
        draw_text(surface, fonts["small"], status, WHITE, (220, 530))
    _draw_button(surface, fonts["body"], pygame.Rect(20, 600, 170, 60), "BACK", MUTED)
    start_label = (
        "ALREADY CLAIMED"
        if challenge_mode == "daily" and daily_claimed
        else "START CHALLENGE"
    )
    _draw_button(
        surface,
        fonts["body"],
        pygame.Rect(760, 590, 220, 76),
        start_label,
        MUTED if challenge_mode == "daily" and daily_claimed else HUMAN_COLOR,
    )


def draw_crates(
    surface: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    credits: int,
    crates: dict[str, int],
    status: str,
) -> None:
    surface.fill(BACKGROUND)
    pygame.draw.rect(surface, PANEL, (0, 0, SCREEN_WIDTH, 76))
    draw_text(surface, fonts["title"], "SUPPLY CRATES", WHITE, (25, 16))
    draw_text(surface, fonts["body"], f"Credits: {credits}", GOLD_COLOR, (770, 22))
    draw_text(surface, fonts["body"], "Crates", GOLD_COLOR, (40, 110))
    for index, (crate_id, details) in enumerate(CRATE_TYPES.items()):
        row_y = 150 + index * 100
        draw_text(
            surface,
            fonts["small"],
            f"{details['name']} | Owned: {crates.get(crate_id, 0)}",
            WHITE,
            (40, row_y),
        )
        _draw_button(
            surface,
            fonts["small"],
            pygame.Rect(40, row_y + 24, 390, 48),
            f"OPEN {str(details['name']).upper()}",
            GOLD_COLOR,
        )
        draw_text(
            surface,
            fonts["tower"],
            str(details["description"]),
            MUTED,
            (40, row_y + 75),
        )
    if status:
        draw_text(surface, fonts["small"], status, WHITE, (220, 620))
    _draw_button(surface, fonts["body"], pygame.Rect(20, 620, 170, 55), "BACK", MUTED)


def draw_trait_lobby(
    surface: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    credits: int,
    owned_units: set[int],
    selected_unit: int,
    unit_traits: dict[str, dict[str, object]],
    trait_options: dict[str, list[dict[str, object]]],
    luck: int,
    batch_count: int,
    unit_scroll: int,
    option_scroll: int,
    status: str,
) -> None:
    surface.fill(BACKGROUND)
    pygame.draw.rect(surface, PANEL, (0, 0, SCREEN_WIDTH, 76))
    draw_text(surface, fonts["title"], "TRAIT ROLL LOBBY", WHITE, (25, 16))
    draw_text(surface, fonts["body"], f"Credits: {credits}", GOLD_COLOR, (770, 22))
    draw_text(surface, fonts["body"], "Select unit", GOLD_COLOR, (20, 88))
    visible_units = sorted(owned_units)[unit_scroll:unit_scroll + 8]
    for row_index, unit_index in enumerate(visible_units):
        unit = unit_stats(unit_index)
        unit_id = str(unit["id"])
        current_trait = unit_traits.get(unit_id)
        row = pygame.Rect(20, 115 + row_index * 56, 455, 49)
        selected = unit_index == selected_unit
        pygame.draw.rect(
            surface,
            (53, 72, 73) if selected else (34, 48, 48),
            row,
            border_radius=5,
        )
        pygame.draw.rect(
            surface,
            GOLD_COLOR if selected else RARITY_COLORS[str(unit["rarity"])],
            row,
            2,
            border_radius=5,
        )
        trait_name = str(current_trait["name"]) if current_trait else "No trait"
        draw_text(surface, fonts["small"], str(unit["name"]), WHITE, (row.x + 10, row.y + 5))
        draw_text(
            surface,
            fonts["tower"],
            f"{unit['rarity']} | Current trait: {trait_name}",
            MUTED,
            (row.x + 10, row.y + 28),
        )
    draw_text(
        surface,
        fonts["tower"],
        f"Units {unit_scroll + 1}-{min(unit_scroll + 8, len(owned_units))} of {len(owned_units)} | Scroll",
        MUTED,
        (20, 572),
    )

    unit = unit_stats(selected_unit)
    unit_id = str(unit["id"])
    current_trait = unit_traits.get(unit_id)
    current_options = trait_options.get(unit_id, [])
    draw_text(surface, fonts["body"], f"Roll for {unit['name']}", WHITE, (500, 88))
    for button_luck, rectangle, label in (
        (1, pygame.Rect(500, 145, 145, 48), "1x luck"),
        (10, pygame.Rect(660, 145, 145, 48), "10x luck"),
        (100, pygame.Rect(820, 145, 145, 48), "100x luck"),
    ):
        _draw_button(
            surface,
            fonts["small"],
            rectangle,
            label,
            GOLD_COLOR if button_luck == luck else HUMAN_COLOR,
        )
    for index, count in enumerate(TRAIT_BATCH_COUNTS):
        rectangle = pygame.Rect(500 + index * 115, 205, 105, 50)
        cost = TRAIT_ROLL_COSTS[luck] * count
        _draw_button(
            surface,
            fonts["small"],
            rectangle,
            f"{count}x | {cost}",
            GOLD_COLOR if count == batch_count else HUMAN_COLOR,
        )
    chance = TRAIT_BASE_CHANCE * (luck ** 0.5) * 100
    draw_text(
        surface,
        fonts["tower"],
        f"{batch_count} independent rolls | {chance:.2f}% trait chance each | "
        f"Cost: {TRAIT_ROLL_COSTS[luck] * batch_count}",
        MUTED,
        (500, 268),
    )
    draw_text(
        surface,
        fonts["tower"],
        "The 0.001% Overlord chance is separate from ordinary trait odds.",
        MUTED,
        (500, 287),
    )
    draw_text(
        surface,
        fonts["small"],
        f"Current: {current_trait['name'] if current_trait else 'No trait'}",
        GOLD_COLOR if current_trait else MUTED,
        (500, 325),
    )
    _draw_button(
        surface,
        fonts["small"],
        pygame.Rect(500, 355, 470, 40),
        f"KEEP CURRENT: {current_trait['name'] if current_trait else 'NO TRAIT'}",
        GOLD_COLOR,
    )
    draw_text(
        surface,
        fonts["tower"],
        f"Successful options: {len(current_options)} | Click an option to apply; "
        "keeping your current trait is always safe.",
        MUTED,
        (500, 397),
    )
    visible_options = current_options[option_scroll:option_scroll + 5]
    for row_index, trait in enumerate(visible_options):
        row = pygame.Rect(500, 420 + row_index * 36, 470, 32)
        pygame.draw.rect(surface, (38, 55, 57), row, border_radius=4)
        pygame.draw.rect(
            surface,
            GOLD_COLOR if trait["id"] == ULTIMATE_TRAIT_ID else HUMAN_COLOR,
            row,
            1,
            border_radius=4,
        )
        draw_text(
            surface,
            fonts["tower"],
            f"APPLY {trait['name']} | DMG x{trait['damage_multiplier']:g} | "
            f"Attack speed x{trait['attack_speed_multiplier']:g}",
            WHITE,
            (row.x + 8, row.y + 9),
        )
    if len(current_options) > 5:
        draw_text(
            surface,
            fonts["tower"],
            f"Options {option_scroll + 1}-{min(option_scroll + 5, len(current_options))} | Scroll",
            MUTED,
            (500, 605),
        )
    if status:
        draw_text(surface, fonts["small"], status, WHITE, (220, 635))
    _draw_button(surface, fonts["body"], pygame.Rect(20, 620, 170, 55), "BACK", MUTED)


def draw_unit_collection(
    surface: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    owned_units: set[int],
    equipped_units: set[int],
    unit_levels: dict[str, int],
    unit_copies: dict[str, int],
    selected_unit: int,
    scroll: int,
    status: str,
    mouse_position: tuple[int, int] | None = None,
    unit_traits: dict[str, dict[str, object]] | None = None,
) -> None:
    surface.fill(BACKGROUND)
    pygame.draw.rect(surface, PANEL, (0, 0, SCREEN_WIDTH, 76))
    draw_text(surface, fonts["title"], "UNIT COLLECTION", WHITE, (25, 16))
    draw_text(surface, fonts["small"], "Owned units and duplicate copies, grouped by rarity order", MUTED, (370, 27))

    indices = list(all_unit_indices())
    visible_indices = indices[scroll:scroll + 8]
    hovered_unit: int | None = None
    for row_index, unit_index in enumerate(visible_indices):
        unit = unit_stats(unit_index)
        unit_id = str(unit["id"])
        owned = unit_index in owned_units
        rarity = str(unit["rarity"])
        color = RARITY_COLORS[rarity]
        row = pygame.Rect(20, 105 + row_index * 55, 600, 49)
        pygame.draw.rect(surface, (53, 72, 73) if unit_index == selected_unit else (34, 48, 48), row, border_radius=5)
        pygame.draw.rect(surface, color if owned else (79, 87, 84), row, 2 if owned else 1, border_radius=5)
        name = str(unit["name"]) if owned else f"??? - {rarity}"
        draw_text(surface, fonts["small"], name, color if owned else MUTED, (row.x + 10, row.y + 5))
        copies = unit_copies.get(unit_id, 0)
        level = unit_levels.get(unit_id, 1)
        trait = (unit_traits or {}).get(unit_id)
        trait_label = f"Trait: {trait['name']} | " if trait is not None else ""
        if unit_index < len(TOWER_TYPES):
            quantity = f"Base unit | Level {level}"
        else:
            cost = duplicate_cost(unit_index)
            quantity = f"Level {level} | Copies {copies}/{cost} to next level"
        draw_text(
            surface,
            fonts["tower"],
            f"{trait_label}{rarity} | DMG {unit['damage']} | {quantity}",
            WHITE if owned else MUTED,
            (row.x + 10, row.y + 28),
        )
        action = pygame.Rect(630, row.y, 100, 49)
        if mouse_position is not None and (row.collidepoint(mouse_position) or action.collidepoint(mouse_position)):
            hovered_unit = unit_index
        action_text = "UNEQUIP" if unit_index in equipped_units else "EQUIP"
        action_color = GOLD_COLOR if unit_index in equipped_units else HUMAN_COLOR
        if not owned:
            action_text = "LOCKED"
            action_color = MUTED
        _draw_button(surface, fonts["tower"], action, action_text, action_color)

    detail_unit = hovered_unit if hovered_unit is not None else selected_unit
    unit = unit_stats(detail_unit)
    unit_id = str(unit["id"])
    owned = detail_unit in owned_units
    color = RARITY_COLORS[str(unit["rarity"])]
    detail_rect = pygame.Rect(750, 105, 230, 430)
    pygame.draw.rect(surface, PANEL, detail_rect, border_radius=6)
    pygame.draw.rect(surface, color, detail_rect, 2, border_radius=6)
    level = unit_levels.get(unit_id, 1)
    level_multiplier = UPGRADE_STAT_MULTIPLIER ** (level - 1)
    is_starter = unit_id == STARTER_UNIT_ID
    abilities = set(unit["abilities"])
    roles: list[str] = []
    if int(unit["damage"]) > 0:
        roles.append("Damage dealer")
    if "income" in abilities:
        roles.append("Money maker")
    if abilities.intersection({"burn", "poison", "bleed"}):
        roles.append("Damage over time")
    if "slow" in abilities:
        roles.append("Crowd control")
    if "splash" in abilities:
        roles.append("Area damage")
    if "pierce" in abilities:
        roles.append("Piercing")
    if "chain" in abilities:
        roles.append("Chain attack")
    if "execute" in abilities:
        roles.append("Finisher")
    descriptor = str(unit.get("role", ""))
    if descriptor and not descriptor.lower().endswith("specialist"):
        roles.append(descriptor)

    draw_text(surface, fonts["tower"], "UNIT DETAILS" if hovered_unit is None else "UNIT PREVIEW", GOLD_COLOR, (760, 116))
    draw_text(surface, fonts["small"], str(unit["rarity"]), color, (760, 140))
    draw_text(surface, fonts["body"], str(unit["name"]) if owned else "Locked unit", WHITE, (760, 161))
    starter_label = "Starter" if is_starter else "Not starter"
    draw_text(
        surface,
        fonts["tower"],
        f"{starter_label} | Place ${unit['cost']}",
        HUMAN_COLOR if is_starter else MUTED,
        (760, 187),
    )
    role_lines = roles or [str(unit.get("role", "Specialist"))]
    for role_index, role in enumerate(role_lines[:3]):
        draw_text(surface, fonts["tower"], role, WHITE, (760, 208 + role_index * 18))

    stats_top = 208 + min(len(role_lines), 3) * 18 + 5
    draw_text(surface, fonts["tower"], f"BASE  ->  LEVEL {level}", GOLD_COLOR, (760, stats_top))
    draw_text(
        surface,
        fonts["tower"],
        f"DMG {unit['damage']} -> {round(int(unit['damage']) * level_multiplier)}",
        WHITE,
        (760, stats_top + 20),
    )
    draw_text(
        surface,
        fonts["tower"],
        f"RANGE {unit['range']} -> {round(float(unit['range']) * level_multiplier)}",
        WHITE,
        (760, stats_top + 39),
    )
    draw_text(
        surface,
        fonts["tower"],
        (
            f"RATE {float(unit['fire_rate']):g}s -> {float(unit['fire_rate']) / level_multiplier:.2f}s"
            if float(unit["fire_rate"]) < 99
            else "RATE N/A"
        ),
        WHITE,
        (760, stats_top + 58),
    )
    if "income" in abilities:
        base_income = int(unit["income"])
        upgraded_income = round(base_income * level_multiplier)
        draw_text(
            surface,
            fonts["tower"],
            f"CASH {base_income} -> {upgraded_income} / {unit['income_interval']:g}s",
            GOLD_COLOR,
            (760, stats_top + 78),
        )
    ability_top = stats_top + (101 if "income" in abilities else 81)
    draw_text(surface, fonts["tower"], f"Copies: {unit_copies.get(unit_id, 0)}", WHITE, (760, ability_top))
    draw_text(surface, fonts["tower"], "Abilities:", GOLD_COLOR, (760, ability_top + 20))
    for ability_index, ability in enumerate(unit["abilities"]):
        draw_text(surface, fonts["tower"], str(ability), MUTED, (760, ability_top + 40 + ability_index * 18))

    selected_stats = unit_stats(selected_unit)
    selected_id = str(selected_stats["id"])
    selected_owned = selected_unit in owned_units
    draw_text(
        surface,
        fonts["tower"],
        f"Selected: {selected_stats['name']}",
        WHITE,
        (760, 525),
    )
    if selected_owned:
        if selected_unit < len(TOWER_TYPES):
            upgrade_label = f"UPGRADE {unit_upgrade_cost(unit_levels.get(selected_id, 1))} CREDITS"
        else:
            upgrade_label = f"LEVEL UP ({duplicate_cost(selected_unit)} COPIES)"
    else:
        upgrade_label = "UNIT LOCKED"
    _draw_button(
        surface,
        fonts["small"],
        pygame.Rect(800, 545, 170, 46),
        upgrade_label,
        GOLD_COLOR if selected_owned else MUTED,
    )

    if status:
        draw_text(surface, fonts["small"], status, WHITE, (210, 620))
    _draw_button(surface, fonts["body"], pygame.Rect(20, 600, 170, 60), "BACK", MUTED)
    _draw_button(surface, fonts["small"], pygame.Rect(850, 605, 130, 58), "START GAME", HUMAN_COLOR)
    draw_text(surface, fonts["tower"], f"Showing {scroll + 1}-{min(scroll + 8, len(indices))} of {len(indices)}. Scroll to browse.", MUTED, (20, 570))


def draw_admin_panel(
    surface: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    account_name: str | None,
    accounts: list[dict[str, object]],
    account_scroll: int,
    username_input: str,
    credits_input: str,
    starting_cash_input: str,
    starting_cash: int,
    selected_unit: int,
    status: str,
    focused_field: str | None,
    crate_count_input: str = "1",
    story_level_input: str = "1",
    selected_crate: str = "standard",
    selected_mode: str = "normal",
    selected_map: str = "meadow",
    game_speed: float = 1.0,
) -> None:
    surface.fill(BACKGROUND)
    pygame.draw.rect(surface, PANEL, (0, 0, SCREEN_WIDTH, 70))
    draw_text(surface, fonts["title"], "ADMIN PANEL", WHITE, (25, 16))
    draw_text(surface, fonts["small"], f"Administrator: {account_name or 'unknown'}", GOLD_COLOR, (300, 24))

    _draw_button(surface, fonts["small"], pygame.Rect(20, 78, 170, 38), "BACK TO LOBBY", MUTED)
    _draw_button(surface, fonts["small"], pygame.Rect(820, 78, 160, 38), "REFRESH ACCOUNTS", HUMAN_COLOR)

    _draw_input(
        surface,
        fonts,
        pygame.Rect(20, 128, 230, 38),
        "Account username",
        username_input,
        focused_field == "admin_username",
        False,
    )
    _draw_input(
        surface,
        fonts,
        pygame.Rect(265, 128, 150, 38),
        "Credits to add",
        credits_input,
        focused_field == "admin_credits",
        False,
    )
    _draw_button(surface, fonts["small"], pygame.Rect(425, 128, 155, 38), "ADD CREDITS", GOLD_COLOR)
    speed_label = "REVOKE CUSTOM SPEED" if any(
        str(account.get("username", "")).casefold() == username_input.casefold()
        and account.get("custom_speed_access") is True
        for account in accounts
    ) else "GRANT CUSTOM SPEED"
    _draw_button(surface, fonts["small"], pygame.Rect(760, 128, 220, 38), speed_label, HUMAN_COLOR)

    draw_text(surface, fonts["small"], "Grant unit:", WHITE, (20, 183))
    unit = unit_stats(selected_unit)
    unit_name = f"{unit['name']} ({unit['rarity']})"
    _draw_button(surface, fonts["body"], pygame.Rect(150, 178, 42, 36), "<", MUTED)
    draw_text(surface, fonts["small"], str(unit_name), RARITY_COLORS[str(unit["rarity"])], (205, 190))
    _draw_button(surface, fonts["body"], pygame.Rect(480, 178, 42, 36), ">", MUTED)
    _draw_button(surface, fonts["small"], pygame.Rect(550, 178, 220, 36), "UNLOCK SELECTED UNIT", HUMAN_COLOR)
    _draw_button(surface, fonts["small"], pygame.Rect(790, 178, 190, 36), "UNLOCK ALL UNITS", GOLD_COLOR)

    _draw_button(
        surface,
        fonts["small"],
        pygame.Rect(20, 228, 200, 36),
        f"CRATE: {CRATE_TYPES[selected_crate]['name']}",
        GOLD_COLOR,
    )
    _draw_input(
        surface,
        fonts,
        pygame.Rect(230, 228, 150, 36),
        "Crate amount",
        crate_count_input,
        focused_field == "admin_crate_count",
        False,
    )
    _draw_button(surface, fonts["small"], pygame.Rect(395, 228, 175, 36), "GRANT CRATES", GOLD_COLOR)

    _draw_input(
        surface,
        fonts,
        pygame.Rect(20, 278, 200, 36),
        "Starting cash",
        starting_cash_input,
        focused_field == "starting_cash",
        False,
    )
    _draw_button(surface, fonts["small"], pygame.Rect(230, 278, 190, 36), "SAVE STARTING CASH", GOLD_COLOR)
    _draw_button(surface, fonts["small"], pygame.Rect(440, 278, 180, 36), "SET STORY LEVEL", HUMAN_COLOR)
    _draw_input(
        surface,
        fonts,
        pygame.Rect(630, 278, 150, 36),
        "Story level",
        story_level_input,
        focused_field == "admin_story_level",
        False,
    )
    _draw_button(surface, fonts["small"], pygame.Rect(790, 278, 190, 36), "RESET DAILY CLAIM", MUTED)

    current_mode = next((str(mode["name"]) for mode in GAME_MODES if mode["key"] == selected_mode), selected_mode)
    current_map = str(MAPS.get(selected_map, MAPS["meadow"])["name"])
    _draw_button(
        surface,
        fonts["small"],
        pygame.Rect(20, 328, 300, 36),
        f"MODE: {current_mode}  [CLICK TO CYCLE]",
        HUMAN_COLOR,
    )
    _draw_button(
        surface,
        fonts["small"],
        pygame.Rect(330, 328, 300, 36),
        f"MAP: {current_map}  [CLICK TO CYCLE]",
        HUMAN_COLOR,
    )
    _draw_button(
        surface,
        fonts["small"],
        pygame.Rect(640, 328, 340, 36),
        f"GAME SPEED: {game_speed:g}X  [CLICK TO CYCLE]",
        GOLD_COLOR,
    )

    draw_text(surface, fonts["body"], f"Registered accounts ({len(accounts)})", WHITE, (20, 375))
    headers = ("USERNAME", "ROLE", "CREDITS", "UNITS", "CRATES", "STORY", "CASH", "10X")
    column_x = (30, 175, 270, 380, 485, 590, 685, 810)
    for label, x in zip(headers, column_x):
        draw_text(surface, fonts["tower"], label, GOLD_COLOR, (x, 403))
    visible_accounts = accounts[account_scroll:account_scroll + 7]
    for row_index, account in enumerate(visible_accounts):
        y = 425 + row_index * 29
        username = str(account.get("username", ""))
        row = pygame.Rect(20, y - 2, 960, 27)
        pygame.draw.rect(surface, (53, 72, 73) if row_index % 2 == 0 else (38, 55, 57), row)
        draw_text(surface, fonts["tower"], username[:18], WHITE, (30, y + 4))
        draw_text(
            surface,
            fonts["tower"],
            "ADMIN" if account.get("is_admin") is True else "Player",
            GOLD_COLOR if account.get("is_admin") is True else MUTED,
            (175, y + 4),
        )
        draw_text(surface, fonts["tower"], str(account.get("credits", 0)), WHITE, (270, y + 4))
        draw_text(surface, fonts["tower"], str(account.get("unlocked_units", 0)), WHITE, (380, y + 4))
        crate_counts = account.get("crates", {})
        crate_total = sum(value for value in crate_counts.values() if isinstance(value, int)) if isinstance(crate_counts, dict) else 0
        draw_text(surface, fonts["tower"], str(crate_total), WHITE, (485, y + 4))
        draw_text(surface, fonts["tower"], str(account.get("story_level", 1)), WHITE, (590, y + 4))
        draw_text(surface, fonts["tower"], f"${account.get('starting_cash', 250)}", WHITE, (685, y + 4))
        draw_text(surface, fonts["tower"], "YES" if account.get("custom_speed_access") is True else "NO", WHITE, (810, y + 4))
    if not accounts:
        draw_text(surface, fonts["small"], "No registered accounts found.", MUTED, (30, 430))
    if status:
        draw_text(surface, fonts["tower"], status, WHITE, (20, 641))
    draw_text(surface, fonts["tower"], "Scroll accounts | Click a row to select its account", MUTED, (20, 663))


def _draw_input(
    surface: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    rectangle: pygame.Rect,
    label: str,
    value: str,
    focused: bool,
    password: bool,
) -> None:
    pygame.draw.rect(surface, (38, 55, 57), rectangle, border_radius=4)
    pygame.draw.rect(surface, GOLD_COLOR if focused else (88, 110, 106), rectangle, 2, border_radius=4)
    display_value = "*" * len(value) if password else value
    placeholder = label if not value else display_value
    color = MUTED if not value else WHITE
    draw_text(surface, fonts["small"], placeholder, color, (rectangle.x + 10, rectangle.y + 12))


def _draw_button(
    surface: pygame.Surface,
    font: pygame.font.Font,
    rectangle: pygame.Rect,
    text: str,
    color: tuple[int, int, int],
) -> None:
    pygame.draw.rect(surface, (38, 55, 57), rectangle, border_radius=4)
    pygame.draw.rect(surface, color, rectangle, 2, border_radius=4)
    label = font.render(text, True, WHITE)
    surface.blit(label, label.get_rect(center=rectangle.center))


@lru_cache(maxsize=64)
def _placement_icon(
    color: tuple[int, int, int],
    icon: str,
) -> pygame.Surface:
    preview_icon = pygame.Surface((38, 38), pygame.SRCALPHA)
    pygame.draw.circle(preview_icon, (*color, 145), (19, 19), 15)
    label = pygame.font.Font(None, 25).render(icon, True, WHITE)
    preview_icon.blit(label, label.get_rect(center=(19, 19)))
    return preview_icon


def _draw_3d_ground(
    surface: pygame.Surface,
    path_points: tuple[tuple[int, int], ...],
    map_name: str,
) -> None:
    surface.blit(_map_background(path_points, map_name), (0, 0))

    for y in range(TOP_BAR_HEIGHT + 12, TOWER_BAR_TOP, 28):
        shadow = (42 + ((y // 28) % 2) * 6, 52 + ((y // 28) % 2) * 5, 44 + ((y // 28) % 2) * 4)
        pygame.draw.line(surface, shadow, (0, y + 6), (SCREEN_WIDTH, y + 6), 2)

    shadow_points = [(x + 8, y + 8) for x, y in path_points]
    pygame.draw.lines(surface, (34, 24, 20), False, shadow_points, 70)
    pygame.draw.lines(surface, (73, 57, 42), False, shadow_points, 64)
    pygame.draw.lines(surface, PATH_COLOR, False, path_points, 54)
    pygame.draw.lines(surface, (207, 183, 142), False, path_points, 2)

    pygame.draw.circle(
        surface,
        (80, 153, 217),
        (SCREEN_WIDTH - 31, path_points[-1][1] + 10),
        25,
    )
    pygame.draw.circle(
        surface,
        (167, 213, 233),
        (SCREEN_WIDTH - 31, path_points[-1][1] + 10),
        25,
        3,
    )


def draw_game(
    surface: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    defenders: list[Defender],
    zombies: list[Zombie],
    projectiles: list[Projectile],
    selected_defender: Defender | None,
    money: int,
    lives: int,
    wave: int,
    status: str,
    game_over: bool,
    selected_tower_type: int,
    mouse_position: tuple[int, int],
    valid_placement: bool,
    placement_mode: bool,
    available_towers: set[int],
    game_speed: float,
    credits: int,
    mode_key: str,
    unit_management_open: bool = False,
    unit_management_scroll: int = 0,
    preparing: bool = False,
    path_points: tuple[tuple[int, int], ...] = SCREEN_PATH_POINTS,
    map_name: str = "Meadow",
    run_label: str | None = None,
    target_waves: int | None = None,
    victory: bool = False,
    autoplay_mode: str = "off",
    player: dict[str, float] | None = None,
    world_3d: bool = False,
) -> None:
    if world_3d:
        surface.fill((0, 0, 0, 0))
    else:
        _draw_3d_ground(surface, path_points, map_name)
        if player is not None:
            _draw_3d_player(surface, player, (SCREEN_WIDTH // 2, 500))
        for defender in defenders:
            defender.draw(surface, defender is selected_defender)
        for zombie in zombies:
            zombie.draw(surface)
        for projectile in projectiles:
            projectile.draw(surface)

    mouse_x, mouse_y = mouse_position
    if not world_3d and placement_mode and TOP_BAR_HEIGHT <= mouse_y < TOWER_BAR_TOP:
        tower_type = unit_stats(selected_tower_type)
        center = (mouse_x, mouse_y)
        preview_color = (100, 220, 135) if valid_placement else (235, 100, 91)
        radius = int(tower_type["range"])
        draw_circle_overlay(surface, center, radius, tower_type["color"], 24)
        pygame.draw.circle(surface, preview_color, center, radius, 1)
        preview_icon = _placement_icon(
            tuple(tower_type["color"]),
            str(tower_type["icon"]),
        )
        surface.blit(preview_icon, (mouse_x - 19, mouse_y - 19))
        pygame.draw.circle(surface, preview_color, center, 18, 2)

    pygame.draw.rect(surface, PANEL, (0, 0, SCREEN_WIDTH, TOP_BAR_HEIGHT))
    pygame.draw.line(
        surface,
        (76, 105, 100),
        (0, TOP_BAR_HEIGHT - 1),
        (SCREEN_WIDTH, TOP_BAR_HEIGHT - 1),
        2,
    )
    draw_text(surface, fonts["title"], "LAST STAND", WHITE, (18, 8))
    draw_text(surface, fonts["small"], f"Wave {wave}", GOLD_COLOR, (22, 43))
    draw_text(surface, fonts["body"], f"Humans: {len(defenders)}", HUMAN_COLOR, (185, 25))
    draw_text(surface, fonts["body"], f"Scrap: ${money}", GOLD_COLOR, (365, 25))
    draw_text(surface, fonts["body"], f"Base: {lives} lives", WHITE, (525, 25))
    draw_text(surface, fonts["small"], f"Credits: {credits}", GOLD_COLOR, (185, 48))
    mode = GAME_MODES_BY_KEY.get(mode_key)
    mode_name = str(mode["name"]) if mode is not None else mode_key
    draw_text(surface, fonts["small"], f"Mode: {mode_name}", MUTED, (365, 48))
    draw_text(
        surface,
        fonts["tower"],
        f"{run_label or 'Infinite'} | {map_name}"
        + (f" | Target: {target_waves}" if target_waves is not None else ""),
        MUTED,
        (485, 51),
    )
    draw_text(surface, fonts["small"], f"Speed: {game_speed:g}x", MUTED, (610, 13))
    autoplay_labels = {"off": "OFF", "waves": "WAVES", "full": "FULL"}
    autoplay_label = autoplay_labels.get(autoplay_mode, "OFF")
    _draw_button(
        surface,
        fonts["tower"],
        pygame.Rect(610, 34, 205, 30),
        f"AUTO: {autoplay_label} [O]",
        GOLD_COLOR if autoplay_mode != "off" else MUTED,
    )
    if wave > 0 and not game_over and not preparing:
        _draw_button(
            surface,
            fonts["tower"],
            pygame.Rect(830, 5, 150, 56),
            "SKIP WAVE [N]",
            GOLD_COLOR,
        )

    if status:
        status_color = GOLD_COLOR if "Need" in status else WHITE
        draw_text(surface, fonts["small"], status, status_color, (18, TOWER_BAR_TOP - 21))

    pygame.draw.rect(
        surface,
        PANEL,
        (0, TOWER_BAR_TOP, SCREEN_WIDTH, SCREEN_HEIGHT - TOWER_BAR_TOP),
    )
    pygame.draw.line(
        surface,
        (76, 105, 100),
        (0, TOWER_BAR_TOP),
        (SCREEN_WIDTH, TOWER_BAR_TOP),
        2,
    )
    owned_counts: dict[int, int] = {}
    for defender in defenders:
        owned_counts[defender.tower_type] = owned_counts.get(defender.tower_type, 0) + 1
    for slot, index in enumerate(sorted(available_towers)):
        tower_type = unit_stats(index)
        x = 10 + slot * 102
        card = pygame.Rect(x, TOWER_BAR_TOP + 8, 96, 64)
        selected = index == selected_tower_type
        pygame.draw.rect(surface, (53, 72, 73) if selected else (38, 55, 57), card, border_radius=6)
        pygame.draw.rect(
            surface,
            tower_type["color"] if selected else (88, 110, 106),
            card,
            2,
            border_radius=6,
        )
        owned = owned_counts.get(index, 0)
        hotkey = str(slot + 1)
        tower_name = fonts["tower"].render(f"[{hotkey}] {tower_type['name']}", True, tower_type["color"])
        surface.blit(tower_name, (x + 4, TOWER_BAR_TOP + 13))
        draw_text(surface, fonts["tower"], str(tower_type["role"]), MUTED, (x + 5, TOWER_BAR_TOP + 34))
        draw_text(
            surface,
            fonts["small"],
            f"${tower_type['cost']} | {owned}x",
            WHITE,
            (x + 5, TOWER_BAR_TOP + 51),
        )

    upgrade_button = pygame.Rect(530, TOWER_BAR_TOP + 8, 170, 64)
    pygame.draw.rect(surface, (53, 72, 73), upgrade_button, border_radius=6)
    pygame.draw.rect(surface, GOLD_COLOR, upgrade_button, 2, border_radius=6)
    if selected_defender is None:
        draw_text(
            surface,
            fonts["body"],
            "[U] Upgrade",
            MUTED,
            (upgrade_button.x + 12, upgrade_button.y + 10),
        )
        draw_text(
            surface,
            fonts["small"],
            "Select a human first",
            MUTED,
            (upgrade_button.x + 12, upgrade_button.y + 37),
        )
    elif selected_defender.level >= combat_upgrade_cap(selected_defender.tower_type):
        draw_text(
            surface,
            fonts["body"],
            "MAX LEVEL",
            GOLD_COLOR,
            (upgrade_button.x + 12, upgrade_button.y + 10),
        )
        draw_text(
            surface,
            fonts["small"],
            f"{selected_defender.stats['name']} Lv.{selected_defender.level}",
            WHITE,
            (upgrade_button.x + 12, upgrade_button.y + 37),
        )
    else:
        next_cost = (
            UPGRADE_COSTS[selected_defender.level - 1]
            if selected_defender.level <= len(UPGRADE_COSTS)
            else round(UPGRADE_COSTS[-1] * 1.5 ** (selected_defender.level - len(UPGRADE_COSTS)))
        )
        draw_text(
            surface,
            fonts["body"],
            f"[U] Upgrade Lv.{selected_defender.level + 1}",
            GOLD_COLOR,
            (upgrade_button.x + 12, upgrade_button.y + 10),
        )
        draw_text(
            surface,
            fonts["small"],
            f"{selected_defender.stats['name']}  |  ${next_cost}",
            WHITE,
            (upgrade_button.x + 12, upgrade_button.y + 37),
        )
    manager_button = pygame.Rect(715, TOWER_BAR_TOP + 8, 255, 64)
    pygame.draw.rect(surface, (53, 72, 73), manager_button, border_radius=6)
    pygame.draw.rect(
        surface,
        GOLD_COLOR if unit_management_open else (88, 110, 106),
        manager_button,
        2,
        border_radius=6,
    )
    draw_text(surface, fonts["body"], "[M] UNIT MANAGEMENT", WHITE, (manager_button.x + 12, manager_button.y + 9))
    draw_text(surface, fonts["tower"], "Click unit to select | RMB: sell", MUTED, (manager_button.x + 12, manager_button.y + 38))

    if unit_management_open:
        _draw_unit_management_panel(
            surface,
            fonts,
            defenders,
            selected_defender,
            money,
            unit_management_scroll,
        )

    if game_over:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 15, 17, 190))
        surface.blit(overlay, (0, 0))
        message = fonts["title"].render(
            "CHALLENGE COMPLETE" if victory else "THE BASE HAS FALLEN",
            True,
            WHITE,
        )
        hint = fonts["body"].render(
            (
                f"Completed {wave} waves. You have {credits} credits."
                if victory
                else f"You reached wave {wave}. You have {credits} credits."
            ),
            True,
            GOLD_COLOR,
        )
        surface.blit(message, message.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 22)))
        surface.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 22)))
        lobby_button = pygame.Rect(300, 410, 180, 56)
        retry_button = pygame.Rect(520, 410, 180, 56)
        _draw_button(surface, fonts["body"], lobby_button, "LOBBY", HUMAN_COLOR)
        retry_label = (
            "NEXT LEVEL"
            if victory and run_label is not None and run_label.startswith("Story")
            else "LOBBY"
            if victory
            else "RETRY"
        )
        _draw_button(surface, fonts["body"], retry_button, retry_label, GOLD_COLOR)
        draw_text(surface, fonts["small"], "Esc quits", MUTED, (SCREEN_WIDTH // 2 - 35, 485))
    elif preparing:
        draw_text(
            surface,
            fonts["body"],
            "DEPLOYMENT PAUSED",
            GOLD_COLOR,
            (730, 455),
        )
        draw_text(
            surface,
            fonts["tower"],
            "Place units; simulation starts when ready.",
            WHITE,
            (705, 480),
        )
        _draw_button(
            surface,
            fonts["small"],
            pygame.Rect(605, 510, 145, 62),
            "LOBBY",
            MUTED,
        )
        _draw_button(
            surface,
            fonts["body"],
            pygame.Rect(770, 510, 200, 62),
            "START WAVE",
            HUMAN_COLOR,
        )


def _draw_unit_management_panel(
    surface: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    defenders: list[Defender],
    selected_defender: Defender | None,
    money: int,
    scroll: int,
) -> None:
    panel = pygame.Rect(690, 84, 290, 500)
    pygame.draw.rect(surface, PANEL, panel, border_radius=8)
    pygame.draw.rect(surface, GOLD_COLOR, panel, 2, border_radius=8)
    draw_text(surface, fonts["body"], "UNIT MANAGEMENT", WHITE, (705, 94))
    draw_text(surface, fonts["tower"], f"Placed units: {len(defenders)} | Scroll to browse", MUTED, (705, 116))

    for row_index, defender in enumerate(defenders[scroll:scroll + 5]):
        row = pygame.Rect(705, 128 + row_index * 32, 260, 28)
        selected = defender is selected_defender
        pygame.draw.rect(surface, (53, 72, 73) if selected else (38, 55, 57), row, border_radius=3)
        pygame.draw.rect(surface, GOLD_COLOR if selected else (88, 110, 106), row, 1, border_radius=3)
        draw_text(
            surface,
            fonts["tower"],
            f"{defender.stats['name']}  Lv.{defender.level}  ({int(defender.x)},{int(defender.y)})",
            WHITE,
            (712, row.y + 7),
        )

    if not defenders:
        draw_text(surface, fonts["small"], "Place a unit to manage it here.", MUTED, (705, 145))
    if selected_defender is None:
        draw_text(surface, fonts["small"], "Select a placed unit.", MUTED, (705, 305))
        return

    defender = selected_defender
    stats_top = 300
    draw_text(surface, fonts["small"], f"{defender.stats['name']}  |  Level {defender.level}", GOLD_COLOR, (705, stats_top))
    if defender.level >= combat_upgrade_cap(defender.tower_type):
        next_level = None
        upgrade_cost = 0
    else:
        next_level = defender.level + 1
        upgrade_cost = (
            UPGRADE_COSTS[defender.level - 1]
            if defender.level <= len(UPGRADE_COSTS)
            else round(UPGRADE_COSTS[-1] * 1.5 ** (defender.level - len(UPGRADE_COSTS)))
        )
    next_damage = (
        round(int(defender.stats["damage"]) * defender.lobby_multiplier * (1.35 ** (next_level - 1)))
        if next_level is not None
        else None
    )
    next_range = (
        round(float(defender.stats["range"]) * defender.lobby_multiplier + (next_level - 1) * 20)
        if next_level is not None
        else None
    )
    next_fire_rate = (
        float(defender.stats["fire_rate"]) / defender.lobby_multiplier * (0.88 ** (next_level - 1))
        if next_level is not None
        else None
    )
    draw_text(
        surface,
        fonts["tower"],
        f"Damage: {defender.damage}" + (f" -> {next_damage}" if next_damage is not None else " (MAX)"),
        WHITE,
        (705, stats_top + 25),
    )
    draw_text(
        surface,
        fonts["tower"],
        f"Range: {defender.attack_range:g}" + (f" -> {next_range}" if next_range is not None else " (MAX)"),
        WHITE,
        (705, stats_top + 45),
    )
    rate_label = (
        f"Fire interval: {defender.fire_rate:.2f}s"
        + (f" -> {next_fire_rate:.2f}s" if next_fire_rate is not None else " (MAX)")
        if defender.fire_rate < 99
        else "Fire interval: N/A"
    )
    draw_text(surface, fonts["tower"], rate_label, WHITE, (705, stats_top + 65))
    if "income" in defender.stats["abilities"]:
        income = round(
            int(defender.stats["income"])
            * defender.lobby_multiplier
            * defender.level
        )
        next_income = (
            round(int(defender.stats["income"]) * defender.lobby_multiplier * next_level)
            if next_level is not None
            else None
        )
        draw_text(
            surface,
            fonts["tower"],
            f"Income: ${income}/tick" + (f" -> ${next_income}" if next_income is not None else " (MAX)"),
            GOLD_COLOR,
            (705, stats_top + 85),
        )

    button = pygame.Rect(710, 530, 250, 40)
    if next_level is None:
        _draw_button(surface, fonts["small"], button, "MAX LEVEL", MUTED)
    else:
        _draw_button(
            surface,
            fonts["small"],
            button,
            f"UPGRADE TO LV.{next_level} - ${upgrade_cost}",
            GOLD_COLOR if money >= upgrade_cost else MUTED,
        )
