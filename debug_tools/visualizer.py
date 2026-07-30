"""
Drone map visualizer — Pygame-based, Wayland-compatible.

Features
--------
* Zoom   : scroll wheel (centered on cursor) or trackpad pinch-to-zoom (locked center)
* Pan    : click-drag on canvas background
* Step   : ← / → keys or Prev/Next screen buttons
* Play   : auto-plays with configurable speed slider
* Select : click a node to inspect connections + drone occupancy
* Colors : respects zone color metadata from the map file
* Scale  : Ctrl +/- zooms the entire UI (perfect for 2K/4K displays)
"""

import math
from typing import final

import pygame

from colors import COLOR_MAP

ZoneData = dict[str, str | int]
TurnLog = list[list[str]]


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Convert a "#rrggbb" hex color string to an (r, g, b) tuple."""
    hex_str = hex_str.lstrip("#")
    return int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)


SOLVER_FINISHED_EVENT = pygame.USEREVENT + 1

BG_DARK = hex_to_rgb("#1a1a1e")
BG_PANEL = hex_to_rgb("#25252b")
BG_CARD = hex_to_rgb("#2e2e36")
BORDER = hex_to_rgb("#3a3a44")
TEXT_PRI = hex_to_rgb("#e8e8ec")
TEXT_SEC = hex_to_rgb("#8888a0")
TEXT_MUT = hex_to_rgb("#55556a")
ACCENT = hex_to_rgb("#7c6af7")
ACCENT_HI = hex_to_rgb("#a89bf8")
EDGE_DEF = hex_to_rgb("#3a3a55")
EDGE_ACTIVE = hex_to_rgb("#7c6af7")

ZONE_TYPE_RING = {
    "normal": "#3a3a55",
    "priority": "#4ade80",
    "restricted": "#fb923c",
    "blocked": "#444444",
    "start": "#7c6af7",
    "end": "#facc15",
}

ZONE_TYPE_RING_RGB = {k: hex_to_rgb(v) for k, v in ZONE_TYPE_RING.items()}


def resolve_color_rgb(
    name: str, fallback_hex: str = "#60a5fa"
) -> tuple[int, int, int]:
    """Look up a named color in COLOR_MAP, falling back to fallback_hex."""
    hex_str = COLOR_MAP.get(name.lower(), fallback_hex)
    return hex_to_rgb(hex_str)


def get_drone_colors(
    did: str,
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Return a stable (base_color, highlight_color) pair for a drone id."""
    colors = [
        "#f87171",
        "#60a5fa",
        "#4ade80",
        "#facc15",
        "#c084fc",
        "#fb923c",
        "#22d3ee",
        "#f472b6",
        "#a3e635",
        "#2dd4bf",
        "#6366f1",
        "#ec4899",
        "#f472b6",
        "#e2e8f0",
        "#d97706",
        "#0d9488",
    ]
    try:
        val = int("".join(filter(str.isdigit, did)))
    except ValueError:
        val = hash(did)
    hex_color = colors[val % len(colors)]
    rgb = hex_to_rgb(hex_color)
    rgb_hi = (
        min(255, rgb[0] + 55),
        min(255, rgb[1] + 55),
        min(255, rgb[2] + 55),
    )
    return rgb, rgb_hi


@final
class DroneVisualizer:
    """
    Interactive Pygame visualizer for the drone routing simulation.
    """

    def __init__(
        self,
        zones: list[ZoneData],
        connections: list[tuple[str, str]],
        turns: TurnLog | None = None,
    ) -> None:
        self.zones = zones
        self.connections = connections
        self.turns: TurnLog = turns or []
        self.zones_by_name: dict[str, ZoneData] = {
            str(z["name"]): z for z in zones
        }

        self._scale: float = 50.0
        self._tx: float = 0.0
        self._ty: float = 0.0
        self._drag_start: tuple[int, int] | None = None
        self._drag_origin: tuple[float, float] | None = None

        self._turn_index: int = -1
        self._playing: bool = False
        self._speed_val: int = 600

        self._drone_positions: list[dict[str, str]] = []
        self._build_positions()

        self._selected: str | None = None

        self._pulse: float = 0.0

        self._dragging_timeline: bool = False
        self._dragging_speed: bool = False
        self._ui_scale: float = 1.0
        self._fonts: dict[tuple[str, int, bool], pygame.font.Font] = {}

        self._target_scale: float = self._scale
        self._zoom_center_screen: tuple[float, float] | None = None
        self._zoom_center_world: tuple[float, float] | None = None
        self._drone_coords: dict[str, tuple[float, float]] = {}
        self.is_ready = turns is not None

    def _build_positions(self) -> None:
        """Build a per-turn snapshot of drone positions from the turn log."""
        if not self.turns:
            return

        start_name = next(
            (
                str(z["name"])
                for z in self.zones
                if z.get("zone_type") == "start"
            ),
            str(self.zones[0]["name"]) if self.zones else "start",
        )

        all_ids: set[str] = set()
        for move_list in self.turns:
            for move in move_list:
                drone_id = move.split("-")[0]
                all_ids.add(drone_id)

        initial: dict[str, str] = {did: start_name for did in sorted(all_ids)}
        self._drone_positions = [initial]

        current = dict(initial)
        for move_list in self.turns:
            current = dict(current)
            for move in move_list:
                parts = move.split("-", 1)
                if len(parts) == 2:
                    drone_id, dest = parts
                    current[drone_id] = dest
            self._drone_positions.append(dict(current))

    def _world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        return wx * self._scale + self._tx, wy * self._scale + self._ty

    def _screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return (sx - self._tx) / self._scale, (sy - self._ty) / self._scale

    def _fit_view(self, canvas_w: int, canvas_h: int) -> None:
        if not self.zones:
            return
        xs = [float(int(z["x"])) for z in self.zones]
        ys = [float(int(z["y"])) for z in self.zones]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        pad = 80.0
        span_x = max_x - min_x or 1.0
        span_y = max_y - min_y or 1.0
        self._scale = max(
            80.0,
            min(
                (canvas_w - pad * 2) / span_x,
                (canvas_h - pad * 2) / span_y,
                250.0,
            ),
        )
        self._target_scale = self._scale
        self._tx = (
            canvas_w - span_x * self._scale
        ) / 2.0 - min_x * self._scale
        self._ty = (
            canvas_h - span_y * self._scale
        ) / 2.0 - min_y * self._scale

    def _hit_zone(self, sx: float, sy: float) -> str | None:
        r = max(16.0, min(80.0, self._scale * 0.22))
        for z in self.zones:
            zx, zy = self._world_to_screen(
                float(int(z["x"])), float(int(z["y"]))
            )
            if math.hypot(sx - zx, sy - zy) <= r * 1.3:
                return str(z["name"])
        return None

    def _step(self, delta: int) -> None:
        if not self.turns:
            return
        self._turn_index = max(
            -1, min(len(self.turns) - 1, self._turn_index + delta)
        )

    def _go_start(self) -> None:
        self._turn_index = -1

    def _go_end(self) -> None:
        if self.turns:
            self._turn_index = len(self.turns) - 1

    def _toggle_play(self) -> None:
        self._playing = not self._playing

    def _current_positions(self) -> dict[str, str]:
        if not self._drone_positions:
            return {}
        idx = self._turn_index + 1
        idx = max(0, min(len(self._drone_positions) - 1, idx))
        return self._drone_positions[idx]

    def _end_zone_name(self) -> str:
        return next(
            (
                str(z["name"])
                for z in self.zones
                if z.get("zone_type") == "end"
            ),
            "",
        )

    def _get_font(
        self, name: str, size: int, bold: bool = False
    ) -> pygame.font.Font:
        key = (name, size, bold)
        if key not in self._fonts:
            try:
                self._fonts[key] = pygame.font.SysFont(name, size, bold=bold)
            except Exception:
                self._fonts[key] = pygame.font.Font(None, size)
        return self._fonts[key]

    def _draw_dashed_line(
        self,
        surface: pygame.Surface,
        color: tuple[int, int, int],
        start: tuple[float, float],
        end: tuple[float, float],
        width: int = 1,
        dash_length: float = 6.0,
    ) -> None:
        x1, y1 = start
        x2, y2 = end
        dx = x2 - x1
        dy = y2 - y1
        distance = math.hypot(dx, dy)
        if distance == 0:
            return

        num_dashes = int(distance / (dash_length * 2))
        for i in range(num_dashes):
            start_ratio = (i * 2 * dash_length) / distance
            end_ratio = ((i * 2 + 1) * dash_length) / distance
            if end_ratio > 1.0:
                end_ratio = 1.0
            p1 = (x1 + dx * start_ratio, y1 + dy * start_ratio)
            p2 = (x1 + dx * end_ratio, y1 + dy * end_ratio)
            _ = pygame.draw.line(surface, color, p1, p2, width)

    def run(self) -> None:
        """Start the visualizer (blocking)."""
        _ = pygame.init()

        base_sidebar_w = 320
        base_playback_h = 80

        win_w, win_h = 1000, 700
        screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
        pygame.display.set_caption("Fly-in Drone Map")

        sidebar_w = int(base_sidebar_w * self._ui_scale)
        playback_h = int(base_playback_h * self._ui_scale)
        self._fit_view(win_w - sidebar_w, win_h - playback_h)

        clock = pygame.time.Clock()
        last_ticks = pygame.time.get_ticks()
        play_timer = 0.0

        running = True
        while running:
            current_ticks = pygame.time.get_ticks()
            dt = current_ticks - last_ticks
            last_ticks = current_ticks

            self._pulse += 0.003 * dt

            us = self._ui_scale
            sidebar_w = int(base_sidebar_w * us)
            playback_h = int(base_playback_h * us)

            font_header = self._get_font("Helvetica", int(18 * us), bold=True)
            font_body = self._get_font("Helvetica", int(14 * us))
            font_mono = self._get_font("Courier", int(14 * us))

            win_w, win_h = screen.get_size()
            canvas_w = win_w - sidebar_w
            canvas_h = win_h - playback_h

            btn_prev_start = pygame.Rect(
                int(15 * us), int(20 * us), int(40 * us), int(40 * us)
            )
            btn_prev = pygame.Rect(
                int(60 * us), int(20 * us), int(40 * us), int(40 * us)
            )
            btn_play = pygame.Rect(
                int(105 * us), int(20 * us), int(40 * us), int(40 * us)
            )
            btn_next = pygame.Rect(
                int(150 * us), int(20 * us), int(40 * us), int(40 * us)
            )
            btn_next_end = pygame.Rect(
                int(195 * us), int(20 * us), int(40 * us), int(40 * us)
            )

            timeline_x = int(325 * us)
            timeline_w = max(50, canvas_w - timeline_x - int(150 * us))
            timeline_y = int(37 * us)
            timeline_h = int(8 * us)
            timeline_rect = pygame.Rect(
                timeline_x, timeline_y, timeline_w, timeline_h
            )

            speed_x = canvas_w - int(130 * us)
            speed_y = int(20 * us)
            speed_w = int(70 * us)
            speed_h = int(8 * us)
            speed_slider_rect = pygame.Rect(
                speed_x + int(40 * us),
                speed_y + int(16 * us),
                speed_w,
                speed_h,
            )

            if abs(self._scale - self._target_scale) > 0.01:
                factor = 1.0 - math.exp(-0.015 * dt)
                self._scale += (self._target_scale - self._scale) * max(
                    0.05, min(1.0, factor)
                )

                if (
                    self._zoom_center_screen is not None
                    and self._zoom_center_world is not None
                ):
                    mx, my = self._zoom_center_screen
                    wx, wy = self._zoom_center_world
                    self._tx = mx - wx * self._scale
                    self._ty = my - wy * self._scale
            else:
                self._scale = self._target_scale
                self._zoom_center_screen = None
                self._zoom_center_world = None

            if self._playing:
                play_timer += dt
                delay = max(100, 2100 - self._speed_val)
                if play_timer >= delay:
                    play_timer = 0.0
                    if self._turn_index >= len(self.turns) - 1:
                        self._playing = False
                    else:
                        self._step(1)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == SOLVER_FINISHED_EVENT:
                    print("[UI] Solver data arrived. Rebuilding positions...")
                    self._build_positions()
                    self.is_ready = True
                    self._fit_view(win_w - sidebar_w, win_h - playback_h)

                elif event.type == pygame.VIDEORESIZE:
                    new_w = max(sidebar_w + 100, int(event.w))
                    new_h = max(playback_h + 100, int(event.h))
                    if (new_w, new_h) != screen.get_size():
                        screen = pygame.display.set_mode(
                            (new_w, new_h), pygame.RESIZABLE
                        )
                    win_w, win_h = screen.get_size()
                    canvas_w = win_w - sidebar_w
                    canvas_h = win_h - playback_h
                    timeline_w = max(50, canvas_w - timeline_x - int(150 * us))
                    timeline_rect = pygame.Rect(
                        timeline_x, timeline_y, timeline_w, timeline_h
                    )
                    speed_x = canvas_w - int(130 * us)
                    speed_slider_rect = pygame.Rect(
                        speed_x + int(40 * us),
                        speed_y + int(16 * us),
                        speed_w,
                        speed_h,
                    )

                elif event.type == pygame.MOUSEWHEEL:
                    mx, my = pygame.mouse.get_pos()
                    if mx < canvas_w and my < canvas_h:
                        wx, wy = self._screen_to_world(mx, my)
                        self._zoom_center_screen = (mx, my)
                        self._zoom_center_world = (wx, wy)

                        val = (
                            int(event.y)
                            if int(event.y) != 0
                            else -int(event.x)
                        )
                        if val != 0:
                            is_touch = getattr(event, "touch", False)
                            sensitivity = 0.035 if is_touch else 0.065
                            zoom_factor = 1.0 + val * sensitivity
                            self._target_scale = max(
                                5.0,
                                min(2000.0, self._target_scale * zoom_factor),
                            )

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    pos = event.pos
                    mx, my = int(pos[0]), int(pos[1])

                    if mx < canvas_w and my < canvas_h:
                        button = int(event.button)
                        if button == 1:
                            hit = self._hit_zone(float(mx), float(my))
                            if hit:
                                self._selected = (
                                    None if self._selected == hit else hit
                                )
                            else:
                                self._drag_start = (mx, my)
                                self._drag_origin = (self._tx, self._ty)
                                self._target_scale = self._scale
                                self._zoom_center_screen = None
                                self._zoom_center_world = None

                    elif mx < canvas_w and my >= canvas_h:
                        px = int(mx)
                        py = int(my - canvas_h)
                        button = int(event.button)
                        if button == 1:
                            if btn_prev_start.collidepoint(px, py):
                                self._go_start()
                            elif btn_prev.collidepoint(px, py):
                                self._step(-1)
                            elif btn_play.collidepoint(px, py):
                                self._toggle_play()
                            elif btn_next.collidepoint(px, py):
                                self._step(1)
                            elif btn_next_end.collidepoint(px, py):
                                self._go_end()

                            elif timeline_rect.collidepoint(px, py):
                                self._dragging_timeline = True
                                ratio = max(
                                    0.0,
                                    min(
                                        1.0,
                                        float(px - timeline_x) / timeline_w,
                                    ),
                                )
                                self._turn_index = max(
                                    -1,
                                    min(
                                        len(self.turns) - 1,
                                        int(ratio * len(self.turns)) - 1,
                                    ),
                                )

                            elif speed_slider_rect.inflate(
                                10, 10
                            ).collidepoint(px, py):
                                self._dragging_speed = True
                                ratio = max(
                                    0.0,
                                    min(
                                        1.0,
                                        float(px - speed_slider_rect.x)
                                        / speed_w,
                                    ),
                                )
                                self._speed_val = int(100 + ratio * 1900)

                elif event.type == pygame.MOUSEBUTTONUP:
                    button = int(event.button)
                    if button == 1:
                        self._drag_start = None
                        self._dragging_timeline = False
                        self._dragging_speed = False

                elif event.type == pygame.MOUSEMOTION:
                    pos = event.pos
                    mx, my = int(pos[0]), int(pos[1])
                    if (
                        self._drag_start is not None
                        and self._drag_origin is not None
                    ):
                        dx = mx - self._drag_start[0]
                        dy = my - self._drag_start[1]
                        self._tx = self._drag_origin[0] + dx
                        self._ty = self._drag_origin[1] + dy

                    elif self._dragging_timeline and self.turns:
                        px = mx
                        ratio = max(
                            0.0, min(1.0, float(px - timeline_x) / timeline_w)
                        )
                        self._turn_index = max(
                            -1,
                            min(
                                len(self.turns) - 1,
                                int(ratio * len(self.turns)) - 1,
                            ),
                        )

                    elif self._dragging_speed:
                        px = mx
                        ratio = max(
                            0.0,
                            min(
                                1.0, float(px - speed_slider_rect.x) / speed_w
                            ),
                        )
                        self._speed_val = int(100 + ratio * 1900)

                elif event.type == pygame.KEYDOWN:
                    mod = int(event.mod)
                    key = int(event.key)
                    is_ctrl = bool(mod & pygame.KMOD_CTRL)

                    if key == pygame.K_LEFT:
                        self._step(-1)
                    elif key == pygame.K_RIGHT:
                        self._step(1)
                    elif key == pygame.K_SPACE:
                        self._toggle_play()
                    elif key in (pygame.K_f, pygame.K_r):
                        self._fit_view(canvas_w, canvas_h)

                    elif key in (pygame.K_EQUALS, pygame.K_PLUS):
                        if is_ctrl:
                            self._ui_scale = min(3.0, self._ui_scale * 1.1)
                        else:
                            mx, my = pygame.mouse.get_pos()
                            if mx >= canvas_w or my >= canvas_h:
                                mx, my = canvas_w // 2, canvas_h // 2
                            wx, wy = self._screen_to_world(mx, my)
                            self._zoom_center_screen = (mx, my)
                            self._zoom_center_world = (wx, wy)
                            self._target_scale = min(
                                2000.0, self._target_scale * 1.2
                            )

                    elif key == pygame.K_MINUS:
                        if is_ctrl:
                            self._ui_scale = max(0.5, self._ui_scale / 1.1)
                        else:
                            mx, my = pygame.mouse.get_pos()
                            if mx >= canvas_w or my >= canvas_h:
                                mx, my = canvas_w // 2, canvas_h // 2
                            wx, wy = self._screen_to_world(mx, my)
                            self._zoom_center_screen = (mx, my)
                            self._zoom_center_world = (wx, wy)
                            self._target_scale = max(
                                5.0, self._target_scale * 0.8
                            )

            _ = screen.fill(BG_DARK)

            # Draw Canvas
            if canvas_w > 0 and canvas_h > 0:
                canvas_surf = screen.subsurface(
                    pygame.Rect(0, 0, canvas_w, canvas_h)
                )
                self._draw_canvas(canvas_surf, canvas_w, canvas_h, dt)

            # Draw Sidebar
            if sidebar_w > 0 and win_h > 0 and win_w >= sidebar_w:
                sidebar_surf = screen.subsurface(
                    pygame.Rect(win_w - sidebar_w, 0, sidebar_w, win_h)
                )
                self._draw_sidebar(
                    sidebar_surf,
                    sidebar_w,
                    win_h,
                    win_w,
                    us,
                    font_header,
                    font_body,
                    font_mono,
                )

            # Draw Playback
            if canvas_w > 0 and playback_h > 0 and win_h >= playback_h:
                play_surf = screen.subsurface(
                    pygame.Rect(0, canvas_h, canvas_w, playback_h)
                )
                self._draw_playback(
                    play_surf,
                    canvas_w,
                    canvas_h,
                    playback_h,
                    win_h,
                    us,
                    font_body,
                    btn_prev_start,
                    btn_prev,
                    btn_play,
                    btn_next,
                    btn_next_end,
                    timeline_x,
                    timeline_w,
                    timeline_y,
                    timeline_h,
                    timeline_rect,
                    speed_x,
                    speed_y,
                    speed_w,
                    speed_h,
                    speed_slider_rect,
                )

            pygame.display.flip()
            _ = clock.tick(60)

        pygame.quit()

    def _draw_canvas(
        self,
        canvas_surf: pygame.Surface,
        canvas_w: int,
        canvas_h: int,
        dt: float,
    ) -> None:
        """Draw the main grid, connection lines, zones, and drones."""
        _ = canvas_surf.fill(BG_DARK)

        wx0, wy0 = self._screen_to_world(0, 0)
        wx1, wy1 = self._screen_to_world(canvas_w, canvas_h)
        for gx in range(math.floor(wx0), int(wx1) + 2):
            sx, _ = self._world_to_screen(float(gx), 0)
            _ = pygame.draw.line(
                canvas_surf, (34, 34, 48), (sx, 0), (sx, canvas_h), 1
            )
        for gy in range(math.floor(wy0), int(wy1) + 2):
            _, sy = self._world_to_screen(0, float(gy))
            _ = pygame.draw.line(
                canvas_surf, (34, 34, 48), (0, sy), (canvas_w, sy), 1
            )

        active_edges: set[frozenset[str]] = set()
        if self.is_ready and self.turns and self._turn_index >= 0:
            for move in self.turns[self._turn_index]:
                parts = move.split("-", 1)
                if len(parts) == 2:
                    drone_id, dest = parts
                    src = self._drone_positions[self._turn_index].get(
                        drone_id, ""
                    )
                    if src and src != dest:
                        active_edges.add(frozenset([src, dest]))

        for name_a, name_b in self.connections:
            za = self.zones_by_name.get(name_a)
            zb = self.zones_by_name.get(name_b)
            if za is None or zb is None:
                continue
            ax, ay = self._world_to_screen(
                float(int(za["x"])), float(int(za["y"]))
            )
            bx, by = self._world_to_screen(
                float(int(zb["x"])), float(int(zb["y"]))
            )
            is_active = frozenset([name_a, name_b]) in active_edges
            is_selected = self._selected in (name_a, name_b)

            if is_active:
                width = max(3, min(6, int(self._scale * 0.05)))
                glow_color = (
                    min(255, EDGE_ACTIVE[0] + 50),
                    min(255, EDGE_ACTIVE[1] + 50),
                    min(255, EDGE_ACTIVE[2] + 50),
                )
                _ = pygame.draw.line(
                    canvas_surf,
                    glow_color,
                    (ax, ay),
                    (bx, by),
                    width + 2,
                )
                _ = pygame.draw.line(
                    canvas_surf, EDGE_ACTIVE, (ax, ay), (bx, by), width
                )
            else:
                if is_selected:
                    color = ACCENT_HI
                    width = max(2, min(8, int(self._scale * 0.03)))
                else:
                    color = EDGE_DEF
                    width = max(1, min(4, int(self._scale * 0.015)))
                _ = pygame.draw.line(
                    canvas_surf, color, (ax, ay), (bx, by), width
                )

            if self._scale > 38:
                dist_dx = float(int(zb["x"])) - float(int(za["x"]))
                dist_dy = float(int(zb["y"])) - float(int(za["y"]))
                dist = round(math.hypot(dist_dx, dist_dy), 1)
                mx = (ax + bx) / 2
                my = (ay + by) / 2
                font_dist = self._get_font(
                    "Helvetica",
                    max(8, min(24, int(self._scale * 0.08))),
                )
                text_surf = font_dist.render(str(dist), True, TEXT_MUT)
                rect = text_surf.get_rect(center=(mx, my))
                _ = pygame.draw.rect(
                    canvas_surf,
                    BG_DARK,
                    rect.inflate(6, 4),
                    border_radius=2,
                )
                _ = canvas_surf.blit(text_surf, rect)

        drones_here: dict[str, int] = {}
        if self.is_ready:
            positions = self._current_positions()
            for zone_name in positions.values():
                drones_here[zone_name] = drones_here.get(zone_name, 0) + 1

        for z in self.zones:
            name = str(z["name"])
            wx = float(int(z["x"]))
            wy = float(int(z["y"]))
            sx, sy = self._world_to_screen(wx, wy)

            r = max(16.0, min(80.0, self._scale * 0.22))
            zone_type = str(z.get("zone_type", "normal"))
            raw_color = str(z.get("color", ""))
            fill_hex = (
                resolve_color_rgb(raw_color, "#2e2e48")
                if raw_color
                else hex_to_rgb("#2e2e48")
            )
            ring_hex = ZONE_TYPE_RING_RGB.get(
                zone_type, ZONE_TYPE_RING_RGB["normal"]
            )

            is_selected = self._selected == name
            has_drones = name in drones_here

            if is_selected:
                _ = pygame.draw.circle(
                    canvas_surf,
                    ACCENT_HI,
                    (int(sx), int(sy)),
                    int(r + 6),
                    2,
                )
            elif has_drones:
                pulse_r = r + 4 + math.sin(self._pulse) * 3
                mixed = (
                    int(ring_hex[0] * 0.5 + BG_DARK[0] * 0.5),
                    int(ring_hex[1] * 0.5 + BG_DARK[1] * 0.5),
                    int(ring_hex[2] * 0.5 + BG_DARK[2] * 0.5),
                )
                _ = pygame.draw.circle(
                    canvas_surf,
                    mixed,
                    (int(sx), int(sy)),
                    int(pulse_r),
                    2,
                )

            _ = pygame.draw.circle(
                canvas_surf,
                ring_hex,
                (int(sx), int(sy)),
                int(r + 3),
                2,
            )

            _ = pygame.draw.circle(
                canvas_surf, fill_hex, (int(sx), int(sy)), int(r)
            )

            if zone_type == "blocked":
                _ = pygame.draw.line(
                    canvas_surf,
                    (255, 68, 68),
                    (sx - r * 0.7, sy - r * 0.7),
                    (sx + r * 0.7, sy + r * 0.7),
                    2,
                )
                _ = pygame.draw.line(
                    canvas_surf,
                    (255, 68, 68),
                    (sx + r * 0.7, sy - r * 0.7),
                    (sx - r * 0.7, sy + r * 0.7),
                    2,
                )

            short = name[:2].upper()
            font_short = self._get_font(
                "Helvetica", max(7, int(r * 0.55)), bold=True
            )
            text_surf = font_short.render(short, True, TEXT_PRI)
            rect = text_surf.get_rect(center=(int(sx), int(sy)))
            _ = canvas_surf.blit(text_surf, rect)

            if has_drones:
                count = drones_here[name]
                bx, by_b = sx + r * 0.7, sy - r * 0.7
                br = max(8.0, r * 0.35)
                _ = pygame.draw.circle(
                    canvas_surf, ACCENT, (int(bx), int(by_b)), int(br)
                )
                font_badge = self._get_font(
                    "Helvetica", max(7, int(br * 0.9)), bold=True
                )
                text_surf = font_badge.render(
                    str(count), True, (255, 255, 255)
                )
                rect = text_surf.get_rect(center=(int(bx), int(by_b)))
                _ = canvas_surf.blit(text_surf, rect)

            if self._scale > 25.0:
                fs = max(9, min(40, int(self._scale * 0.11)))
                font_name = self._get_font("Helvetica", fs)
                lbl_color = TEXT_PRI if is_selected else TEXT_SEC
                text_surf = font_name.render(name, True, lbl_color)
                rect = text_surf.get_rect(
                    center=(int(sx), int(sy + r + fs * 0.8 + 4))
                )
                bg_rect = rect.inflate(8, 4)
                _ = pygame.draw.rect(
                    canvas_surf, (20, 20, 26), bg_rect, border_radius=3
                )
                _ = canvas_surf.blit(text_surf, rect)

                if self._scale > 50.0:
                    font_coords = self._get_font(
                        "Helvetica",
                        max(7, min(24, int(self._scale * 0.08))),
                    )
                    text_surf = font_coords.render(
                        f"({int(z['x'])}, {int(z['y'])})",
                        True,
                        TEXT_MUT,
                    )
                    rect = text_surf.get_rect(
                        center=(
                            int(sx),
                            int(
                                sy
                                + r
                                + fs * 1.6
                                + max(7, min(24, int(self._scale * 0.08)))
                                * 0.8
                                + 6
                            ),
                        )
                    )
                    _ = canvas_surf.blit(text_surf, rect)

        if self.is_ready:
            positions = self._current_positions()
            r_val = max(16.0, min(80.0, self._scale * 0.22))

            zone_drones: dict[str, list[str]] = {}
            for did, zone_name in sorted(positions.items()):
                zone_drones.setdefault(zone_name, []).append(did)

            for zone_name, drones in zone_drones.items():
                zn_data = self.zones_by_name.get(zone_name)
                if zn_data is not None:
                    zx = float(int(zn_data["x"]))
                    zy = float(int(zn_data["y"]))
                elif "-" in zone_name:
                    parts = zone_name.split("-")
                    if len(parts) == 2:
                        za = self.zones_by_name.get(parts[0])
                        zb = self.zones_by_name.get(parts[1])
                        if za is not None and zb is not None:
                            zx = (
                                float(int(za["x"])) + float(int(zb["x"]))
                            ) / 2.0
                            zy = (
                                float(int(za["y"])) + float(int(zb["y"]))
                            ) / 2.0
                        else:
                            continue
                    else:
                        continue
                else:
                    continue

                n = len(drones)
                for i, did in enumerate(drones):
                    angle = (2.0 * math.pi * i / max(n, 1)) + self._pulse * 0.5
                    orbit_px = r_val + 16.0

                    orbit_dx = (math.cos(angle) * orbit_px) / self._scale
                    orbit_dy = (math.sin(angle) * orbit_px) / self._scale

                    twx = zx + orbit_dx
                    twy = zy + orbit_dy

                    if did not in self._drone_coords:
                        self._drone_coords[did] = (twx, twy)
                    else:
                        awx, awy = self._drone_coords[did]
                        factor = 1.0 - math.exp(-0.008 * dt)
                        awx += (twx - awx) * factor
                        awy += (twy - awy) * factor
                        self._drone_coords[did] = (awx, awy)

            for did, coords in self._drone_coords.items():
                if did not in positions:
                    continue

                awx, awy = coords
                sx, sy = self._world_to_screen(awx, awy)

                drone_color, drone_border_color = get_drone_colors(did)

                dd = max(5.0, min(30.0, self._scale * 0.08))
                points = [
                    (sx, sy - dd),
                    (sx + dd, sy),
                    (sx, sy + dd),
                    (sx - dd, sy),
                ]
                _ = pygame.draw.polygon(canvas_surf, drone_color, points)
                _ = pygame.draw.polygon(
                    canvas_surf, drone_border_color, points, 1
                )

                if self._scale > 35:
                    font_dr = self._get_font(
                        "Helvetica",
                        max(6, int(dd * 0.85)),
                        bold=True,
                    )
                    drone_num = "".join(filter(str.isdigit, did)) or did
                    text_surf = font_dr.render(
                        drone_num,
                        True,
                        (255, 255, 255)
                        if sum(drone_color) < 400
                        else (0, 0, 0),
                    )
                    rect = text_surf.get_rect(center=(int(sx), int(sy)))
                    _ = canvas_surf.blit(text_surf, rect)

    def _draw_sidebar(
        self,
        sidebar_surf: pygame.Surface,
        sidebar_w: int,
        win_h: int,
        win_w: int,
        us: float,
        font_header: pygame.font.Font,
        font_body: pygame.font.Font,
        font_mono: pygame.font.Font,
    ) -> None:
        """Draw the right sidebar panel with inspection cards and legend."""
        _ = sidebar_surf.fill(BG_PANEL)
        _ = pygame.draw.line(sidebar_surf, BORDER, (0, 0), (0, win_h), 1)

        text_surf = font_header.render("Zone info", True, TEXT_SEC)
        _ = sidebar_surf.blit(text_surf, (int(14 * us), int(14 * us)))

        card_info_rect = pygame.Rect(
            int(10 * us),
            int(34 * us),
            sidebar_w - int(20 * us),
            int(160 * us),
        )
        _ = pygame.draw.rect(
            sidebar_surf, BG_CARD, card_info_rect, border_radius=4
        )

        line_height = font_mono.get_linesize()

        if not self.is_ready:
            # Draw skeleton lines for Zone info card
            y_offset = card_info_rect.y + int(12 * us)
            for idx in range(4):
                pygame.draw.rect(
                    sidebar_surf,
                    (50, 50, 64),
                    pygame.Rect(
                        card_info_rect.x + int(10 * us),
                        y_offset + int(line_height * 0.2),
                        int(140 * us) if idx % 2 == 0 else int(100 * us),
                        int(10 * us),
                    ),
                    border_radius=int(2 * us),
                )
                y_offset += line_height
        else:
            info_lines: list[str] = []
            if self._selected and self._selected in self.zones_by_name:
                z = self.zones_by_name[self._selected]
                info_lines.append(f"name:  {z['name']}")
                info_lines.append(f"type:  {z.get('zone_type', 'normal')}")
                info_lines.append(f"pos:   ({z['x']}, {z['y']})")
                info_lines.append(f"cap:   {z.get('max_drones', 1)} drone(s)")
                info_lines.append(f"color: {z.get('color', 'none')}")

                nbrs = [
                    (b if a == self._selected else a)
                    for a, b in self.connections
                    if a == self._selected or b == self._selected
                ]
                info_lines.append(f"\nconnections ({len(nbrs)}):")
                for nb in nbrs[:4]:
                    info_lines.append(f"  → {nb}")
                if len(nbrs) > 4:
                    info_lines.append("  ... and more")
            else:
                info_lines = ["Click a zone", "to inspect it."]

            y_offset = card_info_rect.y + int(8 * us)
            for line in info_lines:
                text_surf = font_mono.render(line, True, TEXT_PRI)
                _ = sidebar_surf.blit(
                    text_surf, (card_info_rect.x + int(8 * us), y_offset)
                )
                y_offset += line_height

        text_surf = font_header.render("Drones this turn", True, TEXT_SEC)
        _ = sidebar_surf.blit(text_surf, (int(14 * us), int(210 * us)))

        card_drone_rect = pygame.Rect(
            int(10 * us),
            int(230 * us),
            sidebar_w - int(20 * us),
            int(180 * us),
        )
        _ = pygame.draw.rect(
            sidebar_surf, BG_CARD, card_drone_rect, border_radius=4
        )

        y_offset = card_drone_rect.y + int(8 * us)
        if not self.is_ready:
            # Draw skeleton lines for Drones card
            for idx in range(6):
                pygame.draw.circle(
                    sidebar_surf,
                    (50, 50, 64),
                    (
                        card_drone_rect.x + int(20 * us),
                        y_offset + int(line_height * 0.4),
                    ),
                    int(5 * us),
                )
                pygame.draw.rect(
                    sidebar_surf,
                    (50, 50, 64),
                    pygame.Rect(
                        card_drone_rect.x + int(32 * us),
                        y_offset + int(line_height * 0.2),
                        int(120 * us) if idx % 2 == 0 else int(90 * us),
                        int(10 * us),
                    ),
                    border_radius=int(2 * us),
                )
                y_offset += line_height
        else:
            positions = self._current_positions()
            if positions:
                sorted_drones = sorted(positions.items())
                visible_drones = sorted_drones[:11]
                for did, zone in visible_drones:
                    mark = "  (done)" if zone == self._end_zone_name() else ""
                    text_surf = font_mono.render(
                        f"{did:>4}  →  {zone}{mark}", True, TEXT_PRI
                    )
                    _ = sidebar_surf.blit(
                        text_surf,
                        (card_drone_rect.x + int(8 * us), y_offset),
                    )
                    y_offset += line_height
                if len(sorted_drones) > 11:
                    text_surf = font_mono.render(
                        f"  ... and {len(sorted_drones) - 11} more",
                        True,
                        TEXT_SEC,
                    )
                    _ = sidebar_surf.blit(
                        text_surf,
                        (card_drone_rect.x + int(8 * us), y_offset),
                    )
            else:
                text_surf = font_mono.render(
                    "No simulation loaded.", True, TEXT_PRI
                )
                _ = sidebar_surf.blit(
                    text_surf, (card_drone_rect.x + int(8 * us), y_offset)
                )

        text_surf = font_header.render("Zone types", True, TEXT_SEC)
        _ = sidebar_surf.blit(text_surf, (int(14 * us), int(426 * us)))

        legend_items = [
            ("start", "Start hub"),
            ("end", "End hub"),
            ("normal", "Normal"),
            ("priority", "Priority (1 turn)"),
            ("restricted", "Restricted (2 turns)"),
            ("blocked", "Blocked"),
        ]
        y_offset = int(450 * us)
        for lkey, label in legend_items:
            color = ZONE_TYPE_RING_RGB.get(lkey, (85, 85, 106))
            _ = pygame.draw.circle(
                sidebar_surf,
                color,
                (
                    int(20 * us),
                    y_offset + int(font_body.get_linesize() * 0.4),
                ),
                int(5 * us),
            )
            text_surf = font_body.render(label, True, TEXT_SEC)
            _ = sidebar_surf.blit(text_surf, (int(32 * us), y_offset))
            y_offset += font_body.get_linesize() + int(4 * us)

        text_surf = font_header.render("Keyboard Controls", True, TEXT_SEC)
        _ = sidebar_surf.blit(text_surf, (int(14 * us), int(576 * us)))
        hints = [
            "Space: Play / Pause",
            "Left / Right: Step turn",
            "+ / -: Zoom graph",
            "Ctrl +/-: Zoom UI",
            "F / R: Fit view to map",
        ]
        y_offset = int(600 * us)
        for hint in hints:
            text_surf = font_body.render(hint, True, TEXT_SEC)
            _ = sidebar_surf.blit(text_surf, (int(14 * us), y_offset))
            y_offset += font_body.get_linesize() + int(2 * us)

    def _draw_playback(
        self,
        play_surf: pygame.Surface,
        canvas_w: int,
        canvas_h: int,
        playback_h: int,
        win_h: int,
        us: float,
        font_body: pygame.font.Font,
        btn_prev_start: pygame.Rect,
        btn_prev: pygame.Rect,
        btn_play: pygame.Rect,
        btn_next: pygame.Rect,
        btn_next_end: pygame.Rect,
        timeline_x: int,
        timeline_w: int,
        timeline_y: int,
        timeline_h: int,
        timeline_rect: pygame.Rect,
        speed_x: int,
        speed_y: int,
        speed_w: int,
        speed_h: int,
        speed_slider_rect: pygame.Rect,
    ) -> None:
        """Draw the bottom playback panel with controls and timeline."""
        _ = play_surf.fill(BG_PANEL)
        _ = pygame.draw.line(play_surf, BORDER, (0, 0), (canvas_w, 0), 1)

        mx, my = pygame.mouse.get_pos()
        px, py = mx, my - canvas_h

        buttons = [
            (btn_prev_start, "prev_start"),
            (btn_prev, "prev"),
            (btn_play, "pause" if self._playing else "play"),
            (btn_next, "next"),
            (btn_next_end, "next_end"),
        ]

        for rect, icon_type in buttons:
            if not self.is_ready:
                btn_color = BG_CARD
                _ = pygame.draw.rect(
                    play_surf, btn_color, rect, border_radius=4
                )
                cx, cy = rect.center
                size = min(rect.width, rect.height) * 0.28
                color = TEXT_MUT
            else:
                is_hover = rect.collidepoint(px, py)
                btn_color = BORDER if is_hover else BG_CARD
                _ = pygame.draw.rect(
                    play_surf, btn_color, rect, border_radius=4
                )
                cx, cy = rect.center
                size = min(rect.width, rect.height) * 0.28
                color = TEXT_PRI

            if icon_type == "prev_start":
                bx = cx - size
                bw = max(2, int(size * 0.35))
                _ = pygame.draw.rect(
                    play_surf,
                    color,
                    pygame.Rect(bx, cy - size, bw, size * 2),
                )
                tx1 = cx - size * 0.2
                tx2 = cx + size
                _ = pygame.draw.polygon(
                    play_surf,
                    color,
                    [(tx1, cy), (tx2, cy - size), (tx2, cy + size)],
                )

            elif icon_type == "prev":
                tx1 = cx - size
                tx2 = cx + size * 0.8
                _ = pygame.draw.polygon(
                    play_surf,
                    color,
                    [(tx1, cy), (tx2, cy - size), (tx2, cy + size)],
                )

            elif icon_type == "play":
                tx1 = cx + size
                tx2 = cx - size * 0.8
                _ = pygame.draw.polygon(
                    play_surf,
                    color,
                    [(tx1, cy), (tx2, cy - size), (tx2, cy + size)],
                )

            elif icon_type == "pause":
                bw = max(2, int(size * 0.45))
                gap = max(2, int(size * 0.5))
                _ = pygame.draw.rect(
                    play_surf,
                    color,
                    pygame.Rect(cx - gap / 2 - bw, cy - size, bw, size * 2),
                )
                _ = pygame.draw.rect(
                    play_surf,
                    color,
                    pygame.Rect(cx + gap / 2, cy - size, bw, size * 2),
                )

            elif icon_type == "next":
                tx1 = cx + size
                tx2 = cx - size * 0.8
                _ = pygame.draw.polygon(
                    play_surf,
                    color,
                    [(tx1, cy), (tx2, cy - size), (tx2, cy + size)],
                )

            elif icon_type == "next_end":
                tx1 = cx + size * 0.2
                tx2 = cx - size
                _ = pygame.draw.polygon(
                    play_surf,
                    color,
                    [(tx1, cy), (tx2, cy - size), (tx2, cy + size)],
                )
                bx = cx + size - max(2, int(size * 0.35))
                bw = max(2, int(size * 0.35))
                _ = pygame.draw.rect(
                    play_surf,
                    color,
                    pygame.Rect(bx, cy - size, bw, size * 2),
                )

        if not self.is_ready:
            # Pulsing skeleton text
            pulse_alpha = int(155 + 100 * math.sin(self._pulse * 2))
            text_color = (pulse_alpha, pulse_alpha, min(255, pulse_alpha + 40))
            turn_txt = "Computing Optimal Drone Paths... Please wait"
            text_surf = font_body.render(turn_txt, True, text_color)
            _ = play_surf.blit(text_surf, (timeline_x, int(6 * us)))

            # Skeleton timeline
            _ = pygame.draw.rect(
                play_surf,
                BG_DARK,
                timeline_rect,
                border_radius=int(3 * us),
            )
            # draw a subtle loading bar sweep
            sweep_ratio = (pygame.time.get_ticks() % 2000) / 2000.0
            sweep_x = timeline_x + int(timeline_w * sweep_ratio)
            sweep_w = int(timeline_w * 0.15)
            if sweep_x + sweep_w > timeline_x + timeline_w:
                sweep_w = (timeline_x + timeline_w) - sweep_x
            _ = pygame.draw.rect(
                play_surf,
                (50, 50, 64),
                pygame.Rect(sweep_x, timeline_y, sweep_w, timeline_h),
                border_radius=int(3 * us),
            )
        else:
            if self._turn_index < 0:
                turn_txt = "Initial state (all drones at start)"
            else:
                turn_txt = f"Turn {self._turn_index + 1} / {len(self.turns)}"
                if self.turns:
                    moves = self.turns[self._turn_index]
                    turn_txt += f"  ·  {len(moves)} move{'s' if len(moves) != 1 else ''}"

            text_surf = font_body.render(turn_txt, True, ACCENT_HI)
            _ = play_surf.blit(text_surf, (timeline_x, int(6 * us)))

            _ = pygame.draw.rect(
                play_surf,
                BG_DARK,
                timeline_rect,
                border_radius=int(3 * us),
            )

            if self.turns:
                ratio = (self._turn_index + 1) / len(self.turns)
                fill_w = int(timeline_w * ratio)
                if fill_w > 0:
                    _ = pygame.draw.rect(
                        play_surf,
                        ACCENT,
                        pygame.Rect(
                            timeline_x, timeline_y, fill_w, timeline_h
                        ),
                        border_radius=int(3 * us),
                    )

                for i in range(len(self.turns)):
                    tx = timeline_x + int(
                        timeline_w * (i + 1) / len(self.turns)
                    )
                    _ = pygame.draw.line(
                        play_surf,
                        BG_PANEL,
                        (tx, timeline_y),
                        (tx, timeline_y + timeline_h),
                        1,
                    )

        text_surf = font_body.render("Speed", True, TEXT_SEC)
        _ = play_surf.blit(text_surf, (speed_x, speed_y - int(2 * us)))

        _ = pygame.draw.rect(
            play_surf,
            BG_DARK,
            speed_slider_rect,
            border_radius=int(3 * us),
        )
        if not self.is_ready:
            speed_ratio = 0.25
            handle_color = TEXT_MUT
        else:
            speed_ratio = (self._speed_val - 100) / 1900.0
            slider_hover = speed_slider_rect.inflate(10, 10).collidepoint(
                px, py
            )
            handle_color = (
                ACCENT_HI if (slider_hover or self._dragging_speed) else ACCENT
            )

        hx = speed_slider_rect.x + int(speed_w * speed_ratio)
        hy = speed_slider_rect.y + speed_h // 2

        _ = pygame.draw.circle(play_surf, handle_color, (hx, hy), int(6 * us))

    def update_turns(self, turns: list[list[str]]) -> None:
        """Called by the background thread when solving is complete."""
        self.turns = turns
        event = pygame.event.Event(SOLVER_FINISHED_EVENT)
        pygame.event.post(event)


if __name__ == "__main__":
    mock_zones: list[ZoneData] = [
        {
            "name": "hub0",
            "x": 1,
            "y": 1,
            "color": "green",
            "zone_type": "start",
            "max_drones": 5,
        },
        {
            "name": "goal",
            "x": 10,
            "y": 7,
            "color": "yellow",
            "zone_type": "end",
            "max_drones": 5,
        },
        {
            "name": "roof1",
            "x": 3,
            "y": 4,
            "color": "red",
            "zone_type": "restricted",
            "max_drones": 1,
        },
        {
            "name": "roof2",
            "x": 6,
            "y": 2,
            "color": "blue",
            "zone_type": "normal",
            "max_drones": 1,
        },
        {
            "name": "corridorA",
            "x": 4,
            "y": 3,
            "color": "green",
            "zone_type": "priority",
            "max_drones": 2,
        },
        {
            "name": "tunnelB",
            "x": 7,
            "y": 4,
            "color": "red",
            "zone_type": "restricted",
            "max_drones": 1,
        },
    ]

    mock_connections: list[tuple[str, str]] = [
        ("hub0", "roof1"),
        ("hub0", "corridorA"),
        ("roof1", "roof2"),
        ("roof2", "goal"),
        ("corridorA", "tunnelB"),
        ("tunnelB", "goal"),
    ]

    mock_turns: TurnLog = [
        ["D1-roof1", "D2-corridorA"],
        ["D1-roof2", "D2-tunnelB"],
        ["D1-goal", "D2-goal"],
    ]

    app = DroneVisualizer(mock_zones, mock_connections, mock_turns)
    app.run()
