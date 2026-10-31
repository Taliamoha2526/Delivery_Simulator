"""The car: physical state of the car's movement.
Assignment & phase: note the current cycle phase(dropping/ picking)
Driver: the logic behind moving the car through intersection & routing.
"""

from dataclasses import dataclass, field
from enum import Enum
from citysim.city.geometry import Direction
from citysim.city.network import EdgeKey

class MovementState(str, Enum):
    PARKED = "PARKED"
    MOVING = "MOVING"
    STOPPED_AT_LIGHT = "STOPPED_AT_LIGHT"
    STOPPED_IN_TRAFFIC = "STOPPED_IN_TRAFFIC"

@dataclass
class Car:
    id: int
    parked_node: int | None            # intersection where it is parked (None while on a road)
    x: float
    y: float
    edge: EdgeKey | None = None        # current road (start, end) while driving
    pos: float = 0.0                   # metres travelled along the current road
    direction: Direction = Direction.E
    velocity: float = 0.0              # m/s along the road
    destination: int | None = None     # intersection the car is heading for
    route: list[int] = field(default_factory=list)   # intersections still to visit after the edge's end
    state: MovementState = MovementState.PARKED
    odometer: float = 0.0              # metres driven
    moving_time: float = 0.0           # seconds spent moving
    stopped_time: float = 0.0          # seconds spent on the road but stopped

    @property
    def is_parked(self) -> bool:
        return self.edge is None

    @property
    def head_node(self) -> int:
        """The intersection a route for this car must start from."""
        return self.parked_node if self.edge is None else self.edge[1]

    @property
    def road(self) -> EdgeKey | None:
        return self.edge

    def set_route(self, nodes_after_head: list[int], destination: int | None) -> None:
        self.route = list(nodes_after_head)
        self.destination = destination

    def clear_route(self) -> None:
        self.route = []
        self.destination = None


class AssignmentPhase(str, Enum):
    TO_PICKUP = "TO_PICKUP"
    TO_DROPOFF = "TO_DROPOFF"


@dataclass
class Assignment:
    request_id: int
    phase: AssignmentPhase

@dataclass
class Driver:
    def __init__(self, driver_id: int, car: Car):
        self.id = driver_id
        self.car = car
        self.assignment: Assignment | None = None
        self.destination: int | None = None     # intersection the driver wants to reach next
        self.route_dirty = False                # destination changed; the route must be recomputed
        self.deliveries_completed = 0
        self.busy_time = 0.0
        self.idle_time = 0.0

    @property
    def available(self) -> bool:
        return self.assignment is None

    @property
    def current_request_id(self) -> int | None:
        return None if self.assignment is None else self.assignment.request_id

    def set_destination(self, node: int | None) -> None:
        self.destination = node
        self.route_dirty = True
