"""
KiCad symbol templates for common part types.

Generates complete ``(symbol ...)`` S-expression trees matching KiCad's
own Device:R_US, Device:C, and Device:L symbols so generated libraries
look identical to hand-placed parts. Graphics coordinates are copied
from the KiCad 9.0 Device library.
"""

from __future__ import annotations

from collections.abc import Callable

from kist.models import Part, PartBase, Tier
from kist.models.config import CategoryDef
from kist.sexpr import Atom, SExpr

# -- Helpers ---


def _q(val: str) -> Atom:
    """Quoted atom."""
    return Atom(val, quoted=True)


def _k(val: str) -> Atom:
    """Keyword (unquoted) atom."""
    return Atom(val)


def _hidden_property(key: str, value: str) -> list[SExpr]:
    """A property hidden at (0,0,0) with standard font size."""
    return [
        _k("property"),
        _q(key),
        _q(value),
        [_k("at"), _k("0"), _k("0"), _k("0")],
        [
            _k("effects"),
            [_k("font"), [_k("size"), _k("1.27"), _k("1.27")]],
            [_k("hide"), _k("yes")],
        ],
    ]


def _pin(number: str, x: str, y: str, angle: str, length: str) -> list[SExpr]:
    """A passive-line pin with hidden name ``~``."""
    return [
        _k("pin"),
        _k("passive"),
        _k("line"),
        [_k("at"), _k(x), _k(y), _k(angle)],
        [_k("length"), _k(length)],
        [
            _k("name"),
            _q("~"),
            [_k("effects"), [_k("font"), [_k("size"), _k("1.27"), _k("1.27")]]],
        ],
        [
            _k("number"),
            _q(number),
            [_k("effects"), [_k("font"), [_k("size"), _k("1.27"), _k("1.27")]]],
        ],
    ]


def _stroke(width: str = "0") -> list[SExpr]:
    return [_k("stroke"), [_k("width"), _k(width)], [_k("type"), _k("default")]]


def _fill_none() -> list[SExpr]:
    return [_k("fill"), [_k("type"), _k("none")]]


# -- Property builder ---


def build_properties(part: PartBase) -> dict[str, str]:
    """
    Extract KiCad property values from a Part model.

    Returns a dict suitable for passing to template functions or
    ``SymbolLibrary.update_properties()``.
    """
    datasheet = str(part.datasheet) if part.datasheet else "~"
    keywords = " ".join(part.keywords + part.tags)
    return {
        "Reference": part.reference,
        "Value": part.value,
        "Footprint": part.footprint,
        "Datasheet": datasheet,
        "Description": part.description,
        "ki_keywords": keywords,
    }


# -- Resistor template (IEC rectangle body) ---


def resistor_symbol_iec(name: str, props: dict[str, str]) -> list[SExpr]:
    """
    Complete ``(symbol ...)`` tree for a resistor.

    IEC rectangle body matching KiCad Device:R, two passive pins.
    """
    return [
        _k("symbol"),
        _q(name),
        [_k("pin_numbers"), [_k("hide"), _k("yes")]],
        [_k("pin_names"), [_k("offset"), _k("0")]],
        [_k("exclude_from_sim"), _k("no")],
        [_k("in_bom"), _k("yes")],
        [_k("on_board"), _k("yes")],
        # Visible properties
        [
            _k("property"),
            _q("Reference"),
            _q(props.get("Reference", "R")),
            [_k("at"), _k("2.032"), _k("0"), _k("90")],
            [
                _k("effects"),
                [_k("font"), [_k("size"), _k("1.27"), _k("1.27")]],
            ],
        ],
        [
            _k("property"),
            _q("Value"),
            _q(props.get("Value", name)),
            [_k("at"), _k("0"), _k("0"), _k("90")],
            [
                _k("effects"),
                [_k("font"), [_k("size"), _k("1.27"), _k("1.27")]],
            ],
        ],
        # Hidden properties
        _hidden_property("Footprint", props.get("Footprint", "")),
        _hidden_property("Datasheet", props.get("Datasheet", "~")),
        _hidden_property("Description", props.get("Description", "")),
        _hidden_property("ki_keywords", props.get("ki_keywords", "")),
        # Graphics sub-symbol: rectangle body
        [
            _k("symbol"),
            _q(f"{name}_0_1"),
            [
                _k("rectangle"),
                [_k("start"), _k("-1.016"), _k("-2.54")],
                [_k("end"), _k("1.016"), _k("2.54")],
                _stroke("0.254"),
                _fill_none(),
            ],
        ],
        # Pins sub-symbol
        [
            _k("symbol"),
            _q(f"{name}_1_1"),
            _pin("1", "0", "3.81", "270", "1.27"),
            _pin("2", "0", "-3.81", "90", "1.27"),
        ],
    ]


# -- Resistor template (US zigzag body) ---


def _zigzag_polyline(points: list[tuple[str, str]]) -> list[SExpr]:
    """A polyline from a list of (x, y) coordinate pairs."""
    pts: list[SExpr] = [_k("pts")]
    for x, y in points:
        pts.append([_k("xy"), _k(x), _k(y)])
    return [_k("polyline"), pts, _stroke(), _fill_none()]


def resistor_symbol(name: str, props: dict[str, str]) -> list[SExpr]:
    """
    Complete ``(symbol ...)`` tree for a resistor.

    US zigzag body matching KiCad Device:R_US, two passive pins.
    """
    return [
        _k("symbol"),
        _q(name),
        [_k("pin_numbers"), [_k("hide"), _k("yes")]],
        [_k("pin_names"), [_k("offset"), _k("0")]],
        [_k("exclude_from_sim"), _k("no")],
        [_k("in_bom"), _k("yes")],
        [_k("on_board"), _k("yes")],
        # Visible properties
        [
            _k("property"),
            _q("Reference"),
            _q(props.get("Reference", "R")),
            [_k("at"), _k("2.54"), _k("0"), _k("90")],
            [
                _k("effects"),
                [_k("font"), [_k("size"), _k("1.27"), _k("1.27")]],
            ],
        ],
        [
            _k("property"),
            _q("Value"),
            _q(props.get("Value", name)),
            [_k("at"), _k("-2.54"), _k("0"), _k("90")],
            [
                _k("effects"),
                [_k("font"), [_k("size"), _k("1.27"), _k("1.27")]],
            ],
        ],
        # Hidden properties
        _hidden_property("Footprint", props.get("Footprint", "")),
        _hidden_property("Datasheet", props.get("Datasheet", "~")),
        _hidden_property("Description", props.get("Description", "")),
        _hidden_property("ki_keywords", props.get("ki_keywords", "")),
        # Graphics sub-symbol: US zigzag body (5 polylines from Device:R_US)
        [
            _k("symbol"),
            _q(f"{name}_0_1"),
            # Top lead stub
            _zigzag_polyline([("0", "2.286"), ("0", "2.54")]),
            # Upper zigzag
            _zigzag_polyline(
                [
                    ("0", "2.286"),
                    ("1.016", "1.905"),
                    ("0", "1.524"),
                    ("-1.016", "1.143"),
                    ("0", "0.762"),
                ]
            ),
            # Middle zigzag
            _zigzag_polyline(
                [
                    ("0", "0.762"),
                    ("1.016", "0.381"),
                    ("0", "0"),
                    ("-1.016", "-0.381"),
                    ("0", "-0.762"),
                ]
            ),
            # Lower zigzag
            _zigzag_polyline(
                [
                    ("0", "-0.762"),
                    ("1.016", "-1.143"),
                    ("0", "-1.524"),
                    ("-1.016", "-1.905"),
                    ("0", "-2.286"),
                ]
            ),
            # Bottom lead stub
            _zigzag_polyline([("0", "-2.286"), ("0", "-2.54")]),
        ],
        # Pins sub-symbol
        [
            _k("symbol"),
            _q(f"{name}_1_1"),
            _pin("1", "0", "3.81", "270", "1.27"),
            _pin("2", "0", "-3.81", "90", "1.27"),
        ],
    ]


# -- Capacitor template (parallel plates) ---


def capacitor_symbol(name: str, props: dict[str, str]) -> list[SExpr]:
    """
    Complete ``(symbol ...)`` tree for an unpolarized capacitor.

    Parallel plate body matching KiCad Device:C, two passive pins.
    """
    return [
        _k("symbol"),
        _q(name),
        [_k("pin_numbers"), [_k("hide"), _k("yes")]],
        [_k("pin_names"), [_k("offset"), _k("0.254")]],
        [_k("exclude_from_sim"), _k("no")],
        [_k("in_bom"), _k("yes")],
        [_k("on_board"), _k("yes")],
        # Visible properties
        [
            _k("property"),
            _q("Reference"),
            _q(props.get("Reference", "C")),
            [_k("at"), _k("0.635"), _k("2.54"), _k("0")],
            [
                _k("effects"),
                [_k("font"), [_k("size"), _k("1.27"), _k("1.27")]],
                [_k("justify"), _k("left")],
            ],
        ],
        [
            _k("property"),
            _q("Value"),
            _q(props.get("Value", name)),
            [_k("at"), _k("0.635"), _k("-2.54"), _k("0")],
            [
                _k("effects"),
                [_k("font"), [_k("size"), _k("1.27"), _k("1.27")]],
                [_k("justify"), _k("left")],
            ],
        ],
        # Hidden properties
        _hidden_property("Footprint", props.get("Footprint", "")),
        _hidden_property("Datasheet", props.get("Datasheet", "~")),
        _hidden_property("Description", props.get("Description", "")),
        _hidden_property("ki_keywords", props.get("ki_keywords", "")),
        # Graphics sub-symbol: two parallel plates
        [
            _k("symbol"),
            _q(f"{name}_0_1"),
            [
                _k("polyline"),
                [
                    _k("pts"),
                    [_k("xy"), _k("-2.032"), _k("0.762")],
                    [_k("xy"), _k("2.032"), _k("0.762")],
                ],
                _stroke("0.508"),
                _fill_none(),
            ],
            [
                _k("polyline"),
                [
                    _k("pts"),
                    [_k("xy"), _k("-2.032"), _k("-0.762")],
                    [_k("xy"), _k("2.032"), _k("-0.762")],
                ],
                _stroke("0.508"),
                _fill_none(),
            ],
        ],
        # Pins sub-symbol
        [
            _k("symbol"),
            _q(f"{name}_1_1"),
            _pin("1", "0", "3.81", "270", "2.794"),
            _pin("2", "0", "-3.81", "90", "2.794"),
        ],
    ]


# -- Inductor template (arc coil) ---


def _arc(start_y: str, mid_y: str, end_y: str) -> list[SExpr]:
    """Single arc segment for the inductor coil body."""
    return [
        _k("arc"),
        [_k("start"), _k("0"), _k(start_y)],
        [_k("mid"), _k("0.6323"), _k(mid_y)],
        [_k("end"), _k("0"), _k(end_y)],
        _stroke(),
        _fill_none(),
    ]


def inductor_symbol(name: str, props: dict[str, str]) -> list[SExpr]:
    """
    Complete ``(symbol ...)`` tree for an inductor.

    Four-arc coil body matching KiCad Device:L, two passive pins.
    """
    return [
        _k("symbol"),
        _q(name),
        [_k("pin_numbers"), [_k("hide"), _k("yes")]],
        [_k("pin_names"), [_k("offset"), _k("1.016")], [_k("hide"), _k("yes")]],
        [_k("exclude_from_sim"), _k("no")],
        [_k("in_bom"), _k("yes")],
        [_k("on_board"), _k("yes")],
        # Visible properties
        [
            _k("property"),
            _q("Reference"),
            _q(props.get("Reference", "L")),
            [_k("at"), _k("-1.27"), _k("0"), _k("90")],
            [
                _k("effects"),
                [_k("font"), [_k("size"), _k("1.27"), _k("1.27")]],
            ],
        ],
        [
            _k("property"),
            _q("Value"),
            _q(props.get("Value", name)),
            [_k("at"), _k("1.905"), _k("0"), _k("90")],
            [
                _k("effects"),
                [_k("font"), [_k("size"), _k("1.27"), _k("1.27")]],
            ],
        ],
        # Hidden properties
        _hidden_property("Footprint", props.get("Footprint", "")),
        _hidden_property("Datasheet", props.get("Datasheet", "~")),
        _hidden_property("Description", props.get("Description", "")),
        _hidden_property("ki_keywords", props.get("ki_keywords", "")),
        # Graphics sub-symbol: four arcs
        [
            _k("symbol"),
            _q(f"{name}_0_1"),
            _arc("2.54", "1.905", "1.27"),
            _arc("1.27", "0.635", "0"),
            _arc("0", "-0.635", "-1.27"),
            _arc("-1.27", "-1.905", "-2.54"),
        ],
        # Pins sub-symbol
        [
            _k("symbol"),
            _q(f"{name}_1_1"),
            _pin("1", "0", "3.81", "270", "1.27"),
            _pin("2", "0", "-3.81", "90", "1.27"),
        ],
    ]


# -- Stub template (properties only, no graphics) ---


def stub_symbol(name: str, props: dict[str, str]) -> list[SExpr]:
    """
    Minimal symbol with properties but no graphics or pins.

    Used for part categories that don't have a standard schematic
    symbol template (ICs, connectors, etc.).
    """
    return [
        _k("symbol"),
        _q(name),
        [_k("exclude_from_sim"), _k("no")],
        [_k("in_bom"), _k("yes")],
        [_k("on_board"), _k("yes")],
        _hidden_property("Reference", props.get("Reference", "U")),
        _hidden_property("Value", props.get("Value", name)),
        _hidden_property("Footprint", props.get("Footprint", "")),
        _hidden_property("Datasheet", props.get("Datasheet", "~")),
        _hidden_property("Description", props.get("Description", "")),
        _hidden_property("ki_keywords", props.get("ki_keywords", "")),
    ]


# -- Dispatch ---

_TEMPLATES: dict[str, Callable] = {
    "resistor": resistor_symbol,
    "resistor_iec": resistor_symbol_iec,
    "capacitor": capacitor_symbol,
    "inductor": inductor_symbol,
}

_RESERVED_PROPERTY_KEYS = frozenset(
    {
        "Reference",
        "Value",
        "Footprint",
        "Datasheet",
        "Description",
        "ki_keywords",
    }
)


def spec_property_key(spec_key: str) -> str:
    """Map a part spec key to a non-conflicting KiCad property name."""
    if spec_key in _RESERVED_PROPERTY_KEYS:
        return f"spec_{spec_key}"
    return spec_key


def _spec_property(key: str, value: str, *, hidden: bool = True) -> list[SExpr]:
    """A specification property at (0,0,0).  Hidden by default."""
    effects: list[SExpr] = [
        _k("effects"),
        [_k("font"), [_k("size"), _k("1.27"), _k("1.27")]],
    ]
    if hidden:
        effects.append([_k("hide"), _k("yes")])
    return [
        _k("property"),
        _q(key),
        _q(value),
        [_k("at"), _k("0"), _k("0"), _k("0")],
        effects,
    ]


def symbol_for_part(
    part: Part,
    categories: dict[str, CategoryDef] | None = None,
    *,
    visible_specs: set[str] | None = None,
) -> list[SExpr]:
    """
    Generate the appropriate symbol tree for *part*.

    Jellybean parts whose category has a ``symbol_template`` get full
    graphic templates. Everything else gets a stub with properties only.

    Part specifications are appended as hidden properties. Any spec
    name in *visible_specs* keeps its visible state (not forced hidden),
    so that user-toggled visibility survives re-sync.
    """
    props = build_properties(part)
    if part.tier == Tier.JELLYBEAN and categories:
        cat_def = categories.get(part.category)
        if cat_def and cat_def.symbol_template:
            template_fn = _TEMPLATES.get(cat_def.symbol_template)
            if template_fn:
                tree = template_fn(part.name, props)
                _append_specs(tree, part, visible_specs)
                return tree
    tree = stub_symbol(part.name, props)
    _append_specs(tree, part, visible_specs)
    return tree


def _append_specs(
    tree: list[SExpr],
    part: Part,
    visible_specs: set[str] | None,
) -> None:
    """Append specification properties to a symbol tree."""
    if not part.specifications:
        return
    visible = visible_specs or set()
    for key, value in part.specifications.items():
        prop_key = spec_property_key(key)
        tree.append(_spec_property(prop_key, value, hidden=prop_key not in visible))
