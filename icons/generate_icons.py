#!/usr/bin/env python3
"""Generate (and optionally upload) the 8x8 icons for the Awtrix apps.

Awtrix renders an icon by filename from the device's /ICONS folder, so the
names here match the AWTRIX_ICON_* values passed to the bridge. Icons live
only on the clock's flash — re-flashing with "erase" wipes them — so this
script exists to recreate them from scratch.

Awtrix's GIF renderer wants 8-bit GIFs with no transparency; "off" pixels are
written as solid black, which is what an unlit matrix pixel looks like anyway.

    python generate_icons.py                    # write GIFs to ./
    python generate_icons.py --out /tmp/icons   # write elsewhere
    python generate_icons.py --upload awtrix_abc123.local

Requires pillow (see requirements-dev.txt).
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
import uuid
from pathlib import Path

from PIL import Image

# Each icon is 8 rows of 8 characters. "." is an unlit pixel; every other
# character indexes that icon's palette. Colors matter as much as shapes at
# this size — the apps are told apart by hue before the glyph resolves.
ICONS: dict[str, tuple[list[str], dict[str, tuple[int, int, int]]]] = {
    # Battery, for state of charge. Three fills for the same shape: the
    # bridge swaps them by the sign of battery power. At 8x8 there is no room
    # for an arrow or bolt inside the 4x4 interior, so direction is carried by
    # color — which reads from across the room, unlike a 2px glyph.
    "fwh_soc": (  # idle: neither charging nor discharging
        [
            "........",
            ".WWWWWW.",
            ".WIIIIW.",
            ".WIIIIWW",
            ".WIIIIWW",
            ".WIIIIW.",
            ".WWWWWW.",
            "........",
        ],
        {"W": (200, 200, 200), "I": (110, 130, 150)},
    ),
    "fwh_soc_chg": (  # charging: green
        [
            "........",
            ".WWWWWW.",
            ".WGGGGW.",
            ".WGGGGWW",
            ".WGGGGWW",
            ".WGGGGW.",
            ".WWWWWW.",
            "........",
        ],
        {"W": (200, 200, 200), "G": (0, 220, 70)},
    ),
    "fwh_soc_dis": (  # discharging: amber
        [
            "........",
            ".WWWWWW.",
            ".WAAAAW.",
            ".WAAAAWW",
            ".WAAAAWW",
            ".WAAAAW.",
            ".WWWWWW.",
            "........",
        ],
        {"W": (200, 200, 200), "A": (255, 150, 0)},
    ),
    # Sun, for solar production. Mirrored on both axes: an 8x8 glyph reads as
    # a mistake rather than a style the moment one side carries more pixels
    # than the other. test_icons.py enforces it.
    "fwh_solar": (
        [
            "R..RR..R",
            ".R.RR.R.",
            "..YYYY..",
            "RRYYYYRR",
            "RRYYYYRR",
            "..YYYY..",
            ".R.RR.R.",
            "R..RR..R",
        ],
        {"Y": (255, 200, 0), "R": (255, 110, 0)},
    ),
    # House with a lit window, for whole-home load.
    "fwh_load": (
        [
            "...CC...",
            "..CCCC..",
            ".CCCCCC.",
            "CCCCCCCC",
            ".C....C.",
            ".C.WW.C.",
            ".C.WW.C.",
            ".CCCCCC.",
        ],
        {"C": (0, 170, 255), "W": (255, 190, 60)},
    ),
    # Transmission pylon, for grid import/export. A lattice tower's internal
    # detail does not survive 8x8 (it reads as a robot), so this is the
    # silhouette: full-width upper crossarm, tower body, splayed legs.
    "fwh_grid": (
        [
            "BBBBBBBB",
            "...BB...",
            "..B..B..",
            "..B..B..",
            ".BBBBBB.",
            ".B....B.",
            ".B....B.",
            "BB....BB",
        ],
        {"B": (120, 190, 255)},
    ),
}


def render(name: str) -> Image.Image:
    rows, palette = ICONS[name]
    if len(rows) != 8 or any(len(r) != 8 for r in rows):
        raise ValueError(f"{name}: every icon must be exactly 8x8")
    image = Image.new("RGB", (8, 8), (0, 0, 0))
    pixels = image.load()
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            if char != ".":
                pixels[x, y] = palette[char]
    return image.convert("P", palette=Image.ADAPTIVE, colors=64)


def write_all(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in ICONS:
        path = out_dir / f"{name}.gif"
        render(name).save(path, optimize=False)
        written.append(path)
    return written


def upload(host: str, paths: list[Path]) -> None:
    """POST each icon to the device's file endpoint, as its web UI does."""
    for path in paths:
        boundary = uuid.uuid4().hex
        body = b"".join(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="data"; '
                f'filename="/ICONS/{path.name}"\r\n'.encode(),
                b"Content-Type: image/gif\r\n\r\n",
                path.read_bytes(),
                f"\r\n--{boundary}--\r\n".encode(),
            ]
        )
        request = urllib.request.Request(
            f"http://{host}/edit",
            data=body,
            method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            print(f"{path.name} -> {host} HTTP {response.status}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=".", help="directory to write GIFs into")
    parser.add_argument("--upload", metavar="HOST", help="Awtrix hostname or IP")
    args = parser.parse_args()

    paths = write_all(Path(args.out))
    for path in paths:
        print(f"wrote {path}")
    if args.upload:
        upload(args.upload, paths)
    return 0


if __name__ == "__main__":
    sys.exit(main())
