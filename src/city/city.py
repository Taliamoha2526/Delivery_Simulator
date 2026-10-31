"""The static map: terrain, road network, houses and buildings. Built deterministically from config.

Intersections form a width x height grid, so there are (width-1) x (height-1) blocks .
Every block gets one kind:
    HOUSES    up to four house plots ( built with house_density)
    EMPTY     an empty lot: roads around it, nothing on it
    BUILDING  one large non house building (shop, warehouse, school, office)
    BLOCKED   inaccessible terrain (hill, forest, lake)

Streets run along block edges. A street is removed when:
- every block beside it is blocked,
- it is covered by a barrier ( a wall or a closed road)

Removing streets never disconnects the map.

Drivers pick up and drop off at access nodes (intersection at the corner of a block)
"""

from dataclasses import dataclass
from enum import Enum
from src.config import CityConfig, TrafficConfig
from src.city.geometry import Direction
from src.city.network import Intersection, Road, RoadNetwork
from src.rng import RandomStreams

# A block is represented by its column, row
Block = tuple[int, int]


class BlockKind(str, Enum):
    HOUSES = "HOUSES"
    EMPTY = "EMPTY"
    BUILDING = "BUILDING"
    BLOCKED = "BLOCKED"


class TerrainKind(str, Enum):
    HILL = "HILL"
    FOREST = "FOREST"
    LAKE = "LAKE"


class BuildingKind(str, Enum):
    SHOP = "SHOP"
    WAREHOUSE = "WAREHOUSE"
    SCHOOL = "SCHOOL"
    OFFICE = "OFFICE"


class BarrierKind(str, Enum):
    WALL = "WALL"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class House:
    id: int
    block: Block
    quadrant: tuple[int, int]     # (0|1, 0|1): west/east, north/south half of the block
    x: float
    y: float
    size: float
    access_node: int


@dataclass(frozen=True)
class Building:
    """A non house building doesn't get deliveries."""
    id: int
    kind: BuildingKind
    block: Block
    x: float                      # centre
    y: float
    width: float
    height: float
    access_node: int


@dataclass(frozen=True)
class Terrain:
    """Inaccessible ground covering one whole block."""
    block: Block
    kind: TerrainKind
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class Barrier:
    """A street between two intersections that is impassable in both directions."""
    a: int
    b: int
    kind: BarrierKind


class City:
    def __init__(self, config: CityConfig, network: RoadNetwork, houses: list[House],
                 buildings: list[Building] | None = None, terrain: list[Terrain] | None = None,
                 barriers: list[Barrier] | None = None,
                 block_kinds: dict[Block, BlockKind] | None = None):
        self.config = config
        self.network = network
        self.houses = houses
        self.houses_by_id = {h.id: h for h in houses}
        self.buildings = buildings or []
        self.buildings_by_id = {b.id: b for b in self.buildings}
        self.terrain = terrain or []
        self.barriers = barriers or []
        self.block_kinds = block_kinds or {}
        self.width_m = (config.width - 1) * config.block_length
        self.height_m = (config.height - 1) * config.block_length

    def house(self, house_id: int) -> House:
        return self.houses_by_id[house_id]

    def building(self, building_id: int) -> Building:
        return self.buildings_by_id[building_id]


def node_id(col: int, row: int, width: int) -> int:
    return row * width + col

Street = tuple[int, int]

def _all_streets(cfg: CityConfig) -> list[Street]:
    streets = []
    for row in range(cfg.height):
        for col in range(cfg.width):
            here = node_id(col, row, cfg.width)
            if col + 1 < cfg.width:
                streets.append((here, node_id(col + 1, row, cfg.width)))
            if row + 1 < cfg.height:
                streets.append((here, node_id(col, row + 1, cfg.width)))
    return streets


def _blocks_beside(street: Street, cfg: CityConfig) -> list[Block]:
    """The blocks that lie alongside a street."""
    (ac, ar), (bc, br) = (_col_row(street[0], cfg.width), _col_row(street[1], cfg.width))
    if ar == br:                               # horizontal: blocks above and below
        cands = [(min(ac, bc), ar - 1), (min(ac, bc), ar)]
    else:                                      # vertical: blocks left and right
        cands = [(ac - 1, min(ar, br)), (ac, min(ar, br))]
    return [(x, y) for x, y in cands if 0 <= x < cfg.width - 1 and 0 <= y < cfg.height - 1]


def _col_row(node: int, width: int) -> tuple[int, int]:
    return node % width, node // width


def _components(streets: set[Street]) -> list[set[int]]:
    """Connected groups of intersections."""
    adj: dict[int, list[int]] = {}
    for a, b in streets:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen: set[int] = set()
    groups = []
    for start in sorted(adj):
        if start in seen:
            continue
        group, stack = {start}, [start]
        while stack:
            for nxt in adj[stack.pop()]:
                if nxt not in group:
                    group.add(nxt)
                    stack.append(nxt)
        seen |= group
        groups.append(group)
    groups.sort(key=lambda g: (-len(g), min(g)))
    return groups


def _build_network(cfg: CityConfig, speed_limit: float, streets: set[Street]) -> RoadNetwork:
    net = RoadNetwork()
    for node in sorted({n for s in streets for n in s}):
        col, row = _col_row(node, cfg.width)
        net.add_intersection(Intersection(node, col, row, col * cfg.block_length, row * cfg.block_length))
    road_id = 0
    for a, b in sorted(streets):
        na, nb = net.intersections[a], net.intersections[b]
        direction = Direction.E if na.row == nb.row else Direction.S
        net.add_road(Road(road_id, a, b, cfg.block_length, speed_limit, direction))
        net.add_road(Road(road_id + 1, b, a, cfg.block_length, speed_limit, direction.opposite))
        road_id += 2
    return net


def build_network(cfg: CityConfig, speed_limit: float) -> RoadNetwork:
    """The plain, fully regular grid."""
    return _build_network(cfg, speed_limit, set(_all_streets(cfg)))


def _grow_terrain(rng, cfg: CityConfig) -> dict[Block, TerrainKind]:
    """Clumps of blocked blocks (hills, forests, lakes)."""
    nbx, nby = cfg.width - 1, cfg.height - 1
    target = round(cfg.blocked_fraction * nbx * nby)
    blocked: dict[Block, TerrainKind] = {}
    kinds = list(TerrainKind)
    attempts = 0
    while len(blocked) < target and attempts < 100 + 20 * target:
        attempts += 1
        seed = (rng.randrange(nbx), rng.randrange(nby))
        if seed in blocked:
            continue
        kind = kinds[rng.randrange(len(kinds))]
        size = max(1, min(target - len(blocked), cfg.blob_size + rng.randint(-1, 1)))
        blob = [seed]
        blocked[seed] = kind
        while len(blob) < size:
            frontier = sorted({(x + dx, y + dy) for x, y in blob for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                               if 0 <= x + dx < nbx and 0 <= y + dy < nby
                               and (x + dx, y + dy) not in blocked})
            if not frontier:
                break
            cell = frontier[rng.randrange(len(frontier))]
            blocked[cell] = kind
            blob.append(cell)
    return blocked


def _place_barriers(rng, cfg: CityConfig, streets: set[Street]) -> list[Barrier]:
    """Pick streets to wall off / close, without disconnecting the map."""
    ordered = sorted(streets)
    rng.shuffle(ordered)
    want = {BarrierKind.WALL: round(cfg.wall_fraction * len(streets)),
            BarrierKind.CLOSED: round(cfg.closed_road_fraction * len(streets))}
    barriers: list[Barrier] = []
    for kind in (BarrierKind.WALL, BarrierKind.CLOSED):
        placed = 0
        for street in ordered:
            if placed >= want[kind]:
                break
            if street not in streets:
                continue
            streets.discard(street)
            if len(_components(streets)) == 1 and {n for s in streets for n in s} >= set(street):
                barriers.append(Barrier(street[0], street[1], kind))
                placed += 1
            else:
                streets.add(street)
    return barriers


def _corners(block: Block) -> list[tuple[int, int]]:
    bx, by = block
    return [(bx, by), (bx + 1, by), (bx, by + 1), (bx + 1, by + 1)]


def _nearest_node(cfg: CityConfig, nodes: set[int], x: float, y: float, rng=None) -> int | None:
    """The existing intersection node closest to (x, y)."""
    best, best_d = [], None
    for node in sorted(nodes):
        col, row = _col_row(node, cfg.width)
        d = (col * cfg.block_length - x) ** 2 + (row * cfg.block_length - y) ** 2
        if best_d is None or d < best_d - 1e-9:
            best, best_d = [node], d
        elif abs(d - best_d) <= 1e-9:
            best.append(node)
    if not best:
        return None
    return best[0] if rng is None else best[rng.randrange(len(best))]


def build_city(cfg: CityConfig, traffic: TrafficConfig | None = None) -> City:
    traffic = traffic or TrafficConfig()
    streams = RandomStreams(cfg.layout_seed)
    nbx, nby = cfg.width - 1, cfg.height - 1
    L = cfg.block_length

    # 1. terrain, and the streets that survive it
    blocked = _grow_terrain(streams.stream("city.terrain"), cfg)
    streets = {s for s in _all_streets(cfg) if not all(b in blocked for b in _blocks_beside(s, cfg))}
    if not streets:
        raise ValueError("the map has no roads left; lower city.blocked_fraction")
    streets = set().union(*[{s for s in streets if s[0] in g and s[1] in g}
                            for g in _components(streets)[:1]])     # keep only the largest connected part

    # 2. walls and closed roads (without disconnecting the map)
    barriers = _place_barriers(streams.stream("city.barriers"), cfg, streets)
    network = _build_network(cfg, traffic.speed_limit, streets)
    nodes = set(network.intersections)

    # 3. what each remaining block holds
    rng = streams.stream("city.blocks")
    free = [(bx, by) for by in range(nby) for bx in range(nbx) if (bx, by) not in blocked]
    shuffled = list(free)
    rng.shuffle(shuffled)
    n_building = round(cfg.building_fraction * len(free))
    n_empty = round(cfg.empty_fraction * len(free))
    kinds: dict[Block, BlockKind] = {b: BlockKind.BLOCKED for b in blocked}
    for i, block in enumerate(shuffled):
        if i < n_building:
            kinds[block] = BlockKind.BUILDING
        elif i < n_building + n_empty:
            kinds[block] = BlockKind.EMPTY
        else:
            kinds[block] = BlockKind.HOUSES
    # A free block is one whose corner can not hold anything so must remain empty
    for block in free:
        if not any(node_id(c, r, cfg.width) in nodes for c, r in _corners(block)):
            kinds[block] = BlockKind.EMPTY

    terrain = [Terrain(b, k, b[0] * L, b[1] * L, (b[0] + 1) * L, (b[1] + 1) * L)
               for b, k in sorted(blocked.items(), key=lambda kv: (kv[0][1], kv[0][0]))]

    # 4. houses and buildings
    house_rng, build_rng = streams.stream("city.houses"), streams.stream("city.buildings")
    plots: list[House] = []
    buildings: list[Building] = []
    margin = 6.0
    inner = L - cfg.road_width
    for by in range(nby):
        for bx in range(nbx):
            kind = kinds.get((bx, by))
            corner_nodes = {node_id(c, r, cfg.width) for c, r in _corners((bx, by))} & nodes
            if kind == BlockKind.HOUSES:
                for q in range(4):
                    qx, qy = q % 2, q // 2
                    if house_rng.random() >= cfg.house_density:
                        continue
                    x, y = (bx + 0.25 + 0.5 * qx) * L, (by + 0.25 + 0.5 * qy) * L
                    node = _nearest_node(cfg, corner_nodes, x, y)
                    if node is not None:
                        plots.append(House(-1, (bx, by), (qx, qy), x, y, cfg.house_size, node))
            elif kind == BlockKind.BUILDING:
                shape = ("full", "wide", "tall")[build_rng.randrange(3)]
                bkind = list(BuildingKind)[build_rng.randrange(len(BuildingKind))]
                qx, qy = build_rng.randrange(2), build_rng.randrange(2)
                cx, cy = (bx + 0.5) * L, (by + 0.5) * L
                w = h = inner - 2 * margin
                if shape == "wide":
                    cy, h = (by + 0.25 + 0.5 * qy) * L, L / 2 - cfg.road_width / 2 - 2 * margin
                elif shape == "tall":
                    cx, w = (bx + 0.25 + 0.5 * qx) * L, L / 2 - cfg.road_width / 2 - 2 * margin
                node = _nearest_node(cfg, corner_nodes, cx, cy, build_rng)
                if node is not None:
                    buildings.append(Building(len(buildings), bkind, (bx, by), cx, cy, w, h, node))

    if cfg.num_houses is not None:
        if cfg.num_houses > len(plots):
            raise ValueError(f"num_houses={cfg.num_houses} but this map only has {len(plots)} house plots; "
                             "raise city.house_density or lower the blocked/empty/building fractions")
        keep = sorted(streams.stream("city.subset").sample(range(len(plots)), cfg.num_houses))
        plots = [plots[i] for i in keep]
    if not plots:
        raise ValueError("the map has no houses; raise city.house_density or lower the other fractions")
    if len({h.access_node for h in plots}) < 2:
        raise ValueError("the houses on this map share a single intersection, so no delivery trip is possible; "
                         "raise city.house_density or use a larger city")
    houses = [House(i, h.block, h.quadrant, h.x, h.y, h.size, h.access_node) for i, h in enumerate(plots)]

    return City(cfg, network, houses, buildings, terrain, barriers, kinds)