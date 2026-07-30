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
    """Interactive pygame viewer for a network and its per-turn drone log."""

    def __init__(
        self,
        network: Network,
        width: int = 800,
        height: int = 600,
        margin: int = 65,
    ) -> None:
        """Open a pygame window and fit the network's zones inside it."""
        self.network: Network = network
        pg.init()
        self.margin = margin
        self.screen: pg.Surface = pg.display.set_mode(
            (width, height), pg.RESIZABLE
        )
        self.clock: pg.time.Clock = pg.time.Clock()
        self.font: pg.font.Font = pg.font.SysFont(None, 20)
        self.last_directions: dict[int, pg.math.Vector2] = {}
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
        self.fonts: dict[int, pg.font.Font] = {}
        self.turn_index: int = 0
        self.anim_speed: int = 0

    def _font_finder(self, size: int) -> pg.font.Font:
        """Return a cached SysFont for size, creating it if needed."""
        if size not in self.fonts:
            self.fonts[size] = pg.font.SysFont(None, size)
        return self.fonts[size]

    def _fit_view(self, width: int, height: int) -> None:
        """Compute scale/translation so all zones fit within the window."""
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
        """Convert network coordinates to current on-screen pixel position."""
        return (wx * self.scale + self.tx, wy * self.scale + self.ty)

    def _screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        """Convert an on-screen pixel position back to network coordinates."""
        return ((sx - self.tx) / self.scale, (sy - self.ty) / self.scale)

    def draw_network(self) -> None:
        """Draw the background, every connection line, and every zone."""
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
                self.screen, cx, cy, int(26), type_color
            )
            pygame.gfxdraw.aacircle(self.screen, cx, cy, int(26), type_color)
            pygame.gfxdraw.filled_circle(
                self.screen, cx, cy, int(24), body_color
            )
            pygame.gfxdraw.aacircle(self.screen, cx, cy, int(24), body_color)
            if self.scale > self.base_scale * 1.03:
                size = int(clamp(14 * ratio, 8, 27))
                text_surface = self._font_finder(size).render(
                    zone.name, True, pg.Color(MACCHIATO["text"])
                )
                text_rect = text_surface.get_rect(
                    center=(zone_position[0], zone_position[1] + (35))
                )
                self.screen.blit(text_surface, text_rect)
            capacity_surface = self.font.render(
                str(zone.capacity), True, pg.Color(MACCHIATO["crust"])
            )
            capacity_rect = capacity_surface.get_rect(
                center=(zone_position[0], zone_position[1])
            )
            self.screen.blit(capacity_surface, capacity_rect)

    def token_to_pos(self, token: str) -> tuple[float, float]:
        """Resolve a zone name or connection name to a screen position.

        Zone tokens map to that zone's position; connection tokens map to
        the midpoint between the two zones it links.
        """
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
        """Draw every drone as an arrow interpolated between two positions.

        Drones sharing the same from/to token pair are fanned out around
        their shared interpolated point so they don't overlap.
        """
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
                angle = i * (360 / len(drone_ids))
                color = pg.Color(DRONE_COLORS[drone_id % len(DRONE_COLORS)])
                offset = pg.math.Vector2((45), 0).rotate(angle)
                final_pos = (
                    int(base_pos[0] + offset.x),
                    int(base_pos[1] + offset.y),
                )
                raw = pg.math.Vector2(to_x - from_x, to_y - from_y)
                if raw.length_squared() > 0:
                    direction = raw.normalize()
                    self.last_directions[drone_id] = direction
                else:
                    direction = self.last_directions.get(
                        drone_id, pg.math.Vector2(1, 0)
                    )
                size = 12
                tip = final_pos + direction * size
                back_left = (
                    final_pos - direction * size + direction.rotate(90) * size
                )
                back_right = (
                    final_pos - direction * size - direction.rotate(90) * size
                )
                pg.draw.polygon(
                    self.screen, color, [tip, back_left, back_right]
                )
                text_surface = self.font.render(
                    str(drone_id), True, pg.Color(MACCHIATO["crust"])
                )
                text_rect = text_surface.get_rect(center=final_pos)
                self.screen.blit(text_surface, text_rect)

    def draw_hud(self, snapshots: list[dict[int, str]]) -> None:
        """Draw the bottom bar showing the current turn index."""
        bar_height = 100
        bar_rect = pg.Rect(
            0,
            self.screen.get_height() - bar_height,
            self.screen.get_width(),
            bar_height,
        )
        pg.draw.rect(self.screen, pg.Color(MACCHIATO["crust"]), bar_rect)
        pg.draw.line(
            self.screen,
            pg.Color(MACCHIATO["surface1"]),
            bar_rect.topleft,
            bar_rect.topright,
            2,
        )
        turn_surface = self.font.render(
            f"Turn {self.turn_index}/{len(snapshots) - 1}",
            True,
            pg.Color(MACCHIATO["text"]),
        )
        turn_rect = turn_surface.get_rect(midleft=(20, bar_rect.centery))
        self.screen.blit(turn_surface, turn_rect)

    def render(self, turn_log: list[dict[int, str]]) -> None:
        """Run the interactive render loop until the window is closed.

        Builds a per-turn position snapshot from turn_log, then handles
        playback (space), stepping (arrows), speed (up/down), zoom
        (+/-/wheel) and panning (drag) while animating drones between
        turns.
        """
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
        self.turn_index = 0
        anim_target: int | None = None
        anim_progress: float = 0.0
        paused = True
        running = True
        self.anim_speed = 200
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
                                    self.turn_index + 1, len(snapshots) - 1
                                )
                        case pg.K_LEFT:
                            if anim_target is None:
                                anim_target = max(self.turn_index - 1, 0)
                        case pg.K_UP:
                            if self.anim_speed > 200:
                                self.anim_speed -= 200
                        case pg.K_DOWN:
                            if self.anim_speed < 1000:
                                self.anim_speed += 200
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
                    self.base_scale = self.scale
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
                anim_progress += dt / self.anim_speed
            elif anim_target is None and not paused:
                anim_target = min(self.turn_index + 1, len(snapshots) - 1)
            if anim_progress >= 1.0:
                if anim_target is not None:
                    self.turn_index = anim_target
                anim_target = None
                anim_progress = 0.0
            self.draw_network()
            self.draw_drones(
                snapshots[self.turn_index],
                snapshots[anim_target]
                if anim_target is not None
                else snapshots[self.turn_index],
                anim_progress,
            )
            self.draw_hud(snapshots)
            pg.display.flip()
        pg.quit()
