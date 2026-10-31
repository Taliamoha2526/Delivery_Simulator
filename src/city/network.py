"""The explicit road network: a directed graph of intersections and roads.
A road is one directed segment (one lane, one direction).
Every street between two neighbouring intersections is two way.
"""

from dataclasses import dataclass
from src.city.geometry import Direction

# Edge is represented by start intersection id, end intersection id
EdgeKey = tuple[int, int]


@dataclass(frozen=True)
class Intersection:
    id: int
    col: int
    row: int
    x: float
    y: float


@dataclass(frozen=True)
class Road:
    id: int
    start: int
    end: int
    length: float
    speed_limit: float
    direction: Direction

    @property
    def key(self) -> EdgeKey:
        return (self.start, self.end)


class RoadNetwork:
    def __init__(self) -> None:
        self.intersections: dict[int, Intersection] = {}
        self.roads: dict[EdgeKey, Road] = {}
        self._out: dict[int, list[int]] = {}
        self._in: dict[int, list[int]] = {}

    def add_intersection(self, node: Intersection) -> None:
        self.intersections[node.id] = node
        self._out.setdefault(node.id, [])
        self._in.setdefault(node.id, [])

    def add_road(self, road: Road) -> None:
        if road.start not in self.intersections or road.end not in self.intersections:
            raise KeyError("both ends of a road must be existing intersections")
        self.roads[road.key] = road
        self._out[road.start] = sorted(self._out[road.start] + [road.end])
        self._in[road.end] = sorted(self._in[road.end] + [road.start])

    def neighbors(self, node: int) -> list[int]:
        """Intersections reachable by one road."""
        return self._out[node]

    def incoming(self, node: int) -> list[Road]:
        return [self.roads[(u, node)] for u in self._in[node]]

    def outgoing(self, node: int) -> list[Road]:
        return [self.roads[(node, v)] for v in self._out[node]]

    def road(self, start: int, end: int) -> Road:
        return self.roads[(start, end)]

    def has_road(self, start: int, end: int) -> bool:
        return (start, end) in self.roads

    def position(self, node: int) -> tuple[float, float]:
        n = self.intersections[node]
        return (n.x, n.y)

    def node_at(self, col: int, row: int) -> int:
        for n in self.intersections.values():
            if n.col == col and n.row == row:
                return n.id
        raise KeyError((col, row))

    def degree(self, node: int) -> int:
        """Number of distinct neighbouring intersections."""
        return len(set(self._out[node]) | set(self._in[node]))

    def junction_type(self, node: int) -> str:
        """Shape of an intersection: isolated, dead_end, straight, corner, t_junction or crossing."""
        dirs = {self.roads[(node, v)].direction for v in self._out[node]}
        if len(dirs) == 0:
            return "isolated"
        if len(dirs) == 1:
            return "dead_end"
        if len(dirs) == 2:
            return "straight" if next(iter(dirs)).opposite in dirs else "corner"
        return "t_junction" if len(dirs) == 3 else "crossing"

    def components(self) -> list[set[int]]:
        """Groups of intersections joined by roads."""
        seen: set[int] = set()
        groups: list[set[int]] = []
        for start in sorted(self.intersections):
            if start in seen:
                continue
            group, stack = {start}, [start]
            while stack:
                node = stack.pop()
                for nxt in set(self._out[node]) | set(self._in[node]):
                    if nxt not in group:
                        group.add(nxt)
                        stack.append(nxt)
            seen |= group
            groups.append(group)
        groups.sort(key=lambda g: (-len(g), min(g)))
        return groups

    def is_strongly_connected(self) -> bool:
        """Every intersection can reach every other one."""
        if not self.intersections:
            return True
        start = next(iter(self.intersections))

        def reach(adj: dict[int, list[int]]) -> set[int]:
            seen, stack = {start}, [start]
            while stack:
                for nxt in adj[stack.pop()]:
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
            return seen

        everything = set(self.intersections)
        return reach(self._out) == everything and reach(self._in) == everything