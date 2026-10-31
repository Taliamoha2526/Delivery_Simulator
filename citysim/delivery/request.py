"""A delivery request and its lifecycle."""

from dataclasses import dataclass, field
from enum import Enum


class RequestStatus(str, Enum):
    CREATED = "CREATED"
    WAITING = "WAITING"
    ASSIGNED = "ASSIGNED"
    EN_ROUTE_TO_PICKUP = "EN_ROUTE_TO_PICKUP"
    PICKED_UP = "PICKED_UP"
    EN_ROUTE_TO_DESTINATION = "EN_ROUTE_TO_DESTINATION"
    DELIVERED = "DELIVERED"

_ORDER = list(RequestStatus)

@dataclass
class Request:
    id: int
    pickup_house: int
    dropoff_house: int
    pickup_node: int
    dropoff_node: int
    created_at: float
    status: RequestStatus = RequestStatus.CREATED
    driver_id: int | None = None
    history: list[tuple[float, RequestStatus]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.history.append((self.created_at, self.status))

    def advance(self, status: RequestStatus, time: float) -> None:
        """Move to the next lifecycle state."""
        if _ORDER.index(status) != _ORDER.index(self.status) + 1:
            raise ValueError(f"request {self.id}: illegal transition {self.status.value} -> {status.value}")
        self.status = status
        self.history.append((time, status))

    def time_of(self, status: RequestStatus) -> float | None:
        for t, s in self.history:
            if s == status:
                return t
        return None

    @property
    def assigned_at(self) -> float | None:
        return self.time_of(RequestStatus.ASSIGNED)

    @property
    def picked_up_at(self) -> float | None:
        return self.time_of(RequestStatus.PICKED_UP)

    @property
    def delivered_at(self) -> float | None:
        return self.time_of(RequestStatus.DELIVERED)

    @property
    def is_waiting(self) -> bool:
        return self.status == RequestStatus.WAITING

    @property
    def is_done(self) -> bool:
        return self.status == RequestStatus.DELIVERED
