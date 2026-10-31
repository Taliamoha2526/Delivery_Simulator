from citysim.render.scene import SceneRenderer
from citysim.render.surface import PILSurface
from citysim.render.scene import RenderOptions, PANEL_BG

def save_frame(sim, path: str, width: int = 1280, height: int = 860, options: RenderOptions | None = None) -> None:
    """Render the simulation's current state to an image file using Pillow."""
    scene = SceneRenderer(sim.city, options)
    scene.layout(width, height)
    surface = PILSurface(width, height, background=PANEL_BG)
    scene.draw_frame(surface, sim.snapshot())
    surface.image().save(path)
