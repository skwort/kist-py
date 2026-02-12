"""Well-known category definitions for ``kist init``."""

from __future__ import annotations

from kist.models.config import CategoryDef

WELL_KNOWN_CATEGORIES: dict[str, CategoryDef] = {
    "RES": CategoryDef(
        name="Resistors",
        refdes="R",
        key_specs=["resistance", "tolerance"],
        value_field="resistance",
        symbol_template="resistor",
    ),
    "CAP": CategoryDef(
        name="Capacitors",
        refdes="C",
        key_specs=["capacitance", "voltage_rating"],
        subcategory_key_specs={
            "CER": ["capacitance", "voltage_rating", "dielectric"],
            "ELEC": ["capacitance", "voltage_rating"],
            "TANT": ["capacitance", "voltage_rating"],
            "FILM": ["capacitance", "voltage_rating"],
        },
        subcategory_names={
            "CER": "Ceramic",
            "ELEC": "Electrolytic",
            "TANT": "Tantalum",
            "FILM": "Film",
        },
        value_field="capacitance",
        symbol_template="capacitor",
    ),
    "IND": CategoryDef(
        name="Inductors",
        refdes="L",
        key_specs=["inductance", "current_rating"],
        subcategory_key_specs={
            "FERRITE": ["impedance_100mhz", "current_rating"],
            "CM": ["impedance", "current_rating"],
            "CHOKE": ["inductance", "current_rating"],
        },
        value_field="inductance",
        symbol_template="inductor",
    ),
    "DIO": CategoryDef(
        name="Diodes",
        refdes="D",
        key_specs=["reverse_voltage", "forward_current"],
        subcategory_key_specs={
            "SCHOTTKY": ["reverse_voltage", "forward_current"],
            "ZENER": ["zener_voltage", "power_rating"],
            "TVS": ["standoff_voltage", "peak_power"],
            "LED": ["colour"],
        },
        value_field=["reverse_voltage", "forward_current"],
        subcategory_value_field={
            "LED": "colour",
            "ZENER": "zener_voltage",
            "TVS": "standoff_voltage",
            "SCHOTTKY": ["reverse_voltage", "forward_current"],
        },
    ),
    "TRAN": CategoryDef(
        name="Transistors",
        refdes="Q",
        subcategory_key_specs={
            "NMOS": ["vds_max", "id_max"],
            "PMOS": ["vds_max", "id_max"],
            "NPN": ["vceo", "ic_max"],
            "PNP": ["vceo", "ic_max"],
        },
        subcategory_value_field={
            "NMOS": ["vds_max", "id_max"],
            "PMOS": ["vds_max", "id_max"],
            "NPN": ["vceo", "ic_max"],
            "PNP": ["vceo", "ic_max"],
        },
    ),
    "IC": CategoryDef(
        name="ICs",
        refdes="U",
    ),
    "CONN": CategoryDef(
        name="Connectors",
        refdes="J",
    ),
    "SW": CategoryDef(
        name="Switches",
        refdes="SW",
    ),
    "REL": CategoryDef(
        name="Relays",
        refdes="K",
    ),
    "XTAL": CategoryDef(
        name="Crystals",
        refdes="Y",
        key_specs=["frequency", "load_capacitance"],
        value_field="frequency",
    ),
    "FUSE": CategoryDef(
        name="Fuses",
        refdes="F",
        key_specs=["current_rating", "voltage_rating"],
        subcategory_key_specs={
            "PTC": ["hold_current", "voltage_rating"],
        },
        value_field=["current_rating", "voltage_rating"],
        subcategory_value_field={
            "PTC": ["hold_current", "voltage_rating"],
        },
    ),
    "TFRM": CategoryDef(
        name="Transformers",
        refdes="T",
    ),
    "TP": CategoryDef(
        name="Test Points",
        refdes="TP",
    ),
    "FID": CategoryDef(
        name="Fiducials",
        refdes="FID",
    ),
    "MECH": CategoryDef(
        name="Mechanical",
        refdes="H",
    ),
    "MISC": CategoryDef(
        name="Miscellaneous",
        refdes="U",
    ),
}
