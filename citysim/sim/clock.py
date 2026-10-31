"""The simulation clock.
Simulated time only ever changes through advancing the clock, one fixed dt at a time.
Time is derived as tick * dt rather than accumulated, so there is no floating point drift however long a run is.
"""
class SimClock:
    def __init__(self, dt: float, speed: float = 1.0):
        if dt <= 0:
            raise ValueError("dt must be positive")
        self.dt = dt
        # Simulated seconds per wall clock seconds (pacing)
        self.speed = speed
        self.running = False
        self.tick = 0

    @property
    def time(self) -> float:
        return self.tick * self.dt

    def advance(self) -> float:
        self.tick += 1
        return self.time

    def reset(self) -> None:
        self.tick = 0
        self.running = False
