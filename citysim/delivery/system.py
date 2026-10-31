"""The delivery system: owns requests and moves them through the lifecycle.
Handles:
- Creation
- Assignment
- Pickup
- Delivery
"""

from citysim.agents.car import Assignment, AssignmentPhase, Driver
from citysim.city.city import City
from citysim.sim.events import EventBus, EventType
from citysim.agents.generators import RequestSpec
from citysim.delivery.request import Request, RequestStatus


class DeliverySystem:
    def __init__(self, city: City, events: EventBus):
        self.city = city
        self.events = events
        self.requests: dict[int, Request] = {}
        self._next_id = 0
        self._waiting: list[Request] = []          # FIFO
        self._in_progress: dict[int, Request] = {}
        self.completed: list[Request] = []

    def waiting(self) -> list[Request]:
        return list(self._waiting)

    def in_progress(self) -> list[Request]:
        return [self._in_progress[k] for k in sorted(self._in_progress)]

    def active(self) -> list[Request]:
        """Requests not yet delivered."""
        return self.waiting() + self.in_progress()

    @property
    def active_count(self) -> int:
        return len(self._waiting) + len(self._in_progress)

    @property
    def created_count(self) -> int:
        return self._next_id

    def submit(self, spec: RequestSpec, time: float) -> Request:
        pickup, dropoff = self.city.house(spec.pickup_house), self.city.house(spec.dropoff_house)
        request = Request(self._next_id, pickup.id, dropoff.id, pickup.access_node, dropoff.access_node, created_at=time)
        self._next_id += 1
        self.requests[request.id] = request
        request.advance(RequestStatus.WAITING, time)
        self._waiting.append(request)
        self.events.publish(EventType.REQUEST_CREATED, time, request_id=request.id)
        return request

    def assign(self, request: Request, driver: Driver, time: float) -> None:
        if not request.is_waiting:
            raise ValueError(f"request {request.id} is not waiting")
        if not driver.available:
            raise ValueError(f"driver {driver.id} is not available")
        self._waiting.remove(request)
        self._in_progress[request.id] = request
        request.driver_id = driver.id
        request.advance(RequestStatus.ASSIGNED, time)
        request.advance(RequestStatus.EN_ROUTE_TO_PICKUP, time)
        driver.assignment = Assignment(request.id, AssignmentPhase.TO_PICKUP)
        driver.set_destination(request.pickup_node)
        self.events.publish(EventType.REQUEST_ASSIGNED, time, request_id=request.id, driver_id=driver.id)

    def on_arrival(self, driver: Driver, node: int, time: float) -> None:
        """The driver's car is stopped at intersection """
        while driver.assignment is not None:
            request = self.requests[driver.assignment.request_id]
            if driver.assignment.phase == AssignmentPhase.TO_PICKUP and node == request.pickup_node:
                request.advance(RequestStatus.PICKED_UP, time)
                request.advance(RequestStatus.EN_ROUTE_TO_DESTINATION, time)
                driver.assignment.phase = AssignmentPhase.TO_DROPOFF
                driver.set_destination(request.dropoff_node)
                self.events.publish(EventType.PICKUP_COMPLETED, time, request_id=request.id, driver_id=driver.id)
            elif driver.assignment.phase == AssignmentPhase.TO_DROPOFF and node == request.dropoff_node:
                request.advance(RequestStatus.DELIVERED, time)
                del self._in_progress[request.id]
                self.completed.append(request)
                driver.assignment = None
                driver.deliveries_completed += 1
                driver.destination = None
                driver.route_dirty = False
                driver.car.clear_route()
                self.events.publish(EventType.DELIVERY_COMPLETED, time, request_id=request.id, driver_id=driver.id)
                self.events.publish(EventType.DRIVER_AVAILABLE, time, driver_id=driver.id)
            else:
                return
