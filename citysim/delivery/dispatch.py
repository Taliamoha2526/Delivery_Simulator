"""Dispatch: which waiting request goes to which available driver."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Sequence
from citysim.agents.car import Driver
from citysim.registry import Registry
from citysim.delivery.request import Request

if TYPE_CHECKING:
    from citysim.sim.simulation import Simulation

DISPATCHERS = Registry("dispatcher")

class Dispatcher(ABC):
    def reset(self) -> None:
        """Called when the simulation resets."""

    @abstractmethod
    def assign(self, waiting: Sequence[Request], available: Sequence[Driver],
               sim: "Simulation") -> list[tuple[Request, Driver]]:
        """Return (request, driver) pairs."""


@DISPATCHERS.register("nearest")
class NearestDriverDispatcher(Dispatcher):
    """Oldest request first; give it the available driver closest to the pickup."""

    def __init__(self, **_params):
        pass

    def assign(self, waiting, available, sim):
        pool = list(available)
        pairs = []
        ctx = sim.routing_context()
        for request in waiting:
            if not pool:
                break
            best = min(pool, key=lambda d: (sim.router.cost(d.car.head_node, request.pickup_node, ctx), d.id))
            pool.remove(best)
            pairs.append((request, best))
        return pairs


@DISPATCHERS.register("first_available")
class FirstAvailableDispatcher(Dispatcher):
    """Oldest request first; give it the lowest id available driver."""

    def __init__(self, **_params):
        pass

    def assign(self, waiting, available, sim):
        return list(zip(waiting, sorted(available, key=lambda d: d.id)))
