"""Vehicle movement: the traffic rules, applied each timestep.
A car arrives with a route (list of intersections to be visited);
the engine moves it along the roads and enforces the physical rules:
- cars stay on the road graph and follow their route;
- never exceed min(vehicle_speed, road speed limit);
- stop at a red light and only cross on green;
- never get closer than car_length + min_gap to the car ahead;
- never enter a road whose entrance is still occupied to avoid collisions;
- at the end of its route a car pulls over and parks at that intersection.
"""

from dataclasses import dataclass
from citysim.agents.car import Car, MovementState
from citysim.city.network import EdgeKey, RoadNetwork
from citysim.config import TrafficConfig
from citysim.city.lights import TrafficLightSystem

_EPS = 1e-9


@dataclass(frozen=True)
class Arrival:
    car: Car
    node: int


class TrafficEngine:
    def __init__(self, network: RoadNetwork, lights: TrafficLightSystem, config: TrafficConfig):
        self.network = network
        self.lights = lights
        self.config = config
        self.spacing = config.car_length + config.min_gap
        # Queues represent cars on each road
        self.queues: dict[EdgeKey, list[Car]] = {key: [] for key in sorted(network.roads)}

    def cars_on(self, edge: EdgeKey) -> list[Car]:
        return self.queues[edge]

    def load(self, edge: EdgeKey) -> int:
        return len(self.queues[edge])

    def all_driving_cars(self) -> list[Car]:
        return [c for q in self.queues.values() for c in q]

    def step(self, cars: list[Car], dt: float) -> list[Arrival]:
        """Advance every car by dt seconds. Returns the cars that arrived."""
        arrivals: list[Arrival] = []
        moved: set[int] = set()

        for edge in self.queues:
            queue = self.queues[edge]
            if not queue:
                continue
            road = self.network.roads[edge]
            ahead_pos: float | None = None
            for car in list(queue):
                if car.id in moved:
                    ahead_pos = car.pos
                    continue
                stayed = self._advance(car, road, ahead_pos, dt, moved, arrivals)
                if stayed:
                    ahead_pos = car.pos

        for car in sorted(cars, key=lambda c: c.id):   # parked cars with a route pull out
            if car.is_parked and car.route and car.id not in moved:
                self._depart(car, moved)
        return arrivals

    def _advance(self, car: Car, road, ahead_pos, dt, moved, arrivals) -> bool:
        """Move one driving car. Returns True if it is still on road."""
        start = car.pos
        speed = min(self.config.vehicle_speed, road.speed_limit)
        target = start + speed * dt
        blocked_by = None

        if ahead_pos is not None:
            cap = ahead_pos - self.spacing
            if target > cap:
                target, blocked_by = max(start, cap), "traffic"

        stays = True
        if target >= road.length - _EPS:
            node = road.end
            # When the route is finished: arrive and park
            if not car.route:
                self._park(car, road, start, dt, arrivals)
                return False
            if not self.lights.is_green(node, road.direction.axis):
                target, blocked_by = min(target, road.length), "light"
            else:
                nxt = (node, car.route[0])
                next_queue = self.queues[nxt]
                room = (next_queue[-1].pos - self.spacing) if next_queue else float("inf")
                overshoot = target - road.length
                # The entrance of the next road is occupied
                if room < 0:
                    target, blocked_by = road.length, "traffic"
                else:
                    entered = min(overshoot, room)
                    self._transfer(car, road, nxt, entered, start, dt)
                    moved.add(car.id)
                    stays = False

        if stays:
            advance = target - start
            car.pos = target
            self._record(car, advance, dt, blocked_by)
            self._place(car)
        return stays

    def _transfer(self, car: Car, road, nxt: EdgeKey, entered: float, start: float, dt: float) -> None:
        self.queues[(road.start, road.end)].remove(car)
        next_road = self.network.roads[nxt]
        car.route.pop(0)
        car.edge, car.pos, car.direction = nxt, entered, next_road.direction
        self.queues[nxt].append(car)
        self._record(car, (road.length - start) + entered, dt, None)
        self._place(car)

    def _park(self, car: Car, road, start: float, dt: float, arrivals: list[Arrival]) -> None:
        self.queues[(road.start, road.end)].remove(car)
        advance = road.length - start
        car.edge, car.pos, car.parked_node = None, 0.0, road.end
        car.x, car.y = self.network.position(road.end)
        self._record(car, advance, dt, None)
        car.velocity, car.state = 0.0, MovementState.PARKED
        arrivals.append(Arrival(car, road.end))

    def _depart(self, car: Car, moved: set[int]) -> None:
        node = car.parked_node
        nxt = (node, car.route[0])
        queue = self.queues[nxt]
        # When the entrance is occupied, wait at the curb
        if queue and queue[-1].pos - self.spacing < 0:
            return
        road = self.network.roads[nxt]
        car.route.pop(0)
        car.edge, car.pos, car.parked_node = nxt, 0.0, None
        car.direction, car.velocity = road.direction, 0.0
        car.state = MovementState.MOVING
        queue.append(car)
        moved.add(car.id)
        self._place(car)

    def _record(self, car: Car, advance: float, dt: float, blocked_by: str | None) -> None:
        car.odometer += advance
        car.velocity = advance / dt
        if advance > _EPS:
            car.moving_time += dt
            car.state = MovementState.MOVING
        else:
            car.stopped_time += dt
            car.state = (MovementState.STOPPED_AT_LIGHT if blocked_by == "light"
                         else MovementState.STOPPED_IN_TRAFFIC)

    def _place(self, car: Car) -> None:
        start = self.network.intersections[car.edge[0]]
        d = car.direction
        car.x, car.y = start.x + d.dx * car.pos, start.y + d.dy * car.pos

    def find_collisions(self) -> list[tuple[int, int]]:
        """Pairs of cars on the same road closer than a car length(collided together).
        The check should always be empty."""
        bad = []
        for queue in self.queues.values():
            for front, back in zip(queue, queue[1:]):
                if front.pos - back.pos < self.config.car_length - 1e-6:
                    bad.append((front.id, back.id))
        return bad
