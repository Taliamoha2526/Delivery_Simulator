"""A class registry is used for every replaceable strategy.
Strategies are selected by the name in the config.
"""

import importlib
from typing import Any, Callable


class Registry:
    def __init__(self, kind: str):
        self.kind = kind
        self._items: dict[str, type] = {}

    def register(self, name: str, *, replace: bool = False) -> Callable[[type], type]:
        def decorator(cls: type) -> type:
            if name in self._items and not replace:
                raise KeyError(f"{self.kind} '{name}' is already registered")
            self._items[name] = cls
            return cls

        return decorator

    def names(self) -> list[str]:
        return sorted(self._items)

    def get(self, name: str) -> type:
        if name in self._items:
            return self._items[name]
        if ":" in name:
            module_name, _, attr = name.partition(":")
            try:
                return getattr(importlib.import_module(module_name), attr)
            except (ImportError, AttributeError) as exc:
                raise KeyError(f"Cannot import {self.kind} '{name}': {exc}") from exc
        raise KeyError(f"Unknown {self.kind} '{name}'. Available: {self.names()} "
                       f"(or use 'module:Class')")

    def create(self, name: str, *args: Any, **kwargs: Any) -> Any:
        return self.get(name)(*args, **kwargs)
