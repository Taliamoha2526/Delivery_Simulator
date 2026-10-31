"""The set of drivers (each with a car)."""
import random
from citysim.city.network import RoadNetwork
from citysim.agents.car import Car, Driver

class Fleet:
    def __init__(self, drivers: list[Driver]):
        self.drivers = drivers
        self._by_car = {d.car.id: d for d in drivers}

    @classmethod
    def create(cls, count: int, network: RoadNetwork, rng: random.Random) -> "Fleet":
        """Create cars traffic at random intersections."""
        node_ids = sorted(network.intersections)
        drivers = []
        for i in range(count):
            node = node_ids[rng.randrange(len(node_ids))]
            x, y = network.position(node)
            drivers.append(Driver(i, Car(id=i, parked_node=node, x=x, y=y)))
        return cls(drivers)

    @property
    def cars(self) -> list[Car]:
        return [d.car for d in self.drivers]

    def available(self) -> list[Driver]:
        return [d for d in self.drivers if d.available]

    def busy(self) -> list[Driver]:
        return [d for d in self.drivers if not d.available]

    def driver_for_car(self, car_id: int) -> Driver:
        return self._by_car[car_id]
