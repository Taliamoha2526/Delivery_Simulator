"""Interfaces for things that inject demand or events into the simulation.
 RequestGenerator decides when delivery requests appear and where.
 EventGenerator is the hook for future stochastic events.
"""

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING
from src.city.city import City
from src.registry import Registry
from src.config import RequestsConfig
from src.rng import poisson

if TYPE_CHECKING:
    from src.sim.simulation import Simulation

REQUEST_GENERATORS = Registry("request generator")
EVENT_GENERATORS = Registry("event generator")


@dataclass(frozen=True)
class RequestSpec:
    pickup_house: int
    dropoff_house: int


@dataclass
class GenerationContext:
    time: float
    dt: float
    rng: random.Random
    city: City
    active_requests: int


class RequestGenerator(ABC):
    def reset(self) -> None:
        """Called when the simulation resets."""

    @abstractmethod
    def generate(self, ctx: GenerationContext) -> list[RequestSpec]:
        """Requests that appear during this timestep."""


class EventGenerator(ABC):
    def reset(self) -> None:
        """Called when the simulation resets."""

    @abstractmethod
    def step(self, sim: "Simulation", rng: random.Random) -> None:
        """Called once per timestep."""

@REQUEST_GENERATORS.register("random")
class RandomRequestGenerator(RequestGenerator):
    """New requests arrive as a Poisson process with requests.rate per second.
    Pickup and drop off are independent uniform draws over houses, resampled
    until they sit at different intersections."""

    def __init__(self, config: RequestsConfig):
        self.rate = config.rate

    def generate(self, ctx: GenerationContext) -> list[RequestSpec]:
        houses = ctx.city.houses
        if len({h.access_node for h in houses}) < 2:
            return []
        specs = []
        for _ in range(poisson(ctx.rng, self.rate * ctx.dt)):
            pickup = houses[ctx.rng.randrange(len(houses))]
            dropoff = houses[ctx.rng.randrange(len(houses))]
            while dropoff.access_node == pickup.access_node:
                dropoff = houses[ctx.rng.randrange(len(houses))]
            specs.append(RequestSpec(pickup.id, dropoff.id))
        return specs
