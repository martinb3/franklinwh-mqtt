"""Checks on the icon pixel maps.

These catch the class of mistake that is invisible while writing the art out
as strings but obvious the moment it lights up on a matrix.
"""

import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "generate_icons", Path(__file__).parent.parent / "icons" / "generate_icons.py"
)
generate_icons = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate_icons)

ICONS = generate_icons.ICONS

# Icons whose subject is symmetric left-to-right. The battery is excluded on
# purpose: its terminal nub sits on the right. The pylon tapers and the bolt
# leans, so neither is mirrored either.
MIRRORED_LEFT_RIGHT = ["fwh_solar", "fwh_load"]

# The battery is symmetric the other way — its nub is centred vertically.
MIRRORED_TOP_BOTTOM = ["fwh_solar", "fwh_soc", "fwh_soc_chg", "fwh_soc_dis"]


@pytest.mark.parametrize("name", list(ICONS))
def test_icon_is_eight_by_eight(name):
    rows = ICONS[name][0]
    assert len(rows) == 8, f"{name} has {len(rows)} rows"
    assert all(len(row) == 8 for row in rows), f"{name} has a row of wrong width"


@pytest.mark.parametrize("name", list(ICONS))
def test_every_character_has_a_color(name):
    rows, palette = ICONS[name]
    used = {ch for row in rows for ch in row if ch != "."}
    assert used <= set(palette), f"{name} uses {used - set(palette)} with no color"


@pytest.mark.parametrize("name", MIRRORED_LEFT_RIGHT)
def test_symmetric_icons_are_mirrored_left_right(name):
    """The sun originally drifted left: rows 0 and 7 were 'R..R..R.'."""
    for i, row in enumerate(ICONS[name][0]):
        assert row == row[::-1], f"{name} row {i} ({row!r}) is not left-right mirrored"


@pytest.mark.parametrize("name", MIRRORED_TOP_BOTTOM)
def test_symmetric_icons_are_mirrored_top_bottom(name):
    rows = ICONS[name][0]
    for i in range(4):
        assert rows[i] == rows[7 - i], f"{name} row {i} does not mirror row {7 - i}"


def test_battery_variants_differ_only_in_color():
    shapes = {
        name: [row.translate(str.maketrans("GAI", "XXX")) for row in ICONS[name][0]]
        for name in ("fwh_soc", "fwh_soc_chg", "fwh_soc_dis")
    }
    assert len(set(map(str, shapes.values()))) == 1, "battery states changed shape"
