"""Drawing surfaces: the thin layer between the scene renderer and a graphics library.
The renderer only calls the handful of primitives so the same scene can be drawn live in a Tk window or saved as a PNG.
Two layers exist:
- static : redraws only when resizing
- dynamic : redraws on each frame
"""

from typing import Protocol, Sequence
Point = tuple[float, float]

class Surface(Protocol):
    def begin(self, layer: str) -> None: ...
    def rect(self, x0: float, y0: float, x1: float, y1: float, fill: str | None = None,
             outline: str | None = None, width: float = 1) -> None: ...
    def polygon(self, points: Sequence[Point], fill: str | None = None,
                outline: str | None = None, width: float = 1) -> None: ...
    def ellipse(self, x0: float, y0: float, x1: float, y1: float, fill: str | None = None,
                outline: str | None = None, width: float = 1) -> None: ...
    def line(self, points: Sequence[Point], fill: str, width: float = 1, dash: bool = False) -> None: ...
    def text(self, x: float, y: float, s: str, fill: str, size: int = 11, anchor: str = "nw",
             bold: bool = False, mono: bool = False) -> None: ...


class TkSurface:
    """Draws on a canvas. Each layer is a canvas tag that is wiped on beginning."""

    def __init__(self, canvas):
        self.canvas = canvas
        self.layer = "static"

    def begin(self, layer: str) -> None:
        self.layer = layer
        self.canvas.delete(layer)

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=1):
        self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill or "", outline=outline or "", width=width, tags=self.layer)

    def polygon(self, points, fill=None, outline=None, width=1):
        flat = [c for p in points for c in p]
        self.canvas.create_polygon(*flat, fill=fill or "", outline=outline or "", width=width, tags=self.layer)

    def ellipse(self, x0, y0, x1, y1, fill=None, outline=None, width=1):
        self.canvas.create_oval(x0, y0, x1, y1, fill=fill or "", outline=outline or "", width=width, tags=self.layer)

    def line(self, points, fill, width=1, dash=False):
        flat = [c for p in points for c in p]
        self.canvas.create_line(*flat, fill=fill, width=width, dash=(4, 3) if dash else None, tags=self.layer)

    def text(self, x, y, s, fill, size=11, anchor="nw", bold=False, mono=False):
        family = "Courier" if mono else "Helvetica"
        font = (family, -int(size), "bold") if bold else (family, -int(size))
        self.canvas.create_text(x, y, text=s, fill=fill, anchor=anchor, font=font, tags=self.layer)

    def finish_frame(self) -> None:
        self.canvas.tag_lower("static")


class PILSurface:
    """Draws on a Pillow image, supersampled for smooth edges. Used for PNG export."""

    _ANCHORS = {"nw": "la", "n": "ma", "ne": "ra", "w": "lm", "center": "mm", "e": "rm", "sw": "ls", "s": "ms", "se": "rs"}

    def __init__(self, width: int, height: int, background: str = "#ffffff", ssaa: int = 2):
        from PIL import Image, ImageDraw   # imported lazily: Pillow is optional
        self.width, self.height, self.ssaa, self.background = width, height, ssaa, background
        self._image = Image.new("RGB", (width * ssaa, height * ssaa), background)
        self._draw = ImageDraw.Draw(self._image)
        self._fonts: dict = {}

    def begin(self, layer: str) -> None:
        if layer == "static":
            self._draw.rectangle([0, 0, self._image.width, self._image.height], fill=self.background)

    def _s(self, v: float) -> float:
        return v * self.ssaa

    def _pts(self, points):
        return [(self._s(x), self._s(y)) for x, y in points]

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=1):
        self._draw.rectangle([self._s(x0), self._s(y0), self._s(x1), self._s(y1)], fill=fill,
                             outline=outline, width=max(1, round(self._s(width))) if outline else 0)

    def polygon(self, points, fill=None, outline=None, width=1):
        pts = self._pts(points)
        if fill:
            self._draw.polygon(pts, fill=fill)
        if outline:
            self._draw.line(pts + [pts[0]], fill=outline, width=max(1, round(self._s(width))), joint="curve")

    def ellipse(self, x0, y0, x1, y1, fill=None, outline=None, width=1):
        self._draw.ellipse([self._s(x0), self._s(y0), self._s(x1), self._s(y1)], fill=fill,
                           outline=outline, width=max(1, round(self._s(width))) if outline else 0)

    def line(self, points, fill, width=1, dash=False):
        self._draw.line(self._pts(points), fill=fill, width=max(1, round(self._s(width))))

    def _font(self, size: int, bold: bool, mono: bool):
        from PIL import ImageFont

        key = (size, bold, mono)
        if key not in self._fonts:
            px = int(self._s(size))
            names = (["DejaVuSansMono-Bold.ttf", "DejaVuSansMono.ttf"] if mono else
                     ["DejaVuSans-Bold.ttf", "DejaVuSans.ttf"])
            names = names if bold else names[1:]
            font = None
            for name in names + ["Arial.ttf", "LiberationSans-Regular.ttf"]:
                try:
                    font = ImageFont.truetype(name, px)
                    break
                except OSError:
                    continue
            self._fonts[key] = font or ImageFont.load_default(size=px)
        return self._fonts[key]

    def text(self, x, y, s, fill, size=11, anchor="nw", bold=False, mono=False):
        self._draw.text((self._s(x), self._s(y)), s, fill=fill, font=self._font(size, bold, mono), anchor=self._ANCHORS.get(anchor, "la"))

    def image(self):
        from PIL import Image

        if self.ssaa == 1:
            return self._image
        return self._image.resize((self.width, self.height), Image.LANCZOS)


