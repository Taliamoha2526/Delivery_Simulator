"""The simulation: a thin orchestrator.
It builds the components, wires them together and calls them in a fixed order each timestep.
It has no dependency on the renderer, and runs headlessly as fast as Python allows.
"""

from typing import Callable
from citysim.agents.fleet import Fleet
from citysim.city.city import City, build_city
from citysim.sim.clock import SimClock
from citysim.config import SimConfig
from citysim.delivery.dispatch import DISPATCHERS, Dispatcher
from citysim.delivery.system import DeliverySystem
from citysim.sim.events import Event, EventBus
from citysim.agents.generators import (EVENT_GENERATORS, REQUEST_GENERATORS, EventGenerator,GenerationContext, RequestGenerator)
from citysim.sim.events import Metrics
from citysim.rng import RandomStreams
from citysim.delivery.routing import ROUTERS, Router, RoutingContext
from citysim.sim.snapshot import SimSnapshot, build_snapshot
from citysim.city.engine import TrafficEngine, TrafficLightSystem


class Simulation:
    def __init__(self, config: SimConfig | None = None, *, router: Router | None = None,
                 request_generator: RequestGenerator | None = None,
                 dispatcher: Dispatcher | None = None,
                 event_generators: list[EventGenerator] | None = None):
        self.config = (config or SimConfig()).copy().validate()
        self._injected = dict(router=router, request_generator=request_generator,
                              dispatcher=dispatcher, event_generators=event_generators)
        self._subscribers: list[tuple[str | None, Callable[[Event], None]]] = []
        self.city: City = build_city(self.config.city, self.config.traffic)
        self.clock = SimClock(self.config.simulation.dt, self.config.render.speed)
        self.reset()

    @property
    def seed(self) -> int:
        return self.streams.seed

    def reset(self, seed: int | None = None) -> None:
        """Return to t=0. With the same seed the run repeats exactly; pass a new seed to change it."""
        cfg = self.config
        if seed is not None:
            cfg.simulation.seed = seed
        self.clock.reset()
        self.streams = RandomStreams(cfg.simulation.seed)
        self.events = EventBus()
        self.lights = TrafficLightSystem(self.city.network, cfg.traffic)
        self.engine = TrafficEngine(self.city.network, self.lights, cfg.traffic)
        self.fleet = Fleet.create(cfg.drivers.num_drivers, self.city.network,self.streams.stream("fleet"))
        self.delivery = DeliverySystem(self.city, self.events)
        inj = self._injected
        self.router = inj["router"] or ROUTERS.create(cfg.routing.strategy, **cfg.routing.params)
        self.request_generator = inj["request_generator"] or REQUEST_GENERATORS.create(cfg.requests.generator, cfg.requests)
        self.dispatcher = inj["dispatcher"] or DISPATCHERS.create(cfg.dispatch.strategy,**cfg.dispatch.params)
        if inj["event_generators"] is not None:
            self.event_generators = list(inj["event_generators"])
        else:
            self.event_generators = [
                EVENT_GENERATORS.create(name, **cfg.events.params.get(name, {}))
                for name in cfg.events.generators]
        for part in (self.router, self.request_generator, self.dispatcher, *self.event_generators):
            part.reset()

        self.metrics = Metrics(cfg.simulation.metrics_sample_interval)
        self.metrics.attach(self)
        for event_type, handler in self._subscribers:
            self.events.subscribe(event_type, handler)

    def subscribe(self, event_type: str | None, handler: Callable[[Event], None]) -> None:
        """Listen for events. None listens to every event."""
        self._subscribers.append((event_type, handler))
        self.events.subscribe(event_type, handler)

    @property
    def finished(self) -> bool:
        return self.clock.time >= self.config.simulation.duration - 1e-9

    def routing_context(self) -> RoutingContext:
        return RoutingContext(self.city.network, self.clock.time, self.engine.load, self.lights)

    def snapshot(self) -> SimSnapshot:
        return build_snapshot(self)

    def step(self) -> None:
        """Advance the world by one dt."""
        # 1. Advance the clock
        t = self.clock.advance()
        dt = self.clock.dt
        # 2. Generate events
        ctx = GenerationContext(t, dt, self.streams.stream("requests"), self.city,self.delivery.active_count)
        for spec in self.request_generator.generate(ctx):
            self.delivery.submit(spec, t)
        for i, generator in enumerate(self.event_generators):
            generator.step(self, self.streams.stream(f"events.{i}"))
        # 3. Update traffic lights
        self.lights.update(dt)
        # 4. Assignments
        waiting, available = self.delivery.waiting(), self.fleet.available()
        if waiting and available:
            for request, driver in self.dispatcher.assign(waiting, available, self):
                self.delivery.assign(request, driver, t)
        # 5. Plan routes
        self._plan_routes(t)
        # 6. Move vehicles
        for arrival in self.engine.step(self.fleet.cars, dt):
            self.delivery.on_arrival(self.fleet.driver_for_car(arrival.car.id), arrival.node, t)
        # 7. Pickups adn deliveries
        self.metrics.update(self)
        # 8. Update metrics
    def _plan_routes(self, t: float) -> None:
        ctx = self.routing_context()
        for driver in self.fleet.drivers:
            car = driver.car
            while driver.route_dirty:
                driver.route_dirty = False
                if driver.destination is None:
                    car.clear_route()
                    break
                origin = car.head_node
                if car.is_parked and origin == driver.destination:
                    car.clear_route()
                    self.delivery.on_arrival(driver, origin, t)
                    continue
                route = self.router.route(origin, driver.destination, ctx)
                car.set_route(list(route.nodes[1:]), driver.destination)
