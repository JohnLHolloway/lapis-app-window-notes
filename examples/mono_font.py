#!/usr/bin/env python3
"""Read the device's BMFont .fnt + .mono atlases, without numpy.

    python3 examples/mono_font.py A             # print one glyph as ASCII art
    python3 examples/mono_font.py "hello" b     # print a word, fonts: a or b
"""

from __future__ import annotations

import pathlib
import re
import sys

FONT_DIR = pathlib.Path("/usr/share/lapis-hwserviced/gui/mono/font")
FONTS = {
    "a": "avicenna_18",              # serif, 95 glyphs
    "b": "KohiMono20-Medium",        # monospaced, 101 glyphs
    "c": "kohi_11",                  # digits only
}


def load_mono(path: pathlib.Path):
    raw = path.read_bytes()
    if raw[:4] != b"MONO":
        raise ValueError("not a .mono atlas: " + str(path))
    width = int.from_bytes(raw[4:6], "little")
    height = int.from_bytes(raw[6:8], "little")
    stride = int.from_bytes(raw[8:10], "little")
    plane = raw[14 : 14 + stride * height]      # after "MONO" + 4 u16 header words
    return width, height, stride, plane


def bit(plane, stride, x, y):
    return (plane[y * stride + (x >> 3)] >> (7 - (x & 7))) & 1


def load_font(stem: str):
    text = (FONT_DIR / (stem + ".fnt")).read_text()
    glyphs = {}
    page = None
    for line in text.splitlines():
        if line.startswith("page "):
            match = re.search(r'file="([^"]+)"', line)
            if match:
                page = match.group(1)
        elif line.startswith("char "):
            values = dict(re.findall(r"(\w+)=(-?\d+)", line))
            glyphs[int(values["id"])] = {k: int(values[k]) for k in
                                         ("x", "y", "width", "height", "xoffset", "yoffset", "xadvance")}
    atlas_name = pathlib.Path(page).stem + ".mono" if page else stem + ".mono"
    width, height, stride, plane = load_mono(FONT_DIR / atlas_name)
    return glyphs, (width, height, stride, plane)


def render(text: str, stem: str) -> list[str]:
    glyphs, (_, _, stride, plane) = load_font(stem)
    canvas = {}
    pen = 0
    lowest = 0
    for ch in text:
        glyph = glyphs.get(ord(ch))
        if not glyph:
            pen += 4
            continue
        for row in range(glyph["height"]):
            for column in range(glyph["width"]):
                if bit(plane, stride, glyph["x"] + column, glyph["y"] + row):
                    y = glyph["yoffset"] + row
                    canvas[(pen + glyph["xoffset"] + column, y)] = True
                    lowest = max(lowest, y)
        pen += glyph["xadvance"]
    return ["".join("#" if canvas.get((x, y)) else " " for x in range(pen))
            for y in range(lowest + 1)]


if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "A"
    key = sys.argv[2] if len(sys.argv) > 2 else "a"
    stem = FONTS.get(key, key)
    for line in render(text, stem):
        print(line.rstrip())
