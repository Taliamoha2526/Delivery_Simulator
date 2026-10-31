from enum import Enum

class Axis(str, Enum):
    NS = "NS"
    EW = "EW"

class Direction(Enum):
    N = (0, -1)
    E = (1, 0)
    S = (0, 1)
    W = (-1, 0)

    @property
    def dx(self) -> int:
        return self.value[0]

    @property
    def dy(self) -> int:
        return self.value[1]

    @property
    def axis(self) -> Axis:
        return Axis.NS if self in (Direction.N, Direction.S) else Axis.EW

    @property
    def opposite(self) -> "Direction":
        return Direction((-self.dx, -self.dy))

    @classmethod
    def from_delta(cls, dx: float, dy: float) -> "Direction":
        if abs(dx) >= abs(dy):
            return cls.E if dx > 0 else cls.W
        return cls.S if dy > 0 else cls.N