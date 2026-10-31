"""Interactive window (Tkinter, part of the Python standard library).
The window only drives the simulation controller and draws snapshots of the simulation.
"""

import time
from src.sim.controller import SimulationController
from src.render.scene import RenderOptions, SceneRenderer
from src.render.surface import TkSurface

SPEED_STEPS = [0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]


class TkApp:
    def __init__(self, controller: SimulationController, autostart: bool = True):
        import tkinter as tk

        self.tk = tk
        self.controller = controller
        sim = controller.sim
        cfg = sim.config.render
        self.fps = cfg.fps
        self.scene = SceneRenderer(sim.city, RenderOptions())
        self.root = tk.Tk()
        self.root.title("City Delivery Simulator")
        self.root.geometry(f"{cfg.window_width}x{cfg.window_height}")
        self.root.minsize(760, 520)
        bar = tk.Frame(self.root)
        bar.pack(side="top", fill="x")

        def button(text, command, width=None, padx=(2, 2)):
            b = tk.Button(bar, text=text, command=command, takefocus=0, **({"width": width} if width else {}))
            b.pack(side="left", padx=padx, pady=2)
            return b

        self.run_button = button("Start", self.toggle, 8)
        button("Step", self.step, 6)
        button("Reset", self.reset, 6)
        button("Slower  -", lambda: self.change_speed(-1), 9, (12, 2))
        button("Faster  +", lambda: self.change_speed(+1), 9)
        button("Routes (t)", self.toggle_routes, None, (12, 2))
        button("Labels (l)", self.toggle_labels)
        self.canvas = tk.Canvas(self.root, highlightthickness=0, background="#1e2228")
        self.canvas.pack(side="top", fill="both", expand=True)
        self.surface = TkSurface(self.canvas)
        self.canvas.bind("<Configure>", self._on_resize)
        for keys, action in ((("<space>",), self.toggle), (("n", "<Right>"), self.step),
                             (("r",), self.reset), (("plus", "equal", "<Up>"), lambda: self.change_speed(+1)),
                             (("minus", "<Down>"), lambda: self.change_speed(-1)),
                             (("t",), self.toggle_routes), (("l",), self.toggle_labels),
                             (("q", "<Escape>"), self.root.destroy)):
            for key in keys:
                self.root.bind(key if key.startswith("<") else f"<Key-{key}>", lambda _e, a=action: a())

        self._last = time.perf_counter()
        if autostart:
            controller.start()

    def toggle(self) -> None:
        self.controller.toggle()
        self._redraw_dynamic()

    def step(self) -> None:
        self.controller.pause()
        self.controller.step()
        self._redraw_dynamic()

    def reset(self) -> None:
        self.controller.reset()
        self._redraw_dynamic()

    def change_speed(self, direction: int) -> None:
        current = self.controller.speed
        idx = min(range(len(SPEED_STEPS)), key=lambda i: abs(SPEED_STEPS[i] - current))
        idx = max(0, min(len(SPEED_STEPS) - 1, idx + direction))
        self.controller.set_speed(SPEED_STEPS[idx])
        self._redraw_dynamic()

    def toggle_routes(self) -> None:
        self.scene.options.show_routes = not self.scene.options.show_routes
        self._redraw_dynamic()

    def toggle_labels(self) -> None:
        self.scene.options.show_labels = not self.scene.options.show_labels
        self._redraw_dynamic()

    def _on_resize(self, event) -> None:
        self.scene.layout(event.width, event.height)
        self.scene.draw_static(self.surface)
        self._redraw_dynamic()

    def _redraw_dynamic(self) -> None:
        if self.scene.width == 0:
            return
        self.scene.draw_dynamic(self.surface, self.controller.sim.snapshot())
        self.surface.finish_frame()
        self.run_button.config(text="Pause" if self.controller.running else "Start")

    def _tick(self) -> None:
        now = time.perf_counter()
        wall_dt, self._last = min(now - self._last, 0.25), now
        self.controller.update(wall_dt)
        self._redraw_dynamic()
        self.root.after(max(1, int(1000 / self.fps)), self._tick)

    def run(self) -> None:
        self.root.after(50, self._tick)
        self.root.mainloop()


def launch(controller: SimulationController, autostart: bool = True) -> None:
    TkApp(controller, autostart).run()
