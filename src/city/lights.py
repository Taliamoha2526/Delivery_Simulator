"""Traffic lights.
LightController is the interface one intersection's light implements.

FixedCycleController strategy: When North/South is green, then East/West is green,
  each for light_phase_duration seconds,
  optionally with a short all red clearance between phases.

TrafficLightSystem owns one controller per intersection and answers for the vehicle engine.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from src.city.geometry import Axis
from src.city.network import RoadNetwork
from src.config import TrafficConfig
from src.registry import Registry


class LightColor(str, Enum):
    GREEN = "GREEN"
    RED = "RED"


LIGHT_CONTROLLERS = Registry("light controller")


@dataclass(frozen=True)
class Phase:
    name: str
    ns: LightColor
    ew: LightColor
    duration: float

    def color_for(self, axis: Axis) -> LightColor:
        return self.ns if axis == Axis.NS else self.ew


class LightController(ABC):
    """Controls the light at one intersection."""

    def __init__(self, node: int):
        self.node = node

    @abstractmethod
    def update(self, dt: float) -> None:
        """Advance the controller by dt simulated seconds."""

    @abstractmethod
    def color_for(self, axis: Axis) -> LightColor:
        """Colour currently shown to traffic travelling along the axis."""

    def is_green(self, axis: Axis) -> bool:
        return self.color_for(axis) == LightColor.GREEN

    @property
    def phase_name(self) -> str:
        return ""


@LIGHT_CONTROLLERS.register("fixed_cycle")
class FixedCycleController(LightController):

    def __init__(self, node: int, config: TrafficConfig, offset: float = 0.0):
        super().__init__(node)
        green, red = config.light_phase_duration, config.all_red_time
        phases = [Phase("NS_GREEN", LightColor.GREEN, LightColor.RED, green)]
        if red > 0:
            phases.append(Phase("ALL_RED_1", LightColor.RED, LightColor.RED, red))
        phases.append(Phase("EW_GREEN", LightColor.RED, LightColor.GREEN, green))
        if red > 0:
            phases.append(Phase("ALL_RED_2", LightColor.RED, LightColor.RED, red))
        self.phases = phases
        self.cycle_length = sum(p.duration for p in phases)
        self.phase_index = 0
        self.timer = 0.0          # seconds spent in the current phase
        self.update(offset % self.cycle_length)

    @property
    def phase(self) -> Phase:
        return self.phases[self.phase_index]

    @property
    def phase_name(self) -> str:
        return self.phase.name

    @property
    def phase_duration(self) -> float:
        return self.phase.duration

    def update(self, dt: float) -> None:
        self.timer += dt
        while self.timer >= self.phase.duration:
            self.timer -= self.phase.duration
            self.phase_index = (self.phase_index + 1) % len(self.phases)

    def color_for(self, axis: Axis) -> LightColor:
        return self.phase.color_for(axis)


class TrafficLightSystem:
    """One controller per intersection, updated together."""

    def __init__(self, network: RoadNetwork, config: TrafficConfig):
        self.config = config
        self.controllers: dict[int, LightController] = {}
        for node in network.intersections.values():
            self.controllers[node.id] = self._make(node.col, node.row, node.id)

    def _make(self, col: int, row: int, node: int) -> LightController:
        cls = LIGHT_CONTROLLERS.get(self.config.light_strategy)
        offset = 0.0
        if self.config.stagger_lights and (col + row) % 2 == 1:
            offset = self.config.light_phase_duration + self.config.all_red_time
        return cls(node, self.config, offset)

    def update(self, dt: float) -> None:
        for controller in self.controllers.values():
            controller.update(dt)

    def is_green(self, node: int, axis: Axis) -> bool:
        return self.controllers[node].is_green(axis)

    def state(self, node: int) -> dict[Axis, LightColor]:
        c = self.controllers[node]
        return {Axis.NS: c.color_for(Axis.NS), Axis.EW: c.color_for(Axis.EW)}
