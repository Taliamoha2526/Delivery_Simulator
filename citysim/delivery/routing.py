"""Routing interface.
A router answers one question given an origin and a destination intersection:
which sequence of intersections should a car follow?
Strategies receive RoutingContext with read only access to the network and live traffic information.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable
import heapq
from citysim.city.network import EdgeKey, RoadNetwork
from citysim.registry import Registry

ROUTERS = Registry("router")

class NoRouteError(RuntimeError):
    pass

@dataclass(frozen=True)
class Route:
    # Ordered by origin up to destination
    nodes: tuple[int, ...]
    # Cost is whatever the strategy minimised (metres for shortest path)
    cost: float


@dataclass
class RoutingContext:
    network: RoadNetwork
    time: float
    edge_load: Callable[[EdgeKey], int]
    lights: object | None = None


class Router(ABC):
    name = "router"

    def reset(self) -> None:
        """Called when the simulation resets."""

    @abstractmethod
    def route(self, origin: int, destination: int, ctx: RoutingContext) -> Route:
        """Return the route from origin to destination."""

    def cost(self, origin: int, destination: int, ctx: RoutingContext) -> float:
        """Estimated cost of travelling (used by dispatchers)."""
        return self.route(origin, destination, ctx).cost


@ROUTERS.register("shortest_path")
class ShortestPathRouter(Router):
    """Shortest path by distance."""

    name = "shortest_path"

    def __init__(self, **_params):
        self._trees: dict[int, tuple[dict[int, float], dict[int, int]]] = {}

    def reset(self) -> None:
        self._trees.clear()

    def _tree(self, origin: int, ctx: RoutingContext):
        if origin not in self._trees:
            dist = {origin: 0.0}
            prev: dict[int, int] = {}
            heap = [(0.0, origin)]
            while heap:
                d, u = heapq.heappop(heap)
                if d > dist.get(u, float("inf")):
                    continue
                for v in ctx.network.neighbors(u):
                    nd = d + ctx.network.road(u, v).length
                    if nd < dist.get(v, float("inf")) - 1e-9:
                        dist[v], prev[v] = nd, u
                        heapq.heappush(heap, (nd, v))
            self._trees[origin] = (dist, prev)
        return self._trees[origin]

    def route(self, origin: int, destination: int, ctx: RoutingContext) -> Route:
        dist, prev = self._tree(origin, ctx)
        if destination not in dist:
            raise NoRouteError(f"no route from {origin} to {destination}")
        nodes = [destination]
        while nodes[-1] != origin:
            nodes.append(prev[nodes[-1]])
        nodes.reverse()
        return Route(tuple(nodes), dist[destination])
