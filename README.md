# Lapis app-window notes

Field notes and a working reference client for the **Lapis** handheld's own
screen: a 400x240, 1-bit, reflective Sharp memory LCD, driven by
`lapis-hwserviced`'s AppWindowManager.

This is not an official specification. The authoritative documents ship on the
device, and this repository is our reading of them plus everything we had to
learn by writing an app:

    /usr/share/lapis-hwserviced/app-window/protocol-v1.json
    /usr/share/lapis-hwserviced/app-window/sdk-rust/            (Rust SDK + crates)
    /usr/share/lapis-hwserviced/app-window/icon-catalog-v2.json

Everything here was verified against **lapis-hwserviced 0.10.0**,
app-window protocol **v1**, terminal input protocol **v3**, icon catalog **v2**.

## The short version

An app is a normal Linux process. It asks the daemon for a window, hands over one
end of a `SOCK_SEQPACKET` pair, and then answers frame requests with 12 056-byte
packets: a 56-byte `LPFW` header and 12 000 bytes of pixels. No compositor, no
Wayland, no web view, and no window toolkit. The daemon owns the panel.

    process ──D-Bus──▶ hwserviced   CreateWindow(title, icon, fd)
    process ◀──seqpacket── frames   LPFW + 400x240 1bpp
    process ◀──seqpacket── input    A / fingerprint / B

## Contents

| file | what it covers |
|---|---|
| [docs/protocol.md](docs/protocol.md) | D-Bus interface, wire header, packet kinds, the frame lifecycle |
| [docs/input.md](docs/input.md) | capability bits, input codes, the B button and the fingerprint sensor |
| [docs/fonts.md](docs/fonts.md) | the device's BMFont + .mono atlases, reverse-engineered |
| [docs/gotchas.md](docs/gotchas.md) | the things that cost us an evening |
| examples/minimal_app.py | a complete 150-line client: window, test card, input, clean exit |
| examples/mono_font.py | read a .mono atlas and the .fnt that indexes it |

## Try it

On a Lapis, as a user in the `lapis-display-client` group (the shipped `lapis`
account is):

    python3 examples/minimal_app.py --seconds 5

It prints the screen capabilities, opens a window titled "Minimal", draws a test
card for five seconds, and exits. While it runs, the switcher shows it next to
the other apps.

## Screen at a glance

| | |
|---|---|
| pixels | 400 x 240, 1 bit per pixel |
| format | MONO_1BPP_MSB_FIRST, stride 50 bytes, 1 = white |
| frame | 12 000 bytes of pixels, 12 056 with the header |
| refresh | up to 40 frames per second, pull-based |
| chrome | 4 px safe area; the system toolbar covers y 215-239 |
| windows | up to 24 at once, titles 1-30 printable ASCII bytes |
| input | A, the fingerprint button, sensor tap/hold/swipes, B |

## The app we built with it

[weather](https://github.com/JohnLHolloway/lapis-weather) - an ambient weather
window: solar and lunar geometry, live weather, and five procedurally drawn
views in one bit per pixel.
