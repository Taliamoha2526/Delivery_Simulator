"""Scene renderer: turns the static city and a snapshot into drawing calls."""

from dataclasses import dataclass
from src.city.city import City
from src.city.city import Direction
from src.sim.snapshot import CarView, SimSnapshot
from src.render.surface import Surface

# Palette configuration
LAWN = "#dfe6d6"
ROAD = "#4b5058"
ROAD_LINE = "#8b919a"
HOUSE_FILL, HOUSE_EDGE = "#dcc7a6", "#a88c66"
PICKUP, PICKUP_FILL = "#ec7a14", "#f9dcb8"
DROPOFF, DROPOFF_FILL = "#2f78de", "#cfe0f8"
LIGHT_GREEN, LIGHT_RED, LIGHT_EDGE = "#2fd46f", "#e5484d", "#1d2025"
TASK_COLORS = {"idle": "#ffffff", "to_pickup": PICKUP, "to_dropoff": "#1fa35a"}
PANEL_BG, PANEL_FG, PANEL_DIM = "#1e2228", "#e8eaed", "#8e96a1"
DRIVER_COLORS = ["#e6194b", "#3b6fe0", "#8e44ad", "#d35400", "#16a085", "#7f5539",
                 "#c2185b", "#00838f", "#6d4c9f", "#a0522d", "#2e7d32", "#455a64"]
TERRAIN = {"HILL": ("#b9a98c", "#8f7f63"), "FOREST": ("#8fb27a", "#4f7a3f"), "LAKE": ("#9cc3e0", "#5b93bd")}
BUILDING_COLORS = {"SHOP": "#e3a6b8", "WAREHOUSE": "#b7bcc4", "SCHOOL": "#f2d98a", "OFFICE": "#a9b9e6"}
BUILDING_LETTER = {"SHOP": "S", "WAREHOUSE": "W", "SCHOOL": "E", "OFFICE": "O"}
WALL_COLOR, CLOSED_COLOR = "#6b3f2e", "#d9534f"


def driver_color(driver_id: int) -> str:
    return DRIVER_COLORS[driver_id % len(DRIVER_COLORS)]


def _lighten(hex_color: str, amount: float = 0.55) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    r, g, b = (round(c + (255 - c) * amount) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def format_clock(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


@dataclass
class RenderOptions:
    show_routes: bool = True
    show_labels: bool = True
    panel_width: int = 330


class SceneRenderer:
    def __init__(self, city: City, options: RenderOptions | None = None):
        self.city = city
        self.options = options or RenderOptions()
        self.width = self.height = 0
        self.scale = 1.0
        self.ox = self.oy = 0.0
        self.road_px = 10.0
        self._approaches: dict[int, list[Direction]] = {}
        for node in city.network.intersections:
            self._approaches[node] = [r.direction.opposite for r in city.network.incoming(node)]

    def layout(self, width: int, height: int) -> None:
        """Fit the city into the area left of the HUD panel."""
        self.width, self.height = width, height
        map_w = max(width - self.options.panel_width, 100)
        margin = 28
        c = self.city
        self.scale = max(min((map_w - 2 * margin) / max(c.width_m, 1), (height - 2 * margin) / max(c.height_m, 1)), 0.05)
        self.ox = (map_w - c.width_m * self.scale) / 2
        self.oy = (height - c.height_m * self.scale) / 2
        self.road_px = max(c.config.road_width * self.scale * 1.25, 12.0)

    def sx(self, x: float) -> float:
        return self.ox + x * self.scale

    def sy(self, y: float) -> float:
        return self.oy + y * self.scale

    def _draw_terrain(self, surface: Surface) -> None:
        for t in self.city.terrain:
            fill, edge = TERRAIN[t.kind.value]
            x0, y0, x1, y1 = self.sx(t.x0), self.sy(t.y0), self.sx(t.x1), self.sy(t.y1)
            surface.rect(x0, y0, x1, y1, fill=fill)
            cx, cy, w = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0)
            if t.kind.value == "HILL":
                for dx, s in ((-0.18, 0.30), (0.14, 0.38)):
                    surface.polygon([(cx + w * dx - w * s, cy + w * 0.22), (cx + w * dx, cy - w * s * 1.1),
                                     (cx + w * dx + w * s, cy + w * 0.22)], fill=edge, outline="#6f6249")
            elif t.kind.value == "FOREST":                             # a few trees
                for dx, dy in ((-0.22, -0.18), (0.2, -0.2), (0, 0.02), (-0.2, 0.22), (0.22, 0.2)):
                    r = w * 0.13
                    surface.ellipse(cx + w * dx - r, cy + w * dy - r, cx + w * dx + r, cy + w * dy + r,
                                    fill=edge, outline="#35592b")
            else:                                                      # lake
                surface.ellipse(x0 + w * 0.12, y0 + w * 0.2, x1 - w * 0.12, y1 - w * 0.2, fill=edge,
                                outline="#3f7399", width=2)

    def _draw_buildings_and_barriers(self, surface: Surface) -> None:
        for b in self.city.buildings:
            hw, hh = b.width * self.scale / 2, b.height * self.scale / 2
            x, y = self.sx(b.x), self.sy(b.y)
            surface.rect(x - hw, y - hh, x + hw, y + hh, fill=BUILDING_COLORS[b.kind.value], outline="#6c6f76", width=2)
            surface.text(x, y, BUILDING_LETTER[b.kind.value], "#3a3d44", size=int(max(min(hw, hh) * 0.9, 9)), anchor="center", bold=True)
        net = self.city.network
        for br in self.city.barriers:
            ax, ay = self.sx(net.intersections[br.a].x), self.sy(net.intersections[br.a].y)
            bx, by = self.sx(net.intersections[br.b].x), self.sy(net.intersections[br.b].y)
            wall = br.kind.value == "WALL"
            surface.line([(ax, ay), (bx, by)], fill=WALL_COLOR if wall else CLOSED_COLOR,
                         width=max(self.road_px * (0.45 if wall else 0.35), 3))
            if not wall:
                surface.text((ax + bx) / 2, (ay + by) / 2, "x", "#ffffff", size=int(max(self.road_px, 10)), anchor="center", bold=True)
    def draw_frame(self, surface: Surface, snap: SimSnapshot) -> None:
        self.draw_static(surface)
        self.draw_dynamic(surface, snap)

    def draw_static(self, surface: Surface) -> None:
        surface.begin("static")
        c, net, rw = self.city, self.city.network, self.road_px
        pad = rw / 2 + 10
        surface.rect(self.sx(0) - pad, self.sy(0) - pad, self.sx(c.width_m) + pad,
                     self.sy(c.height_m) + pad, fill=LAWN)
        self._draw_terrain(surface)
        drawn = set()
        for (a, b), road in net.roads.items():
            if (b, a) in drawn:
                continue
            drawn.add((a, b))
            ax, ay = self.sx(net.intersections[a].x), self.sy(net.intersections[a].y)
            bx, by = self.sx(net.intersections[b].x), self.sy(net.intersections[b].y)
            surface.rect(min(ax, bx) - rw / 2, min(ay, by) - rw / 2, max(ax, bx) + rw / 2, max(ay, by) + rw / 2, fill=ROAD)
            surface.line([(ax, ay), (bx, by)], fill=ROAD_LINE, width=1, dash=True)
        for n in net.intersections.values():
            x, y = self.sx(n.x), self.sy(n.y)
            surface.rect(x - rw / 2, y - rw / 2, x + rw / 2, y + rw / 2, fill=ROAD)
        h = c.config.house_size * self.scale / 2
        for house in c.houses:
            x, y = self.sx(house.x), self.sy(house.y)
            surface.rect(x - h, y - h, x + h, y + h, fill=HOUSE_FILL, outline=HOUSE_EDGE, width=1)
        self._draw_buildings_and_barriers(surface)
        surface.rect(self.width - self.options.panel_width, 0, self.width, self.height, fill=PANEL_BG)

    def draw_dynamic(self, surface: Surface, snap: SimSnapshot) -> None:
        surface.begin("dynamic")
        self._draw_requests(surface, snap)
        if self.options.show_routes:
            self._draw_routes(surface, snap)
        self._draw_lights(surface, snap)
        self._draw_cars(surface, snap)
        self._draw_hud(surface, snap)

    def _draw_requests(self, surface: Surface, snap: SimSnapshot) -> None:
        city = self.city
        h = city.config.house_size * self.scale / 2
        for r in snap.requests:
            picked = r.status in ("PICKED_UP", "EN_ROUTE_TO_DESTINATION")
            px, py = self.sx(r.pickup_xy[0]), self.sy(r.pickup_xy[1])
            dx, dy = self.sx(r.dropoff_xy[0]), self.sy(r.dropoff_xy[1])
            if not picked:
                surface.line([(px, py), (dx, dy)], fill="#a3a9b1", width=1, dash=True)
        for r in snap.requests:
            picked = r.status in ("PICKED_UP", "EN_ROUTE_TO_DESTINATION")
            px, py = self.sx(r.pickup_xy[0]), self.sy(r.pickup_xy[1])
            dx, dy = self.sx(r.dropoff_xy[0]), self.sy(r.dropoff_xy[1])
            if not picked:
                surface.rect(px - h, py - h, px + h, py + h, fill=PICKUP_FILL, outline=PICKUP, width=2)
                self._marker(surface, px, py, PICKUP, f"{r.request_id}", round_shape=True, hollow=False)
            surface.rect(dx - h, dy - h, dx + h, dy + h, fill=DROPOFF_FILL, outline=DROPOFF, width=2)
            self._marker(surface, dx, dy, DROPOFF, f"{r.request_id}", round_shape=False, hollow=not picked)

    def _marker(self, surface, x, y, color, label, round_shape, hollow):
        r = max(self.city.config.house_size * self.scale * 0.42, 6.0)
        fill = "#ffffff" if hollow else color
        text_color = color if hollow else "#ffffff"
        if round_shape:
            surface.ellipse(x - r, y - r, x + r, y + r, fill=fill, outline=color, width=2)
        else:
            surface.polygon([(x, y - r * 1.15), (x + r * 1.15, y), (x, y + r * 1.15), (x - r * 1.15, y)], fill=fill, outline=color, width=2)
        surface.text(x, y, label, text_color, size=int(max(r * 1.1, 8)), anchor="center", bold=True)

    def _draw_routes(self, surface: Surface, snap: SimSnapshot) -> None:
        for car in snap.cars:
            if len(car.route) >= 2:
                pts = [(self.sx(x), self.sy(y)) for x, y in car.route]
                surface.line(pts, fill=_lighten(driver_color(car.driver_id), 0.35), width=2, dash=True)

    def _draw_lights(self, surface: Surface, snap: SimSnapshot) -> None:
        rw = self.road_px
        d, lane, r = rw / 2 + 4, rw * 0.25, max(rw * 0.2, 2.6)
        for light in snap.lights:
            cx, cy = self.sx(light.x), self.sy(light.y)
            for side in self._approaches[light.node]:
                ox, oy = {Direction.W: (-d, lane), Direction.E: (d, -lane),
                          Direction.N: (-lane, -d), Direction.S: (lane, d)}[side]
                colour = light.ew if side in (Direction.W, Direction.E) else light.ns
                surface.ellipse(cx + ox - r, cy + oy - r, cx + ox + r, cy + oy + r,
                                fill=LIGHT_GREEN if colour == "GREEN" else LIGHT_RED, outline=LIGHT_EDGE, width=1)

    def _car_polygon(self, car: CarView):
        length = max(min(self.scale * 15, 22), 14)
        width = length * 0.58
        d = Direction[car.heading]
        fx, fy = d.dx, d.dy
        rx, ry = -d.dy, d.dx
        lane = self.road_px * 0.24
        cx = self.sx(car.x) + rx * lane
        cy = self.sy(car.y) + ry * lane
        hl, hw = length / 2, width / 2
        return [(cx + fx * hl + rx * hw, cy + fy * hl + ry * hw),
                (cx + fx * hl - rx * hw, cy + fy * hl - ry * hw),
                (cx - fx * hl - rx * hw, cy - fy * hl - ry * hw),
                (cx - fx * hl + rx * hw, cy - fy * hl + ry * hw)], (cx, cy)

    def _draw_cars(self, surface: Surface, snap: SimSnapshot) -> None:
        for car in snap.cars:
            colour = driver_color(car.driver_id)
            if car.state == "PARKED":
                x, y = self.sx(car.x), self.sy(car.y)
                s = max(self.road_px * 0.36, 4.5)
                surface.rect(x - s, y - s, x + s, y + s, fill=_lighten(colour, 0.45), outline=colour, width=2)
                cx, cy = x, y
            else:
                poly, (cx, cy) = self._car_polygon(car)
                surface.polygon(poly, fill=colour, outline="#101114", width=1)
            surface.ellipse(cx - 2.2, cy - 2.2, cx + 2.2, cy + 2.2, fill=TASK_COLORS[car.task],
                            outline="#101114", width=1)
            if self.options.show_labels:
                surface.text(cx, cy - 11, str(car.driver_id), "#15171a", size=10, anchor="s", bold=True)

    def _draw_hud(self, surface: Surface, snap: SimSnapshot) -> None:
        x0 = self.width - self.options.panel_width + 16
        y = 14
        m = snap.metrics

        def line(s, fill=PANEL_FG, size=13, bold=False, gap=4):
            nonlocal y
            surface.text(x0, y, s, fill, size=size, bold=bold, mono=True)
            y += size + gap

        status = "FINISHED" if snap.finished else ("RUNNING" if snap.running else "PAUSED")
        line("CITY DELIVERY SIM", size=16, bold=True, gap=8)
        line(f"time   {format_clock(snap.time)}  / {format_clock(snap.duration)}")
        line(f"state  {status}   speed x{snap.speed:g}")
        line(f"tick {snap.tick}   seed {snap.seed}", PANEL_DIM, 12, 10)
        line("REQUESTS", PANEL_DIM, 12, 2)
        line(f"waiting   {m['requests_waiting']:>4}")
        line(f"active    {m['requests_active']:>4}")
        line(f"completed {m['requests_completed']:>4}", gap=8)
        line("DRIVERS", PANEL_DIM, 12, 2)
        line(f"available {m['drivers_available']:>4}")
        line(f"busy      {m['drivers_busy']:>4}", gap=8)
        line("METRICS", PANEL_DIM, 12, 2)
        avg = m["avg_completion_time"]
        line(f"avg delivery  {avg:6.1f} s" if avg is not None else "avg delivery     -  s")
        line(f"distance  {m['total_distance_m'] / 1000:8.1f} km", gap=10)
        line("DRIVERS (id  task  request)", PANEL_DIM, 12, 3)
        room = int((self.height - y - 150) / 15)
        for car in snap.cars[:max(room, 0)]:
            rid = "-" if car.request_id is None else f"R{car.request_id}"
            surface.rect(x0, y + 1, x0 + 10, y + 11, fill=driver_color(car.driver_id))
            surface.text(x0 + 16, y, f"{car.driver_id:<3}{car.task:<11}{rid:<5}", PANEL_FG, size=12, mono=True)
            y += 15
        if len(snap.cars) > max(room, 0):
            line(f"... +{len(snap.cars) - max(room, 0)} more", PANEL_DIM, 12)

        y = self.height - 138
        line("LEGEND", PANEL_DIM, 12, 2)
        for colour, text in ((PICKUP, "pickup (house, order #)"), (DROPOFF, "destination"),
                             (TASK_COLORS["to_pickup"], "car dot: to pickup"),
                             (TASK_COLORS["to_dropoff"], "car dot: carrying")):
            surface.ellipse(x0, y + 2, x0 + 9, y + 11, fill=colour)
            surface.text(x0 + 16, y, text, PANEL_FG, size=12, mono=True)
            y += 15
        y += 4
        line("space run/pause  n step  r reset", PANEL_DIM, 11, 1)
        line("+/- speed   t routes   l labels", PANEL_DIM, 11, 1)
