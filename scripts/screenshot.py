"""
Generate TUI screenshots for documentation.

Usage:
    uv run python scripts/screenshot.py [OPTIONS]

Creates a temporary library with demo parts and captures SVG screenshots.

Options:
    --screen SCREEN   Screen to capture: browse, detail, add (default: browse)
    --size WxH        Terminal size (default: 120x36)
    --output PATH     Output path (default: site/assets/<screen>-screenshot.svg)
    --part NAME       Part to open in detail view (default: IC-STM32F405RGT6-LQFP64)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import tempfile
from pathlib import Path

from kist.core.database import PartsDatabase
from kist.core.library import init_library
from kist.models.part import (
    Alternate,
    JellybeanPart,
    ProprietaryPart,
    SemiJellybeanPart,
    SupplierInfo,
    Tier,
)

# -- Demo parts ---


def _jb(**kw: object) -> JellybeanPart:
    defaults = {
        "tier": Tier.JELLYBEAN,
        "keywords": [],
        "exclude_from_bom": False,
        "exclude_from_board": False,
    }
    return JellybeanPart(**(defaults | kw))  # type: ignore[arg-type]


def _sj(**kw: object) -> SemiJellybeanPart:
    defaults = {
        "tier": Tier.SEMI_JELLYBEAN,
        "keywords": [],
        "exclude_from_bom": False,
        "exclude_from_board": False,
    }
    return SemiJellybeanPart(**(defaults | kw))  # type: ignore[arg-type]


def _pr(**kw: object) -> ProprietaryPart:
    defaults = {
        "tier": Tier.PROPRIETARY,
        "keywords": [],
        "exclude_from_bom": False,
        "exclude_from_board": False,
    }
    return ProprietaryPart(**(defaults | kw))  # type: ignore[arg-type]


DEMO_PARTS = [
    _jb(
        name="RES-10K-1PCT-0603",
        description="10K 1% 100mW thick film resistor, 0603",
        category="RES",
        package="0603",
        mounting="smd",
        value="10K",
        reference="R",
        symbol="00k-Resistors:RES-10K-1PCT-0603",
        footprint="R_0603",
        tags=["resistor", "10k", "1%"],
        specifications={"resistance": "10K", "tolerance": "1%", "power": "100mW"},
        alternates=[Alternate(mpn="RC0603FR-0710KL", manufacturer="Yageo")],
        suppliers={"digikey": SupplierInfo(sku="311-10.0KHRCT-ND")},
    ),
    _jb(
        name="RES-100R-1PCT-0402",
        description="100R 1% 62.5mW thick film resistor, 0402",
        category="RES",
        package="0402",
        mounting="smd",
        value="100R",
        reference="R",
        symbol="00k-Resistors:RES-100R-1PCT-0402",
        footprint="R_0402",
        tags=["resistor"],
        specifications={"resistance": "100R", "tolerance": "1%", "power": "62.5mW"},
        alternates=[],
        suppliers={},
    ),
    _jb(
        name="RES-4K7-1PCT-0603",
        description="4.7K 1% 100mW thick film resistor, 0603",
        category="RES",
        package="0603",
        mounting="smd",
        value="4K7",
        reference="R",
        symbol="00k-Resistors:RES-4K7-1PCT-0603",
        footprint="R_0603",
        tags=["resistor"],
        specifications={"resistance": "4K7", "tolerance": "1%", "power": "100mW"},
        alternates=[],
        suppliers={},
    ),
    _jb(
        name="CAP-100n-50V-X7R-0603",
        description="100nF 50V X7R ceramic capacitor, 0603",
        category="CAP",
        subcategory="CER",
        package="0603",
        mounting="smd",
        value="100n",
        reference="C",
        symbol="01k-Capacitors:CAP-100n-50V-X7R-0603",
        footprint="C_0603",
        tags=["capacitor", "100nf", "decoupling"],
        specifications={"capacitance": "100n", "voltage": "50V", "dielectric": "X7R"},
        alternates=[Alternate(mpn="CL10B104KB8NNNC", manufacturer="Samsung")],
        suppliers={"digikey": SupplierInfo(sku="1276-1003-1-ND")},
    ),
    _jb(
        name="CAP-10u-25V-X5R-0805",
        description="10uF 25V X5R ceramic capacitor, 0805",
        category="CAP",
        subcategory="CER",
        package="0805",
        mounting="smd",
        value="10u",
        reference="C",
        symbol="01k-Capacitors:CAP-10u-25V-X5R-0805",
        footprint="C_0805",
        tags=["capacitor", "10uf"],
        specifications={"capacitance": "10u", "voltage": "25V", "dielectric": "X5R"},
        alternates=[],
        suppliers={},
    ),
    _jb(
        name="CAP-1u-16V-X7R-0402",
        description="1uF 16V X7R ceramic capacitor, 0402",
        category="CAP",
        subcategory="CER",
        package="0402",
        mounting="smd",
        value="1u",
        reference="C",
        symbol="01k-Capacitors:CAP-1u-16V-X7R-0402",
        footprint="C_0402",
        tags=["capacitor"],
        specifications={"capacitance": "1u", "voltage": "16V", "dielectric": "X7R"},
        alternates=[],
        suppliers={},
    ),
    _jb(
        name="IND-10u-1A-0805",
        description="10uH 1A shielded inductor, 0805",
        category="IND",
        package="0805",
        mounting="smd",
        value="10u",
        reference="L",
        symbol="02k-Inductors:IND-10u-1A-0805",
        footprint="L_0805",
        tags=["inductor", "power"],
        specifications={"inductance": "10u", "current": "1A"},
        alternates=[],
        suppliers={},
    ),
    _sj(
        name="IC-TL072-SO8",
        description="Dual JFET op-amp, low noise, SO-8",
        category="IC",
        package="SO-8",
        mounting="smd",
        value="TL072",
        reference="U",
        symbol="05k-ICs:IC-TL072-SO8",
        footprint="SOIC-8",
        tags=["opamp", "dual", "audio"],
        mpn="TL072CDR",
        manufacturer="Texas Instruments",
        base_pn="TL072",
        alternates=[Alternate(mpn="TL072BCP", manufacturer="STMicroelectronics")],
        suppliers={"digikey": SupplierInfo(sku="296-1775-1-ND")},
    ),
    _pr(
        name="IC-STM32F405RGT6-LQFP64",
        description="ARM Cortex-M4 MCU, 168MHz, 1MB flash",
        category="IC",
        package="LQFP-64",
        mounting="smd",
        value="STM32F405RGT6",
        reference="U",
        symbol="05k-ICs:IC-STM32F405RGT6-LQFP64",
        footprint="LQFP-64",
        tags=["mcu", "arm", "stm32"],
        mpn="STM32F405RGT6",
        manufacturer="STMicroelectronics",
        datasheet="https://www.st.com/resource/en/datasheet/stm32f405rg.pdf",
        suppliers={
            "digikey": SupplierInfo(sku="497-11767-ND"),
            "mouser": SupplierInfo(sku="511-STM32F405RGT6"),
        },
    ),
    _pr(
        name="IC-WM8960CGEFL-QFN32",
        description="Stereo audio codec, I2C, 24-bit",
        category="IC",
        package="QFN-32",
        mounting="smd",
        value="WM8960",
        reference="U",
        symbol="05k-ICs:IC-WM8960CGEFL-QFN32",
        footprint="QFN-32",
        tags=["audio", "codec"],
        mpn="WM8960CGEFL/RV",
        manufacturer="Cirrus Logic",
        suppliers={"digikey": SupplierInfo(sku="598-WM8960CGEFL/RV-ND")},
    ),
    _pr(
        name="IC-ESP32-S3-WROOM-1",
        description="WiFi+BLE module, dual-core, 8MB flash",
        category="IC",
        package="MODULE",
        mounting="smd",
        value="ESP32-S3",
        reference="U",
        symbol="05k-ICs:IC-ESP32-S3-WROOM-1",
        footprint="ESP32-S3-WROOM-1",
        tags=["wifi", "ble", "esp32"],
        mpn="ESP32-S3-WROOM-1-N8",
        manufacturer="Espressif",
        suppliers={"digikey": SupplierInfo(sku="1965-N8-ND")},
    ),
    _sj(
        name="DIO-1N4148W-SOD123",
        description="Fast switching diode, 100V 150mA",
        category="DIO",
        package="SOD-123",
        mounting="smd",
        value="1N4148W",
        reference="D",
        symbol="03k-Diodes:DIO-1N4148W-SOD123",
        footprint="D_SOD-123",
        tags=["diode", "switching"],
        mpn="1N4148W-7-F",
        manufacturer="Diodes Inc",
        base_pn="1N4148",
        alternates=[Alternate(mpn="1N4148WS", manufacturer="ON Semi")],
        suppliers={"digikey": SupplierInfo(sku="1N4148W-FDICT-ND")},
    ),
    _pr(
        name="CONN-USB-C-16P",
        description="USB-C receptacle, 16-pin, mid-mount",
        category="CONN",
        package="SMD",
        mounting="smd",
        value="USB-C",
        reference="J",
        symbol="06k-Connectors:CONN-USB-C-16P",
        footprint="USB_C_Receptacle",
        tags=["usb", "type-c"],
        mpn="TYPE-C-31-M-12",
        manufacturer="Korean Hroparts",
        suppliers={"lcsc": SupplierInfo(sku="C165948")},
    ),
    _jb(
        name="XTAL-8MHz-20ppm-3225",
        description="8MHz crystal, 20ppm, 3225",
        category="XTAL",
        package="3225",
        mounting="smd",
        value="8MHz",
        reference="Y",
        symbol="09k-Crystals:XTAL-8MHz-20ppm-3225",
        footprint="Crystal_SMD_3225",
        tags=["crystal", "8mhz"],
        specifications={"frequency": "8MHz", "tolerance": "20ppm"},
        alternates=[],
        suppliers={},
    ),
]


def create_demo_library() -> Path:
    """Create a temporary library populated with demo parts."""
    tmpdir = Path(tempfile.mkdtemp(prefix="kist-demo-"))
    init_library(tmpdir)

    db = PartsDatabase(tmpdir / "parts.json")
    db.load()
    for part in DEMO_PARTS:
        db.add(part)

    return tmpdir


def _strip_window_chrome(svg: str) -> str:
    """
    Remove Rich's terminal window decorator and collapse its margins/padding
    so the output is just the raw terminal content.

    Rich hardcodes: 1px margin, 40px top-padding (title bar area), 8px
    side/bottom padding, rounded corners, a border stroke, and macOS
    traffic-light circles.  We strip all of that.
    """
    # Rich's hardcoded layout constants
    margin = 1
    pad_top = 40
    pad_side = 8
    pad_bottom = 8
    # How much to trim from top (margin + title-bar padding)
    trim_top = margin + pad_top
    # How much to trim from sides/bottom
    trim_side = margin + pad_side
    trim_bottom = margin + pad_bottom

    # Remove the traffic-light circles group
    svg = re.sub(
        r"\s*<g transform=\"translate\(26,22\)\">\s*"
        r"<circle[^/]*/>\s*<circle[^/]*/>\s*<circle[^/]*/>\s*</g>\s*",
        "\n",
        svg,
    )
    # Remove the title text element
    svg = re.sub(r"<text[^>]*-title[^>]*>[^<]*</text>", "", svg)

    # Shrink the viewBox to remove margins and header padding
    def _shrink_viewbox(m: re.Match[str]) -> str:
        w, h = float(m.group(1)), float(m.group(2))
        new_w = w - trim_side * 2
        new_h = h - trim_top - trim_bottom
        return f'viewBox="0 0 {new_w:.10g} {new_h:.10g}"'

    svg = re.sub(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', _shrink_viewbox, svg)

    # Expand the background rect to fill the new viewBox and strip the border
    def _fix_bg_rect(m: re.Match[str]) -> str:
        w, h = float(m.group(1)), float(m.group(2))
        new_w = w - trim_side * 2 + margin * 2
        new_h = h - trim_top - trim_bottom + margin * 2
        return f'<rect fill="{m.group(3)}" x="0" y="0" width="{new_w:.10g}" height="{new_h:.10g}" />'

    svg = re.sub(
        r'<rect fill="([^"]*)"[^>]*x="\d+"[^>]*y="\d+"[^>]*'
        r'width="([\d.]+)"[^>]*height="([\d.]+)"[^/]*/>'
        r"(?=.*?clip-path)",  # only match the first (chrome) rect
        lambda m: (
            f'<rect fill="{m.group(1)}" x="0" y="0" '
            f'width="{float(m.group(2)) - trim_side * 2 + margin * 2:.10g}" '
            f'height="{float(m.group(3)) - trim_top - trim_bottom + margin * 2:.10g}" />'
        ),
        svg,
        count=1,
    )

    # Shift the content group up-left to account for removed padding
    def _fix_translate(m: re.Match[str]) -> str:
        x, y = float(m.group(1)), float(m.group(2))
        new_x = x - trim_side
        new_y = y - trim_top
        return f"translate({new_x:.10g}, {new_y:.10g})"

    svg = re.sub(
        r"translate\(([\d.]+),\s*([\d.]+)\)",
        _fix_translate,
        svg,
        count=1,
    )

    return svg


async def capture(
    screen: str,
    size: tuple[int, int],
    output: Path,
    part_name: str,
) -> None:
    """Capture a screenshot of the TUI."""
    from kist.tui.app import KistApp
    from kist.tui.screens.detail import DetailModal

    lib_path = create_demo_library()
    os.chdir(lib_path)

    start = "add" if screen == "add" else None
    app = KistApp(start_screen=start)

    async with app.run_test(size=size) as pilot:
        # Wait for mount + library discovery + data load
        for _ in range(10):
            await pilot.pause()
        app.parts_version += 1
        for _ in range(5):
            await pilot.pause()

        if screen == "detail":
            # Find the requested part and open its detail modal
            db = PartsDatabase(lib_path / "parts.json")
            db.load()
            part = next(
                (p for p in db.list_parts() if p.name == part_name),
                None,
            )
            if part is None:
                print(f"Part not found: {part_name}")
                print("Available:", [p.name for p in db.list_parts()])
                return

            app.push_screen(DetailModal(part))
            for _ in range(10):
                await pilot.pause()

        output.parent.mkdir(parents=True, exist_ok=True)
        svg = _strip_window_chrome(app.export_screenshot(title=""))
        output.write_text(svg, encoding="utf-8")
        print(f"Saved: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture kist TUI screenshots")
    parser.add_argument(
        "--screen",
        default="browse",
        choices=["browse", "detail", "add"],
        help="Screen to capture (default: browse)",
    )
    parser.add_argument(
        "--size",
        default="120x36",
        help="Terminal size as WxH (default: 120x36)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path (default: site/assets/<screen>-screenshot.svg)",
    )
    parser.add_argument(
        "--part",
        default="IC-STM32F405RGT6-LQFP64",
        help="Part to open in detail view (default: IC-STM32F405RGT6-LQFP64)",
    )
    args = parser.parse_args()

    w, h = (int(x) for x in args.size.split("x"))
    # Resolve to absolute before capture() changes CWD to the temp library
    output = (
        args.output or Path(f"site/assets/{args.screen}-screenshot.svg")
    ).resolve()

    asyncio.run(capture(args.screen, (w, h), output, args.part))


if __name__ == "__main__":
    main()
