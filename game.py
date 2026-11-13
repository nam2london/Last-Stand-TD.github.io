"""Game loop and tower-defense rules."""

import math
import random
from dataclasses import dataclass
from datetime import date

import pygame

from account_client import AccountClient, AccountServiceError
from entities import Defender, Projectile, Zombie
from progression import (
    CRATE_TYPES,
    ROLL_COST,
    STARTER_UNIT_ID,
    TRAIT_BATCH_COUNTS,
    TRAIT_BASE_CHANCE,
    TRAITS,
    TRAIT_ROLL_COSTS,
    ULTIMATE_TRAIT_ID,
    all_unit_indices,
    battle_pass_level,
    battle_pass_reward,
    combat_upgrade_cap,
    duplicate_cost,
    random_trait,
    roll_unit,
    roll_story_crate_unit,
    roll_traits,
    BATTLE_PASS_XP_PER_WAVE,
    unit_index_for_id,
    unit_stats,
    unit_upgrade_cost,
)
from rendering import (
    draw_admin_panel,
    draw_battle_pass,
    draw_crates,
    draw_challenge_menu,
    draw_game,
    draw_setup,
    draw_trait_lobby,
    draw_unit_collection,
)
from settings import (
    DAILY_CHALLENGES,
    GAME_MODES,
    GAME_MODES_BY_KEY,
    MAPS,
    SCREEN_PATH_POINTS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TOP_BAR_HEIGHT,
    TOWER_BAR_TOP,
    STORY_BASE_CREDITS,
    STORY_LEVEL_CREDIT_INCREMENT,
    STORY_BASE_WAVES,
    STORY_WAVES_PER_LEVEL,
    STORY_MAX_WAVES,
    MAX_EQUIPPED_TOWERS,
    DEFAULT_GAME_SPEED,
    GAME_SPEED_PRESETS,
    LOBBY_STATION_RECTS,
    LOBBY_MOVE_SPEED,
    LOBBY_JUMP_VELOCITY,
    LOBBY_GRAVITY,
    TOWER_TYPES,
    UPGRADE_COSTS,
)


@dataclass
class WaveSpawnGroup:
    wave: int
    enemies: list[str]
    spawn_timer: float = 0.0
    spawned: int = 0
    defeated: int = 0
    escaped: int = 0
    skipped: bool = False


class TowerDefenseGame:
    """Owns the simulation state and the Pygame event loop."""

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Last Stand - Tower Defense")
        self.screen = pygame.display.set_mode(
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            pygame.HIDDEN,
        )
        self.overlay_surface = pygame.Surface(
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            pygame.SRCALPHA,
        )
        self.frame_surface = self.screen
        self.mouse_position = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        self.ui_mouse_position = self.mouse_position
        self.held_keys: set[int] = set()
        self.fonts = {
            "title": pygame.font.Font(None, 34),
            "body": pygame.font.Font(None, 25),
            "small": pygame.font.Font(None, 19),
            "tower": pygame.font.Font(None, 15),
        }
        self.account_client = AccountClient()
        self.screen_state = "lobby"
        self.available_towers = set(range(MAX_EQUIPPED_TOWERS))
        self.game_speed = DEFAULT_GAME_SPEED
        self.autoplay_mode = "off"
        self.autoplay_timer = 0.0
        self.speed_input = f"{DEFAULT_GAME_SPEED:g}"
        self.username_input = ""
        self.password_input = ""
        self.grant_username_input = ""
        self.focused_field: str | None = None
        self.account_name: str | None = None
        self.account_token: str | None = None
        self.credits = 0
        self.owned_units = set(range(len(TOWER_TYPES)))
        starter_index = unit_index_for_id(STARTER_UNIT_ID)
        if starter_index is not None:
            self.owned_units.add(starter_index)
        self.unit_copies: dict[str, int] = {}
        self.unit_levels: dict[str, int] = {}
        self.unit_traits: dict[str, dict[str, object]] = {}
        self.trait_options: dict[str, list[dict[str, object]]] = {}
        self.trait_luck = 1
        self.trait_batch_count = 5
        self.trait_unit_scroll = 0
        self.trait_option_scroll = 0
        self.crates: dict[str, int] = {crate_id: 0 for crate_id in CRATE_TYPES}
        self.battle_pass_xp = 0
        self.battle_pass_claimed: set[int] = set()
        self.starting_cash = 250
        self.starting_cash_input = "250"
        self.admin_username_input = ""
        self.admin_credits_input = ""
        self.admin_crate_count_input = "1"
        self.admin_story_level_input = "1"
        self.admin_selected_crate = "standard"
        self.admin_accounts: list[dict[str, object]] = []
        self.admin_account_scroll = 0
        self.collection_scroll = 0
        self.selected_lobby_unit = 0
        self.selected_mode = "normal"
        self.selected_map = "meadow"
        self.play_mode = "infinite"
        self.daily_challenge_date = ""
        self.story_level = 1
        self.story_level_playing = 1
        self.challenge_target_waves: int | None = None
        self.challenge_won = False
        self.is_admin = False
        self.has_custom_speed = False
        self.status = "Explore with WASD, right-click to face a direction, jump with Space, and use E at a station."
        self.pending_credits = 0
        self.pending_crates = 0
        self.pending_battle_pass_xp = 0
        self.match_rewards_saved = False
        self.autoplay_timer = 0.0
        self.path_points = tuple(MAPS[self.selected_map]["path_points"])
        self.lobby_player = {
            "x": 180.0,
            "y": 220.0,
            "vx": 0.0,
            "vy": 0.0,
            "z": 0.0,
            "z_velocity": 0.0,
            "grounded": True,
        }
        self.lobby_facing_heading = 0.0
        self.last_lobby_station: str | None = None
        self.player = self.lobby_player
        self.reset()

    def reset(self) -> None:
        self.defenders: list[Defender] = []
        self.zombies: list[Zombie] = []
        self.projectiles: list[Projectile] = []
        self.lobby_player.update({"x": 180.0, "y": 220.0, "z": 0.0, "z_velocity": 0.0, "grounded": True})
        self.lobby_facing_heading = 0.0
        self.money = self.starting_cash
        self.lives = 10
        self.wave = 0
        self.wave_groups: dict[int, WaveSpawnGroup] = {}
        self.started_waves: set[int] = set()
        self.cleared_waves: set[int] = set()
        self.wave_start_timers: dict[int, float] = {}
        self.selected_defender: Defender | None = None
        self.selected_tower_type = min(self.available_towers)
        self.placement_mode = False
        self.unit_management_open = False
        self.unit_management_scroll = 0
        self.game_over = False
        self.challenge_won = False
        self.path_points = tuple(MAPS[self.selected_map]["path_points"])
        self.pending_credits = 0
        self.pending_crates = 0
        self.pending_battle_pass_xp = 0
        self.match_rewards_saved = False
        self.autoplay_timer = 0.0

    def update_lobby_player(self, delta_time: float) -> None:
        forward = (pygame.K_w in self.held_keys) - (pygame.K_s in self.held_keys)
        strafe = (pygame.K_d in self.held_keys) - (pygame.K_a in self.held_keys)
        if forward or strafe:
            heading = math.radians(self.lobby_facing_heading)
            move_x = strafe * math.cos(heading) - forward * math.sin(heading)
            move_y = -strafe * math.sin(heading) - forward * math.cos(heading)
            length = math.hypot(move_x, move_y)
            distance = LOBBY_MOVE_SPEED * delta_time
            steps = max(1, math.ceil(distance / 8))
            step_x = move_x / length * distance / steps
            step_y = move_y / length * distance / steps
            for _ in range(steps):
                previous_x = self.lobby_player["x"]
                previous_y = self.lobby_player["y"]
                self.lobby_player["x"] = max(35.0, min(965.0, previous_x + step_x))
                self.lobby_player["y"] = max(100.0, min(455.0, previous_y + step_y))
                for px, py, width, height in LOBBY_STATION_RECTS.values():
                    center_x = px + width / 2
                    center_y = py + height / 2
                    dx = self.lobby_player["x"] - center_x
                    dy = self.lobby_player["y"] - center_y
                    distance_to_station = math.hypot(dx, dy)
                    if 0 < distance_to_station < 24:
                        self.lobby_player["x"] = center_x + dx / distance_to_station * 24
                        self.lobby_player["y"] = center_y + dy / distance_to_station * 24
        player = self.lobby_player
        floor_height = self._lobby_platform_height(player["x"], player["y"])
        if pygame.K_SPACE in self.held_keys and player["grounded"]:
            player["z_velocity"] = LOBBY_JUMP_VELOCITY
            player["grounded"] = False
        if player["grounded"]:
            player["z"] = floor_height
        else:
            steps = max(1, math.ceil(delta_time * 240))
            step_time = delta_time / steps
            for _ in range(steps):
                player["z_velocity"] -= LOBBY_GRAVITY * step_time
                player["z"] += player["z_velocity"] * step_time
                if player["z"] <= floor_height:
                    player["z"] = floor_height
                    player["z_velocity"] = 0.0
                    player["grounded"] = True
                    break

    def face_lobby_player_toward(self, screen_x: float, screen_y: float) -> None:
        dx = screen_x - self.lobby_player["x"]
        dy = self.lobby_player["y"] - screen_y
        if dx or dy:
            self.lobby_facing_heading = math.degrees(math.atan2(-dx, dy))

    @staticmethod
    def _lobby_platform_height(x: float, y: float) -> float:
        for px, py, width, height in LOBBY_STATION_RECTS.values():
            if px <= x <= px + width and py <= y <= py + height:
                return 0.34
        return 0.0

    def _lobby_station_for_player(self) -> str | None:
        x = self.lobby_player["x"]
        y = self.lobby_player["y"]
        for name, rect in LOBBY_STATION_RECTS.items():
            px, py, pw, ph = rect
            dx = x - (px + pw / 2)
            dy = y - (py + ph / 2)
            if dx * dx + dy * dy <= 55**2:
                return name
        return None

    def run(self) -> None:
        from three_d import run_3d

        try:
            run_3d(self)
        finally:
            pygame.quit()

    def step_frame(self, delta_time: float) -> bool:
        """Advance game state and draw its 2D menus or the 3D-game HUD."""
        self.frame_surface = self.screen
        if self.screen_state == "setup":
            running = self.handle_setup_events()
            draw_setup(
                self.screen,
                self.fonts,
                self.available_towers,
                self.game_speed,
                self.speed_input,
                self.username_input,
                self.password_input,
                self.grant_username_input,
                self.focused_field,
                self.account_name,
                self.is_admin,
                self.has_custom_speed,
                self.status,
            )
        elif self.screen_state == "lobby":
            self.update_lobby_player(delta_time)
            running = self.handle_lobby_events()
        elif self.screen_state == "battle_pass":
            running = self.handle_battle_pass_events()
            draw_battle_pass(
                self.screen,
                self.fonts,
                self.battle_pass_xp,
                self.battle_pass_claimed,
                self.status,
            )
        elif self.screen_state in ("daily_challenge", "story_mode"):
            running = self.handle_challenge_events()
            draw_challenge_menu(
                self.screen,
                self.fonts,
                "daily" if self.screen_state == "daily_challenge" else "story",
                self.selected_mode,
                self.story_level,
                self.daily_challenge_claimed(),
                self.status,
            )
        elif self.screen_state == "crates":
            running = self.handle_crates_events()
            draw_crates(self.screen, self.fonts, self.credits, self.crates, self.status)
        elif self.screen_state == "traits":
            running = self.handle_trait_events()
            draw_trait_lobby(
                self.screen,
                self.fonts,
                self.credits,
                self.owned_units,
                self.selected_lobby_unit,
                self.unit_traits,
                self.trait_options,
                self.trait_luck,
                self.trait_batch_count,
                self.trait_unit_scroll,
                self.trait_option_scroll,
                self.status,
            )
        elif self.screen_state == "collection":
            running = self.handle_collection_events()
            draw_unit_collection(
                self.screen,
                self.fonts,
                self.owned_units,
                self.available_towers,
                self.unit_levels,
                self.unit_copies,
                self.selected_lobby_unit,
                self.collection_scroll,
                self.status,
                self.mouse_position,
                self.unit_traits,
            )
        elif self.screen_state == "admin":
            running = self.handle_admin_events()
            draw_admin_panel(
                self.screen,
                self.fonts,
                self.account_name,
                self.admin_accounts,
                self.admin_account_scroll,
                self.admin_username_input,
                self.admin_credits_input,
                self.starting_cash_input,
                self.starting_cash,
                self.selected_lobby_unit,
                self.status,
                self.focused_field,
                self.admin_crate_count_input,
                self.admin_story_level_input,
                self.admin_selected_crate,
                self.selected_mode,
                self.selected_map,
                self.game_speed,
            )
        elif self.screen_state in ("playing", "preparation"):
            running = self.handle_events()
            preparing = self.screen_state == "preparation"
            if not self.game_over:
                if preparing:
                    self.update_autoplay(delta_time)
                else:
                    game_delta = delta_time * self.game_speed
                    self.update(game_delta)
                    self.update_autoplay(game_delta)
            self.frame_surface = self.overlay_surface
            draw_game(
                self.overlay_surface,
                self.fonts,
                self.defenders,
                self.zombies,
                self.projectiles,
                self.selected_defender,
                self.money,
                self.lives,
                self.wave,
                self.status,
                self.game_over,
                self.selected_tower_type,
                self.mouse_position,
                self.can_place_defender(self.mouse_position),
                self.placement_mode,
                self.available_towers,
                self.game_speed,
                self.credits + self.pending_credits,
                self.selected_mode,
                self.unit_management_open,
                self.unit_management_scroll,
                preparing,
                self.path_points,
                str(MAPS[self.selected_map]["name"]),
                {
                    "infinite": "Infinite",
                    "daily": "Daily Challenge",
                    "story": f"Story {self.story_level_playing}",
                }.get(self.play_mode, self.play_mode),
                self.challenge_target_waves,
                self.challenge_won,
                self.autoplay_mode,
                self.player,
                world_3d=True,
            )
        else:
            running = True
        return running

    def handle_setup_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.screen_state = "lobby"
                    continue
                if event.key == pygame.K_TAB:
                    self.cycle_focused_field()
                elif event.key == pygame.K_RETURN:
                    if self.focused_field in ("username", "password"):
                        self.authenticate(register=False)
                    elif self.focused_field == "custom_speed":
                        self.commit_custom_speed()
                        self.focused_field = None
                    elif self.focused_field == "grant_username":
                        self.grant_speed_access()
                    else:
                        self.go_to_lobby()
                elif event.key == pygame.K_BACKSPACE and self.focused_field:
                    self.edit_focused_field(backspace=True)
                elif self.focused_field:
                    self.edit_focused_field(event.unicode)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_setup_click(event.pos)
        return True

    def handle_setup_click(self, position: tuple[int, int]) -> None:
        for index in range(len(TOWER_TYPES)):
            card = pygame.Rect(20 + (index % 5) * 192, 104 + (index // 5) * 98, 180, 90)
            if card.collidepoint(position):
                if index in self.available_towers and len(self.available_towers) == 1:
                    self.status = "Keep at least one tower in your loadout."
                    return
                if index not in self.available_towers and len(self.available_towers) >= MAX_EQUIPPED_TOWERS:
                    self.status = f"You can equip up to {MAX_EQUIPPED_TOWERS} towers."
                    return
                if index in self.available_towers:
                    self.available_towers.remove(index)
                else:
                    self.available_towers.add(index)
                if self.selected_tower_type not in self.available_towers:
                    self.selected_tower_type = min(self.available_towers)
                self.save_loadout()
                return

        for index, speed in enumerate(GAME_SPEED_PRESETS):
            button = pygame.Rect(40 + index * 112, 340, 100, 46)
            if button.collidepoint(position):
                self.game_speed = speed
                self.speed_input = f"{speed:g}"
                self.focused_field = None
                return

        if pygame.Rect(400, 340, 150, 46).collidepoint(position):
            if self.has_custom_speed:
                self.focused_field = "custom_speed"
                self.speed_input = ""
                self.status = "Enter a speed from 1 to 10, then press Enter."
            else:
                self.status = "Standard speeds are available to everyone; custom speeds require account access."
            return
        if pygame.Rect(565, 340, 120, 46).collidepoint(position):
            if self.has_custom_speed:
                self.focused_field = "custom_speed"
                self.speed_input = ""
                self.status = "Enter a speed from 1 to 10, then press Enter."
            else:
                self.status = "Standard speeds are available to everyone; custom speeds require account access."
            return

        field_rectangles = {
            "username": pygame.Rect(40, 456, 245, 42),
            "password": pygame.Rect(300, 456, 245, 42),
            "grant_username": pygame.Rect(40, 548, 245, 42),
        }
        for field_name, rectangle in field_rectangles.items():
            if rectangle.collidepoint(position):
                self.focused_field = field_name
                return

        if pygame.Rect(560, 456, 120, 42).collidepoint(position):
            self.authenticate(register=True)
            return
        if pygame.Rect(690, 456, 120, 42).collidepoint(position):
            self.authenticate(register=False)
            return
        if pygame.Rect(820, 456, 140, 42).collidepoint(position):
            self.logout()
            return
        if pygame.Rect(300, 548, 180, 42).collidepoint(position):
            self.grant_speed_access()
            return
        if pygame.Rect(800, 610, 160, 62).collidepoint(position):
            self.go_to_lobby()

    def cycle_focused_field(self) -> None:
        if self.screen_state == "admin":
            fields = [
                "admin_username",
                "admin_credits",
                "admin_crate_count",
                "starting_cash",
                "admin_story_level",
            ]
            if self.focused_field not in fields:
                self.focused_field = fields[0]
            else:
                next_index = (fields.index(self.focused_field) + 1) % len(fields)
                self.focused_field = fields[next_index]
            return
        fields = ["username", "password"]
        if self.has_custom_speed:
            fields.append("custom_speed")
        if self.is_admin:
            fields.append("grant_username")
        if self.focused_field not in fields:
            self.focused_field = fields[0]
        else:
            next_index = (fields.index(self.focused_field) + 1) % len(fields)
            self.focused_field = fields[next_index]

    def edit_focused_field(self, text: str = "", backspace: bool = False) -> None:
        field_name = self.focused_field
        if field_name is None:
            return
        current_value = {
            "username": self.username_input,
            "password": self.password_input,
            "custom_speed": self.speed_input,
            "grant_username": self.grant_username_input,
            "admin_username": self.admin_username_input,
            "admin_credits": self.admin_credits_input,
            "admin_crate_count": self.admin_crate_count_input,
            "admin_story_level": self.admin_story_level_input,
            "starting_cash": self.starting_cash_input,
        }[field_name]
        if backspace:
            updated_value = current_value[:-1]
        elif field_name == "custom_speed":
            if text not in "0123456789." or (text == "." and "." in current_value):
                return
            updated_value = current_value + text
            if len(updated_value) > 4:
                return
        elif field_name in (
            "admin_credits",
            "admin_crate_count",
            "admin_story_level",
            "starting_cash",
        ):
            if not text.isdigit() or len(current_value) >= 10:
                return
            updated_value = current_value + text
        else:
            if not text.isprintable() or len(current_value) >= (24 if field_name not in ("password", "admin_username") else 128):
                return
            updated_value = current_value + text

        if field_name == "username":
            self.username_input = updated_value
        elif field_name == "password":
            self.password_input = updated_value
        elif field_name == "custom_speed":
            self.speed_input = updated_value
        elif field_name == "grant_username":
            self.grant_username_input = updated_value
        elif field_name == "admin_username":
            self.admin_username_input = updated_value
        elif field_name == "admin_credits":
            self.admin_credits_input = updated_value
        elif field_name == "admin_crate_count":
            self.admin_crate_count_input = updated_value
        elif field_name == "admin_story_level":
            self.admin_story_level_input = updated_value
        elif field_name == "starting_cash":
            self.starting_cash_input = updated_value

    def commit_custom_speed(self) -> bool:
        try:
            speed = float(self.speed_input)
        except ValueError:
            self.status = "Enter a valid speed from 1 to 10."
            return False
        if not 1 <= speed <= 10:
            self.status = "Custom speed must be from 1x to 10x."
            return False
        if not self.has_custom_speed:
            if self.game_speed not in GAME_SPEED_PRESETS:
                self.game_speed = DEFAULT_GAME_SPEED
            self.speed_input = f"{self.game_speed:g}"
            return True
        self.game_speed = speed
        self.speed_input = f"{speed:g}"
        self.status = f"Game speed set to {speed:g}x."
        return True

    def authenticate(self, register: bool) -> None:
        try:
            account = (
                self.account_client.register(self.username_input, self.password_input)
                if register
                else self.account_client.login(self.username_input, self.password_input)
            )
        except AccountServiceError as error:
            self.status = str(error)
            return

        token = account.get("token")
        username = account.get("username")
        if not isinstance(token, str) or not isinstance(username, str):
            self.status = "The account server returned incomplete account information."
            return
        self.account_token = token
        self.account_name = username
        self.is_admin = account.get("is_admin") is True
        self.has_custom_speed = account.get("custom_speed_access") is True
        self.password_input = ""
        self.focused_field = None
        try:
            self.load_profile(self.account_client.get_profile(token))
        except AccountServiceError as error:
            self.status = f"Signed in as {username}, but profile loading failed: {error}"
            return
        if not self.has_custom_speed and self.game_speed not in GAME_SPEED_PRESETS:
            self.game_speed = DEFAULT_GAME_SPEED
            self.speed_input = f"{self.game_speed:g}"
        self.status = f"Signed in as {username}."

    def logout(self) -> None:
        if self.account_token is not None:
            try:
                self.account_client.logout(self.account_token)
            except AccountServiceError as error:
                self.status = str(error)
                return
        self.account_token = None
        self.account_name = None
        self.is_admin = False
        self.has_custom_speed = False
        self.credits = 0
        self.owned_units = set(range(len(TOWER_TYPES)))
        starter_index = unit_index_for_id(STARTER_UNIT_ID)
        if starter_index is not None:
            self.owned_units.add(starter_index)
        self.unit_levels = {}
        self.unit_copies = {}
        self.unit_traits = {}
        self.trait_options = {}
        self.crates = {crate_id: 0 for crate_id in CRATE_TYPES}
        self.battle_pass_xp = 0
        self.battle_pass_claimed = set()
        self.available_towers = set(range(MAX_EQUIPPED_TOWERS))
        if self.game_speed not in GAME_SPEED_PRESETS:
            self.game_speed = DEFAULT_GAME_SPEED
        self.speed_input = f"{self.game_speed:g}"
        self.status = "Signed out. Standard game speeds remain available."

    def grant_speed_access(self) -> None:
        if not self.is_admin or self.account_token is None:
            self.status = "Sign in as an admin to grant custom-speed access."
            return
        try:
            self.account_client.grant_speed_access(
                self.grant_username_input,
                True,
                self.account_token,
            )
        except AccountServiceError as error:
            self.status = str(error)
            return
        self.status = f"Granted custom-speed access to {self.grant_username_input}."
        self.grant_username_input = ""

    def start_game(self, play_mode: str = "infinite") -> None:
        if play_mode not in ("infinite", "daily", "story"):
            self.status = "Choose a valid game mode."
            return
        if play_mode == "daily" and self.daily_challenge_claimed():
            self.status = "Today's daily challenge reward was already claimed."
            return
        if not self.commit_match_credits():
            return
        if not 1 <= len(self.available_towers) <= MAX_EQUIPPED_TOWERS:
            self.status = f"Equip between 1 and {MAX_EQUIPPED_TOWERS} towers before starting."
            return
        if not self.save_loadout():
            return
        if self.has_custom_speed and not self.commit_custom_speed():
            return
        if not self.has_custom_speed:
            if self.game_speed not in GAME_SPEED_PRESETS:
                self.game_speed = DEFAULT_GAME_SPEED
        self.reset()
        self.play_mode = play_mode
        if play_mode == "daily":
            self.challenge_target_waves = int(DAILY_CHALLENGES[self.selected_mode]["waves"])
        elif play_mode == "story":
            self.story_level_playing = self.story_level
            self.challenge_target_waves = min(
                STORY_BASE_WAVES
                + (self.story_level_playing - 1) * STORY_WAVES_PER_LEVEL,
                STORY_MAX_WAVES,
            )
        else:
            self.challenge_target_waves = None
        self.placement_mode = True
        self.screen_state = "preparation"
        self.status = (
            f"Deploy for {play_mode} mode: clear {self.challenge_target_waves} waves."
            if self.challenge_target_waves is not None
            else "Deploy your units before starting the first wave."
        )

    def begin_wave(self) -> None:
        if self.screen_state != "preparation":
            return
        self.screen_state = "playing"
        self.placement_mode = False
        self.schedule_wave(1)
        self.status = "First wave incoming!"

    def cycle_autoplay_mode(self) -> None:
        modes = ("off", "waves", "full")
        self.autoplay_mode = modes[(modes.index(self.autoplay_mode) + 1) % len(modes)]
        self.autoplay_timer = 0.0
        if self.autoplay_mode == "off":
            self.status = "Autoplay disabled."
        elif self.autoplay_mode == "waves":
            self.status = "Wave autoplay enabled; tower placement remains manual."
        else:
            self.placement_mode = False
            self.status = "Full autoplay enabled; the AI will deploy and upgrade units."

    def update_autoplay(self, delta_time: float) -> None:
        if self.autoplay_mode == "off" or self.game_over:
            return
        self.autoplay_timer -= delta_time
        if self.autoplay_timer > 0:
            return
        self.autoplay_timer = 0.65
        if self.screen_state == "preparation":
            if self.autoplay_mode == "full" and self.autoplay_build_or_upgrade():
                return
            self.begin_wave()
        elif self.screen_state == "playing" and self.autoplay_mode == "full":
            self.autoplay_build_or_upgrade()

    def autoplay_build_or_upgrade(self) -> bool:
        path_samples: list[tuple[int, int]] = []
        for start, end in zip(self.path_points, self.path_points[1:]):
            steps = max(1, max(abs(end[0] - start[0]), abs(end[1] - start[1])) // 35)
            path_samples.extend(
                (
                    round(start[0] + (end[0] - start[0]) * step / steps),
                    round(start[1] + (end[1] - start[1]) * step / steps),
                )
                for step in range(steps + 1)
            )

        build_options: list[tuple[float, int, tuple[int, int]]] = []
        for tower_type in sorted(self.available_towers):
            stats = unit_stats(tower_type)
            cost = int(stats["cost"])
            fire_rate = float(stats["fire_rate"])
            damage = int(stats["damage"])
            income = int(stats.get("income", 0))
            if (
                cost > self.money
                or fire_rate <= 0
                or (damage <= 0 and income <= 0)
            ):
                continue

            best_position: tuple[int, int] | None = None
            best_coverage = 0
            attack_range = int(stats["range"])
            for x in range(42, SCREEN_WIDTH - 23, 36):
                for y in range(TOP_BAR_HEIGHT + 24, TOWER_BAR_TOP - 20, 36):
                    position = (x, y)
                    if not self.can_place_defender(position, tower_type):
                        continue
                    coverage = (
                        1
                        if damage <= 0
                        else sum(
                            (sample_x - x) ** 2 + (sample_y - y) ** 2 <= attack_range**2
                            for sample_x, sample_y in path_samples
                        )
                    )
                    if coverage > best_coverage:
                        best_position = position
                        best_coverage = coverage

            if best_position is None:
                continue
            placed_count = sum(
                defender.tower_type == tower_type for defender in self.defenders
            )
            output_per_cost = (
                damage / fire_rate
                if damage > 0
                else income / float(stats["income_interval"])
            ) / cost
            build_options.append(
                (
                    output_per_cost / (1 + placed_count * 0.35) * best_coverage,
                    tower_type,
                    best_position,
                )
            )

        if build_options:
            _, tower_type, position = max(build_options)
            self.selected_tower_type = tower_type
            self.place_defender(position)
            return True

        upgrade_options: list[tuple[float, Defender]] = []
        for defender in self.defenders:
            if defender.level >= combat_upgrade_cap(defender.tower_type):
                continue
            cost = (
                UPGRADE_COSTS[defender.level - 1]
                if defender.level <= len(UPGRADE_COSTS)
                else round(UPGRADE_COSTS[-1] * 1.5 ** (defender.level - len(UPGRADE_COSTS)))
            )
            if cost <= self.money:
                stats = unit_stats(defender.tower_type)
                damage = int(stats["damage"])
                value = (
                    damage / max(0.01, float(stats["fire_rate"]))
                    if damage > 0
                    else int(stats.get("income", 0))
                    / max(0.01, float(stats.get("income_interval", 1)))
                )
                upgrade_options.append((value / cost, defender))
        if not upgrade_options:
            return False
        _, self.selected_defender = max(upgrade_options, key=lambda option: option[0])
        self.upgrade_selected_defender()
        return True

    def skip_wave(self) -> None:
        if self.screen_state != "playing" or self.game_over or self.wave < 1:
            return
        next_wave = self.wave + 1
        if self.play_mode == "story" and next_wave > STORY_MAX_WAVES:
            self.status = f"Story chapters are limited to {STORY_MAX_WAVES} waves."
            return
        self.wave_start_timers.pop(next_wave, None)
        self.schedule_wave(next_wave)
        group = self.wave_groups[next_wave]
        group.skipped = True
        if self.play_mode in ("daily", "story") and self.challenge_target_waves is not None:
            self.challenge_target_waves = max(self.challenge_target_waves, next_wave)
        self.status = (
            f"Wave {next_wave} added. Clear every enemy in the skipped waves to complete "
            f"the challenge ({len(self.cleared_waves)}/{self.challenge_target_waves} waves cleared)."
            if self.play_mode in ("daily", "story")
            else f"Wave {next_wave} started; earlier waves keep their own spawn pace."
        )

    @staticmethod
    def enemy_types_for_wave(wave: int) -> list[str]:
        enemy_count = 4 + wave * 2
        enemies: list[str] = []
        for index in range(enemy_count):
            if wave >= 4 and index % 5 == 4:
                enemies.append("tank")
            elif wave >= 2 and index % 3 == 2:
                enemies.append("runner")
            else:
                enemies.append("normal")
        if wave % 10 == 0:
            enemies.append("mini_boss")
        if wave % 50 == 0:
            enemies.append("boss")
        return enemies

    def schedule_wave(self, wave: int) -> None:
        if wave in self.started_waves:
            return
        self.wave = max(self.wave, wave)
        self.started_waves.add(wave)
        self.wave_groups[wave] = WaveSpawnGroup(
            wave=wave,
            enemies=self.enemy_types_for_wave(wave),
        )

    def complete_wave(self, group: WaveSpawnGroup) -> None:
        wave_cleared = (
            group.spawned > 0
            and group.escaped == 0
            and group.defeated == group.spawned
        )
        if wave_cleared:
            self.cleared_waves.add(group.wave)
            self.battle_pass_xp += BATTLE_PASS_XP_PER_WAVE
            self.pending_battle_pass_xp += BATTLE_PASS_XP_PER_WAVE
            self.match_rewards_saved = False
        mode = GAME_MODES_BY_KEY[self.selected_mode]
        crate_interval = int(mode["crate_interval"])
        if self.play_mode == "infinite" and (
            group.wave % crate_interval == 0
            and random.random() < float(mode["crate_chance"])
        ):
            crate_id = "standard"
            self.crates[crate_id] = self.crates.get(crate_id, 0) + 1
            self.pending_crates += 1
            self.match_rewards_saved = False
            self.status = f"Wave {group.wave} cleared! A Supply Crate dropped."
        elif self.play_mode == "infinite" and self.selected_mode == "forbidden":
            self.status = f"Wave {group.wave} cleared."
        if (
            self.play_mode == "infinite"
            and self.selected_mode == "forbidden"
            and group.escaped == 0
            and group.defeated == group.spawned
            and group.spawned > 0
        ):
            self.pending_credits += 100
            self.match_rewards_saved = False
            self.status = f"Wave {group.wave} cleared! +100 credits."
        self.wave_groups.pop(group.wave, None)
        if self.play_mode in ("daily", "story") and not wave_cleared:
            self.game_over = True
            self.wave_start_timers.clear()
            wave_label = "Skipped wave" if group.skipped else "Wave"
            self.status = (
                f"{wave_label} {group.wave} was not cleared: every enemy must be defeated. "
                "Retry the challenge to earn its reward."
            )
            return
        if (
            self.play_mode in ("daily", "story")
            and self.challenge_target_waves is not None
            and all(
                wave in self.cleared_waves
                for wave in range(1, self.challenge_target_waves + 1)
            )
        ):
            self.game_over = True
            self.challenge_won = True
            self.wave_start_timers.clear()
            self.claim_challenge_reward()
            return
        next_wave = group.wave + 1
        if (
            next_wave not in self.started_waves
            and (
                self.play_mode == "infinite"
                or self.challenge_target_waves is None
                or next_wave <= self.challenge_target_waves
            )
        ):
            self.wave_start_timers.setdefault(next_wave, 2.0)

    def go_to_lobby(self) -> None:
        if not self.commit_match_credits():
            return
        self.screen_state = "lobby"
        self.status = "Choose units, upgrade your roster, and select a mode."

    def daily_challenge_claimed(self) -> bool:
        return self.daily_challenge_date == date.today().isoformat()

    def claim_challenge_reward(self) -> None:
        if not self.commit_match_credits():
            return
        if self.play_mode == "daily":
            if self.daily_challenge_claimed():
                self.status = "Today's daily challenge reward was already claimed."
                return
            reward = DAILY_CHALLENGES[self.selected_mode]
        elif self.play_mode == "story":
            if self.story_level_playing != self.story_level:
                self.status = "That story level has already been completed."
                return
            reward = {
                "credits": STORY_BASE_CREDITS
                + (self.story_level_playing - 1) * STORY_LEVEL_CREDIT_INCREMENT,
                "crates": 1,
            }
        else:
            return

        if self.account_token is not None:
            try:
                profile = self.account_client.claim_challenge_reward(
                    self.play_mode,
                    self.account_token,
                    difficulty=self.selected_mode if self.play_mode == "daily" else None,
                    story_level=(
                        self.story_level_playing if self.play_mode == "story" else None
                    ),
                )
                self.load_profile(profile)
            except AccountServiceError as error:
                self.challenge_won = False
                self.status = f"Challenge cleared, but its reward could not be saved: {error}"
                return
        else:
            self.credits += int(reward["credits"])
            crate_id = "standard" if self.play_mode == "daily" else "story"
            self.crates[crate_id] = self.crates.get(crate_id, 0) + int(reward["crates"])
            if self.play_mode == "daily":
                self.daily_challenge_date = date.today().isoformat()
            else:
                self.story_level += 1

        if self.play_mode == "daily":
            self.status = (
                f"Daily challenge complete! +{reward['credits']:,} credits, "
                f"+{reward['crates']} Supply Crate(s)."
            )
        else:
            self.status = (
                f"Story level {self.story_level_playing} complete! "
                f"+{reward['credits']:,} credits, +1 Story Crate."
            )

    def handle_challenge_events(self) -> bool:
        challenge_mode = "daily" if self.screen_state == "daily_challenge" else "story"
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_b):
                self.screen_state = "lobby"
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if pygame.Rect(20, 600, 170, 60).collidepoint(event.pos):
                    self.screen_state = "lobby"
                elif challenge_mode == "daily" and not self.daily_challenge_claimed():
                    selected = next(
                        (
                            str(mode["key"])
                            for index, mode in enumerate(GAME_MODES)
                            if pygame.Rect(20 + index * 192, 230, 180, 150).collidepoint(event.pos)
                        ),
                        None,
                    )
                    if selected is not None:
                        self.selected_mode = selected
                    elif pygame.Rect(760, 590, 220, 76).collidepoint(event.pos):
                        self.start_game("daily")
                elif challenge_mode == "story" and pygame.Rect(760, 590, 220, 76).collidepoint(event.pos):
                    self.start_game("story")
        return True

    def load_profile(self, profile: dict[str, object]) -> None:
        credits = profile.get("credits")
        unlocked = profile.get("unlocked_units")
        levels = profile.get("unit_levels")
        copies = profile.get("unit_copies", {})
        traits = profile.get("unit_traits", {})
        trait_options = profile.get("trait_options", {})
        crates = profile.get("crates", {})
        battle_pass_xp = profile.get("battle_pass_xp", 0)
        battle_pass_claimed = profile.get("battle_pass_claimed", [])
        daily_challenge_date = profile.get("daily_challenge_date", "")
        story_level = profile.get("story_level", 1)
        equipped_units = profile.get("equipped_units", [])
        if (
            not isinstance(credits, int)
            or isinstance(credits, bool)
            or credits < 0
            or not isinstance(unlocked, list)
            or not isinstance(levels, dict)
            or not isinstance(copies, dict)
            or not isinstance(traits, dict)
            or not isinstance(trait_options, dict)
            or not isinstance(crates, dict)
            or not isinstance(battle_pass_xp, int)
            or isinstance(battle_pass_xp, bool)
            or battle_pass_xp < 0
            or not isinstance(battle_pass_claimed, list)
            or not all(
                isinstance(level, int) and not isinstance(level, bool) and level >= 1
                for level in battle_pass_claimed
            )
            or not isinstance(daily_challenge_date, str)
            or not isinstance(story_level, int)
            or isinstance(story_level, bool)
            or story_level < 1
            or not isinstance(equipped_units, list)
            or not all(isinstance(unit_id, str) for unit_id in equipped_units)
            or len(equipped_units) > MAX_EQUIPPED_TOWERS
        ):
            raise AccountServiceError("The account server returned an invalid player profile.")
        owned_units = set(range(len(TOWER_TYPES)))
        for unit_id in unlocked:
            if isinstance(unit_id, str):
                unit_index = unit_index_for_id(unit_id)
                if unit_index is not None:
                    owned_units.add(unit_index)
        unit_levels: dict[str, int] = {}
        for unit_id, level in levels.items():
            if (
                isinstance(unit_id, str)
                and isinstance(level, int)
                and not isinstance(level, bool)
                and level >= 1
                and unit_index_for_id(unit_id) is not None
            ):
                unit_levels[unit_id] = level
        unit_copies: dict[str, int] = {}
        for unit_id, count in copies.items():
            if (
                isinstance(unit_id, str)
                and isinstance(count, int)
                and not isinstance(count, bool)
                and count >= 0
                and unit_index_for_id(unit_id) is not None
            ):
                unit_copies[unit_id] = count
        trait_catalog = {str(trait["id"]): trait for trait in TRAITS}
        unit_traits: dict[str, dict[str, object]] = {}
        for unit_id, trait in traits.items():
            unit_index = unit_index_for_id(unit_id) if isinstance(unit_id, str) else None
            if (
                unit_index in owned_units
                and isinstance(trait, dict)
                and isinstance(trait.get("id"), str)
                and trait["id"] in trait_catalog
            ):
                unit_traits[unit_id] = dict(trait_catalog[str(trait["id"])])
        pending_options: dict[str, list[dict[str, object]]] = {}
        for unit_id, options in trait_options.items():
            unit_index = unit_index_for_id(unit_id) if isinstance(unit_id, str) else None
            if unit_index not in owned_units or not isinstance(options, list):
                continue
            validated = [
                dict(trait_catalog[str(option["id"])])
                for option in options
                if isinstance(option, dict)
                and isinstance(option.get("id"), str)
                and option["id"] in trait_catalog
            ]
            if validated:
                pending_options[unit_id] = validated
        crate_counts = {crate_id: 0 for crate_id in CRATE_TYPES}
        for crate_id, count in crates.items():
            if (
                crate_id in CRATE_TYPES
                and isinstance(count, int)
                and not isinstance(count, bool)
                and count >= 0
            ):
                crate_counts[crate_id] = count
        self.credits = credits
        self.owned_units = owned_units
        self.unit_levels = unit_levels
        self.unit_copies = unit_copies
        self.unit_traits = unit_traits
        self.trait_options = pending_options
        self.crates = crate_counts
        self.battle_pass_xp = battle_pass_xp
        self.battle_pass_claimed = set(battle_pass_claimed)
        self.daily_challenge_date = daily_challenge_date
        self.story_level = story_level
        if equipped_units:
            restored_loadout: set[int] = set()
            for unit_id in equipped_units:
                unit_index = unit_index_for_id(unit_id)
                if unit_index is not None and unit_index in owned_units:
                    restored_loadout.add(unit_index)
            if restored_loadout:
                self.available_towers = restored_loadout
        starting_cash = profile.get("starting_cash", 250)
        if (
            not isinstance(starting_cash, int)
            or isinstance(starting_cash, bool)
            or starting_cash < 0
        ):
            raise AccountServiceError("The account server returned an invalid starting-cash setting.")
        self.starting_cash = starting_cash
        self.starting_cash_input = str(starting_cash)
        self.available_towers.intersection_update(owned_units)
        if not self.available_towers:
            self.available_towers = set(range(MAX_EQUIPPED_TOWERS))

    def save_loadout(self) -> bool:
        if self.account_token is None:
            return True
        unit_ids = [
            str(unit_stats(unit_index)["id"])
            for unit_index in sorted(self.available_towers)
        ]
        try:
            profile = self.account_client.save_loadout(unit_ids, self.account_token)
            self.load_profile(profile)
        except AccountServiceError as error:
            self.status = f"Could not save your loadout: {error}"
            return False
        return True

    def commit_match_credits(self) -> bool:
        if (
            (
                self.pending_credits <= 0
                and self.pending_crates <= 0
                and self.pending_battle_pass_xp <= 0
            )
            or self.match_rewards_saved
        ):
            return True
        target_credits = self.credits + self.pending_credits
        target_crates = self.crates.copy()
        if self.account_token is not None:
            try:
                profile: dict[str, object] | None = None
                if self.pending_credits > 0:
                    profile = self.account_client.set_profile_credits(
                        target_credits,
                        self.account_token,
                    )
                if self.pending_crates > 0:
                    profile = self.account_client.set_crates(
                        target_crates,
                        self.account_token,
                    )
                if self.pending_battle_pass_xp > 0:
                    profile = self.account_client.set_battle_pass_xp(
                        self.battle_pass_xp,
                        self.account_token,
                    )
                if profile is not None:
                    self.load_profile(profile)
            except AccountServiceError as error:
                self.status = f"Could not save match rewards: {error}"
                return False
        else:
            self.credits = target_credits
        self.pending_credits = 0
        self.pending_crates = 0
        self.pending_battle_pass_xp = 0
        self.match_rewards_saved = True
        return True

    def handle_lobby_events(self) -> bool:
        station = self._lobby_station_for_player()
        station_changed = station != self.last_lobby_station
        self.last_lobby_station = station
        activated = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.screen_state = "setup"
                elif event.key in (pygame.K_RETURN, pygame.K_e):
                    activated = True
                    if station is None:
                        self.status = "Explore with WASD, right-click to face a direction, jump with Space, and use E at a station."
                    elif station == "summon":
                        self.roll_for_unit()
                    elif station == "traits":
                        self.screen_state = "traits"
                    elif station == "battle_pass":
                        self.screen_state = "battle_pass"
                    elif station == "crates":
                        self.screen_state = "crates"
                    elif station == "collection":
                        self.screen_state = "collection"
                    elif station == "start":
                        self.start_game()
                    elif station == "daily":
                        self.screen_state = "daily_challenge"
                    elif station == "story":
                        self.screen_state = "story_mode"
                    elif station == "admin" and self.is_admin:
                        self.open_admin_panel()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_lobby_click(event.pos)
        if station_changed and not activated:
            prompts = {
                "summon": "Walk to the summon podium to roll units.",
                "traits": "Walk to the trait altar to improve your roster.",
                "battle_pass": "Walk to the battle pass board to claim rewards.",
                "crates": "Walk to the crate rack to open rewards.",
                "collection": "Walk to the collection archive to manage units.",
                "start": "Stand on the start platform to launch a run.",
                "daily": "Daily challenge portal ready.",
                "story": "Story campaign portal ready.",
                "admin": "Admin terminal ready.",
            }
            self.status = prompts.get(
                station,
                "Explore with WASD, right-click to face a direction, jump with Space, and use E at a station.",
            )
        return True

    def handle_battle_pass_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_b):
                self.screen_state = "lobby"
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if pygame.Rect(20, 620, 170, 55).collidepoint(event.pos):
                    self.screen_state = "lobby"
                elif pygame.Rect(390, 545, 220, 60).collidepoint(event.pos):
                    self.claim_battle_pass_reward()
        return True

    def claim_battle_pass_reward(self) -> None:
        earned_level = battle_pass_level(self.battle_pass_xp)[0] - 1
        level = 1
        while level in self.battle_pass_claimed and level <= earned_level:
            level += 1
        if level > earned_level:
            self.status = "Earn more battle pass XP to unlock the next reward."
            return
        reward = battle_pass_reward(level)
        if self.account_token is not None:
            try:
                profile = self.account_client.claim_battle_pass_reward(
                    level,
                    self.account_token,
                )
                self.load_profile(profile)
            except AccountServiceError as error:
                self.status = f"Could not claim the battle pass reward: {error}"
                return
        else:
            self.credits += int(reward["credits"])
            crate_id = reward["crate_id"]
            if isinstance(crate_id, str):
                self.crates[crate_id] = self.crates.get(crate_id, 0) + 1
            unit_id = reward["unit_id"]
            if isinstance(unit_id, str):
                unit_index = unit_index_for_id(unit_id)
                if unit_index is None:
                    self.status = "The battle pass reward unit is unavailable."
                    return
                if unit_index in self.owned_units:
                    self.unit_copies[unit_id] = self.unit_copies.get(unit_id, 0) + 1
                else:
                    self.owned_units.add(unit_index)
            self.battle_pass_claimed.add(level)
        reward_details = [f"+{int(reward['credits']):,} credits"]
        if isinstance(reward["crate_id"], str):
            reward_details.append(f"+1 {CRATE_TYPES[str(reward['crate_id'])]['name']}")
        reward_unit_id = reward["unit_id"]
        if isinstance(reward_unit_id, str):
            reward_unit_index = unit_index_for_id(reward_unit_id)
            unit_name = (
                str(unit_stats(reward_unit_index)["name"])
                if reward_unit_index is not None
                else reward_unit_id
            )
            reward_details.append(f"unit {unit_name}")
        self.status = f"Battle pass level {level} claimed: {', '.join(reward_details)}."

    def handle_crates_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_b):
                self.screen_state = "lobby"
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if pygame.Rect(20, 620, 170, 55).collidepoint(event.pos):
                    self.screen_state = "lobby"
                elif any(
                    pygame.Rect(40, 174 + index * 100, 390, 48).collidepoint(event.pos)
                    for index, _ in enumerate(CRATE_TYPES)
                ):
                    crate_index = next(
                        index
                        for index in range(len(CRATE_TYPES))
                        if pygame.Rect(40, 174 + index * 100, 390, 48).collidepoint(event.pos)
                    )
                    self.open_crate(tuple(CRATE_TYPES)[crate_index])
        return True

    def handle_trait_events(self) -> bool:
        owned_units = sorted(self.owned_units)
        pending = self.trait_options.get(
            str(unit_stats(self.selected_lobby_unit)["id"]),
            [],
        )
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_b):
                self.screen_state = "lobby"
            elif event.type == pygame.MOUSEWHEEL:
                mouse_x, mouse_y = self.ui_mouse_position
                if 20 <= mouse_x < 475 and 105 <= mouse_y < 585:
                    self.trait_unit_scroll = max(
                        0,
                        min(max(0, len(owned_units) - 8), self.trait_unit_scroll - event.y),
                    )
                elif 500 <= mouse_x < 980 and 405 <= mouse_y < 600:
                    self.trait_option_scroll = max(
                        0,
                        min(max(0, len(pending) - 5), self.trait_option_scroll - event.y),
                    )
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if pygame.Rect(20, 620, 170, 55).collidepoint(event.pos):
                    self.screen_state = "lobby"
                    continue
                if pygame.Rect(500, 145, 145, 48).collidepoint(event.pos):
                    self.trait_luck = 1
                elif pygame.Rect(660, 145, 145, 48).collidepoint(event.pos):
                    self.trait_luck = 10
                elif pygame.Rect(820, 145, 145, 48).collidepoint(event.pos):
                    self.trait_luck = 100
                elif any(
                    pygame.Rect(500 + index * 115, 205, 105, 50).collidepoint(event.pos)
                    for index, _ in enumerate(TRAIT_BATCH_COUNTS)
                ):
                    batch_index = next(
                        index
                        for index in range(len(TRAIT_BATCH_COUNTS))
                        if pygame.Rect(500 + index * 115, 205, 105, 50).collidepoint(event.pos)
                    )
                    self.trait_batch_count = TRAIT_BATCH_COUNTS[batch_index]
                    self.roll_selected_trait(self.trait_luck, self.trait_batch_count)
                elif pygame.Rect(500, 355, 470, 40).collidepoint(event.pos):
                    unit = unit_stats(self.selected_lobby_unit)
                    current = self.unit_traits.get(str(unit["id"]))
                    self.choose_trait(
                        str(unit["id"]),
                        str(current["id"]) if current is not None else None,
                    )
                else:
                    selected_row = next(
                        (
                            unit_index
                            for row_index, unit_index in enumerate(
                                owned_units[self.trait_unit_scroll:self.trait_unit_scroll + 8]
                            )
                            if pygame.Rect(20, 105 + row_index * 56, 455, 49).collidepoint(event.pos)
                        ),
                        None,
                    )
                    if selected_row is not None:
                        self.selected_lobby_unit = selected_row
                        self.trait_option_scroll = 0
                        continue
                    visible_options = pending[self.trait_option_scroll:self.trait_option_scroll + 5]
                    choice_index = next(
                        (
                            index
                            for index, _ in enumerate(visible_options)
                            if pygame.Rect(500, 420 + index * 36, 470, 32).collidepoint(event.pos)
                        ),
                        None,
                    )
                    if choice_index is not None:
                        unit = unit_stats(self.selected_lobby_unit)
                        self.choose_trait(
                            str(unit["id"]),
                            str(visible_options[choice_index]["id"]),
                        )
        return True

    def open_crate(self, crate_id: str) -> None:
        if crate_id not in CRATE_TYPES:
            self.status = "Unknown crate type."
            return
        if self.account_token is not None:
            try:
                result = self.account_client.open_crate(crate_id, self.account_token)
                self.load_profile(result)
            except AccountServiceError as error:
                self.status = str(error)
                return
            reward = result.get("crate_reward")
            if isinstance(reward, dict) and isinstance(reward.get("unit_id"), str):
                unit_index = unit_index_for_id(str(reward["unit_id"]))
                unit_name = str(unit_stats(unit_index)["name"]) if unit_index is not None else "unit"
                if unit_index is not None:
                    self.selected_lobby_unit = unit_index
                self.status = f"Crate reward: {unit_name}!"
            elif isinstance(reward, dict) and isinstance(reward.get("credits"), int):
                self.status = f"Crate reward: {reward['credits']} credits!"
            return
        if self.crates.get(crate_id, 0) <= 0:
            self.status = "You do not have a crate to open."
            return
        self.crates[crate_id] -= 1
        crate = CRATE_TYPES[crate_id]
        if random.random() < float(crate["unit_chance"]) / 100:
            unit = (
                roll_story_crate_unit()
                if crate_id == "story"
                else {"id": crate["unit_id"]}
            )
            unit_index = unit_index_for_id(str(unit["id"]))
            if unit_index is None:
                raise RuntimeError("A crate reward unit is missing from the unit catalog.")
            if unit_index not in self.owned_units:
                self.owned_units.add(unit_index)
                self.status = f"Crate reward: {unit_stats(unit_index)['name']} unlocked!"
            else:
                unit_id = str(unit_stats(unit_index)["id"])
                self.unit_copies[unit_id] = self.unit_copies.get(unit_id, 0) + 1
                self.status = f"Crate reward: duplicate {unit_stats(unit_index)['name']} copy!"
            self.selected_lobby_unit = unit_index
        else:
            reward = random.randint(
                int(crate["credit_min"]),
                int(crate["credit_max"]),
            )
            self.credits += reward
            self.status = f"Crate reward: {reward} credits!"

    def roll_selected_trait(self, luck: int, count: int) -> None:
        if luck not in TRAIT_ROLL_COSTS:
            self.status = "Choose 1x, 10x, or 100x trait-roll luck."
            return
        if count not in TRAIT_BATCH_COUNTS:
            self.status = "Choose a 5x, 10x, 25x, or 100x trait batch."
            return
        if self.selected_lobby_unit not in self.owned_units:
            self.status = "Select an owned unit before rolling a trait."
            return
        unit = unit_stats(self.selected_lobby_unit)
        unit_id = str(unit["id"])
        cost = TRAIT_ROLL_COSTS[luck] * count
        if self.account_token is not None:
            try:
                result = self.account_client.roll_trait(
                    unit_id,
                    luck,
                    count,
                    self.account_token,
                )
                self.load_profile(result)
                rolled = result.get("trait_results")
            except AccountServiceError as error:
                self.status = str(error)
                return
        else:
            if self.credits < cost:
                self.status = f"Need {cost} credits for this trait roll."
                return
            self.credits -= cost
            rolled = roll_traits(count, luck)
            existing = self.trait_options.setdefault(unit_id, [])
            known_ids = {str(trait["id"]) for trait in existing}
            for trait in rolled:
                trait_id = str(trait["id"])
                if trait_id not in known_ids:
                    existing.append(trait)
                    known_ids.add(trait_id)
        new_options = self.trait_options.get(unit_id, [])
        self.trait_option_scroll = max(0, len(new_options) - 5)
        if new_options:
            self.status = (
                f"{count} rolls completed for {unit['name']}. Choose a trait or keep the current one."
            )
        else:
            self.status = (
                f"No new traits from {count} rolls for {unit['name']}; "
                "your current trait is unchanged."
            )

    def choose_trait(self, unit_id: str, trait_id: str | None) -> None:
        current = self.unit_traits.get(unit_id)
        options = self.trait_options.get(unit_id, [])
        current_id = str(current["id"]) if current is not None else None
        if trait_id is not None and trait_id != current_id and trait_id not in {
            str(option["id"]) for option in options
        }:
            self.status = "Choose the current trait or one of the successful roll results."
            return
        if self.account_token is not None:
            try:
                profile = self.account_client.apply_trait(
                    unit_id,
                    trait_id,
                    self.account_token,
                )
                self.load_profile(profile)
            except AccountServiceError as error:
                self.status = str(error)
                return
        else:
            selected = next(
                (trait for trait in options if trait["id"] == trait_id),
                current if current_id == trait_id else None,
            )
            if selected is None:
                self.unit_traits.pop(unit_id, None)
            else:
                self.unit_traits[unit_id] = dict(selected)
            self.trait_options.pop(unit_id, None)
        if trait_id is None:
            self.status = "Kept no trait for this unit; rolled options cleared."
        elif current_id == trait_id:
            self.status = f"Kept the current {current['name']} trait; rolled options cleared."
        else:
            trait = next(trait for trait in TRAITS if trait["id"] == trait_id)
            self.status = f"Applied the {trait['name']} trait; rolled options cleared."

    def open_admin_panel(self) -> None:
        if not self.is_admin or self.account_token is None:
            self.status = "Sign in as an admin to open the admin panel."
            return
        if self.selected_lobby_unit < len(TOWER_TYPES):
            self.select_admin_unit(1)
        self.refresh_admin_accounts()
        if self.status.startswith("Admin account list failed:"):
            return
        self.screen_state = "admin"
        self.focused_field = None

    def handle_admin_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.screen_state = "lobby"
                    self.focused_field = None
                elif event.key == pygame.K_TAB:
                    self.cycle_focused_field()
                elif event.key == pygame.K_BACKSPACE and self.focused_field:
                    self.edit_focused_field(backspace=True)
                elif self.focused_field:
                    self.edit_focused_field(event.unicode)
            elif event.type == pygame.MOUSEWHEEL:
                self.admin_account_scroll = max(
                    0,
                    min(
                        max(0, len(self.admin_accounts) - 7),
                        self.admin_account_scroll - event.y,
                    ),
                )
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_admin_click(event.pos)
        return True

    def handle_admin_click(self, position: tuple[int, int]) -> None:
        if pygame.Rect(20, 78, 170, 38).collidepoint(position):
            self.screen_state = "lobby"
            self.focused_field = None
            return
        if pygame.Rect(20, 128, 230, 38).collidepoint(position):
            self.focused_field = "admin_username"
            return
        if pygame.Rect(265, 128, 150, 38).collidepoint(position):
            self.focused_field = "admin_credits"
            return
        if pygame.Rect(425, 128, 155, 38).collidepoint(position):
            self.grant_admin_credits()
            return
        if pygame.Rect(760, 128, 220, 38).collidepoint(position):
            self.toggle_admin_speed_access()
            return
        if pygame.Rect(150, 178, 42, 36).collidepoint(position):
            self.select_admin_unit(-1)
            return
        if pygame.Rect(480, 178, 42, 36).collidepoint(position):
            self.select_admin_unit(1)
            return
        if pygame.Rect(550, 178, 220, 36).collidepoint(position):
            self.admin_unlock_unit()
            return
        if pygame.Rect(790, 178, 190, 36).collidepoint(position):
            self.admin_unlock_all_units()
            return
        if pygame.Rect(20, 228, 200, 36).collidepoint(position):
            crate_ids = tuple(CRATE_TYPES)
            crate_index = crate_ids.index(self.admin_selected_crate)
            self.admin_selected_crate = crate_ids[(crate_index + 1) % len(crate_ids)]
            self.status = f"Selected {CRATE_TYPES[self.admin_selected_crate]['name']}."
            return
        if pygame.Rect(230, 228, 150, 36).collidepoint(position):
            self.focused_field = "admin_crate_count"
            return
        if pygame.Rect(395, 228, 175, 36).collidepoint(position):
            self.grant_admin_crates()
            return
        if pygame.Rect(20, 278, 200, 36).collidepoint(position):
            self.focused_field = "starting_cash"
            return
        if pygame.Rect(230, 278, 190, 36).collidepoint(position):
            self.save_starting_cash()
            return
        if pygame.Rect(440, 278, 180, 36).collidepoint(position):
            self.save_admin_story_level()
            return
        if pygame.Rect(630, 278, 150, 36).collidepoint(position):
            self.focused_field = "admin_story_level"
            return
        if pygame.Rect(790, 278, 190, 36).collidepoint(position):
            self.reset_admin_daily_challenge()
            return
        if pygame.Rect(20, 328, 300, 36).collidepoint(position):
            mode_keys = [str(mode["key"]) for mode in GAME_MODES]
            self.selected_mode = mode_keys[(mode_keys.index(self.selected_mode) + 1) % len(mode_keys)]
            self.status = f"Game mode set to {self.selected_mode}."
            return
        if pygame.Rect(330, 328, 300, 36).collidepoint(position):
            map_keys = tuple(MAPS)
            self.selected_map = map_keys[(map_keys.index(self.selected_map) + 1) % len(map_keys)]
            self.path_points = tuple(MAPS[self.selected_map]["path_points"])
            self.status = f"Game map set to {MAPS[self.selected_map]['name']}."
            return
        if pygame.Rect(640, 328, 340, 36).collidepoint(position):
            speeds = (1.0, 2.0, 3.0, 5.0, 10.0)
            current_index = speeds.index(self.game_speed) if self.game_speed in speeds else 0
            self.game_speed = speeds[(current_index + 1) % len(speeds)]
            self.speed_input = f"{self.game_speed:g}"
            self.status = f"Game speed set to {self.game_speed:g}x."
            return
        if pygame.Rect(820, 78, 160, 38).collidepoint(position):
            self.refresh_admin_accounts()
            return
        for row_index, account in enumerate(
            self.admin_accounts[self.admin_account_scroll:self.admin_account_scroll + 7]
        ):
            row = pygame.Rect(20, 423 + row_index * 29, 960, 27)
            if row.collidepoint(position):
                self.admin_username_input = str(account["username"])
                self.starting_cash_input = str(account.get("starting_cash", 250))
                self.admin_story_level_input = str(account.get("story_level", 1))
                self.focused_field = "admin_username"
                self.status = f"Selected account {self.admin_username_input}."
                return

    def refresh_admin_accounts(self, show_status: bool = True) -> None:
        if not self.is_admin or self.account_token is None:
            self.status = "Administrator access is required."
            return
        try:
            response = self.account_client.list_admin_accounts(self.account_token)
        except AccountServiceError as error:
            self.status = f"Admin account list failed: {error}"
            return
        accounts = response.get("accounts")
        if not isinstance(accounts, list) or not all(isinstance(account, dict) for account in accounts):
            self.status = "The account server returned an invalid account list."
            return
        self.admin_accounts = accounts
        self.admin_account_scroll = min(
            self.admin_account_scroll,
            max(0, len(self.admin_accounts) - 7),
        )
        if show_status:
            self.status = f"Loaded {len(accounts)} registered accounts."

    def grant_admin_credits(self) -> None:
        amount = self.parse_admin_integer(self.admin_credits_input, "Credit amount", minimum=1)
        if amount is None:
            return
        if not self.admin_username_input.strip():
            self.status = "Enter or select an account username."
            return
        if self.account_token is None or not self.is_admin:
            self.status = "Administrator access is required."
            return
        try:
            self.account_client.add_account_credits(
                self.admin_username_input.strip(),
                amount,
                self.account_token,
            )
        except AccountServiceError as error:
            self.status = str(error)
            return
        self.status = f"Added {amount} credits to {self.admin_username_input.strip()}."
        self.refresh_admin_accounts(show_status=False)
        if self.admin_username_input.casefold() == (self.account_name or "").casefold():
            self.reload_own_profile()

    def admin_unlock_unit(self) -> None:
        if self.account_token is None or not self.is_admin:
            self.status = "Administrator access is required."
            return
        if not self.admin_username_input.strip():
            self.status = "Enter or select an account username."
            return
        unit = unit_stats(self.selected_lobby_unit)
        try:
            result = self.account_client.unlock_account_unit(
                self.admin_username_input.strip(),
                str(unit["id"]),
                self.account_token,
            )
        except AccountServiceError as error:
            self.status = str(error)
            return
        if result.get("already_unlocked") is True:
            self.status = f"{unit['name']} is already unlocked for {self.admin_username_input.strip()}."
        else:
            self.status = f"Unlocked {unit['name']} for {self.admin_username_input.strip()}."
        self.refresh_admin_accounts(show_status=False)
        if self.admin_username_input.casefold() == (self.account_name or "").casefold():
            self.reload_own_profile()

    def admin_unlock_all_units(self) -> None:
        username = self.admin_username_input.strip()
        if not username:
            self.status = "Enter or select an account username."
            return
        if self.account_token is None or not self.is_admin:
            self.status = "Administrator access is required."
            return
        try:
            result = self.account_client.unlock_all_account_units(username, self.account_token)
        except AccountServiceError as error:
            self.status = str(error)
            return
        self.status = f"Unlocked all {result.get('unlocked_units', 'bonus')} bonus units for {username}."
        self.refresh_admin_accounts(show_status=False)
        if username.casefold() == (self.account_name or "").casefold():
            self.reload_own_profile()

    def grant_admin_crates(self) -> None:
        amount = self.parse_admin_integer(
            self.admin_crate_count_input,
            "Crate amount",
            minimum=1,
        )
        if amount is None:
            return
        if amount > 1_000_000:
            self.status = "Crate amount must be from 1 to 1000000."
            return
        username = self.admin_username_input.strip()
        if not username:
            self.status = "Enter or select an account username."
            return
        if self.account_token is None or not self.is_admin:
            self.status = "Administrator access is required."
            return
        try:
            self.account_client.grant_account_crates(
                username,
                self.admin_selected_crate,
                amount,
                self.account_token,
            )
        except AccountServiceError as error:
            self.status = str(error)
            return
        self.status = f"Granted {amount} {CRATE_TYPES[self.admin_selected_crate]['name']} to {username}."
        self.refresh_admin_accounts(show_status=False)
        if username.casefold() == (self.account_name or "").casefold():
            self.reload_own_profile()

    def save_admin_story_level(self) -> None:
        level = self.parse_admin_integer(
            self.admin_story_level_input,
            "Story level",
            minimum=1,
        )
        if level is None:
            return
        if level > 1_000_000:
            self.status = "Story level must be from 1 to 1000000."
            return
        username = self.admin_username_input.strip()
        if not username:
            self.status = "Enter or select an account username."
            return
        if self.account_token is None or not self.is_admin:
            self.status = "Administrator access is required."
            return
        try:
            self.account_client.set_account_story_level(username, level, self.account_token)
        except AccountServiceError as error:
            self.status = str(error)
            return
        self.status = f"Set {username}'s next story level to {level}."
        self.refresh_admin_accounts(show_status=False)
        if username.casefold() == (self.account_name or "").casefold():
            self.reload_own_profile()

    def reset_admin_daily_challenge(self) -> None:
        username = self.admin_username_input.strip()
        if not username:
            self.status = "Enter or select an account username."
            return
        if self.account_token is None or not self.is_admin:
            self.status = "Administrator access is required."
            return
        try:
            self.account_client.reset_account_daily_challenge(username, self.account_token)
        except AccountServiceError as error:
            self.status = str(error)
            return
        self.status = f"Reset today's daily challenge for {username}."
        self.refresh_admin_accounts(show_status=False)
        if username.casefold() == (self.account_name or "").casefold():
            self.reload_own_profile()

    def save_starting_cash(self) -> None:
        amount = self.parse_admin_integer(self.starting_cash_input, "Starting cash", minimum=0)
        if amount is None:
            return
        if self.account_token is None or not self.is_admin:
            self.status = "Administrator access is required."
            return
        username = self.admin_username_input.strip()
        if not username:
            self.status = "Enter or select an account username."
            return
        try:
            self.account_client.set_starting_cash(username, amount, self.account_token)
        except AccountServiceError as error:
            self.status = str(error)
            return
        self.status = f"Starting cash for {username} set to ${amount}."
        self.refresh_admin_accounts(show_status=False)
        if username.casefold() == (self.account_name or "").casefold():
            self.reload_own_profile()

    def toggle_admin_speed_access(self) -> None:
        username = self.admin_username_input.strip()
        if not username:
            self.status = "Enter or select an account username."
            return
        if self.account_token is None or not self.is_admin:
            self.status = "Administrator access is required."
            return
        account = next(
            (
                item
                for item in self.admin_accounts
                if str(item.get("username", "")).casefold() == username.casefold()
            ),
            None,
        )
        if account is None:
            self.status = "Refresh the account list and select a registered account."
            return
        enabled = account.get("custom_speed_access") is not True
        try:
            self.account_client.grant_speed_access(username, enabled, self.account_token)
        except AccountServiceError as error:
            self.status = str(error)
            return
        self.status = f"Custom-speed access {'granted to' if enabled else 'revoked from'} {username}."
        if username.casefold() == (self.account_name or "").casefold():
            self.has_custom_speed = enabled
        self.refresh_admin_accounts(show_status=False)

    def reload_own_profile(self) -> None:
        if self.account_token is None:
            return
        try:
            self.load_profile(self.account_client.get_profile(self.account_token))
        except AccountServiceError as error:
            self.status = f"Action completed, but profile refresh failed: {error}"

    def select_admin_unit(self, direction: int) -> None:
        bonus_units = list(all_unit_indices())[len(TOWER_TYPES):]
        current_position = bonus_units.index(self.selected_lobby_unit) if self.selected_lobby_unit in bonus_units else 0
        self.selected_lobby_unit = bonus_units[
            (current_position + direction) % len(bonus_units)
        ]

    def parse_admin_integer(
        self,
        value: str,
        label: str,
        minimum: int,
    ) -> int | None:
        try:
            amount = int(value)
        except ValueError:
            self.status = f"Enter a whole-number {label.lower()}."
            return None
        if not minimum <= amount <= 1_000_000_000:
            self.status = f"{label} must be from {minimum} to 1000000000."
            return None
        return amount

    def handle_lobby_click(self, position: tuple[int, int]) -> None:
        if pygame.Rect(720, 295, 260, 44).collidepoint(position):
            self.screen_state = "battle_pass"
            return
        if pygame.Rect(20, 140, 265, 72).collidepoint(position):
            self.screen_state = "collection"
            return
        if pygame.Rect(20, 225, 265, 68).collidepoint(position):
            self.screen_state = "crates"
            return
        if pygame.Rect(20, 300, 265, 48).collidepoint(position):
            self.screen_state = "traits"
            self.trait_unit_scroll = 0
            self.trait_option_scroll = 0
            return
        for index, map_key in enumerate(MAPS):
            if pygame.Rect(20 + index * 190, 492, 178, 36).collidepoint(position):
                self.selected_map = map_key
                self.status = f"{MAPS[map_key]['name']} map selected for infinite mode."
                return
        if pygame.Rect(20, 536, 220, 42).collidepoint(position):
            if self.daily_challenge_claimed():
                self.status = "Today's daily challenge reward was already claimed."
            else:
                self.screen_state = "daily_challenge"
                self.status = "Choose the difficulty for today's challenge."
            return
        if pygame.Rect(252, 536, 220, 42).collidepoint(position):
            self.screen_state = "story_mode"
            self.status = f"Story level {self.story_level} is ready."
            return
        for index, count in enumerate((25, 100, 1000)):
            if pygame.Rect(320 + index * 160, 170, 145, 90).collidepoint(position):
                self.roll_for_unit(count)
                return
        for index, mode in enumerate(GAME_MODES):
            if pygame.Rect(20 + index * 192, 378, 180, 90).collidepoint(position):
                self.selected_mode = str(mode["key"])
                self.status = f"{mode['name']} mode selected."
                return
        if pygame.Rect(20, 600, 170, 60).collidepoint(position):
            self.screen_state = "setup"
            return
        if pygame.Rect(800, 590, 170, 76).collidepoint(position):
            self.start_game()
            return
        if pygame.Rect(815, 80, 165, 34).collidepoint(position) and self.is_admin:
            self.open_admin_panel()

    def toggle_equipped_unit(self, unit_index: int) -> None:
        if unit_index not in self.owned_units:
            self.status = "Unlock this unit before equipping it."
            return
        if unit_index in self.available_towers:
            if len(self.available_towers) == 1:
                self.status = "Keep at least one unit equipped."
                return
            self.available_towers.remove(unit_index)
        elif len(self.available_towers) >= MAX_EQUIPPED_TOWERS:
            self.status = f"You can equip up to {MAX_EQUIPPED_TOWERS} units."
            return
        else:
            self.available_towers.add(unit_index)
        if self.selected_tower_type not in self.available_towers:
            self.selected_tower_type = min(self.available_towers)
        self.status = f"{unit_stats(unit_index)['name']} loadout updated."
        self.save_loadout()

    def roll_for_unit(self, count: int = 1) -> None:
        if count not in (1, 25, 100, 1000):
            self.status = "Choose a supported summon amount."
            return
        cost = ROLL_COST * count
        if self.account_token is not None:
            previous_traits = self.unit_traits.copy()
            try:
                result = self.account_client.roll_unit(self.account_token, count)
                self.load_profile(result)
                gained_traits = {
                    unit_id: trait
                    for unit_id, trait in self.unit_traits.items()
                    if unit_id not in previous_traits
                }
                summary = result.get("summon_summary")
                new_units = 0
                duplicates = 0
                if isinstance(summary, list):
                    for entry in summary:
                        if not isinstance(entry, dict):
                            continue
                        unlock_count = entry.get("new_unlocks")
                        duplicate_count = entry.get("duplicates")
                        if isinstance(unlock_count, int):
                            new_units += unlock_count
                        if isinstance(duplicate_count, int):
                            duplicates += duplicate_count
                    if new_units:
                        unit_id = result.get("unit_id")
                        if isinstance(unit_id, str):
                            unit_index = unit_index_for_id(unit_id)
                            if unit_index is not None:
                                self.selected_lobby_unit = unit_index
                if count == 1:
                    unit_id = result.get("unit_id")
                    unit_index = unit_index_for_id(unit_id) if isinstance(unit_id, str) else None
                    if unit_index is not None:
                        unit = unit_stats(unit_index)
                        if result.get("duplicate") is True:
                            self.status = (
                                f"Duplicate {unit['rarity']} {unit['name']}: "
                                f"{self.unit_copies.get(str(unit['id']), 0)} copies held."
                            )
                        else:
                            self.status = f"Unlocked {unit['rarity']} unit: {unit['name']}!"
                        trait = gained_traits.get(str(unit["id"]))
                        if trait is not None:
                            self.status += f" Trait gained: {trait['name']}."
                        return
                self.status = (
                    f"Summoned {count} units for {cost} credits: "
                    f"{new_units} newly unlocked, {duplicates} duplicates."
                )
                if gained_traits:
                    self.status += f" {len(gained_traits)} trait(s) gained."
            except AccountServiceError as error:
                self.status = str(error)
            return
        if self.credits < cost:
            self.status = f"Summoning x{count} costs {cost} credits."
            return
        self.credits -= cost
        new_units = 0
        duplicates = 0
        last_new_unit: int | None = None
        last_unit: dict[str, object] | None = None
        last_duplicate = False
        summoned_owners = set(self.owned_units)
        summoned_copies = self.unit_copies.copy()
        summoned_traits = self.unit_traits.copy()
        traits_gained = 0
        traits_gained_ids: set[str] = set()
        for _ in range(count):
            unit = roll_unit()
            if unit is None:
                self.credits += cost
                self.status = "The summon table could not produce a unit."
                return
            unit_index = unit_index_for_id(str(unit["id"]))
            if unit_index is None:
                self.credits += cost
                self.status = "The unit catalog returned an unknown unit."
                return
            last_unit = unit
            last_duplicate = unit_index in summoned_owners
            unit_id = str(unit["id"])
            if unit_index in summoned_owners:
                summoned_copies[unit_id] = summoned_copies.get(unit_id, 0) + 1
                duplicates += 1
            else:
                summoned_owners.add(unit_index)
                last_new_unit = unit_index
                new_units += 1
            if unit_id not in summoned_traits and random.random() < TRAIT_BASE_CHANCE:
                summoned_traits[unit_id] = random_trait()
                traits_gained += 1
                traits_gained_ids.add(unit_id)
        self.owned_units = summoned_owners
        self.unit_copies = summoned_copies
        self.unit_traits = summoned_traits
        if last_new_unit is not None:
            self.selected_lobby_unit = last_new_unit
        if count == 1 and last_unit is not None:
            unit_id = str(last_unit["id"])
            if last_duplicate:
                self.status = (
                    f"Duplicate {last_unit['rarity']} {last_unit['name']}: "
                    f"{self.unit_copies.get(unit_id, 0)} copies held."
                )
            else:
                self.status = f"Unlocked {last_unit['rarity']} unit: {last_unit['name']}!"
            trait = self.unit_traits.get(str(last_unit["id"]))
            if trait is not None and str(last_unit["id"]) in traits_gained_ids:
                self.status += f" Trait gained: {trait['name']}."
            return
        self.status = (
            f"Summoned {count} units for {cost} credits: "
            f"{new_units} newly unlocked, {duplicates} duplicates."
        )
        if traits_gained:
            self.status += f" {traits_gained} trait(s) gained."

    def upgrade_lobby_unit(self) -> None:
        if self.selected_lobby_unit not in self.owned_units:
            self.status = "Unlock this unit before upgrading it."
            return
        unit = unit_stats(self.selected_lobby_unit)
        unit_id = str(unit["id"])
        level = self.unit_levels.get(unit_id, 1)
        if self.account_token is not None:
            try:
                profile = self.account_client.upgrade_unit(unit_id, self.account_token)
                self.load_profile(profile)
                new_level = profile.get("upgraded_level")
                self.status = f"{unit['name']} upgraded to lobby level {new_level}."
            except AccountServiceError as error:
                self.status = str(error)
            return
        if self.selected_lobby_unit < len(TOWER_TYPES):
            cost = unit_upgrade_cost(level)
            if self.credits < cost:
                self.status = f"Need {cost} credits to upgrade this base unit."
                return
            self.credits -= cost
        else:
            cost = duplicate_cost(self.selected_lobby_unit)
            copies = self.unit_copies.get(unit_id, 0)
            if copies < cost:
                self.status = f"Need {cost} duplicate copies to level this {unit['rarity']} unit."
                return
            self.unit_copies[unit_id] = copies - cost
        self.unit_levels[unit_id] = level + 1
        self.status = f"{unit['name']} upgraded to lobby level {level + 1}."

    def handle_collection_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_b):
                    self.screen_state = "lobby"
                elif event.key == pygame.K_u:
                    self.upgrade_lobby_unit()
            elif event.type == pygame.MOUSEWHEEL:
                self.collection_scroll = max(
                    0,
                    min(
                        max(0, len(all_unit_indices()) - 8),
                        self.collection_scroll - event.y,
                    ),
                )
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_collection_click(event.pos)
        return True

    def handle_collection_click(self, position: tuple[int, int]) -> None:
        if pygame.Rect(20, 600, 170, 60).collidepoint(position):
            self.screen_state = "lobby"
            return
        if pygame.Rect(850, 605, 130, 58).collidepoint(position):
            self.start_game()
            return
        if pygame.Rect(800, 545, 170, 46).collidepoint(position):
            self.upgrade_lobby_unit()
            return
        for visible_row, unit_index in enumerate(
            list(all_unit_indices())[self.collection_scroll:self.collection_scroll + 8]
        ):
            row = pygame.Rect(20, 105 + visible_row * 55, 600, 49)
            equip_button = pygame.Rect(630, 105 + visible_row * 55, 100, 49)
            if equip_button.collidepoint(position):
                self.selected_lobby_unit = unit_index
                self.toggle_equipped_unit(unit_index)
                return
            if row.collidepoint(position):
                self.selected_lobby_unit = unit_index
                return

    def handle_events(self) -> bool:
        preparing = self.screen_state == "preparation"
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                if not self.commit_match_credits():
                    return True
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if preparing:
                        self.screen_state = "lobby"
                        continue
                    if not self.commit_match_credits():
                        continue
                    return False
                if event.key == pygame.K_o and not self.game_over:
                    self.cycle_autoplay_mode()
                    continue
                if event.key == pygame.K_RETURN and preparing:
                    self.begin_wave()
                    continue
                if event.key == pygame.K_n and not preparing:
                    self.skip_wave()
                    continue
                if event.key == pygame.K_r and self.game_over and self.commit_match_credits():
                    self.reset()
                if not self.game_over:
                    if pygame.K_1 <= event.key <= pygame.K_5:
                        loadout = sorted(self.available_towers)
                        hotkey_index = event.key - pygame.K_1
                        if hotkey_index < len(loadout):
                            self.select_tower_type(loadout[hotkey_index])
                    elif event.key == pygame.K_u:
                        self.upgrade_selected_defender()
                    elif event.key == pygame.K_m:
                        self.unit_management_open = not self.unit_management_open
            if event.type == pygame.MOUSEBUTTONDOWN:
                if preparing and event.button == 1:
                    if pygame.Rect(610, 34, 205, 30).collidepoint(event.pos):
                        self.cycle_autoplay_mode()
                    elif pygame.Rect(770, 510, 200, 62).collidepoint(event.pos):
                        self.begin_wave()
                    elif pygame.Rect(605, 510, 145, 62).collidepoint(event.pos):
                        self.screen_state = "lobby"
                    else:
                        self.handle_left_click(event.pos)
                elif self.game_over and event.button == 1:
                    if pygame.Rect(300, 410, 180, 56).collidepoint(event.pos):
                        self.go_to_lobby()
                    elif pygame.Rect(520, 410, 180, 56).collidepoint(event.pos):
                        if self.challenge_won and self.play_mode == "daily":
                            self.go_to_lobby()
                        else:
                            self.start_game(self.play_mode)
                elif not self.game_over and event.button == 1:
                    if pygame.Rect(610, 34, 205, 30).collidepoint(event.pos):
                        self.cycle_autoplay_mode()
                    elif pygame.Rect(830, 5, 150, 56).collidepoint(event.pos):
                        self.skip_wave()
                    else:
                        self.handle_left_click(event.pos)
                elif not self.game_over and event.button == 3:
                    self.remove_defender(event.pos)
            if (
                not self.game_over
                and event.type == pygame.MOUSEWHEEL
                and self.unit_management_open
                and pygame.Rect(690, 84, 290, 500).collidepoint(self.ui_mouse_position)
            ):
                self.unit_management_scroll = max(
                    0,
                    min(
                        max(0, len(self.defenders) - 5),
                        self.unit_management_scroll - event.y,
                    ),
                )
        return True

    def update(self, delta_time: float) -> None:
        self.update_waves(delta_time)
        for zombie in self.zombies:
            zombie.update(delta_time)
        burning_sources = [
            zombie
            for zombie in self.zombies
            if zombie.burn_spread_dps > 0 and zombie.burn_remaining > 0
        ]
        spread_radius_squared = 32**2
        for source in burning_sources:
            for target in self.zombies:
                dx = target.x - source.x
                dy = target.y - source.y
                if (
                    target is not source
                    and not target.reached_base
                    and target.health > 0
                    and target.burn_spread_dps == 0
                    and dx * dx + dy * dy <= spread_radius_squared
                ):
                    target.apply_burn(
                        source.burn_spread_dps,
                        5.0,
                        stack=True,
                        spread=True,
                    )
        self.lives -= sum(zombie.reached_base for zombie in self.zombies)
        escaped = [zombie for zombie in self.zombies if zombie.reached_base]
        for zombie in escaped:
            group = self.wave_groups.get(zombie.wave)
            if group is not None:
                group.escaped += 1
        self.zombies = [zombie for zombie in self.zombies if not zombie.reached_base]

        for defender in self.defenders:
            self.money += defender.collect_income(delta_time)
            projectile = defender.update(delta_time, self.zombies)
            if projectile is not None:
                self.projectiles.append(projectile)

        for projectile in self.projectiles:
            projectile.update(delta_time, self.zombies)
        self.projectiles = [projectile for projectile in self.projectiles if projectile.active]

        defeated = [zombie for zombie in self.zombies if zombie.health <= 0]
        for zombie in defeated:
            group = self.wave_groups.get(zombie.wave)
            if group is not None:
                group.defeated += 1
        self.money += sum(zombie.reward for zombie in defeated)
        mode = GAME_MODES_BY_KEY[self.selected_mode]
        for _ in defeated:
            if random.random() < float(mode["drop_chance"]):
                self.pending_credits += random.randint(
                    int(mode["credit_min"]),
                    int(mode["credit_max"]),
                )
        self.zombies = [zombie for zombie in self.zombies if zombie.health > 0]

        if self.lives <= 0:
            self.lives = 0
            self.game_over = True
            self.commit_match_credits()

    def update_waves(self, delta_time: float) -> None:
        ready_waves: list[int] = []
        for wave, remaining_time in self.wave_start_timers.items():
            remaining_time -= delta_time
            if remaining_time <= 0:
                ready_waves.append(wave)
            else:
                self.wave_start_timers[wave] = remaining_time
        for wave in ready_waves:
            self.wave_start_timers.pop(wave, None)
            self.schedule_wave(wave)

        mode = GAME_MODES_BY_KEY[self.selected_mode]
        for group in list(self.wave_groups.values()):
            if group.enemies:
                group.spawn_timer -= delta_time
                if group.spawn_timer <= 0:
                    enemy_type = group.enemies.pop(0)
                    self.zombies.append(
                        Zombie(
                            self.path_points,
                            group.wave,
                            int(mode["enemy_power"]),
                            float(mode["movement_speed"]),
                            enemy_type,
                            1.5 ** (group.wave // 10),
                        )
                    )
                    group.spawned += 1
                    group.spawn_timer = max(0.55, 1.15 - group.wave * 0.035)
            if (
                not group.enemies
                and group.spawned == group.defeated + group.escaped
            ):
                self.complete_wave(group)

    def place_defender(self, position: tuple[int, int]) -> None:
        x, y = position
        if self.selected_tower_type not in self.available_towers:
            return
        if y < TOP_BAR_HEIGHT or x < 24 or x > SCREEN_WIDTH - 24 or y > SCREEN_HEIGHT - 24:
            return
        tower_cost = int(unit_stats(self.selected_tower_type)["cost"])
        if self.money < tower_cost:
            self.status = "Need more scrap to recruit a defender."
            return
        if self.is_on_path(x, y, self.path_points):
            self.status = "Defenders must stand on the grass, not the road."
            return
        if any(
            (defender.x - x) ** 2 + (defender.y - y) ** 2 < 42**2
            for defender in self.defenders
        ):
            self.status = "That spot is too close to another defender."
            return

        unit = unit_stats(self.selected_tower_type)
        trait = self.unit_traits.get(str(unit["id"]))
        if (
            trait is not None
            and trait["id"] == ULTIMATE_TRAIT_ID
            and any(
                defender.trait is not None
                and defender.trait.get("id") == ULTIMATE_TRAIT_ID
                for defender in self.defenders
            )
        ):
            self.status = "Only one unit with the Overlord trait may be placed."
            return
        defender = Defender(
            x,
            y,
            self.selected_tower_type,
            self.unit_levels.get(str(unit["id"]), 1),
            trait,
        )
        self.defenders.append(defender)
        self.money -= tower_cost
        self.selected_defender = defender
        self.placement_mode = False
        self.status = f"{defender.stats['name']} recruited."

    def can_place_defender(
        self,
        position: tuple[int, int],
        tower_type: int | None = None,
    ) -> bool:
        x, y = position
        tower_type = self.selected_tower_type if tower_type is None else tower_type
        if tower_type not in self.available_towers:
            return False
        tower_cost = int(unit_stats(tower_type)["cost"])
        unit = unit_stats(tower_type)
        trait = self.unit_traits.get(str(unit["id"]))
        if (
            trait is not None
            and trait["id"] == ULTIMATE_TRAIT_ID
            and any(
                defender.trait is not None
                and defender.trait.get("id") == ULTIMATE_TRAIT_ID
                for defender in self.defenders
            )
        ):
            return False
        return (
            TOP_BAR_HEIGHT <= y < TOWER_BAR_TOP
            and 24 <= x <= SCREEN_WIDTH - 24
            and y <= SCREEN_HEIGHT - 24
            and self.money >= tower_cost
            and not self.is_on_path(x, y, self.path_points)
            and all(
                (defender.x - x) ** 2 + (defender.y - y) ** 2 >= 42**2
                for defender in self.defenders
            )
        )

    def handle_left_click(self, position: tuple[int, int]) -> None:
        x, y = position
        if pygame.Rect(715, TOWER_BAR_TOP + 8, 255, 64).collidepoint(position):
            self.unit_management_open = not self.unit_management_open
            return
        if self.unit_management_open and pygame.Rect(690, 84, 290, 500).collidepoint(position):
            self.handle_unit_management_click(position)
            return
        if y >= TOWER_BAR_TOP:
            for slot, index in enumerate(sorted(self.available_towers)):
                card_x = 10 + slot * 102
                if card_x <= x < card_x + 96 and TOWER_BAR_TOP + 8 <= y < TOWER_BAR_TOP + 72:
                    self.select_tower_type(index)
                    return
            if 530 <= x < 700 and TOWER_BAR_TOP + 8 <= y < TOWER_BAR_TOP + 72:
                self.upgrade_selected_defender()
            return

        for defender in self.defenders:
            if (defender.x - x) ** 2 + (defender.y - y) ** 2 <= 21**2:
                self.selected_defender = defender
                self.placement_mode = False
                self.status = (
                    f"Selected {defender.stats['name']} (level {defender.level}). "
                    "Press U to upgrade."
                )
                return

        self.place_defender(position)

    def select_tower_type(self, tower_type: int) -> None:
        if tower_type not in self.available_towers:
            return
        self.selected_tower_type = tower_type
        self.placement_mode = True
        self.status = f"{unit_stats(tower_type)['name']} selected. Move to preview, click to place."

    def handle_unit_management_click(self, position: tuple[int, int]) -> None:
        panel = pygame.Rect(690, 84, 290, 500)
        if not panel.collidepoint(position):
            return
        upgrade_button = pygame.Rect(710, 530, 250, 40)
        if upgrade_button.collidepoint(position):
            self.upgrade_selected_defender()
            return
        for row_index, defender in enumerate(
            self.defenders[self.unit_management_scroll:self.unit_management_scroll + 5]
        ):
            row = pygame.Rect(705, 128 + row_index * 32, 260, 28)
            if row.collidepoint(position):
                self.selected_defender = defender
                self.status = f"Selected {defender.stats['name']} (level {defender.level})."
                return

    def upgrade_selected_defender(self) -> None:
        defender = self.selected_defender
        if defender is None:
            self.status = "Select a placed human before upgrading."
            return
        cap = combat_upgrade_cap(defender.tower_type)
        if defender.level >= cap:
            self.status = "This defender is already fully upgraded."
            return

        cost = (
            UPGRADE_COSTS[defender.level - 1]
            if defender.level <= len(UPGRADE_COSTS)
            else round(UPGRADE_COSTS[-1] * 1.5 ** (defender.level - len(UPGRADE_COSTS)))
        )
        if self.money < cost:
            self.status = f"Need ${cost} scrap to upgrade this defender."
            return

        self.money -= cost
        defender.level += 1
        self.status = f"{defender.stats['name']} upgraded to level {defender.level}!"

    @staticmethod
    def is_on_path(
        x: int,
        y: int,
        path_points: tuple[tuple[int, int], ...] = SCREEN_PATH_POINTS,
    ) -> bool:
        for start, end in zip(path_points, path_points[1:]):
            x1, y1 = start
            x2, y2 = end
            dx = x2 - x1
            dy = y2 - y1
            segment_length_squared = dx * dx + dy * dy
            progress = ((x - x1) * dx + (y - y1) * dy) / segment_length_squared
            progress = max(0.0, min(1.0, progress))
            closest_x = x1 + progress * dx
            closest_y = y1 + progress * dy
            if (x - closest_x) ** 2 + (y - closest_y) ** 2 < 42**2:
                return True
        return False

    def remove_defender(self, position: tuple[int, int]) -> None:
        x, y = position
        for defender in self.defenders:
            if (defender.x - x) ** 2 + (defender.y - y) ** 2 <= 21**2:
                self.defenders.remove(defender)
                self.money += int(defender.stats["cost"]) // 2
                if self.selected_defender is defender:
                    self.selected_defender = None
                self.status = "Defender dismissed for half the tower cost."
                return
