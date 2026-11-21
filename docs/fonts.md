# The device's fonts

The panel's own type is on disk, and using it is the difference between an app
that looks native and one that looks ported. Everything lives in:

    /usr/share/lapis-hwserviced/gui/mono/font/

Three families ship: Avicenna 18 (a serif, 95 glyphs, the one to use for text),
Kohi Mono 20 Medium (monospaced, 101 glyphs) and Kohi 11 (digits only, for
battery percentages and the like).

## The .fnt descriptor

Plain BMFont text. The lines that matter:

    info face="Avicenna 17" size=18
    common lineHeight=22 base=14 scaleW=306 scaleH=150
    page id=0 file="Pamir-Avicenna-18-fontSprite.png"
    char id=65 x=22 y=52 width=12 height=14 xoffset=0 yoffset=0 xadvance=13

x, y, width, height index the atlas; xoffset and yoffset place the glyph
relative to the pen; xadvance moves the pen. Draw text by walking the string and
stamping each glyph's rectangle at (pen + xoffset, baseline + yoffset), then
advancing the pen by xadvance.

There is no degree sign, no arrows and no bullet in these atlases. We draw a
5-pixel ring by hand for temperatures.

## The .mono atlas

The page file in the .fnt is named .png, but what ships on disk is a .mono: a
tiny uncompressed 1-bit image format.

    bytes 0..3    "MONO"
    bytes 4..5    width    u16 little-endian
    bytes 6..7    height   u16 little-endian
    bytes 8..9    stride   u16 little-endian, bytes per row
    bytes 10..11  u16, observed 1
    bytes 12..13  u16, observed 0
    then          stride * height bytes: plane 0, 1 = ink, MSB first
    then          stride * height bytes: plane 1, identical to plane 0

The second plane is byte-identical in every atlas we checked, so read the first
and ignore the rest. examples/mono_font.py loads one and prints a glyph as ASCII
art, which is the quickest way to convince yourself the polarity is right.

## Sizing

The panel is 400x240 but the system toolbar covers the bottom 25 rows, so design
for 400x215 and keep a 4-pixel safe area. Avicenna at 1x has 12-pixel capitals
and 22-pixel line height; at 2x it is comfortable for a temperature, at 3x for a
clock. There is no italic and no bold - the atlases are single weight, so
hierarchy has to come from size and placement.
