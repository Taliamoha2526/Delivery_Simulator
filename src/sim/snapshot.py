"""Read only snapshots of simulation state.
This is the interface between the simulation and anything that displays it.
A snapshot is plain data so a renderer cannot manipulate the simulation details.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from src.city.geometry import Axis

if TYPE_CHECKING:
    from src.sim.simulation import Simulation


@dataclass(frozen=True)
class CarView:
    car_id: int
    driver_id: int
    x: float
    y: float
    heading: str
    velocity: float
    state: str
    task: str
    request_id: int | None
    destination: tuple[float, float] | None
    route: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class RequestView:
    request_id: int
    status: str
    driver_id: int | None
    pickup_house: int
    dropoff_house: int
    pickup_xy: tuple[float, float]
    dropoff_xy: tuple[float, float]
    created_at: float


@dataclass(frozen=True)
class LightView:
    node: int
    x: float
    y: float
    ns: str
    ew: str


@dataclass(frozen=True)
class SimSnapshot:
    time: float
    tick: int
    seed: int
    running: bool
    speed: float
    finished: bool
    duration: float
    cars: tuple[CarView, ...]
    requests: tuple[RequestView, ...]
    lights: tuple[LightView, ...]
    metrics: dict = field(default_factory=dict)


def build_snapshot(sim: "Simulation") -> SimSnapshot:
    net, city = sim.city.network, sim.city
    cars = []
    for driver in sim.fleet.drivers:
        car = driver.car
        route_pts: tuple[tuple[float, float], ...] = ()
        dest_xy = None
        if car.destination is not None:
            dest_xy = net.position(car.destination)
            pts = [(car.x, car.y)]
            if car.edge is not None:
                pts.append(net.position(car.edge[1]))
            elif car.route:
                pts.append(net.position(car.parked_node))
            pts.extend(net.position(n) for n in car.route)
            route_pts = tuple(pts)
        task = "idle" if driver.assignment is None else driver.assignment.phase.value.lower()
        cars.append(CarView(car.id, driver.id, car.x, car.y, car.direction.name, car.velocity,
                            car.state.value, task, driver.current_request_id, dest_xy, route_pts))

    requests = []
    for r in sim.delivery.active():
        p, d = city.house(r.pickup_house), city.house(r.dropoff_house)
        requests.append(RequestView(r.id, r.status.value, r.driver_id, p.id, d.id,
                                    (p.x, p.y), (d.x, d.y), r.created_at))

    lights = []
    for node_id, ctrl in sim.lights.controllers.items():
        n = net.intersections[node_id]
        state = sim.lights.state(node_id)
        lights.append(LightView(node_id, n.x, n.y, state[Axis.NS].value, state[Axis.EW].value))

    return SimSnapshot(time=sim.clock.time, tick=sim.clock.tick, seed=sim.seed, running=sim.clock.running,
        speed=sim.clock.speed, finished=sim.finished, duration=sim.config.simulation.duration,
        cars=tuple(cars), requests=tuple(requests), lights=tuple(lights), metrics=sim.metrics.summary(sim))

