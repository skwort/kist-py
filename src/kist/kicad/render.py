"""
Render KiCad symbols and footprints to PIL Images.

Takes S-expression trees and draws shapes, pins, pads, and text
onto a Pillow canvas.
"""

from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from kist.kicad.discovery import KiCadEnvironment, parse_lib_table, resolve_uri
from kist.sexpr import find_all, find_one, parse_one

if TYPE_CHECKING:
    from PIL import Image as PILImage
    from PIL import ImageFont as PILImageFont

    from kist.models.config import LibraryConfig


Color = tuple[int, int, int, int]


@dataclass(frozen=True)
class RenderTheme:
    """Semantic colors used by symbol/footprint renderers."""

    canvas_bg: Color = (0, 0, 0, 0)
    symbol_fg: Color = (179, 179, 179, 255)
    symbol_text: Color = (179, 179, 179, 255)
    footprint_silk: Color = (185, 185, 185, 255)
    footprint_fab: Color = (120, 150, 190, 220)
    footprint_courtyard: Color = (210, 190, 90, 180)
    footprint_copper: Color = (240, 130, 75, 230)
    footprint_pad: Color = (245, 150, 90, 170)
    footprint_other: Color = (160, 160, 160, 160)


DEFAULT_RENDER_THEME = RenderTheme()


# -- Path resolution ---


def build_symbol_path_lookup(
    env: KiCadEnvironment,
    kist_root: Path | None = None,
    config: LibraryConfig | None = None,
) -> dict[str, Path]:
    """Build a mapping from library name to .kicad_sym file path."""
    lookup: dict[str, Path] = {}

    sym_table = env.config_dir / "sym-lib-table"
    for entry in parse_lib_table(sym_table):
        path = resolve_uri(entry.uri, env)
        if path.is_file():
            lookup[entry.name] = path

    if kist_root and config:
        sym_dir = kist_root / config.symbols_dir
        if sym_dir.is_dir():
            for sym_file in sym_dir.glob("*.kicad_sym"):
                lookup[sym_file.stem] = sym_file

    return lookup


def build_footprint_path_lookup(
    env: KiCadEnvironment,
    kist_root: Path | None = None,
    config: LibraryConfig | None = None,
) -> dict[str, Path]:
    """Build a mapping from library name to .pretty directory path."""
    lookup: dict[str, Path] = {}

    fp_table = env.config_dir / "fp-lib-table"
    for entry in parse_lib_table(fp_table):
        path = resolve_uri(entry.uri, env)
        if path.is_dir():
            lookup[entry.name] = path

    if kist_root and config:
        fp_dir = kist_root / config.footprints_dir
        if fp_dir.is_dir():
            for pretty_dir in fp_dir.glob("*.pretty"):
                lookup[pretty_dir.stem] = pretty_dir

    return lookup


# -- Font helpers ---


@lru_cache(maxsize=1)
def _mono_font_path() -> str | None:
    """Find a monospace TTF on the system via fc-match."""
    try:
        result = subprocess.run(
            ["fc-match", "-f", "%{file}", "monospace"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            p = result.stdout.strip()
            if Path(p).is_file():
                return p
    except Exception:
        pass
    return None


@lru_cache(maxsize=8)
def _get_font(size_px: int) -> PILImageFont.FreeTypeFont | PILImageFont.ImageFont:
    from PIL import ImageFont

    path = _mono_font_path()
    if path:
        try:
            return ImageFont.truetype(path, size=max(8, size_px))
        except Exception:
            pass
    # Pillow's load_default() signature varies by version; don't pass size.
    return ImageFont.load_default()


# -- Geometry helpers ---


def _fl(s: str) -> float:
    return float(s)


def _xy(node: list) -> tuple[float, float]:
    """Extract (x, y) from a node like (xy x y), (start x y), etc."""
    return _fl(node[1]), _fl(node[2])


def _stroke_width(node: list) -> float:
    stroke = find_one(node, "stroke")
    if stroke is None:
        return 0.0
    w = find_one(stroke, "width")
    return _fl(w[1]) if w else 0.0


def _fill_type(node: list) -> str:
    fill = find_one(node, "fill")
    if fill is None:
        return "none"
    t = find_one(fill, "type")
    return str(t[1]) if t else "none"


def _arc_center(
    sx: float, sy: float, mx: float, my: float, ex: float, ey: float
) -> tuple[float, float, float]:
    """Circle through three points -> (cx, cy, radius)."""
    D = 2 * (sx * (my - ey) + mx * (ey - sy) + ex * (sy - my))
    if abs(D) < 1e-10:
        cx = (sx + ex) / 2
        cy = (sy + ey) / 2
        return cx, cy, math.dist((sx, sy), (ex, ey)) / 2

    a2 = sx * sx + sy * sy
    b2 = mx * mx + my * my
    c2 = ex * ex + ey * ey
    cx = (a2 * (my - ey) + b2 * (ey - sy) + c2 * (sy - my)) / D
    cy = (a2 * (ex - mx) + b2 * (sx - ex) + c2 * (mx - sx)) / D
    r = math.sqrt((sx - cx) ** 2 + (sy - cy) ** 2)
    return cx, cy, r


# -- Text drawing ---


def _draw_text(
    img: PILImage.Image,
    text: str,
    cx: float,
    cy: float,
    angle: float,
    font: PILImageFont.FreeTypeFont | PILImageFont.ImageFont,
    color: tuple[int, ...],
    align: str = "center",
) -> None:
    """Draw *text* centered at (cx, cy) with rotation *angle* degrees."""
    from PIL import Image, ImageDraw

    tmp = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    tmp_draw = ImageDraw.Draw(tmp)
    bbox = tmp_draw.textbbox((0, 0), text, font=font)
    tw = int(bbox[2] - bbox[0])
    th = int(bbox[3] - bbox[1])

    txt_img = Image.new("RGBA", (tw + 4, th + 4), (0, 0, 0, 0))
    txt_draw = ImageDraw.Draw(txt_img)
    txt_draw.text((-bbox[0] + 2, -bbox[1] + 2), text, font=font, fill=color)

    if angle != 0:
        txt_img = txt_img.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)

    pw, ph = txt_img.size
    if align == "left":
        paste_x = int(cx)
    elif align == "right":
        paste_x = int(cx - pw)
    else:
        paste_x = int(cx - pw / 2)
    paste_y = int(cy - ph / 2)
    img.paste(txt_img, (paste_x, paste_y), txt_img)


# ============================================================
# Symbol rendering
# ============================================================

_DRAW_TAGS = frozenset({"polyline", "rectangle", "arc", "circle", "pin"})


def get_symbol_units(sym: list) -> list[int]:
    """Return sorted list of unit numbers in a symbol (excluding 0 = shared).

    Single-unit symbols return ``[1]``.  Multi-unit symbols return
    ``[1, 2, ...]`` etc.
    """
    name = str(sym[1]) if len(sym) > 1 else ""
    units: set[int] = set()
    for child in sym:
        if not isinstance(child, list) or not child or child[0] != "symbol":
            continue
        if len(child) < 2:
            continue
        sub = str(child[1])
        if not sub.startswith(name + "_"):
            continue
        parts = sub[len(name) + 1 :].split("_")
        if len(parts) == 2:
            try:
                u = int(parts[0])
                if u > 0:
                    units.add(u)
            except ValueError:
                pass
    return sorted(units) if units else [1]


def _collect_symbol_primitives(sym: list, unit: int = 0) -> list[list]:
    """Collect drawing nodes for a specific unit.

    *unit* ``0`` means all units (old behaviour).  Otherwise only
    sub-symbols for unit 0 (shared) and the requested unit are included.
    """
    name = str(sym[1]) if len(sym) > 1 else ""
    out: list[list] = []

    def _walk(node: list, include: bool) -> None:
        for child in node:
            if not isinstance(child, list) or not child:
                continue
            tag = child[0]
            if not isinstance(tag, str):
                continue
            if tag in _DRAW_TAGS and include:
                out.append(child)
            elif tag == "symbol" and len(child) > 1:
                sub = str(child[1])
                if sub.startswith(name + "_"):
                    parts = sub[len(name) + 1 :].split("_")
                    if len(parts) == 2:
                        try:
                            sub_unit = int(parts[0])
                        except ValueError:
                            sub_unit = -1
                        if unit == 0 or sub_unit == 0 or sub_unit == unit:
                            _walk(child, True)
                    else:
                        _walk(child, include)
                else:
                    _walk(child, include)

    _walk(sym, False)
    return out


def _collect_visible_properties(sym: list) -> list[dict]:
    """Collect visible property labels with position and font info."""
    props: list[dict] = []
    for child in sym:
        if not isinstance(child, list) or not child or child[0] != "property":
            continue
        if len(child) < 3:
            continue

        effects = find_one(child, "effects")
        if effects:
            hide = find_one(effects, "hide")
            if hide and len(hide) > 1 and str(hide[1]) == "yes":
                continue

        value = str(child[2])
        if not value or value == "~":
            continue

        at = find_one(child, "at")
        if not at:
            continue

        x = _fl(at[1])
        y = _fl(at[2])
        angle = _fl(at[3]) if len(at) > 3 else 0.0

        font_h = 1.27
        if effects:
            font_node = find_one(effects, "font")
            if font_node:
                size_node = find_one(font_node, "size")
                if size_node and len(size_node) > 1:
                    font_h = _fl(size_node[1])

        props.append(
            {
                "text": value,
                "x": x,
                "y": y,
                "angle": angle,
                "font_h": font_h,
            }
        )
    return props


def _font_height_from_effects(effects: list | None, default: float = 1.27) -> float:
    if effects is None:
        return default
    font_node = find_one(effects, "font")
    if font_node is None:
        return default
    size_node = find_one(font_node, "size")
    if size_node and len(size_node) > 1:
        return _fl(size_node[1])
    return default


def _effects_hidden(effects: list | None) -> bool:
    if effects is None:
        return False
    hide = find_one(effects, "hide")
    return bool(hide and len(hide) > 1 and str(hide[1]) == "yes")


def _symbol_pin_config(sym: list) -> tuple[bool, bool, float]:
    """Return (show_pin_names, show_pin_numbers, pin_name_offset_mm)."""
    show_names = True
    show_numbers = True
    name_offset = 0.508

    pin_names = find_one(sym, "pin_names")
    if pin_names:
        hide = find_one(pin_names, "hide")
        if hide and len(hide) > 1 and str(hide[1]) == "yes":
            show_names = False
        offset = find_one(pin_names, "offset")
        if offset and len(offset) > 1:
            name_offset = _fl(offset[1])

    pin_numbers = find_one(sym, "pin_numbers")
    if pin_numbers:
        hide = find_one(pin_numbers, "hide")
        if hide and len(hide) > 1 and str(hide[1]) == "yes":
            show_numbers = False

    return show_names, show_numbers, name_offset


def _collect_pin_labels(prims: list[list], sym: list) -> list[dict]:
    """Collect visible pin name/number labels with placement and font info."""
    show_names, show_numbers, name_offset = _symbol_pin_config(sym)
    labels: list[dict] = []

    for p in prims:
        if p[0] != "pin":
            continue

        at = find_one(p, "at")
        ln = find_one(p, "length")
        if not at or not ln:
            continue

        px, py = _fl(at[1]), _fl(at[2])
        angle = _fl(at[3]) if len(at) > 3 else 0.0
        length = _fl(ln[1])
        rad = math.radians(angle)
        ux, uy = math.cos(rad), math.sin(rad)
        tx, ty = px + length * ux, py + length * uy

        is_vertical = abs(uy) > 0.5

        if abs(ux) > 0.5:
            name_align = "left" if ux > 0 else "right"
        else:
            name_align = "center"

        side_dx = 0.0
        name_angle = 90.0 if is_vertical else 0.0

        if show_names:
            name = find_one(p, "name")
            if name and len(name) > 1:
                text = str(name[1])
                effects = find_one(name, "effects")
                if text and text != "~" and not _effects_hidden(effects):
                    font_h = _font_height_from_effects(effects)
                    name_distance = name_offset + 0.3 + (0.7 if is_vertical else 0.0)
                    if is_vertical:
                        # Keep vertical names on-pin-axis but push them farther
                        # along the pin direction so long rotated names clear
                        # the pin line.
                        est_len = len(text) * font_h * 0.6
                        name_distance += est_len * 0.3
                    labels.append(
                        {
                            "text": text,
                            # Name belongs on the symbol/body side of the pin.
                            "x": tx + ux * name_distance + side_dx,
                            "y": ty + uy * name_distance,
                            "angle": name_angle,
                            "align": name_align,
                            "font_h": font_h,
                        }
                    )

        if show_numbers:
            number = find_one(p, "number")
            if number and len(number) > 1:
                text = str(number[1])
                effects = find_one(number, "effects")
                if text and text != "~" and not _effects_hidden(effects):
                    font_h = _font_height_from_effects(effects)
                    number_offset = max(0.7, font_h * 0.65)
                    # Center on the pin, then shift perpendicular to the
                    # pin direction so the number never sits on the line.
                    center_x = (px + tx) / 2
                    center_y = (py + ty) / 2
                    if abs(ux) > 0.5:
                        # Horizontal pins: number goes above the line.
                        normal_x, normal_y = 0.0, 1.0
                    else:
                        # Vertical pins: number goes to the left of the line.
                        normal_x, normal_y = -1.0, 0.0
                    number_x = center_x + normal_x * number_offset + side_dx
                    number_y = center_y + normal_y * number_offset
                    labels.append(
                        {
                            "text": text,
                            # Pin number is drawn above the pin in local coords.
                            "x": number_x,
                            "y": number_y,
                            "angle": 90.0 if is_vertical else 0.0,
                            "align": "center",
                            "font_h": font_h,
                        }
                    )

    return labels


def _symbol_bounds(
    prims: list[list], props: list[dict], pin_labels: list[dict]
) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []

    for p in prims:
        tag = p[0]
        if tag == "polyline":
            pts = find_one(p, "pts")
            if pts:
                for node in find_all(pts, "xy"):
                    x, y = _xy(node)
                    xs.append(x)
                    ys.append(y)
        elif tag == "rectangle":
            s, e = find_one(p, "start"), find_one(p, "end")
            if s and e:
                for n in (s, e):
                    x, y = _xy(n)
                    xs.append(x)
                    ys.append(y)
        elif tag == "arc":
            s, m, e = find_one(p, "start"), find_one(p, "mid"), find_one(p, "end")
            if s and m and e:
                sx, sy = _xy(s)
                mx, my = _xy(m)
                ex, ey = _xy(e)
                cx, cy, r = _arc_center(sx, sy, mx, my, ex, ey)
                xs.extend([cx - r, cx + r])
                ys.extend([cy - r, cy + r])
        elif tag == "circle":
            c, r = find_one(p, "center"), find_one(p, "radius")
            if c and r:
                cx, cy = _xy(c)
                rv = _fl(r[1])
                xs.extend([cx - rv, cx + rv])
                ys.extend([cy - rv, cy + rv])
        elif tag == "pin":
            at = find_one(p, "at")
            ln = find_one(p, "length")
            if at:
                px, py = _fl(at[1]), _fl(at[2])
                xs.append(px)
                ys.append(py)
                if ln:
                    length = _fl(ln[1])
                    angle = _fl(at[3]) if len(at) > 3 else 0.0
                    rad = math.radians(angle)
                    xs.append(px + length * math.cos(rad))
                    ys.append(py + length * math.sin(rad))

    for prop in props:
        est = len(prop["text"]) * prop["font_h"] * 0.6
        x, y = prop["x"], prop["y"]
        if prop["angle"] in (90.0, 270.0):
            xs.extend([x - prop["font_h"], x + prop["font_h"]])
            ys.extend([y - est / 2, y + est / 2])
        else:
            xs.extend([x - est / 2, x + est / 2])
            ys.extend([y - prop["font_h"], y + prop["font_h"]])

    for label in pin_labels:
        est = len(label["text"]) * label["font_h"] * 0.6
        x, y = label["x"], label["y"]
        xs.extend([x - est / 2, x + est / 2])
        ys.extend([y - label["font_h"], y + label["font_h"]])

    if not xs:
        return -5, -5, 5, 5
    return min(xs), min(ys), max(xs), max(ys)


_PIN_WIDTH_MM = 0.2


def render_symbol(
    sym: list,
    unit: int = 1,
    scale_px_per_mm: float = 80.0,
    padding: int = 30,
    bg: tuple[int, ...] = (0, 0, 0, 0),
    fg: tuple[int, ...] = (255, 255, 255, 255),
    theme: RenderTheme | None = None,
) -> PILImage.Image:
    """Render a KiCad symbol to a PIL Image.

    *unit* selects which unit to render for multi-part symbols
    (1-based).  Unit 0 graphics (shared body) are always included.
    """
    from PIL import Image, ImageDraw

    prims = _collect_symbol_primitives(sym, unit=unit)
    props = _collect_visible_properties(sym)
    pin_labels = _collect_pin_labels(prims, sym)
    min_x, min_y, max_x, max_y = _symbol_bounds(prims, props, pin_labels)

    margin = 0.5
    min_x -= margin
    min_y -= margin
    max_x += margin
    max_y += margin

    scale = scale_px_per_mm
    width = max(1, round((max_x - min_x) * scale) + 2 * padding)
    height = max(1, round((max_y - min_y) * scale) + 2 * padding)
    off_x = float(padding)
    off_y = float(padding)

    def tx(x: float) -> float:
        return off_x + (x - min_x) * scale

    def ty(y: float) -> float:
        return off_y + (max_y - y) * scale

    palette = theme or DEFAULT_RENDER_THEME
    bg_c = palette.canvas_bg if theme else bg
    fg_c = palette.symbol_fg if theme else fg
    text_c = palette.symbol_text if theme else fg

    img = Image.new("RGBA", (width, height), bg_c)
    draw = ImageDraw.Draw(img)
    pin_sw = max(2, round(_PIN_WIDTH_MM * scale))

    for p in prims:
        tag = p[0]
        sw = max(1, round(_stroke_width(p) * scale))
        ft = _fill_type(p)

        if tag == "polyline":
            pts = find_one(p, "pts")
            if not pts:
                continue
            points = [(tx(x), ty(y)) for x, y in (_xy(n) for n in find_all(pts, "xy"))]
            if len(points) >= 2:
                draw.line(points, fill=fg_c, width=sw)

        elif tag == "rectangle":
            s, e = find_one(p, "start"), find_one(p, "end")
            if not s or not e:
                continue
            sx, sy = _xy(s)
            ex, ey = _xy(e)
            x0, y0, x1, y1 = tx(sx), ty(sy), tx(ex), ty(ey)
            rect = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
            fill_c = fg_c if ft == "outline" else None
            draw.rectangle(rect, outline=fg_c, fill=fill_c, width=sw)

        elif tag == "arc":
            s, m, e = find_one(p, "start"), find_one(p, "mid"), find_one(p, "end")
            if not s or not m or not e:
                continue
            sx, sy = _xy(s)
            mx, my = _xy(m)
            ex, ey = _xy(e)
            cx, cy, r = _arc_center(sx, sy, mx, my, ex, ey)
            rp = r * scale
            bbox = [tx(cx) - rp, ty(cy) - rp, tx(cx) + rp, ty(cy) + rp]
            sa = math.degrees(math.atan2(-(sy - cy), sx - cx))
            ma = math.degrees(math.atan2(-(my - cy), mx - cx))
            ea = math.degrees(math.atan2(-(ey - cy), ex - cx))

            def _between_cw(a: float, b: float, t: float) -> bool:
                a, b, t = a % 360, b % 360, t % 360
                return (a <= t <= b) if a <= b else (t >= a or t <= b)

            if _between_cw(sa, ea, ma):
                draw.arc(bbox, start=sa, end=ea, fill=fg_c, width=sw)
            else:
                draw.arc(bbox, start=ea, end=sa, fill=fg_c, width=sw)

        elif tag == "circle":
            c, r = find_one(p, "center"), find_one(p, "radius")
            if not c or not r:
                continue
            cx, cy = _xy(c)
            rv = _fl(r[1]) * scale
            bbox = [tx(cx) - rv, ty(cy) - rv, tx(cx) + rv, ty(cy) + rv]
            fill_c = fg_c if ft == "outline" else None
            draw.ellipse(bbox, outline=fg_c, fill=fill_c, width=sw)

        elif tag == "pin":
            at = find_one(p, "at")
            ln = find_one(p, "length")
            if not at or not ln:
                continue
            px, py = _fl(at[1]), _fl(at[2])
            angle = _fl(at[3]) if len(at) > 3 else 0.0
            length = _fl(ln[1])
            rad = math.radians(angle)
            end_x = px + length * math.cos(rad)
            end_y = py + length * math.sin(rad)
            draw.line(
                [(tx(px), ty(py)), (tx(end_x), ty(end_y))], fill=fg_c, width=pin_sw
            )
            pr = max(3, round(scale * 0.18))
            draw.ellipse(
                [tx(px) - pr, ty(py) - pr, tx(px) + pr, ty(py) + pr], fill=fg_c
            )

    for prop in props:
        font_px = max(8, round(prop["font_h"] * scale))
        font = _get_font(font_px)
        _draw_text(
            img, prop["text"], tx(prop["x"]), ty(prop["y"]), prop["angle"], font, text_c
        )

    for label in pin_labels:
        font_px = max(8, round(label["font_h"] * scale))
        font = _get_font(font_px)
        _draw_text(
            img,
            label["text"],
            tx(label["x"]),
            ty(label["y"]),
            label["angle"],
            font,
            text_c,
            align=label.get("align", "center"),
        )

    return img


# ============================================================
# Footprint rendering
# ============================================================

_FP_DRAW_TAGS = frozenset(
    {
        "fp_line",
        "fp_rect",
        "fp_circle",
        "fp_arc",
        "line",
        "rect",
        "circle",
        "arc",
    }
)
_FP_VISIBLE_LAYERS = frozenset({"F.Fab", "F.SilkS", "B.Fab", "B.SilkS", "F.Cu", "B.Cu"})
_FP_DIM_LAYERS = frozenset({"F.CrtYd", "B.CrtYd"})


def _fp_layer(node: list) -> str:
    layer = find_one(node, "layer")
    return str(layer[1]) if layer and len(layer) > 1 else ""


def _footprint_layer_color(layer: str, palette: RenderTheme) -> Color:
    if layer in ("F.SilkS", "B.SilkS"):
        return palette.footprint_silk
    if layer in ("F.Fab", "B.Fab"):
        return palette.footprint_fab
    if layer in ("F.CrtYd", "B.CrtYd"):
        return palette.footprint_courtyard
    if layer.endswith(".Cu"):
        return palette.footprint_copper
    return palette.footprint_other


def _pad_color(pad: list, palette: RenderTheme) -> Color:
    layers = find_one(pad, "layers")
    if layers:
        for layer in layers[1:]:
            if isinstance(layer, str) and layer.endswith(".Cu"):
                return palette.footprint_pad
    return palette.footprint_fab


@lru_cache(maxsize=32)
def _load_footprint_cached(path: Path, mtime_ns: int) -> list:
    del mtime_ns  # cache key only
    tree = parse_one(path.read_text(encoding="utf-8"))
    if isinstance(tree, list):
        return tree
    raise ValueError(f"Invalid footprint tree in {path}")


def load_footprint(path: Path) -> list:
    """Parse a .kicad_mod file and return the S-expression tree."""
    stat = path.stat()
    return _load_footprint_cached(path, stat.st_mtime_ns)


def render_footprint(
    tree: list,
    scale_px_per_mm: float = 100.0,
    padding: int = 30,
    bg: tuple[int, ...] = (0, 0, 0, 0),
    fg: tuple[int, ...] = (255, 255, 255, 255),
    pad_fg: tuple[int, ...] = (255, 255, 255, 160),
    dim_fg: tuple[int, ...] = (255, 255, 255, 60),
    theme: RenderTheme | None = None,
) -> PILImage.Image:
    """Render a KiCad footprint S-expression tree to a PIL Image."""
    from PIL import Image, ImageDraw

    palette = theme or DEFAULT_RENDER_THEME
    canvas_bg = palette.canvas_bg if theme else bg
    default_fg = palette.footprint_silk if theme else fg
    default_dim = palette.footprint_courtyard if theme else dim_fg
    default_pad = palette.footprint_pad if theme else pad_fg

    # Collect graphics and pads
    graphics: list[tuple[list, tuple[int, ...]]] = []  # (node, color)
    pads: list[list] = []

    for child in tree:
        if not isinstance(child, list) or not child:
            continue
        tag = child[0]
        if not isinstance(tag, str):
            continue
        if tag in _FP_DRAW_TAGS:
            layer = _fp_layer(child)
            if layer in _FP_VISIBLE_LAYERS:
                color = _footprint_layer_color(layer, palette) if theme else default_fg
                graphics.append((child, color))
            elif layer in _FP_DIM_LAYERS:
                graphics.append((child, default_dim))
        elif tag == "pad":
            pads.append(child)

    # Compute bounds
    xs: list[float] = []
    ys: list[float] = []

    for node, _ in graphics:
        tag = node[0]
        if tag in ("fp_line", "line"):
            s, e = find_one(node, "start"), find_one(node, "end")
            if s and e:
                x, y = _xy(s)
                xs.append(x)
                ys.append(y)
                x, y = _xy(e)
                xs.append(x)
                ys.append(y)
        elif tag in ("fp_rect", "rect"):
            s, e = find_one(node, "start"), find_one(node, "end")
            if s and e:
                x, y = _xy(s)
                xs.append(x)
                ys.append(y)
                x, y = _xy(e)
                xs.append(x)
                ys.append(y)
        elif tag in ("fp_circle", "circle"):
            c, e = find_one(node, "center"), find_one(node, "end")
            if c and e:
                cx, cy = _xy(c)
                ex, ey = _xy(e)
                r = math.dist((cx, cy), (ex, ey))
                xs.extend([cx - r, cx + r])
                ys.extend([cy - r, cy + r])
        elif tag in ("fp_arc", "arc"):
            s, m, e = (
                find_one(node, "start"),
                find_one(node, "mid"),
                find_one(node, "end"),
            )
            if s and m and e:
                sx, sy = _xy(s)
                mx, my = _xy(m)
                ex, ey = _xy(e)
                cx, cy, r = _arc_center(sx, sy, mx, my, ex, ey)
                xs.extend([cx - r, cx + r])
                ys.extend([cy - r, cy + r])

    for pad in pads:
        at = find_one(pad, "at")
        size = find_one(pad, "size")
        if at and size:
            px, py = _fl(at[1]), _fl(at[2])
            w, h = _fl(size[1]) / 2, _fl(size[2]) / 2
            xs.extend([px - w, px + w])
            ys.extend([py - h, py + h])

    if not xs:
        return Image.new("RGBA", (60, 60), canvas_bg)

    min_x, min_y = min(xs), min(ys)
    max_x, max_y = max(xs), max(ys)
    margin = 0.2
    min_x -= margin
    min_y -= margin
    max_x += margin
    max_y += margin

    scale = scale_px_per_mm
    width = max(1, round((max_x - min_x) * scale) + 2 * padding)
    height = max(1, round((max_y - min_y) * scale) + 2 * padding)
    off_x = float(padding)
    off_y = float(padding)

    def tx(x: float) -> float:
        return off_x + (x - min_x) * scale

    # Footprints use Y-down (same as screen), no flip needed
    def ty(y: float) -> float:
        return off_y + (y - min_y) * scale

    img = Image.new("RGBA", (width, height), canvas_bg)
    draw = ImageDraw.Draw(img)

    # Draw pads first (behind outlines)
    for pad in pads:
        at = find_one(pad, "at")
        size = find_one(pad, "size")
        if not at or not size:
            continue
        px, py = _fl(at[1]), _fl(at[2])
        pw, ph = _fl(size[1]) * scale, _fl(size[2]) * scale

        # Handle pad rotation
        pad_angle = _fl(at[3]) if len(at) > 3 else 0.0
        if pad_angle in (90.0, 270.0):
            pw, ph = ph, pw

        cx, cy = tx(px), ty(py)

        pad_color = _pad_color(pad, palette) if theme else default_pad

        # Determine pad shape
        shape = "rect"
        for elem in pad:
            if isinstance(elem, str) and elem in (
                "circle",
                "oval",
                "roundrect",
                "rect",
            ):
                shape = elem

        if shape == "circle":
            r = min(pw, ph) / 2
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=pad_color)
        elif shape == "oval":
            draw.ellipse(
                [cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2], fill=pad_color
            )
        elif shape == "roundrect":
            rr_node = find_one(pad, "roundrect_rratio")
            ratio = _fl(rr_node[1]) if rr_node and len(rr_node) > 1 else 0.25
            corner_r = ratio * min(pw, ph)
            draw.rounded_rectangle(
                [cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2],
                radius=corner_r,
                fill=pad_color,
            )
        else:  # rect
            draw.rectangle(
                [cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2], fill=pad_color
            )

    # Draw graphics
    for node, color in graphics:
        tag = node[0]
        sw = max(1, round(_stroke_width(node) * scale))

        if tag in ("fp_line", "line"):
            s, e = find_one(node, "start"), find_one(node, "end")
            if s and e:
                sx, sy = _xy(s)
                ex, ey = _xy(e)
                draw.line([(tx(sx), ty(sy)), (tx(ex), ty(ey))], fill=color, width=sw)

        elif tag in ("fp_rect", "rect"):
            s, e = find_one(node, "start"), find_one(node, "end")
            if s and e:
                sx, sy = _xy(s)
                ex, ey = _xy(e)
                x0, y0, x1, y1 = tx(sx), ty(sy), tx(ex), ty(ey)
                ft = _fill_type(node)
                fill_c = color if ft == "solid" else None
                draw.rectangle(
                    [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)],
                    outline=color,
                    fill=fill_c,
                    width=sw,
                )

        elif tag in ("fp_circle", "circle"):
            c, e = find_one(node, "center"), find_one(node, "end")
            if c and e:
                cx, cy = _xy(c)
                ex, ey = _xy(e)
                r = math.dist((cx, cy), (ex, ey)) * scale
                pcx, pcy = tx(cx), ty(cy)
                draw.ellipse(
                    [pcx - r, pcy - r, pcx + r, pcy + r], outline=color, width=sw
                )

        elif tag in ("fp_arc", "arc"):
            s, m, e = (
                find_one(node, "start"),
                find_one(node, "mid"),
                find_one(node, "end"),
            )
            if s and m and e:
                sx, sy = _xy(s)
                mx, my = _xy(m)
                ex, ey = _xy(e)
                cx, cy, r = _arc_center(sx, sy, mx, my, ex, ey)
                rp = r * scale
                bbox = [tx(cx) - rp, ty(cy) - rp, tx(cx) + rp, ty(cy) + rp]
                # No Y-flip for footprints
                sa = math.degrees(math.atan2(sy - cy, sx - cx))
                ma = math.degrees(math.atan2(my - cy, mx - cx))
                ea = math.degrees(math.atan2(ey - cy, ex - cx))

                def _between(a: float, b: float, t: float) -> bool:
                    a, b, t = a % 360, b % 360, t % 360
                    return (a <= t <= b) if a <= b else (t >= a or t <= b)

                # PIL arc uses inverted Y
                sa_p = -sa
                ma_p = -ma
                ea_p = -ea
                if _between(sa_p % 360, ea_p % 360, ma_p % 360):
                    draw.arc(bbox, start=sa_p, end=ea_p, fill=color, width=sw)
                else:
                    draw.arc(bbox, start=ea_p, end=sa_p, fill=color, width=sw)

    return img
