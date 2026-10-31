"""Run control: start, pause, step, reset, speed, run to completion.
The simulation just knows how to take one step.
The controller decides when steps happen:
"""

from typing import Callable
from src.sim.simulation import Simulation

class SimulationController:
    # To stop a slow frame from snowballing into an ever longer one
    MAX_STEPS_PER_UPDATE = 2000

    def __init__(self, sim: Simulation):
        self.sim = sim
        # Simulated seconds owed but not yet stepped
        self._carry = 0.0

    # States
    @property
    def running(self) -> bool:
        return self.sim.clock.running

    @property
    def speed(self) -> float:
        return self.sim.clock.speed

    def start(self) -> None:
        if not self.sim.finished:
            self.sim.clock.running = True

    def pause(self) -> None:
        self.sim.clock.running = False

    def toggle(self) -> None:
        self.pause() if self.running else self.start()

    def set_speed(self, speed: float) -> None:
        if speed <= 0:
            raise ValueError("speed must be positive")
        self.sim.clock.speed = speed

    def reset(self, seed: int | None = None) -> None:
        self.sim.reset(seed)
        self._carry = 0.0

    # Advancing steps
    def step(self, n: int = 1) -> None:
        """Advance exactly n timesteps."""
        for _ in range(n):
            self.sim.step()

    def update(self, wall_seconds: float) -> int:
        """Called each frame by a renderer. Returns the number of steps taken."""
        if not self.running:
            return 0
        self._carry += wall_seconds * self.sim.clock.speed
        steps = min(int(self._carry / self.sim.clock.dt + 1e-9), self.MAX_STEPS_PER_UPDATE)
        self._carry = 0.0 if steps == self.MAX_STEPS_PER_UPDATE else self._carry - steps * self.sim.clock.dt
        for _ in range(steps):
            self.sim.step()
            if self.sim.finished:
                self.pause()
                break
        return steps

    def run(self, until: float | None = None,
            progress: Callable[[Simulation], None] | None = None,
            progress_every: float = 60.0) -> Simulation:
        """Headless: step as fast as possible upto until."""
        end = self.sim.config.simulation.duration if until is None else until
        next_report = self.sim.clock.time + progress_every
        while self.sim.clock.time < end - 1e-9:
            self.sim.step()
            if progress and self.sim.clock.time >= next_report:
                progress(self.sim)
                next_report += progress_every
        return self.sim
