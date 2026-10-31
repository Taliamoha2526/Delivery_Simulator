"""A minimal publish/subscribe event bus.
Core systems publish facts ("request created", "delivery completed");
interested parties (metrics, loggers, future analysis code) subscribe.
"""

from typing import TYPE_CHECKING
from dataclasses import dataclass, field, asdict
from typing import Any, Callable


class EventType:
    REQUEST_CREATED = "request_created"
    REQUEST_ASSIGNED = "request_assigned"
    PICKUP_COMPLETED = "pickup_completed"
    DELIVERY_COMPLETED = "delivery_completed"
    DRIVER_AVAILABLE = "driver_available"


@dataclass(frozen=True)
class Event:
    time: float
    type: str
    data: dict[str, Any] = field(default_factory=dict)

Handler = Callable[[Event], None]

class EventBus:
    def __init__(self, keep_log: bool = False):
        self._handlers: dict[str | None, list[Handler]] = {}
        self.log: list[Event] | None = [] if keep_log else None

    def subscribe(self, event_type: str | None, handler: Handler) -> None:
        """Subscribe to one event type, or everything."""
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event_type: str, time: float, **data: Any) -> Event:
        event = Event(time=time, type=event_type, data=data)
        if self.log is not None:
            self.log.append(event)
        for handler in self._handlers.get(event_type, []):
            handler(event)
        for handler in self._handlers.get(None, []):
            handler(event)
        return event

if TYPE_CHECKING:   # pragma: no cover
    from citysim.sim.simulation import Simulation

@dataclass
class DeliveryRecord:
    request_id: int
    driver_id: int
    created_at: float
    assigned_at: float
    picked_up_at: float
    delivered_at: float

    @property
    def wait_time(self) -> float:
        return self.assigned_at - self.created_at

    @property
    def pickup_time(self) -> float:
        return self.picked_up_at - self.assigned_at

    @property
    def transit_time(self) -> float:
        return self.delivered_at - self.picked_up_at

    @property
    def completion_time(self) -> float:
        return self.delivered_at - self.created_at

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(wait_time=self.wait_time, pickup_time=self.pickup_time,
                 transit_time=self.transit_time, completion_time=self.completion_time)
        return d


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


class Metrics:
    def __init__(self, sample_interval: float = 0.0):
        self.sample_interval = sample_interval
        self.deliveries: list[DeliveryRecord] = []
        self.samples: list[dict] = []
        self._next_sample = 0.0
        self._sim: "Simulation | None" = None

    def attach(self, sim: "Simulation") -> None:
        self._sim = sim
        sim.events.subscribe(EventType.DELIVERY_COMPLETED, self._on_delivery)

    def _on_delivery(self, event: Event) -> None:
        request = self._sim.delivery.requests[event.data["request_id"]]
        self.deliveries.append(DeliveryRecord(
            request.id, request.driver_id, request.created_at, request.assigned_at,
            request.picked_up_at, request.delivered_at))

    # Per tick updating
    def update(self, sim: "Simulation") -> None:
        dt = sim.clock.dt
        for driver in sim.fleet.drivers:
            if driver.available:
                driver.idle_time += dt
            else:
                driver.busy_time += dt
        if self.sample_interval > 0 and sim.clock.time + 1e-9 >= self._next_sample:
            self.samples.append(self.current(sim))
            self._next_sample += self.sample_interval

    # Current report
    def current(self, sim: "Simulation") -> dict:
        """Instantaneous state of the world."""
        delivery, fleet = sim.delivery, sim.fleet
        return {"time": sim.clock.time,
            "tick": sim.clock.tick,
            "requests_created": delivery.created_count,
            "requests_waiting": len(delivery.waiting()),
            "requests_active": delivery.active_count,
            "requests_completed": len(delivery.completed),
            "drivers_available": len(fleet.available()),
            "drivers_busy": len(fleet.busy()),
            "total_distance_m": sum(d.car.odometer for d in fleet.drivers)}

    def summary(self, sim: "Simulation | None" = None) -> dict:
        sim = sim or self._sim
        out = self.current(sim)
        fleet = sim.fleet
        completion = [r.completion_time for r in self.deliveries]
        n = max(len(fleet.drivers), 1)
        elapsed = max(sim.clock.time, 1e-9)
        out.update({"avg_completion_time": _mean(completion),
            "max_completion_time": max(completion) if completion else None,
            "avg_wait_time": _mean([r.wait_time for r in self.deliveries]),
            "avg_pickup_time": _mean([r.pickup_time for r in self.deliveries]),
            "avg_transit_time": _mean([r.transit_time for r in self.deliveries]),
            "total_travel_time_s": sum(d.car.moving_time for d in fleet.drivers),
            "total_stopped_time_s": sum(d.car.stopped_time for d in fleet.drivers),
            "avg_distance_per_driver_m": out["total_distance_m"] / n,
            "driver_utilisation": sum(d.busy_time for d in fleet.drivers) / (n * elapsed),
            "per_driver": {d.id: {"distance_m": d.car.odometer, "travel_time_s": d.car.moving_time,
                       "stopped_time_s": d.car.stopped_time, "busy_time_s": d.busy_time,
                       "idle_time_s": d.idle_time, "deliveries": d.deliveries_completed}
                for d in fleet.drivers}})
        return out