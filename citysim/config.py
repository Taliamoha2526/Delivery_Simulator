"""Configuration layer.
Every tunable of the simulator is rooted at the SimConfig.
Every field has a sensible default.
Unknown keys are rejected so typos never pass silently.
"""

import copy
import json
import types
import typing
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Iterable, Union


class ConfigError(ValueError):
    """Raised for unknown keys, wrongly typed values or invalid settings."""


@dataclass
class CityConfig:
    width: int = 10
    height: int = 10
    block_length: float = 100.0
    road_width: float = 14.0
    house_size: float = 20.0
    num_houses: int | None = None
    layout_seed: int = 0
    blocked_fraction: float = 0.12
    blob_size: int = 4
    empty_fraction: float = 0.08
    building_fraction: float = 0.10
    house_density: float = 0.70
    wall_fraction: float = 0.04
    closed_road_fraction: float = 0.03

@dataclass
class TrafficConfig:
    light_strategy: str = "fixed_cycle"
    light_phase_duration: float = 15.0
    all_red_time: float = 1.0
    stagger_lights: bool = True
    vehicle_speed: float = 10.0
    speed_limit: float = 14.0
    car_length: float = 4.0
    min_gap: float = 2.0


@dataclass
class DriversConfig:
    num_drivers: int = 10


@dataclass
class RequestsConfig:
    generator: str = "random"
    rate: float = 0.05
    params: dict = field(default_factory=dict)


@dataclass
class DispatchConfig:
    strategy: str = "nearest"
    params: dict = field(default_factory=dict)


@dataclass
class RoutingConfig:
    strategy: str = "shortest_path"
    params: dict = field(default_factory=dict)


@dataclass
class EventsConfig:
    generators: list = field(default_factory=list)
    params: dict = field(default_factory=dict)


@dataclass
class SimulationConfig:
    dt: float = 0.5
    duration: float = 1800.0
    seed: int = 42
    metrics_sample_interval: float = 10.0


@dataclass
class RenderConfig:
    enabled: bool = True
    speed: float = 10.0
    fps: int = 30
    window_width: int = 1280
    window_height: int = 860


@dataclass
class SimConfig:
    city: CityConfig = field(default_factory=CityConfig)
    traffic: TrafficConfig = field(default_factory=TrafficConfig)
    drivers: DriversConfig = field(default_factory=DriversConfig)
    requests: RequestsConfig = field(default_factory=RequestsConfig)
    dispatch: DispatchConfig = field(default_factory=DispatchConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    events: EventsConfig = field(default_factory=EventsConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    render: RenderConfig = field(default_factory=RenderConfig)

    def validate(self) -> "SimConfig":
        c, t = self.city, self.traffic

        def need(ok: bool, msg: str) -> None:
            if not ok:
                raise ConfigError(msg)

        need(c.width >= 2 and c.height >= 2, "city.width and city.height must be >= 2")
        need(c.block_length > 0 and c.road_width > 0 and c.house_size > 0,
             "city.block_length, road_width and house_size must be > 0")
        need(c.house_size <= (c.block_length - c.road_width) / 2,
             "city.house_size is too large: four houses must fit inside one block "
             f"(max {(c.block_length - c.road_width) / 2:g} m for this block_length/road_width)")
        slots = 4 * (c.width - 1) * (c.height - 1)
        need(0 <= c.blocked_fraction <= 0.5, "city.blocked_fraction must be between 0 and 0.5")
        need(c.blob_size >= 1, "city.blob_size must be >= 1")
        need(c.empty_fraction >= 0 and c.building_fraction >= 0
             and c.empty_fraction + c.building_fraction <= 1,
             "city.empty_fraction and city.building_fraction must be >= 0 and sum to at most 1")
        need(0 <= c.house_density <= 1, "city.house_density must be between 0 and 1")
        need(c.wall_fraction >= 0 and c.closed_road_fraction >= 0
             and c.wall_fraction + c.closed_road_fraction <= 0.5,
             "city.wall_fraction and city.closed_road_fraction must be >= 0 and sum to at most 0.5")
        need(t.light_phase_duration > 0, "traffic.light_phase_duration must be > 0")
        need(t.all_red_time >= 0, "traffic.all_red_time must be >= 0")
        need(t.vehicle_speed > 0 and t.speed_limit > 0, "traffic.vehicle_speed and speed_limit must be > 0")
        need(t.car_length > 0 and t.min_gap >= 0, "traffic.car_length must be > 0 and min_gap >= 0")
        need(t.car_length + t.min_gap < c.block_length,
             "traffic.car_length + min_gap must be shorter than city.block_length")
        need(self.drivers.num_drivers >= 0, "drivers.num_drivers must be >= 0")
        need(self.requests.rate >= 0, "requests.rate must be >= 0")
        need(self.simulation.dt > 0, "simulation.dt must be > 0")
        need(self.simulation.duration >= 0, "simulation.duration must be >= 0")
        need(self.simulation.metrics_sample_interval >= 0, "simulation.metrics_sample_interval must be >= 0")
        need(self.render.speed > 0 and self.render.fps > 0, "render.speed and render.fps must be > 0")
        return self

    def to_dict(self) -> dict:
        return asdict(self)

    def copy(self) -> "SimConfig":
        return copy.deepcopy(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SimConfig":
        return _build(cls, data, "").validate()

    @classmethod
    def load(cls, path: str | Path) -> "SimConfig":
        with open(path, "r", encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    def save(self, path: str | Path) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)
            fh.write("\n")

    def with_overrides(self, overrides: Iterable[str] | dict[str, Any]) -> "SimConfig":
        """Return a new config with dotted overrides applied."""

        if isinstance(overrides, dict):
            items = list(overrides.items())
        else:
            items = []
            for text in overrides:
                if "=" not in text:
                    raise ConfigError(f"Override '{text}' must look like section.key=value")
                key, raw = text.split("=", 1)
                items.append((key.strip(), _parse_scalar(raw)))
        data = self.to_dict()
        for dotted, value in items:
            parts = dotted.split(".")
            node = data
            for i, part in enumerate(parts[:-1]):
                if not isinstance(node, dict) or (part not in node and i < 1):
                    raise ConfigError(f"Unknown config section '{'.'.join(parts[:i + 1])}'")
                node = node.setdefault(part, {})   # free-form dicts (params) may grow new keys
            if not isinstance(node, dict):
                raise ConfigError(f"Cannot set '{dotted}'")
            node[parts[-1]] = value
        return SimConfig.from_dict(data)


def _parse_scalar(raw: str) -> Any:
    raw = raw.strip()
    if raw.lower() in ("none", "null"):
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _build(cls: type, data: Any, path: str) -> Any:
    where = path or "<root>"
    if not isinstance(data, dict):
        raise ConfigError(f"Config section '{where}' must be an object, got {type(data).__name__}")
    hints = typing.get_type_hints(cls)
    names = [f.name for f in fields(cls)]
    unknown = sorted(set(data) - set(names))
    if unknown:
        raise ConfigError(f"Unknown config key(s) {unknown} in '{where}'. Valid keys: {names}")
    kwargs: dict[str, Any] = {}
    for name in names:
        if name not in data:
            continue
        hint, value = hints[name], data[name]
        full = f"{path}.{name}" if path else name
        if is_dataclass(hint):
            kwargs[name] = _build(hint, value, full)
        else:
            kwargs[name] = _coerce(hint, value, full)
    return cls(**kwargs)


def _coerce(hint: Any, value: Any, name: str) -> Any:
    origin, args = typing.get_origin(hint), typing.get_args(hint)
    if origin in (Union, types.UnionType):
        if value is None and type(None) in args:
            return None
        errors = []
        for arg in args:
            if arg is type(None):
                continue
            try:
                return _coerce(arg, value, name)
            except ConfigError as exc:
                errors.append(str(exc))
        raise ConfigError(errors[0] if errors else f"Invalid value for '{name}'")
    if hint is bool:
        if isinstance(value, bool):
            return value
        raise ConfigError(f"'{name}' must be true/false, got {value!r}")
    if hint is int:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
            raise ConfigError(f"'{name}' must be an integer, got {value!r}")
        return int(value)
    if hint is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"'{name}' must be a number, got {value!r}")
        return float(value)
    if hint is str:
        if not isinstance(value, str):
            raise ConfigError(f"'{name}' must be a string, got {value!r}")
        return value
    if hint is dict or origin is dict:
        if not isinstance(value, dict):
            raise ConfigError(f"'{name}' must be an object, got {value!r}")
        return value
    if hint is list or origin is list:
        if not isinstance(value, list):
            raise ConfigError(f"'{name}' must be a list, got {value!r}")
        return value
    return value
