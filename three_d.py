"""Panda3D presentation layer for the existing tower-defense simulation."""

from __future__ import annotations

import math
import random
from typing import Any

import pygame
from direct.gui.OnscreenText import OnscreenText
from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    AmbientLight,
    DirectionalLight,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    LPoint3,
    NodePath,
    LVector3,
    Point2,
    Point3,
    TextNode,
    Texture,
    TransparencyAttrib,
    Vec4,
    loadPrcFileData,
)

from entities import ENEMY_ARCHETYPES
from progression import unit_stats
from settings import (
    LOBBY_STATION_RECTS,
    LOBBY_MOVE_SPEED,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TOWER_BAR_TOP,
)


WORLD_SCALE = 0.025
GROUND_Z = 0.0
KEY_CODES = {
    **{letter: getattr(pygame, f"K_{letter}") for letter in "abcdefghijklmnopqrstuvwxyz"},
    **{digit: getattr(pygame, f"K_{digit}") for digit in "0123456789"},
    "space": pygame.K_SPACE,
    "enter": pygame.K_RETURN,
    "escape": pygame.K_ESCAPE,
    "tab": pygame.K_TAB,
    "backspace": pygame.K_BACKSPACE,
}

STATION_LABELS = {
    "summon": "SUMMON",
    "traits": "TRAIT ALTAR",
    "battle_pass": "BATTLE PASS",
    "crates": "CRATE DEPOT",
    "collection": "COLLECTION",
    "start": "DEPLOY",
    "daily": "DAILY PORTAL",
    "story": "STORY PORTAL",
    "admin": "ADMIN",
}

STATION_COLORS = {
    "summon": (0.25, 0.72, 0.95),
    "traits": (0.96, 0.74, 0.24),
    "battle_pass": (0.62, 0.48, 0.86),
    "crates": (0.47, 0.66, 0.35),
    "collection": (0.31, 0.65, 0.78),
    "start": (0.24, 0.82, 0.57),
    "daily": (0.35, 0.55, 0.83),
    "story": (0.36, 0.75, 0.58),
    "admin": (0.78, 0.64, 0.35),
}


def _world_point(screen_x: float, screen_y: float, height: float = 0.0) -> tuple[float, float, float]:
    return (
        (screen_x - SCREEN_WIDTH / 2) * WORLD_SCALE,
        (SCREEN_HEIGHT / 2 - screen_y) * WORLD_SCALE,
        height,
    )


def _rgb(value: tuple[int, int, int] | tuple[float, float, float]) -> Vec4:
    if max(value) > 1:
        return Vec4(*(channel / 255 for channel in value), 1)
    return Vec4(*value, 1)


class ThreeDGameView(ShowBase):
    """Render the hub and combat field in 3D while retaining game.py rules."""

    def __init__(self, game: Any) -> None:
        loadPrcFileData("", "window-title Last Stand - 3D Tower Defense")
        loadPrcFileData("", f"win-size {SCREEN_WIDTH} {SCREEN_HEIGHT}")
        loadPrcFileData("", "sync-video 1")
        loadPrcFileData("", "show-frame-rate-meter 0")
        super().__init__()
        self.game = game
        self.disableMouse()
        self.setBackgroundColor(0.32, 0.53, 0.68, 1)
        self.camLens.setFov(52)
        self.camLens.setNearFar(0.1, 180)

        self._setup_lighting()
        self.game_root = self.render.attachNewNode("game-world")
        self.station_nodes: dict[str, Any] = {}
        self.station_labels: dict[str, Any] = {}
        self.defender_nodes: dict[int, Any] = {}
        self.zombie_nodes: dict[int, Any] = {}
        self.projectile_nodes: dict[int, Any] = {}
        self.player_node: Any | None = None
        self.player_limbs: list[Any] = []
        self.range_node: Any | None = None
        self.placement_node: Any | None = None
        self.world_mode: str | None = None
        self.world_map: str | None = None
        self._camera_initialized = False
        self._camera_yaw = 0.0
        self._camera_pitch = math.degrees(math.atan2(29, 27))
        self._camera_dragging = False
        self._last_camera_pointer: tuple[float, float] | None = None
        self._walk_time = 0.0
        self._cursor_world: tuple[float, float] | None = None
        self._model_prototypes: dict[str, Any] = {}
        self._range_signature: tuple[int, float, float, float] | None = None

        self.overlay_texture = Texture("game-ui")
        self.overlay_texture.setup2dTexture(
            SCREEN_WIDTH,
            SCREEN_HEIGHT,
            Texture.T_unsigned_byte,
            Texture.F_rgba8,
        )
        self.overlay_texture.setMinfilter(Texture.FT_linear)
        self.overlay_texture.setMagfilter(Texture.FT_linear)
        self.overlay_card = self._make_overlay_card()
        self.hub_header = OnscreenText(
            text="LAST STAND  |  3D HUB",
            pos=(-1.28, 0.92),
            scale=0.052,
            align=TextNode.ALeft,
            fg=(0.96, 0.84, 0.55, 1),
            shadow=(0, 0, 0, 0.7),
            parent=self.aspect2d,
        )
        self.hub_footer = OnscreenText(
            text="",
            pos=(-1.28, -0.91),
            scale=0.038,
            align=TextNode.ALeft,
            fg=(0.94, 0.95, 0.88, 1),
            shadow=(0, 0, 0, 0.8),
            parent=self.aspect2d,
        )
        self.hub_status = OnscreenText(
            text="",
            pos=(0, 0.82),
            scale=0.043,
            align=TextNode.ACenter,
            fg=(0.96, 0.84, 0.55, 1),
            shadow=(0, 0, 0, 0.8),
            parent=self.aspect2d,
        )

        self._bind_input()
        self.accept("window-event", self._window_event)
        self.taskMgr.add(self._tick, "last-stand-update")
        self._build_world("hub")

    def _setup_lighting(self) -> None:
        ambient = AmbientLight("ambient")
        ambient.setColor(Vec4(0.56, 0.60, 0.66, 1))
        self.render.setLight(self.render.attachNewNode(ambient))

        sunlight = DirectionalLight("sunlight")
        sunlight.setColor(Vec4(0.96, 0.89, 0.72, 1))
        sunlight.setDirection(LVector3(-1, -2, -3))
        self.render.setLight(self.render.attachNewNode(sunlight))

    def _make_overlay_card(self) -> Any:
        from panda3d.core import CardMaker

        maker = CardMaker("game-ui-overlay")
        maker.setFrame(-self.getAspectRatio(), self.getAspectRatio(), -1, 1)
        card = self.render2d.attachNewNode(maker.generate())
        card.setTexture(self.overlay_texture)
        card.setTransparency(TransparencyAttrib.MAlpha)
        card.setDepthTest(False)
        card.setDepthWrite(False)
        card.setBin("fixed", 100)
        return card

    def _bind_input(self) -> None:
        for key_name, pygame_key in KEY_CODES.items():
            self.accept(key_name, self._key_down, [pygame_key, key_name])
            self.accept(f"{key_name}-up", self._key_up, [pygame_key])
        self.accept("mouse1", self._mouse_down, [1])
        self.accept("mouse3", self._mouse_down, [3])
        self.accept("mouse3-up", self._mouse_up, [3])
        self.accept("wheel_up", self._wheel, [1])
        self.accept("wheel_down", self._wheel, [-1])

    def _key_down(self, key: int, key_name: str) -> None:
        self.game.held_keys.add(key)
        character = key_name if len(key_name) == 1 else ""
        event = pygame.event.Event(
            pygame.KEYDOWN,
            key=key,
            unicode=character,
            mod=pygame.key.get_mods(),
        )
        pygame.event.post(event)

    def _key_up(self, key: int) -> None:
        self.game.held_keys.discard(key)
        pygame.event.post(pygame.event.Event(pygame.KEYUP, key=key))

    def _mouse_down(self, button: int) -> None:
        if button == 3:
            if self.game.screen_state == "lobby":
                world_point = self._ground_point_from_mouse()
                if world_point is not None:
                    screen_x = world_point[0] / WORLD_SCALE + SCREEN_WIDTH / 2
                    screen_y = SCREEN_HEIGHT / 2 - world_point[1] / WORLD_SCALE
                    self.game.face_lobby_player_toward(screen_x, screen_y)
            elif self.game.screen_state in ("playing", "preparation"):
                self._camera_dragging = True
                self._last_camera_pointer = self._pointer_position()
            return
        if self.game.screen_state == "lobby":
            return
        self.game.ui_mouse_position = self._screen_mouse_position()
        position = self._pointer_game_position()
        self.game.mouse_position = position
        pygame.event.post(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                button=button,
                pos=position,
            )
        )

    def _mouse_up(self, button: int) -> None:
        if button == 3:
            self._camera_dragging = False
            self._last_camera_pointer = None

    def _wheel(self, direction: int) -> None:
        pygame.event.post(
            pygame.event.Event(
                pygame.MOUSEWHEEL,
                x=0,
                y=direction,
                flipped=False,
            )
        )

    def _window_event(self, window: Any) -> None:
        if not window.getProperties().getOpen():
            self.userExit()

    def _pointer_position(self) -> tuple[float, float] | None:
        if self.mouseWatcherNode is None or not self.mouseWatcherNode.hasMouse():
            return None
        pointer = self.mouseWatcherNode.getMouse()
        return pointer.getX(), pointer.getY()

    def _screen_mouse_position(self) -> tuple[int, int]:
        pointer = self._pointer_position()
        if pointer is None:
            return self.game.mouse_position
        x = round((pointer[0] + 1) * SCREEN_WIDTH / 2)
        y = round((1 - pointer[1]) * SCREEN_HEIGHT / 2)
        return (
            max(0, min(SCREEN_WIDTH - 1, x)),
            max(0, min(SCREEN_HEIGHT - 1, y)),
        )

    def _ground_point_from_mouse(self) -> tuple[float, float] | None:
        pointer = self._pointer_position()
        if pointer is None:
            return None
        near = Point3()
        far = Point3()
        if not self.camLens.extrude(Point2(*pointer), near, far):
            return None
        near_world = self.render.getRelativePoint(self.camera, near)
        far_world = self.render.getRelativePoint(self.camera, far)
        direction = far_world - near_world
        if abs(direction.getZ()) < 1e-6:
            return None
        progress = (GROUND_Z - near_world.getZ()) / direction.getZ()
        if progress < 0:
            return None
        point = near_world + direction * progress
        return point.getX(), point.getY()

    def _pointer_game_position(self) -> tuple[int, int]:
        screen_position = self._screen_mouse_position()
        if (
            self.game.screen_state in ("playing", "preparation")
            and 76 <= screen_position[1] < TOWER_BAR_TOP
        ):
            world_point = self._ground_point_from_mouse()
            if world_point is not None:
                return (
                    round(world_point[0] / WORLD_SCALE + SCREEN_WIDTH / 2),
                    round(SCREEN_HEIGHT / 2 - world_point[1] / WORLD_SCALE),
                )
        return screen_position

    def _tick(self, task: Any) -> int:
        delta_time = min(max(task.dt, 0.0), 0.05)
        self.game.ui_mouse_position = self._screen_mouse_position()
        self.game.mouse_position = self._pointer_game_position()
        running = self.game.step_frame(delta_time)
        if not running:
            self.userExit()
            return task.done

        mode = "hub" if self.game.screen_state in ("lobby", "setup") else "battlefield"
        map_key = self.game.selected_map if mode == "battlefield" else None
        if mode != self.world_mode or map_key != self.world_map:
            self._build_world(mode)
        if mode == "hub":
            self._update_player(delta_time)
            if self.game.screen_state == "lobby":
                self._update_hub_hud()
                self.overlay_card.hide()
                self.hub_header.show()
                self.hub_footer.show()
                self.hub_status.show()
            else:
                self.hub_footer.hide()
                self.hub_status.hide()
                self._upload_overlay(self.game.frame_surface)
                self.overlay_card.show()
        else:
            self.hub_header.hide()
            self.hub_footer.hide()
            self.hub_status.hide()
            self._sync_battlefield()
            self._update_camera(delta_time)
            self._upload_overlay(self.game.frame_surface)
            self.overlay_card.show()
        return task.cont

    def _upload_overlay(self, surface: pygame.Surface) -> None:
        self.overlay_texture.setRamImage(pygame.image.tostring(surface, "RGBA", True))

    def _make_box(
        self,
        parent: Any,
        name: str,
        position: tuple[float, float, float],
        scale: tuple[float, float, float],
        color: tuple[int, int, int] | tuple[float, float, float],
        model_name: str = "models/misc/rgbCube",
    ) -> Any:
        prototype = self._model_prototypes.get(model_name)
        if prototype is None:
            prototype = (
                self._create_cylinder_model(name)
                if model_name == "models/misc/cylinder"
                else self.loader.loadModel(model_name)
            )
            self._model_prototypes[model_name] = prototype
        node = prototype.copyTo(parent)
        node.setName(name)
        node.setPos(*position)
        if model_name == "models/misc/rgbCube":
            node.setScale(*(dimension * 2 for dimension in scale))
        else:
            node.setScale(*scale)
        node.setColor(_rgb(color))
        return node

    @staticmethod
    def _create_cylinder_model(name: str, segments: int = 16) -> Any:
        vertex_data = GeomVertexData(
            name,
            GeomVertexFormat.getV3n3c4(),
            Geom.UHStatic,
        )
        vertices = GeomVertexWriter(vertex_data, "vertex")
        normals = GeomVertexWriter(vertex_data, "normal")
        colors = GeomVertexWriter(vertex_data, "color")
        triangles = GeomTriangles(Geom.UHStatic)

        def add_vertex(position: tuple[float, float, float], normal: tuple[float, float, float]) -> int:
            index = vertices.getWriteRow()
            vertices.addData3(*position)
            normals.addData3(*normal)
            colors.addData4(1, 1, 1, 1)
            return index

        for index in range(segments):
            first_angle = math.tau * index / segments
            second_angle = math.tau * (index + 1) / segments
            first = (math.cos(first_angle), math.sin(first_angle))
            second = (math.cos(second_angle), math.sin(second_angle))
            a = add_vertex((first[0], first[1], -1), (first[0], first[1], 0))
            b = add_vertex((second[0], second[1], -1), (second[0], second[1], 0))
            c = add_vertex((second[0], second[1], 1), (second[0], second[1], 0))
            d = add_vertex((first[0], first[1], 1), (first[0], first[1], 0))
            triangles.addVertices(a, b, c)
            triangles.addVertices(a, c, d)

            bottom_center = add_vertex((0, 0, -1), (0, 0, -1))
            bottom_first = add_vertex((first[0], first[1], -1), (0, 0, -1))
            bottom_second = add_vertex((second[0], second[1], -1), (0, 0, -1))
            triangles.addVertices(bottom_center, bottom_second, bottom_first)
            top_center = add_vertex((0, 0, 1), (0, 0, 1))
            top_first = add_vertex((first[0], first[1], 1), (0, 0, 1))
            top_second = add_vertex((second[0], second[1], 1), (0, 0, 1))
            triangles.addVertices(top_center, top_first, top_second)

        geometry = Geom(vertex_data)
        geometry.addPrimitive(triangles)
        geom_node = GeomNode(name)
        geom_node.addGeom(geometry)
        return NodePath(geom_node)

    def _make_label(
        self,
        parent: Any,
        text: str,
        position: tuple[float, float, float],
        color: tuple[float, float, float],
    ) -> Any:
        node = TextNode(f"label-{text.lower().replace(' ', '-')}")
        node.setText(text)
        node.setAlign(TextNode.ACenter)
        node.setTextColor(*color, 1)
        label = parent.attachNewNode(node)
        label.setPos(*position)
        label.setScale(0.24)
        label.setBillboardPointEye()
        return label

    def _build_world(self, mode: str) -> None:
        previous_mode = self.world_mode
        self.game_root.removeNode()
        self.game_root = self.render.attachNewNode(f"{mode}-world")
        self.station_nodes.clear()
        self.station_labels.clear()
        self.defender_nodes.clear()
        self.zombie_nodes.clear()
        self.projectile_nodes.clear()
        self.player_node = None
        self.player_limbs.clear()
        self.range_node = None
        self.placement_node = None
        self.world_mode = mode
        self.world_map = self.game.selected_map if mode == "battlefield" else None
        self._camera_initialized = False
        if mode == "battlefield" and previous_mode != "battlefield":
            self._camera_yaw = 0.0
            self._camera_pitch = math.degrees(math.atan2(29, 27))
        self._camera_dragging = False
        self._last_camera_pointer = None

        self._make_box(
            self.game_root,
            "grassland",
            (0, 0, -0.3),
            (17, 12, 0.3),
            (59, 113, 78) if mode == "hub" else (55, 112, 67),
        )
        self._add_ground_details(mode)
        if mode == "hub":
            self._build_hub()
        else:
            self._build_battlefield()

    def _add_ground_details(self, mode: str) -> None:
        rng = random.Random(f"last-stand-{mode}-{self.game.selected_map}")
        for index in range(42 if mode == "hub" else 28):
            x = rng.uniform(-15.5, 15.5)
            y = rng.uniform(-10.5, 10.5)
            if mode == "battlefield" and self._near_path(x, y, 1.0):
                continue
            height = rng.uniform(0.04, 0.12)
            self._make_box(
                self.game_root,
                f"grass-detail-{index}",
                (x, y, 0.01),
                (rng.uniform(0.10, 0.28), rng.uniform(0.08, 0.18), height),
                rng.choice(((78, 135, 80), (88, 143, 86), (48, 101, 69))),
            )

        for index in range(14):
            side = rng.choice(("west", "east", "north", "south"))
            if side in ("west", "east"):
                x = rng.choice((-14.6, 14.6))
                y = rng.uniform(-9.0, 9.0)
            else:
                x = rng.uniform(-14.6, 14.6)
                y = rng.choice((-9.4, 9.4))
            if mode == "battlefield" and self._near_path(x, y, 1.8):
                continue
            self._make_box(
                self.game_root,
                f"tree-trunk-{index}",
                (x, y, 0.9),
                (0.18, 0.18, 0.9),
                (91, 67, 45),
                "models/misc/cylinder",
            )
            self._make_box(
                self.game_root,
                f"tree-crown-{index}",
                (x, y, 2.0),
                (0.9, 0.9, 1.0),
                rng.choice(((48, 105, 61), (57, 123, 70), (72, 131, 74))),
                "models/misc/sphere",
            )

        for index, (x, y) in enumerate(
            (
                (-15.0, -9.0),
                (-14.0, 8.5),
                (14.2, -8.7),
                (15.0, 7.8),
                (-10.0, 10.5),
                (10.4, 10.0),
            )
        ):
            self._make_box(
                self.game_root,
                f"stone-{index}",
                (x, y, 0.5),
                (0.7, 0.55, 0.6),
                (90, 101, 92),
                "models/misc/sphere",
            )

    def _near_path(self, world_x: float, world_y: float, distance: float) -> bool:
        path = self.game.path_points
        px = world_x / WORLD_SCALE + SCREEN_WIDTH / 2
        py = SCREEN_HEIGHT / 2 - world_y / WORLD_SCALE
        limit = distance / WORLD_SCALE
        for start, end in zip(path, path[1:]):
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            length_squared = dx * dx + dy * dy
            progress = max(
                0.0,
                min(1.0, ((px - start[0]) * dx + (py - start[1]) * dy) / length_squared),
            )
            closest_x = start[0] + progress * dx
            closest_y = start[1] + progress * dy
            if (px - closest_x) ** 2 + (py - closest_y) ** 2 <= limit**2:
                return True
        return False

    def _build_hub(self) -> None:
        self._make_box(
            self.game_root,
            "hub-central-platform",
            (0, 0, 0.02),
            (5.0, 3.8, 0.16),
            (57, 91, 83),
        )
        self._make_box(
            self.game_root,
            "hub-center-emblem",
            (0, 0, 0.2),
            (0.75, 0.75, 0.08),
            (226, 190, 92),
            "models/misc/cylinder",
        )

        for name, rect in LOBBY_STATION_RECTS.items():
            x, y, width, depth = rect
            wx, wy, _ = _world_point(x + width / 2, y + depth / 2)
            color = STATION_COLORS[name]
            angle = math.degrees(math.atan2(wy, wx))
            distance = math.hypot(wx, wy)
            walkway = self._make_box(
                self.game_root,
                f"hub-walkway-{name}",
                (wx / 2, wy / 2, 0.11),
                (distance / 2, 0.30, 0.08),
                (111, 121, 105),
            )
            walkway.setH(angle)
            platform = self._make_box(
                self.game_root,
                f"station-{name}",
                (wx, wy, 0.16),
                (width * WORLD_SCALE / 2, depth * WORLD_SCALE / 2, 0.18),
                tuple(channel * 0.72 for channel in color),
            )
            self.station_nodes[name] = platform
            self._make_station_prop(name, wx, wy, color)
            self.station_labels[name] = self._make_label(
                self.game_root,
                STATION_LABELS[name],
                (wx, wy, 2.45),
                (0.98, 0.96, 0.84),
            )

        self._build_player()
        self._build_hub_landmarks()

    def _make_station_prop(
        self,
        name: str,
        x: float,
        y: float,
        color: tuple[float, float, float],
    ) -> None:
        tint = tuple(channel * 255 for channel in color)
        if name == "summon":
            self._make_box(self.game_root, "summon-podium", (x, y, 0.72), (0.62, 0.62, 0.52), (61, 70, 77), "models/misc/cylinder")
            self._make_box(self.game_root, "summon-crystal", (x, y, 1.62), (0.34, 0.34, 0.42), tint, "models/misc/sphere")
        elif name == "traits":
            for index in range(3):
                self._make_box(self.game_root, f"trait-rune-{index}", (x, y, 0.7 + index * 0.18), (0.75 - index * 0.12, 0.75 - index * 0.12, 0.07), tint, "models/misc/cylinder")
            self._make_box(self.game_root, "trait-flame", (x, y, 1.55), (0.24, 0.24, 0.44), (255, 195, 79), "models/misc/sphere")
        elif name == "battle_pass":
            self._make_box(self.game_root, "pass-board-frame", (x, y, 1.0), (0.72, 0.12, 0.82), (112, 91, 143))
            self._make_box(self.game_root, "pass-board-face", (x, y - 0.15, 1.02), (0.56, 0.06, 0.66), tint)
            for row in range(3):
                self._make_box(self.game_root, f"pass-mark-{row}", (x - 0.27 + row * 0.25, y - 0.23, 1.1), (0.05, 0.025, 0.08), (255, 220, 111))
        elif name == "crates":
            for index, offset in enumerate((-0.45, 0.0, 0.45)):
                crate = self._make_box(self.game_root, f"crate-{index}", (x + offset, y, 0.65), (0.27, 0.27, 0.25), (132, 95, 55))
                self._make_box(self.game_root, f"crate-lid-{index}", (x + offset, y, 1.16), (0.28, 0.28, 0.08), tint)
                self._make_box(self.game_root, f"crate-band-{index}", (x + offset, y - 0.28, 0.66), (0.04, 0.02, 0.25), (223, 194, 110))
        elif name == "collection":
            for row in range(3):
                shelf_z = 0.72 + row * 0.4
                self._make_box(self.game_root, f"unit-shelf-{row}", (x, y, shelf_z), (0.86, 0.18, 0.06), (107, 83, 61))
                for col in range(4):
                    self._make_box(self.game_root, f"unit-display-{row}-{col}", (x - 0.58 + col * 0.38, y - 0.04, shelf_z + 0.22), (0.10, 0.09, 0.13), tint, "models/misc/sphere")
        elif name == "start":
            for side in (-1, 1):
                self._make_box(self.game_root, f"deploy-pillar-{side}", (x + side * 0.72, y, 1.02), (0.20, 0.20, 0.86), tint, "models/misc/cylinder")
            self._make_box(self.game_root, "deploy-arch", (x, y, 1.9), (0.92, 0.18, 0.12), tint)
            self._make_box(self.game_root, "deploy-core", (x, y, 1.2), (0.35, 0.14, 0.38), (140, 220, 231), "models/misc/sphere")
        elif name in ("daily", "story"):
            for side in (-1, 1):
                self._make_box(self.game_root, f"{name}-portal-post-{side}", (x + side * 0.48, y, 1.0), (0.12, 0.14, 0.78), tint, "models/misc/cylinder")
            self._make_box(self.game_root, f"{name}-portal-top", (x, y, 1.78), (0.58, 0.15, 0.12), tint)
            self._make_box(self.game_root, f"{name}-portal-core", (x, y, 0.82), (0.36, 0.10, 0.45), (116, 196, 218), "models/misc/sphere")
        else:
            self._make_box(self.game_root, "admin-terminal", (x, y, 0.78), (0.42, 0.34, 0.55), (76, 80, 77))
            self._make_box(self.game_root, "admin-screen", (x, y - 0.34, 1.15), (0.35, 0.06, 0.22), tint)
            self._make_box(self.game_root, "admin-keyboard", (x, y - 0.45, 0.63), (0.34, 0.12, 0.05), (161, 168, 155))

    def _build_player(self) -> None:
        player = self.game_root.attachNewNode("player-character")
        self._make_box(player, "player-torso", (0, 0, 1.0), (0.30, 0.22, 0.40), (58, 149, 196))
        self._make_box(player, "player-head", (0, 0, 1.62), (0.25, 0.25, 0.25), (222, 181, 139), "models/misc/sphere")
        self._make_box(player, "player-hair", (0, 0.02, 1.78), (0.25, 0.24, 0.10), (57, 45, 44), "models/misc/sphere")
        self._make_box(player, "player-arm-left", (-0.38, 0, 1.08), (0.10, 0.14, 0.34), (222, 181, 139))
        self._make_box(player, "player-arm-right", (0.38, 0, 1.08), (0.10, 0.14, 0.34), (222, 181, 139))
        left_leg = self._make_box(player, "player-leg-left", (-0.15, 0, 0.30), (0.13, 0.15, 0.30), (47, 63, 84))
        right_leg = self._make_box(player, "player-leg-right", (0.15, 0, 0.30), (0.13, 0.15, 0.30), (47, 63, 84))
        self.player_limbs = [left_leg, right_leg]
        self.player_node = player

    def _build_hub_landmarks(self) -> None:
        for x, y, index in ((-13, -7, 0), (13, 7, 1), (-12, 8, 2), (12, -8, 3)):
            self._make_box(self.game_root, f"hub-pillar-{index}", (x, y, 1.35), (0.30, 0.30, 1.3), (75, 95, 96), "models/misc/cylinder")
            self._make_box(self.game_root, f"hub-light-{index}", (x, y, 2.8), (0.20, 0.20, 0.20), (123, 225, 233), "models/misc/sphere")

    def _build_battlefield(self) -> None:
        self._make_box(self.game_root, "battlefield-border", (0, 0, -0.12), (15.8, 10.8, 0.12), (48, 78, 59))
        for index, (start, end) in enumerate(zip(self.game.path_points, self.game.path_points[1:])):
            x1, y1, _ = _world_point(*start)
            x2, y2, _ = _world_point(*end)
            dx, dy = x2 - x1, y2 - y1
            length = math.hypot(dx, dy)
            angle = math.degrees(math.atan2(dy, dx))
            road = self._make_box(
                self.game_root,
                f"road-segment-{index}",
                ((x1 + x2) / 2, (y1 + y2) / 2, 0.08),
                (length / 2, 0.72, 0.08),
                (152, 126, 91),
            )
            road.setH(angle)
            edge = self._make_box(
                self.game_root,
                f"road-highlight-{index}",
                ((x1 + x2) / 2, (y1 + y2) / 2, 0.17),
                (length / 2, 0.045, 0.025),
                (208, 184, 142),
            )
            edge.setH(angle)

        start_x, start_y, _ = _world_point(*self.game.path_points[0])
        end_x, end_y, _ = _world_point(*self.game.path_points[-1])
        self._make_box(self.game_root, "enemy-spawn", (start_x, start_y, 0.28), (0.68, 0.68, 0.26), (69, 108, 167), "models/misc/cylinder")
        self._make_box(self.game_root, "base-core", (end_x, end_y, 0.68), (0.76, 0.76, 0.62), (78, 173, 204), "models/misc/cylinder")
        self._make_box(self.game_root, "base-crystal", (end_x, end_y, 1.58), (0.38, 0.38, 0.52), (163, 232, 247), "models/misc/sphere")

    def _make_defender(self, defender: Any) -> Any:
        node = self.game_root.attachNewNode(f"defender-{id(defender)}")
        color = _rgb(tuple(defender.stats["color"]))
        self._make_box(node, "unit-base", (0, 0, 0.15), (0.36, 0.36, 0.13), (47, 68, 76), "models/misc/cylinder")
        self._make_box(node, "unit-body", (0, 0, 0.86), (0.23, 0.22, 0.44), tuple(defender.stats["color"]))
        self._make_box(node, "unit-head", (0, 0, 1.48), (0.20, 0.20, 0.20), (229, 198, 161), "models/misc/sphere")
        gun = self._make_box(node, "unit-weapon", (0.30, 0.12, 0.96), (0.34, 0.08, 0.09), tuple(defender.stats["color"]))
        gun.setH(-25)
        return node

    def _make_zombie(self, zombie: Any) -> tuple[Any, Any, Any]:
        node = self.game_root.attachNewNode(f"zombie-{id(zombie)}")
        archetype = ENEMY_ARCHETYPES[zombie.enemy_type]
        size = max(0.65, min(1.75, zombie.radius / 15))
        color = tuple(archetype["color"])
        self._make_box(node, "zombie-body", (0, 0, 0.72 * size), (0.25 * size, 0.22 * size, 0.43 * size), color, "models/misc/sphere")
        self._make_box(node, "zombie-head", (0, 0, 1.28 * size), (0.23 * size, 0.22 * size, 0.24 * size), color, "models/misc/sphere")
        for side in (-1, 1):
            arm = self._make_box(node, f"zombie-arm-{side}", (side * 0.31 * size, 0, 0.77 * size), (0.09 * size, 0.12 * size, 0.34 * size), color)
            arm.setH(side * 20)
            self._make_box(node, f"zombie-leg-{side}", (side * 0.12 * size, 0, 0.25 * size), (0.10 * size, 0.13 * size, 0.25 * size), (58, 72, 52))
        self._make_box(node, "health-bar-back", (0, 0, 1.86 * size), (0.35 * size, 0.06, 0.04), (85, 39, 38))
        health = self._make_box(node, "health-bar", (0, -0.07, 1.87 * size), (0.32 * size, 0.035, 0.025), (100, 208, 99))
        return node, health, size

    def _sync_battlefield(self) -> None:
        defenders = {id(entity): entity for entity in self.game.defenders}
        zombies = {id(entity): entity for entity in self.game.zombies if entity.health > 0}
        projectiles = {id(entity): entity for entity in self.game.projectiles if entity.active}
        self._prune_nodes(self.defender_nodes, defenders)
        self._prune_nodes(self.zombie_nodes, zombies)
        self._prune_nodes(self.projectile_nodes, projectiles)

        for entity_id, defender in defenders.items():
            node = self.defender_nodes.get(entity_id)
            if node is None:
                node = self._make_defender(defender)
                self.defender_nodes[entity_id] = node
            node.setPos(*_world_point(defender.x, defender.y))
            if defender.target is not None:
                dx = defender.target.x - defender.x
                dy = defender.target.y - defender.y
                node.setH(math.degrees(math.atan2(dy, dx)))
            node.setScale(1.0 + min(0.22, (defender.level - 1) * 0.055))

        for entity_id, zombie in zombies.items():
            entry = self.zombie_nodes.get(entity_id)
            if entry is None:
                entry = self._make_zombie(zombie)
                self.zombie_nodes[entity_id] = entry
            node, health_bar, size = entry
            node.setPos(*_world_point(zombie.x, zombie.y))
            ratio = max(0.02, min(1.0, zombie.health / zombie.max_health))
            health_bar.setSx(0.32 * size * ratio)
            health_bar.setX(-0.32 * size * (1 - ratio))
            if zombie.segment < len(zombie.path_segments):
                next_point = zombie.path[zombie.segment + 1]
                dx = next_point[0] - zombie.x
                dy = next_point[1] - zombie.y
                node.setH(math.degrees(math.atan2(dy, dx)))

        for entity_id, projectile in projectiles.items():
            node = self.projectile_nodes.get(entity_id)
            if node is None:
                node = self._make_box(
                    self.game_root,
                    f"projectile-{entity_id}",
                    (0, 0, 0),
                    (0.11, 0.11, 0.11),
                    tuple(projectile.stats["color"]),
                    "models/misc/sphere",
                )
                self.projectile_nodes[entity_id] = node
            node.setPos(*_world_point(projectile.x, projectile.y, 0.58))

        self._sync_range_ring()
        self._sync_placement_preview()

    @staticmethod
    def _prune_nodes(nodes: dict[int, Any], current: dict[int, Any]) -> None:
        for entity_id in tuple(nodes):
            if entity_id not in current:
                entry = nodes.pop(entity_id)
                node = entry[0] if isinstance(entry, tuple) else entry
                node.removeNode()

    def _sync_range_ring(self) -> None:
        selected = self.game.selected_defender
        if selected is None or selected not in self.game.defenders:
            if self.range_node is not None:
                self.range_node.removeNode()
                self.range_node = None
            self._range_signature = None
            return
        signature = (
            id(selected),
            selected.x,
            selected.y,
            selected.attack_range,
        )
        if signature == self._range_signature:
            return
        if self.range_node is not None:
            self.range_node.removeNode()
        from panda3d.core import LineSegs

        radius = selected.attack_range * WORLD_SCALE
        x, y, _ = _world_point(selected.x, selected.y, 0.04)
        lines = LineSegs("unit-range")
        lines.setThickness(1.5)
        lines.setColor(*_rgb(tuple(selected.stats["color"])))
        points = 64
        for index in range(points + 1):
            angle = index * math.tau / points
            point = (x + math.cos(angle) * radius, y + math.sin(angle) * radius, 0.05)
            if index == 0:
                lines.moveTo(*point)
            else:
                lines.drawTo(*point)
        self.range_node = self.game_root.attachNewNode(lines.create())
        self._range_signature = signature

    def _sync_placement_preview(self) -> None:
        if not self.game.placement_mode or self._cursor_world is None:
            if self.placement_node is not None:
                self.placement_node.removeNode()
                self.placement_node = None
            return
        if self.placement_node is None:
            self.placement_node = self.game_root.attachNewNode("placement-preview")
            self._make_box(
                self.placement_node,
                "placement-preview-body",
                (0, 0, 0.75),
                (0.24, 0.24, 0.48),
                (104, 223, 137),
            )
        x, y = self._cursor_world
        self.placement_node.setPos(x, y, GROUND_Z)
        valid = self.game.can_place_defender(self.game.mouse_position)
        self.placement_node.setColorScale(0.5, 1.0 if valid else 0.35, 0.5, 0.58)
        self.placement_node.setTransparency(TransparencyAttrib.MAlpha)
        self.placement_node.show()

    def _update_player(self, delta_time: float) -> None:
        if self.player_node is None:
            return
        player = self.game.lobby_player
        x, y, z = _world_point(player["x"], player["y"], player["z"])
        self.player_node.setPos(x, y, z)
        heading = self.game.lobby_facing_heading
        self.player_node.setH(heading)
        moving = any(
            key in self.game.held_keys
            for key in (pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d)
        )
        if moving:
            self._walk_time += delta_time * LOBBY_MOVE_SPEED / 36
            self.player_limbs[0].setR(math.sin(self._walk_time) * 28)
            self.player_limbs[1].setR(-math.sin(self._walk_time) * 28)
        else:
            self.player_limbs[0].setR(0)
            self.player_limbs[1].setR(0)

        current = self.camera.getPos()
        heading_radians = math.radians(heading)
        target = LPoint3(
            x + math.sin(heading_radians) * 9.0,
            y - math.cos(heading_radians) * 9.0,
            z + 6.5,
        )
        if self._camera_initialized:
            blend = min(1.0, delta_time * 4.5)
            self.camera.setPos(current + (target - current) * blend)
        else:
            self.camera.setPos(target)
            self._camera_initialized = True
        self.camera.lookAt(x, y, z + 0.9)
        self.hub_header.setText(
            f"LAST STAND  |  {self.game.account_name or 'GUEST'}  |  {self.game.credits:,} CREDITS"
        )

    def _update_hub_hud(self) -> None:
        station = self.game._lobby_station_for_player()
        if station is None:
            prompt = "Explore the island and find a station."
        elif station == "admin" and not self.game.is_admin:
            prompt = "This terminal is available to administrators only."
        elif station == "summon":
            prompt = "Press E to summon a unit."
        elif station == "start":
            prompt = "Press E to deploy into the 3D battlefield."
        else:
            prompt = f"Press E to open {STATION_LABELS[station].lower()}."
        self.hub_footer.setText(
            f"WASD Move     SPACE Jump     E Interact     ESC Setup     |     {prompt}"
        )
        self.hub_status.setText(self.game.status)
        for name, node in self.station_nodes.items():
            node.setColorScale(1.35, 1.35, 1.35, 1) if name == station else node.clearColorScale()

    def _update_camera(self, delta_time: float) -> None:
        pointer = self._pointer_position()
        if self._camera_dragging:
            if pointer is None:
                self._last_camera_pointer = None
            elif self._last_camera_pointer is not None:
                delta_x = (pointer[0] - self._last_camera_pointer[0]) * SCREEN_WIDTH
                delta_y = (pointer[1] - self._last_camera_pointer[1]) * SCREEN_HEIGHT
                self._camera_yaw -= delta_x * 0.25
                self._camera_pitch = min(
                    78.0,
                    max(12.0, self._camera_pitch - delta_y * 0.25),
                )
                self._last_camera_pointer = pointer
            else:
                self._last_camera_pointer = pointer

        distance = math.hypot(27, 29)
        pitch = math.radians(self._camera_pitch)
        yaw = math.radians(self._camera_yaw)
        horizontal_distance = distance * math.cos(pitch)
        target = LPoint3(
            horizontal_distance * math.sin(yaw),
            -horizontal_distance * math.cos(yaw),
            distance * math.sin(pitch),
        )
        current = self.camera.getPos()
        if self._camera_initialized and not self._camera_dragging:
            blend = min(1.0, delta_time * 3.0)
            self.camera.setPos(current + (target - current) * blend)
        else:
            self.camera.setPos(target)
            self._camera_initialized = True
        self.camera.lookAt(0, 0, 0)
        if pointer is None:
            self._cursor_world = None
            return
        self._cursor_world = self._ground_point_from_mouse()


def run_3d(game: Any) -> None:
    """Launch the Panda3D window and advance the existing game object."""
    app = ThreeDGameView(game)
    try:
        app.run()
    finally:
        app.destroy()
