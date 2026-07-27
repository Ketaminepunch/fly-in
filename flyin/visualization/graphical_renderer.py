"""pg-based graphical view of the zone network and live drone positions."""

import pygame as pg
import pygame.gfxdraw
from pygame.math import clamp

from flyin.model import Connection, Network

MACCHIATO: dict[str, str] = {
    "base": "#24273a",
    "surface1": "#494d64",
    "overlay0": "#6e738d",
    "text": "#cad3f5",
    "crust": "#181926",
    "red": "#ed8796",
    "peach": "#f5a97f",
    "yellow": "#eed49f",
    "green": "#a6da95",
    "teal": "#8bd5ca",
    "sky": "#91d7e3",
    "sapphire": "#7dc4e4",
    "mauve": "#c6a0f6",
    "pink": "#f5bde6",
    "flamingo": "#f0c6c6",
}
type_colors: dict[str, str] = {
    "restricted": MACCHIATO["peach"],
    "priority": MACCHIATO["green"],
    "normal": MACCHIATO["sky"],
    "blocked": MACCHIATO["red"],
}
DRONE_COLORS = [
    MACCHIATO["yellow"],
    MACCHIATO["sapphire"],
    MACCHIATO["pink"],
    MACCHIATO["teal"],
    MACCHIATO["mauve"],
    MACCHIATO["flamingo"],
]


class PygameRender:
    def __init__(
        self,
        network: Network,
        width: int = 800,
        height: int = 600,
        margin: int = 40,
    ) -> None:
        self.network: Network = network
        pg.init()
        self.margin = margin
        self.screen: pg.Surface = pg.display.set_mode(
            (width, height), pg.RESIZABLE
        )
        self.clock: pg.time.Clock = pg.time.Clock()
        self.font: pg.font.Font = pg.font.SysFont(None, 24)
        self.positions: dict[str, tuple[float, float]] = {
            zone.name: (zone.x, zone.y) for zone in self.network.zones.values()
        }
        self.connections: dict[str, Connection] = {
            connection.name: connection
            for connections in network.adjacency.values()
            for connection in connections
        }
        self.scale: float = 1.0
        self.tx: float = 0.0
        self.ty: float = 0.0
        self.drag_start: tuple[int, int] | None = None
        self.drag_origin: tuple[float, float] | None = None
        self._fit_view(width, height)
        self.base_scale = self.scale

    def _fit_view(self, width: int, height: int) -> None:
        xs = [zone.x for zone in self.network.zones.values()]
        ys = [zone.y for zone in self.network.zones.values()]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        x_span, y_span = x_max - x_min or 1.0, y_max - y_min or 1.0
        self.scale = min(
            (width - 2 * self.margin) / x_span,
            (height - 2 * self.margin) / y_span,
        )
        self.tx = (width - x_span * self.scale) / 2 - x_min * self.scale
        self.ty = (height - y_span * self.scale) / 2 - y_min * self.scale

    def _world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        return (wx * self.scale + self.tx, wy * self.scale + self.ty)

    def _screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return ((sx - self.tx) / self.scale, (sy - self.ty) / self.scale)

    def draw_network(self) -> None:
        self.screen.fill(pg.Color(MACCHIATO["base"]))
        all_connections = set()
        ratio = self.scale / self.base_scale
        for connections in self.network.adjacency.values():
            for connection in connections:
                all_connections.add(connection)
        for connection in all_connections:
            pos1 = self._world_to_screen(
                *self.positions[connection.zone1_name]
            )
            pos2 = self._world_to_screen(
                *self.positions[connection.zone2_name]
            )
            pg.draw.aaline(
                self.screen, pg.Color(MACCHIATO["overlay0"]), pos1, pos2
            )
        for zone in self.network.zones.values():
            zone_position = self._world_to_screen(*self.positions[zone.name])
            if zone.color == "none":
                body_color = pg.Color(MACCHIATO["surface1"])
            else:
                try:
                    body_color = pg.Color(zone.color)
                except ValueError:
                    body_color = pg.Color(MACCHIATO["surface1"])
            cx, cy = int(zone_position[0]), int(zone_position[1])
            type_color = pg.Color(type_colors[zone.zone_type])
            pygame.gfxdraw.filled_circle(
                self.screen, cx, cy, int(30 * ratio), type_color
            )
            pygame.gfxdraw.aacircle(
                self.screen, cx, cy, int(30 * ratio), type_color
            )
            pygame.gfxdraw.filled_circle(
                self.screen, cx, cy, int(28 * ratio), body_color
            )
            pygame.gfxdraw.aacircle(
                self.screen, cx, cy, int(28 * ratio), body_color
            )
            text_surface = self.font.render(
                zone.name, True, pg.Color(MACCHIATO["text"])
            )
            text_rect = text_surface.get_rect(
                center=(zone_position[0], zone_position[1] + 25 + 12)
            )
            capacity_surface = self.font.render(
                str(zone.capacity), True, pg.Color(MACCHIATO["crust"])
            )
            capacity_rect = capacity_surface.get_rect(
                center=(zone_position[0], zone_position[1])
            )
            self.screen.blit(text_surface, text_rect)
            self.screen.blit(capacity_surface, capacity_rect)

    def token_to_pos(self, token: str) -> tuple[float, float]:
        if token in self.positions:
            wx, wy = self.positions[token]
        else:
            connection = self.connections[token]
            x1, y1 = self.positions[connection.zone1_name]
            x2, y2 = self.positions[connection.zone2_name]
            wx, wy = (x1 + x2) / 2, (y1 + y2) / 2
        return self._world_to_screen(wx, wy)

    def draw_drones(
        self,
        from_positions: dict[int, str],
        to_positions: dict[int, str],
        progress: float,
    ) -> None:
        by_pair: dict[tuple[str, str], list[int]] = {}
        for drone_id, from_token in from_positions.items():
            to_token = to_positions[drone_id]
            by_pair.setdefault((from_token, to_token), []).append(drone_id)

        for tokens, drone_ids in by_pair.items():
            from_token, to_token = tokens
            pos_from = self.token_to_pos(from_token)
            pos_to = self.token_to_pos(to_token)
            from_x, from_y = pos_from
            to_x, to_y = pos_to
            base_x = int(from_x + (to_x - from_x) * min(progress, 1.0))
            base_y = int(from_y + (to_y - from_y) * min(progress, 1.0))
            base_pos = (base_x, base_y)
            for i, drone_id in enumerate(drone_ids):
                color = pg.Color(DRONE_COLORS[drone_id % len(DRONE_COLORS)])
                offset_x = (i - (len(drone_ids) - 1) / 2) * 16
                final_pos = int(base_pos[0] + offset_x), base_pos[1] + 20
                rect = pg.Rect(0, 0, 20, 14)
                rect.center = final_pos
                pg.draw.rect(self.screen, color, rect)
                text_surface = self.font.render(
                    str(drone_id), True, pg.Color(MACCHIATO["crust"])
                )
                text_rect = text_surface.get_rect(center=rect.center)
                self.screen.blit(text_surface, text_rect)

    def render(self, turn_log: list[dict[int, str]]) -> None:
        snapshots: list[dict[int, str]] = []
        current_positions: dict[int, str] = {
            drone_id: self.network.start.name
            for drone_id in range(1, self.network.nb_drones + 1)
        }
        snapshots.append(current_positions)
        for turn in turn_log:
            current_positions = current_positions.copy()
            current_positions.update(turn)
            snapshots.append(current_positions)
        turn_index = 0
        anim_target: int | None = None
        anim_progress: float = 0.0
        paused = False
        paused = True
        running = True
        anim_speed = 200
        while running:
            dt = self.clock.tick(60)
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    running = False
                elif event.type == pg.KEYDOWN:
                    match event.key:
                        case pg.K_SPACE:
                            paused = not paused
                        case pg.K_RIGHT:
                            if anim_target is None:
                                anim_target = min(
                                    turn_index + 1, len(snapshots) - 1
                                )
                        case pg.K_LEFT:
                            if anim_target is None:
                                anim_target = max(turn_index - 1, 0)
                        case pg.K_UP:
                            if anim_speed > 200:
                                anim_speed -= 200
                        case pg.K_DOWN:
                            if anim_speed < 1000:
                                anim_speed += 200
                        case pg.K_EQUALS:
                            mx, my = pg.mouse.get_pos()
                            wx, wy = self._screen_to_world(mx, my)
                            zoom_factor = 1.1
                            self.scale = clamp(
                                self.scale * zoom_factor, 20, 1000
                            )
                            self.tx = mx - wx * self.scale
                            self.ty = my - wy * self.scale
                        case pg.K_MINUS:
                            mx, my = pg.mouse.get_pos()
                            wx, wy = self._screen_to_world(mx, my)
                            zoom_factor = 1 / 1.1
                            self.scale = clamp(
                                self.scale * zoom_factor, 20, 1000
                            )
                            self.tx = mx - wx * self.scale
                            self.ty = my - wy * self.scale
                elif event.type == pg.MOUSEWHEEL:
                    mx, my = pg.mouse.get_pos()
                    wx, wy = self._screen_to_world(mx, my)
                    zoom_factor = 1.1 if event.y > 0 else 1 / 1.1
                    self.scale = clamp(self.scale * zoom_factor, 20, 1000)
                    self.tx = mx - wx * self.scale
                    self.ty = my - wy * self.scale
                elif event.type == pg.VIDEORESIZE:
                    self.screen = pg.display.set_mode(
                        (event.w, event.h), pg.RESIZABLE
                    )
                    self._fit_view(event.w, event.h)
                elif event.type == pg.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        self.drag_start = event.pos
                        self.drag_origin = (self.tx, self.ty)
                elif event.type == pg.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.drag_start = None
                elif event.type == pg.MOUSEMOTION:
                    if (
                        self.drag_start is not None
                        and self.drag_origin is not None
                    ):
                        mx, my = pg.mouse.get_pos()
                        dx, dy = (
                            mx - self.drag_start[0],
                            my - self.drag_start[1],
                        )
                        self.tx = self.drag_origin[0] + dx
                        self.ty = self.drag_origin[1] + dy
            if anim_target is not None:
                anim_progress += dt / anim_speed
            elif anim_target is None and not paused:
                anim_target = min(turn_index + 1, len(snapshots) - 1)
            if anim_progress >= 1.0:
                if anim_target is not None:
                    turn_index = anim_target
                anim_target = None
                anim_progress = 0.0
            self.draw_network()
            self.draw_drones(
                snapshots[turn_index],
                snapshots[anim_target]
                if anim_target is not None
                else snapshots[turn_index],
                anim_progress,
            )
            turn_text = self.font.render(
                f"Turn {turn_index}/{len(snapshots) - 1}",
                True,
                pg.Color(MACCHIATO["text"]),
            )
            self.screen.blit(turn_text, (10, 10))

            pg.display.flip()
        pg.quit()
