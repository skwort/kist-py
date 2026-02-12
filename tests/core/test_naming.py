"""Tests for the naming engine -- value normalisation."""

import pytest

from kist.core.naming import (
    normalise_capacitance,
    normalise_current,
    normalise_frequency,
    normalise_impedance,
    normalise_inductance,
    normalise_package,
    normalise_percentage,
    normalise_power,
    normalise_resistance,
    normalise_voltage,
)

# -- normalise_resistance ----------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("10kΩ", "10K"),
        ("4.7kΩ", "4K7"),
        ("100Ω", "100R"),
        ("1MΩ", "1M"),
        ("4R7", "4R7"),
        ("10k", "10K"),
        ("4.7k", "4K7"),
        ("2.2kΩ", "2K2"),
        ("47Ω", "47R"),
        ("0.47Ω", "0R47"),
        ("1Ω", "1R"),
        ("10Ω", "10R"),
        ("100kΩ", "100K"),
        ("2.2MΩ", "2M2"),
    ],
)
def test_normalise_resistance(input_val, expected):
    assert normalise_resistance(input_val) == expected


# -- normalise_capacitance ---------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("0.1µF", "100n"),
        ("100nF", "100n"),
        ("4.7µF", "4u7"),
        ("10pF", "10p"),
        ("100n", "100n"),
        ("1µF", "1u"),
        ("10µF", "10u"),
        ("22pF", "22p"),
        ("2.2nF", "2n2"),
        ("100µF", "100u"),
        ("1nF", "1n"),
        ("470pF", "470p"),
        ("4u7", "4u7"),
    ],
)
def test_normalise_capacitance(input_val, expected):
    assert normalise_capacitance(input_val) == expected


# -- normalise_inductance ----------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("10µH", "10u"),
        ("4.7µH", "4u7"),
        ("100nH", "100n"),
        ("1µH", "1u"),
        ("2.2µH", "2u2"),
        ("100µH", "100u"),
        ("22nH", "22n"),
        ("330nH", "330n"),
    ],
)
def test_normalise_inductance(input_val, expected):
    assert normalise_inductance(input_val) == expected


# -- normalise_voltage -------------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("3.3V", "3V3"),
        ("50V", "50V"),
        ("1.8V", "1V8"),
        ("5V", "5V"),
        ("12V", "12V"),
        ("25V", "25V"),
        ("100V", "100V"),
        ("16V", "16V"),
        ("30V", "30V"),
        ("40V", "40V"),
        ("63V", "63V"),
    ],
)
def test_normalise_voltage(input_val, expected):
    assert normalise_voltage(input_val) == expected


# -- normalise_current -------------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("1A", "1A"),
        ("1.2A", "1200mA"),
        ("500mA", "500mA"),
        ("5.8A", "5800mA"),
        ("2A", "2A"),
        ("3A", "3A"),
        ("200mA", "200mA"),
        ("20mA", "20mA"),
    ],
)
def test_normalise_current(input_val, expected):
    assert normalise_current(input_val) == expected


# -- normalise_power ---------------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("500mW", "500mW"),
        ("400W", "400W"),
        ("1W", "1W"),
        ("250mW", "250mW"),
        ("62.5mW", "62mW"),
    ],
)
def test_normalise_power(input_val, expected):
    assert normalise_power(input_val) == expected


# -- normalise_frequency -----------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("8MHz", "8MHz"),
        ("16MHz", "16MHz"),
        ("32.768kHz", "32K768Hz"),
        ("100MHz", "100MHz"),
        ("1GHz", "1GHz"),
        ("48MHz", "48MHz"),
    ],
)
def test_normalise_frequency(input_val, expected):
    assert normalise_frequency(input_val) == expected


# -- normalise_percentage ----------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("1%", "1PCT"),
        ("5%", "5PCT"),
        ("20%", "20PCT"),
        ("±10%", "10PCT"),
        ("0.1%", "0.1PCT"),
    ],
)
def test_normalise_percentage(input_val, expected):
    assert normalise_percentage(input_val) == expected


# -- normalise_impedance -----------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("600Ω", "600R"),
        ("2200Ω", "2200R"),
        ("1kΩ", "1000R"),
        ("100Ω", "100R"),
    ],
)
def test_normalise_impedance(input_val, expected):
    assert normalise_impedance(input_val) == expected


# -- normalise_package -------------------------------------------------------


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("SOIC-8", "SO8"),
        ("SO-8", "SO8"),
        ("LQFP-64", "LQFP64"),
        ("0603", "0603"),
        ("SOT-23", "SOT23"),
        ("SOT-23-5", "SOT235"),
        ("SOT-23-6", "SOT236"),
        ("QFN-32", "QFN32"),
        ("TSSOP-16", "TSSOP16"),
        ("MSOP-8", "MSOP8"),
        ("SOT-223", "SOT223"),
        # Unknown packages: uppercase, strip alpha-digit hyphens
        ("SMA", "SMA"),
        ("SOD-323", "SOD323"),
        ("HC-49", "HC49"),
        ("10x10", "10X10"),
    ],
)
def test_normalise_package(input_val, expected):
    assert normalise_package(input_val) == expected
