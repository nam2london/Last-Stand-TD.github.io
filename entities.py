"""Game objects used by the tower-defense simulation."""

from __future__ import annotations

import math
from functools import lru_cache

import pygame

from settings import (
    GOLD_COLOR,
    HEALTH_COLOR,
    PROJECTILE_SPEED,
    WHITE,
    ZOMBIE_COLOR,
)
from progression import UPGRADE_STAT_MULTIPLIER, unit_stats


ENEMY_ARCHETYPES = {
    "normal": {
        "name": "Walker",
        "health": 1.0,
        "speed": 1.0,
        "reward": 1.0,
        "radius": 15,
        "color": ZOMBIE_COLOR,
    },
    "runner": {
        "name": "Runner",
        "health": 0.6,
        "speed": 1.8,
        "reward": 1.2,
        "radius": 12,
        "color": (231, 195, 74),
    },
    "tank": {
        "name": "Tank",
        "health": 3.0,
        "speed": 0.65,
        "reward": 2.0,
        "radius": 20,
        "color": (145, 90, 69),
    },
    "mini_boss": {
        "name": "Mini-Boss",
        "health": 10.0,
        "speed": 0.8,
        "reward": 10.0,
        "radius": 25,
        "color": (186, 91, 187),
    },
    "boss": {
        "name": "BOSS",
        "health": 40.0,
        "speed": 0.6,
        "reward": 40.0,
        "radius": 32,
        "color": (207, 63, 66),
    },
}

_BOSS_TYPES = frozenset(("mini_boss", "boss"))


@lru_cache(maxsize=8)
def _font(size: int) -> pygame.font.Font:
    return pygame.font.Font(None, size)


@lru_cache(maxsize=128)
def _rendered_text(
    text: str,
    size: int,
    color: tuple[int, int, int],
) -> pygame.Surface:
    return _font(size).render(text, True, color)


@lru_cache(maxsize=32)
def _range_overlay(
    color: tuple[int, int, int],
    radius: int,
    alpha: int,
) -> pygame.Surface:
    diameter = radius * 2 + 1
    overlay = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    pygame.draw.circle(overlay, (*color, alpha), (radius, radius), radius)
    return overlay


@lru_cache(maxsize=16)
def _path_segments(
    path: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, int, float], ...]:
    return tuple(
        (
            end[0] - start[0],
            end[1] - start[1],
            math.hypot(end[0] - start[0], end[1] - start[1]),
        )
        for start, end in zip(path, path[1:])
    )


def draw_circle_overlay(
    surface: pygame.Surface,
    center: tuple[int, int],
    radius: int,
    color: tuple[int, int, int],
    alpha: int,
) -> None:
    """Blit a cached translucent circle without allocating a screen-sized surface."""
    overlay = _range_overlay(color, radius, alpha)
    surface.blit(overlay, (center[0] - radius, center[1] - radius))


class Zombie:
    """A zombie that walks along the fixed road toward the base."""

    def __init__(
        self,
        path: tuple[tuple[int, int], ...],
        wave: int,
        power_multiplier: int = 1,
        movement_multiplier: float = 1.0,
        enemy_type: str = "normal",
        hp_multiplier: float = 1.0,
    ) -> None:
        if enemy_type not in ENEMY_ARCHETYPES:
            raise ValueError(f"Unknown enemy type: {enemy_type}")
        archetype = ENEMY_ARCHETYPES[enemy_type]
        self.path = path
        self.path_segments = _path_segments(path)
        self.wave = wave
        self.enemy_type = enemy_type
        self.segment = 0
        self.x = float(path[0][0])
        self.y = float(path[0][1])
        self.radius = int(archetype["radius"])
        self.max_health = round(
            (55 + wave * 12)
            * power_multiplier
            * hp_multiplier
            * float(archetype["health"])
        )
        self.health = float(self.max_health)
        self.speed = (
            (48 + min(wave * 2.5, 35))
            * movement_multiplier
            * float(archetype["speed"])
        )
        self.reward = round((18 + wave * 2) * float(archetype["reward"]))
        self.reached_base = False
        self.burn_remaining = 0.0
        self.burn_dps = 0.0
        self._regular_burn_dps = 0.0
        self._regular_burn_remaining = 0.0
        self._stacked_burns: list[tuple[float, float, bool]] = []
        self.burn_spread_dps = 0.0
        self.poison_remaining = 0.0
        self.poison_dps = 0.0
        self.bleed_remaining = 0.0
        self.bleed_dps = 0.0
        self._bleeds: list[tuple[float, float]] = []
        self.slow_remaining = 0.0
        self.slow_factor = 1.0

    def update(self, delta_time: float) -> None:
        if self.health <= 0 or self.reached_base:
            return

        self.health -= self._regular_burn_dps * min(
            delta_time, self._regular_burn_remaining
        )
        self._regular_burn_remaining = max(
            0.0, self._regular_burn_remaining - delta_time
        )
        active_burns: list[tuple[float, float, bool]] = []
        for damage_per_second, remaining, spreads in self._stacked_burns:
            self.health -= damage_per_second * min(delta_time, remaining)
            remaining = max(0.0, remaining - delta_time)
            if remaining > 0:
                active_burns.append((damage_per_second, remaining, spreads))
        self._stacked_burns = active_burns
        self.burn_dps = self._regular_burn_dps + sum(
            damage_per_second for damage_per_second, _, _ in active_burns
        )
        self.burn_remaining = max(
            [self._regular_burn_remaining]
            + [remaining for _, remaining, _ in active_burns]
        )
        self.burn_spread_dps = max(
            (
                damage_per_second
                for damage_per_second, _, spreads in active_burns
                if spreads
            ),
            default=0.0,
        )

        self.health -= self.poison_dps * min(delta_time, self.poison_remaining)
        self.poison_remaining = max(0.0, self.poison_remaining - delta_time)
        if self.poison_remaining == 0:
            self.poison_dps = 0.0

        active_bleeds: list[tuple[float, float]] = []
        for damage_per_second, remaining in self._bleeds:
            self.health -= damage_per_second * min(delta_time, remaining)
            remaining = max(0.0, remaining - delta_time)
            if remaining > 0:
                active_bleeds.append((damage_per_second, remaining))
        self._bleeds = active_bleeds
        self.bleed_dps = sum(damage_per_second for damage_per_second, _ in active_bleeds)
        self.bleed_remaining = max(
            (remaining for _, remaining in active_bleeds),
            default=0.0,
        )

        if self.health <= 0:
            return

        slowed_time = min(delta_time, self.slow_remaining)
        movement_time = slowed_time * self.slow_factor + (delta_time - slowed_time)
        self.slow_remaining = max(0.0, self.slow_remaining - delta_time)
        if self.slow_remaining == 0:
            self.slow_factor = 1.0

        distance_left = self.speed * movement_time
        while distance_left > 0 and self.segment < len(self.path) - 1:
            target_x, target_y = self.path[self.segment + 1]
            dx, dy, distance = self.path_segments[self.segment]
            if distance <= distance_left:
                self.x = float(target_x)
                self.y = float(target_y)
                distance_left -= distance
                self.segment += 1
            else:
                self.x += dx / distance * distance_left
                self.y += dy / distance * distance_left
                distance_left = 0

        if self.segment >= len(self.path) - 1:
            self.reached_base = True

    def apply_burn(
        self,
        damage_per_second: float,
        duration: float,
        stack: bool = False,
        spread: bool = False,
    ) -> None:
        if stack or spread:
            self._stacked_burns.append((damage_per_second, duration, spread))
            self.burn_dps += damage_per_second
            self.burn_remaining = max(self.burn_remaining, duration)
            if spread:
                self.burn_spread_dps = max(self.burn_spread_dps, damage_per_second)
            return
        self._regular_burn_dps = max(self._regular_burn_dps, damage_per_second)
        self._regular_burn_remaining = max(self._regular_burn_remaining, duration)
        self.burn_dps = self._regular_burn_dps + sum(
            burn_dps for burn_dps, _, _ in self._stacked_burns
        )
        self.burn_remaining = max(self.burn_remaining, duration)

    def apply_poison(self, damage_per_second: float, duration: float) -> None:
        self.poison_dps = max(self.poison_dps, damage_per_second)
        self.poison_remaining = max(self.poison_remaining, duration)

    def apply_bleed(self, damage_per_second: float, duration: float) -> None:
        self._bleeds.append((damage_per_second, duration))
        self.bleed_dps += damage_per_second
        self.bleed_remaining = max(self.bleed_remaining, duration)

    def apply_slow(self, speed_factor: float, duration: float) -> None:
        self.slow_factor = min(self.slow_factor, speed_factor)
        self.slow_remaining = max(self.slow_remaining, duration)

    def draw(self, surface: pygame.Surface) -> None:
        center = (round(self.x), round(self.y))
        body_color = tuple(ENEMY_ARCHETYPES[self.enemy_type]["color"])
        if self.burn_remaining > 0:
            body_color = (235, 119, 68)
        elif self.poison_remaining > 0:
            body_color = (157, 202, 86)
        elif self.bleed_remaining > 0:
            body_color = (190, 76, 100)
        elif self.slow_remaining > 0:
            body_color = (113, 207, 232)

        shadow_center = (center[0] + self.radius // 2, center[1] + self.radius // 2)
        pygame.draw.ellipse(surface, (18, 24, 19), (shadow_center[0] - self.radius - 2, shadow_center[1] - 6, self.radius * 2 + 4, self.radius * 2 // 3))
        pygame.draw.circle(surface, (32, 45, 28), center, self.radius + 3)
        pygame.draw.circle(surface, body_color, center, self.radius)
        highlight = tuple(min(255, channel + 35) for channel in body_color)
        pygame.draw.circle(surface, highlight, (center[0] - self.radius // 3, center[1] - self.radius // 3), self.radius // 2)
        pygame.draw.circle(surface, (42, 48, 34), (center[0] - 5, center[1] - 3), 2)
        pygame.draw.circle(surface, (42, 48, 34), (center[0] + 5, center[1] - 3), 2)

        bar_width = max(34, self.radius * 2)
        bar_y = center[1] - self.radius - 9
        pygame.draw.rect(surface, (53, 47, 42), (center[0] - bar_width // 2, bar_y, bar_width, 5))
        health_width = round(bar_width * max(0, self.health) / self.max_health)
        if health_width:
            pygame.draw.rect(surface, HEALTH_COLOR, (center[0] - bar_width // 2, bar_y, health_width, 5))
        if self.enemy_type in _BOSS_TYPES:
            label = _rendered_text(
                str(ENEMY_ARCHETYPES[self.enemy_type]["name"]), 16, WHITE
            )
            surface.blit(label, label.get_rect(midbottom=(center[0], bar_y - 2)))


class Defender:
    """A human defender that automatically fires at nearby zombies."""

    def __init__(
        self,
        x: int,
        y: int,
        tower_type: int = 0,
        lobby_level: int = 1,
        trait: dict[str, object] | None = None,
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.tower_type = tower_type
        self._stats = unit_stats(tower_type)
        self.level = 1
        self.lobby_level = max(1, lobby_level)
        self.trait = dict(trait) if trait is not None else None
        self.cooldown = 0.0
        self.income_timer = float(self.stats.get("income_interval", 0.0))
        self.target: Zombie | None = None
        self.focus_target: Zombie | None = None
        self.focus_time = 0.0

    @property
    def stats(self) -> dict[str, object]:
        return self._stats

    @property
    def lobby_multiplier(self) -> float:
        return UPGRADE_STAT_MULTIPLIER ** (self.lobby_level - 1)

    @property
    def attack_range(self) -> float:
        return float(self.stats["range"]) * self.lobby_multiplier + (self.level - 1) * 20

    @property
    def damage(self) -> int:
        damage = (
            int(self.stats["damage"])
            * self.lobby_multiplier
            * (1.35 ** (self.level - 1))
        )
        if "empower" in self.stats["abilities"]:
            damage *= self.focus_multiplier
        if self.trait is not None:
            damage *= float(self.trait["damage_multiplier"])
        return round(damage)

    @property
    def focus_multiplier(self) -> float:
        return min(5.0, 1.0 + self.focus_time / 10.0)

    @property
    def fire_rate(self) -> float:
        fire_rate = (
            float(self.stats["fire_rate"])
            / self.lobby_multiplier
            * (0.88 ** (self.level - 1))
        )
        if "accelerate" in self.stats["abilities"]:
            fire_rate /= self.focus_multiplier
        if self.trait is not None:
            fire_rate /= float(self.trait["attack_speed_multiplier"])
        return fire_rate

    def update(self, delta_time: float, zombies: list[Zombie]) -> Projectile | None:
        self.cooldown = max(0.0, self.cooldown - delta_time)
        stats = self.stats
        if "income" in stats["abilities"] and float(stats["range"]) <= 0:
            return None

        range_squared = self.attack_range**2
        target = None
        for zombie in zombies:
            dx = zombie.x - self.x
            dy = zombie.y - self.y
            if (
                not zombie.reached_base
                and zombie.health > 0
                and dx * dx + dy * dy <= range_squared
                and (target is None or zombie.segment > target.segment)
            ):
                target = zombie
        self.target = target
        if self.target is None:
            self.focus_target = None
            self.focus_time = 0.0
        elif self.target is self.focus_target:
            self.focus_time += delta_time
        else:
            self.focus_target = self.target
            self.focus_time = 0.0
        if self.target is not None and self.cooldown == 0:
            self.cooldown = self.fire_rate
            return Projectile(
                self.x,
                self.y,
                self.target,
                self.damage,
                self.tower_type,
                self.lobby_multiplier * (1.35 ** (self.level - 1)),
            )
        return None

    def collect_income(self, delta_time: float) -> int:
        stats = self.stats
        if "income" not in stats["abilities"]:
            return 0

        self.income_timer -= delta_time
        interval = float(stats["income_interval"])
        income_per_tick = round(
            int(stats["income"])
            * self.lobby_multiplier
            * self.level
        )
        payout_count = 0
        if self.income_timer <= 0:
            payout_count = int(-self.income_timer // interval) + 1
            self.income_timer += payout_count * interval
        return payout_count * income_per_tick

    def draw(self, surface: pygame.Surface, show_range: bool = False) -> None:
        center = (round(self.x), round(self.y))
        stats = self.stats
        tower_color = stats["color"]
        if show_range:
            radius = round(self.attack_range)
            draw_circle_overlay(surface, center, radius, tower_color, 28)
            pygame.draw.circle(surface, tower_color, center, radius, 1)

        shadow_center = (center[0] + 6, center[1] + 12)
        pygame.draw.ellipse(surface, (18, 25, 31), (shadow_center[0] - 20, shadow_center[1] - 8, 40, 18))
        pygame.draw.circle(surface, (30, 62, 78), center, 19)
        pygame.draw.circle(surface, tower_color, center, 15)
        highlight = tuple(min(255, channel + 28) for channel in tower_color)
        pygame.draw.circle(surface, highlight, (center[0] - 4, center[1] - 4), 7)
        icon = _rendered_text(str(stats["icon"]), 20, WHITE)
        surface.blit(icon, icon.get_rect(center=center))
        if self.level > 1:
            level_label = _rendered_text(str(self.level), 17, WHITE)
            surface.blit(level_label, (center[0] + 11, center[1] + 8))


class Projectile:
    """A small projectile that travels toward its target."""

    def __init__(
        self,
        x: float,
        y: float,
        target: Zombie,
        damage: int,
        tower_type: int = 0,
        ability_multiplier: float = 1.0,
    ) -> None:
        self.x = x
        self.y = y
        self.target = target
        self.damage = damage
        self.tower_type = tower_type
        self.stats = unit_stats(tower_type)
        self.ability_multiplier = ability_multiplier
        self.start_x = x
        self.start_y = y
        self.active = True

    def update(self, delta_time: float, zombies: list[Zombie] | None = None) -> bool:
        if self.target.health <= 0 or self.target.reached_base:
            target = None
            nearest_distance_squared = math.inf
            for zombie in zombies or ():
                if zombie.health <= 0 or zombie.reached_base:
                    continue
                dx = zombie.x - self.x
                dy = zombie.y - self.y
                distance_squared = dx * dx + dy * dy
                if distance_squared < nearest_distance_squared:
                    nearest_distance_squared = distance_squared
                    target = zombie
            if target is None:
                self.active = False
                return False
            self.target = target

        tower_stats = self.stats
        dx = self.target.x - self.x
        dy = self.target.y - self.y
        distance = math.hypot(dx, dy)
        travel = (
            float(tower_stats.get("projectile_speed", PROJECTILE_SPEED))
            * self.ability_multiplier
            * delta_time
        )
        impact_distance = travel + self.target.radius
        if dx * dx + dy * dy <= impact_distance * impact_distance:
            impact_x = self.target.x
            impact_y = self.target.y
            affected = [self.target]
            abilities = tower_stats["abilities"]
            splash_radius = float(tower_stats.get("splash_radius", 0)) * self.ability_multiplier
            if "splash" in abilities and splash_radius and zombies is not None:
                splash_radius_squared = splash_radius * splash_radius
                affected = [
                    zombie
                    for zombie in zombies
                    if zombie.health > 0
                    and not zombie.reached_base
                    and (zombie.x - impact_x) ** 2 + (zombie.y - impact_y) ** 2
                    <= splash_radius_squared
                ]
            if "pierce" in abilities and zombies is not None:
                line_x = impact_x - self.start_x
                line_y = impact_y - self.start_y
                line_length_squared = line_x * line_x + line_y * line_y
                if line_length_squared:
                    candidates: list[tuple[float, Zombie]] = []
                    pierce_width = float(tower_stats.get("pierce_width", 18))
                    pierce_width_squared = pierce_width * pierce_width
                    for zombie in zombies:
                        if zombie.health <= 0 or zombie.reached_base:
                            continue
                        progress = (
                            (zombie.x - self.start_x) * line_x
                            + (zombie.y - self.start_y) * line_y
                        ) / line_length_squared
                        if not 0 <= progress <= 1:
                            continue
                        closest_x = self.start_x + progress * line_x
                        closest_y = self.start_y + progress * line_y
                        if (
                            (zombie.x - closest_x) ** 2 + (zombie.y - closest_y) ** 2
                            <= pierce_width_squared
                        ):
                            candidates.append((progress, zombie))
                    candidates.sort(key=lambda candidate: candidate[0])
                    hit_ids = {id(zombie) for zombie in affected}
                    hit_limit = int(tower_stats.get("pierce_targets", 3))
                    for _, zombie in candidates:
                        if id(zombie) in hit_ids:
                            continue
                        affected.append(zombie)
                        hit_ids.add(id(zombie))
                        if len(hit_ids) >= hit_limit:
                            break

            if "chain" in abilities and zombies is not None:
                chain_radius = float(tower_stats["chain_radius"]) * self.ability_multiplier
                chain_targets = int(tower_stats["chain_targets"])
                last_target = self.target
                hit_ids = {id(zombie) for zombie in affected}
                chain_radius_squared = chain_radius * chain_radius
                while len(affected) < chain_targets:
                    next_target = None
                    nearest_distance_squared = chain_radius_squared
                    for zombie in zombies:
                        if (
                            zombie.health <= 0
                            or zombie.reached_base
                            or id(zombie) in hit_ids
                        ):
                            continue
                        dx = zombie.x - last_target.x
                        dy = zombie.y - last_target.y
                        distance_squared = dx * dx + dy * dy
                        if distance_squared <= nearest_distance_squared:
                            if (
                                distance_squared < nearest_distance_squared
                                or next_target is None
                            ):
                                nearest_distance_squared = distance_squared
                                next_target = zombie
                    if next_target is None:
                        break
                    last_target = next_target
                    affected.append(last_target)
                    hit_ids.add(id(last_target))

            for hit_index, zombie in enumerate(affected):
                damage = self.damage
                if "chain" in abilities and hit_index > 0:
                    damage = round(
                        damage
                        * float(tower_stats["chain_damage_factor"]) ** hit_index
                    )
                if (
                    "execute" in abilities
                    and zombie.health / zombie.max_health
                    <= float(tower_stats["execute_threshold"])
                ):
                    damage = round(damage * float(tower_stats["execute_multiplier"]))
                zombie.health -= damage
                if "burn" in abilities:
                    zombie.apply_burn(
                        float(tower_stats["burn_dps"]) * self.ability_multiplier,
                        float(tower_stats["burn_duration"]) * self.ability_multiplier,
                    )
                if "stacking_burn" in abilities:
                    burn_duration = float(tower_stats["burn_duration"])
                    zombie.apply_burn(
                        self.damage
                        * float(tower_stats["burn_fraction"])
                        / burn_duration,
                        burn_duration,
                        stack=True,
                        spread=True,
                    )
                if "slow" in abilities:
                    zombie.apply_slow(
                        max(0.1, float(tower_stats["slow_factor"]) / self.ability_multiplier),
                        float(tower_stats["slow_duration"]) * self.ability_multiplier,
                    )
                if "poison" in abilities:
                    zombie.apply_poison(
                        float(tower_stats["poison_dps"]) * self.ability_multiplier,
                        float(tower_stats["poison_duration"]) * self.ability_multiplier,
                    )
                if "bleed" in abilities:
                    zombie.apply_bleed(
                        float(tower_stats["bleed_dps"]) * self.ability_multiplier,
                        float(tower_stats["bleed_duration"]) * self.ability_multiplier,
                    )
            self.active = False
            return True

        self.x += dx / distance * travel
        self.y += dy / distance * travel
        return False

    def draw(self, surface: pygame.Surface) -> None:
        center = (round(self.x), round(self.y))
        pygame.draw.ellipse(surface, (18, 25, 31), (center[0] - 7, center[1] + 5, 16, 7))
        pygame.draw.circle(surface, GOLD_COLOR, center, 5)
        pygame.draw.circle(surface, WHITE, center, 2)
