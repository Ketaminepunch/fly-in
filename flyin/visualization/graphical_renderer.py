"""pg-based graphical view of the zone network and live drone positions."""

import pygame as pg

from flyin.model import Connection, Network

type_colors: dict[str, str] = {
    "restricted": "orange",
    "priority": "green",
    "normal": "blue",
    "blocked": "red",
}
DRONE_COLORS = ["yellow", "cyan", "magenta", "lime", "orange", "deeppink"]


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
        self.screen: pg.Surface = pg.display.set_mode((width, height))
        self.clock: pg.time.Clock = pg.time.Clock()
        self.font: pg.font.Font = pg.font.SysFont(None, 24)
        self.positions: dict[str, tuple[int, int]] = self.compute_positions(
            network, width, height, margin
        )
        self.connections: dict[str, Connection] = {
            connection.name: connection
            for connections in network.adjacency.values()
            for connection in connections
        }

    def compute_positions(
        self, network: Network, width: int, height: int, margin: int
    ) -> dict[str, tuple[int, int]]:
        xs = [zone.x for zone in network.zones.values()]
        ys = [zone.y for zone in network.zones.values()]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        x_span, y_span = x_max - x_min, y_max - y_min
        calced_positions: dict[str, tuple[int, int]] = {}
        for zone in network.zones.values():
            x, y = zone.x, zone.y
            if x_span == 0:
                x_pos = width // 2
            else:
                x_pos = int(
                    margin + (x - x_min) / x_span * ((width - margin) - margin)
                )
            if y_span == 0:
                y_pos = height // 2
            else:
                y_pos = int(
                    margin
                    + (y - y_min) / y_span * ((height - margin) - margin)
                )
            calced_positions[zone.name] = (x_pos, y_pos)
        return calced_positions

    def draw_network(self) -> None:
        self.screen.fill((57, 53, 61))
        all_connections = set()
        for connections in self.network.adjacency.values():
            for connection in connections:
                all_connections.add(connection)
        for connection in all_connections:
            pos1 = self.positions[connection.zone1_name]
            pos2 = self.positions[connection.zone2_name]
            pg.draw.line(self.screen, pg.Color("gray"), pos1, pos2)
        for zone in self.network.zones.values():
            zone_position = self.positions[zone.name]
            if zone.color == "none":
                body_color = pg.Color("gray")
            else:
                try:
                    body_color = pg.Color(zone.color)
                except ValueError:
                    body_color = pg.Color("gray")
            pg.draw.circle(self.screen, body_color, zone_position, 14)
            pg.draw.circle(
                self.screen,
                pg.Color(type_colors[zone.zone_type]),
                zone_position,
                14,
                3,
            )
            text_surface = self.font.render(zone.name, True, pg.Color("white"))
            text_rect = text_surface.get_rect(
                center=(zone_position[0], zone_position[1] + 14 + 12)
            )
            self.screen.blit(text_surface, text_rect)

    def draw_drones(self, current_positions: dict[int, str]) -> None:
        by_token: dict[str, list[int]] = {}
        for drone_id, token in current_positions.items():
            by_token.setdefault(token, []).append(drone_id)
        for token, drone_ids in by_token.items():
            if token in self.positions:
                drone_pos = self.positions[token]
            else:
                connection = self.connections[token]
                x1, y1 = self.positions[connection.zone1_name]
                x2, y2 = self.positions[connection.zone2_name]
                drone_pos = ((x1 + x2) // 2, (y1 + y2) // 2)
            base_pos = drone_pos
            for i, drone_id in enumerate(drone_ids):
                color = pg.Color(DRONE_COLORS[drone_id % len(DRONE_COLORS)])
                offset_x = (i - (len(drone_ids) - 1) / 2) * 16
                final_pos = int(base_pos[0] + offset_x), base_pos[1] + 20
                rect = pg.Rect(0, 0, 20, 14)
                rect.center = final_pos
                pg.draw.rect(self.screen, color, rect)
                text_surface = self.font.render(
                    str(drone_id), True, pg.Color("black")
                )
                text_rect = text_surface.get_rect(center=rect.center)
                self.screen.blit(text_surface, text_rect)

    def render(self, turn_log: list[dict[int, str]]) -> None:
        snapshots:list[dict[int,str]]=[]
        current_positions: dict[int, str] = {
            drone_id: self.network.start.name
            for drone_id in range(1, self.network.nb_drones + 1)
        }
        for turn in turn_log:
            current_positions=current_positions.copy()
            current_positions.update(turn)
            snapshots.append(current_positions)
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    pg.quit()
                    return
            self.draw_network()
            self.draw_drones(current_positions)
            pg.display.flip()
            self.clock.tick(2)
        pg.quit()
