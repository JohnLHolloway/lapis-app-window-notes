# Input: A, the fingerprint sensor, and B

The device has no touch screen. Everything you can press is: the **A** button,
the **B** button, and the fingerprint sensor (a button plus gestures).

## Capability bits

GetInputCapabilities returns a bitfield:

| bit | name | meaning |
|---|---|---|
| 0 | BACK | the daemon understands the B flags on a frame |
| 1 | FOCUS | the daemon routes A and the fingerprint to a focused window |

Observed value on 0.10.0: 3 (both). The bits are additive: a daemon that does
not advertise them would close your window if you set the corresponding frame
flags, which is why older clients check first.

## Taking input

Input is opt-in per frame, with two sticky flags:

| frame flag | bit | effect |
|---|---|---|
| handles B | 1 | a single B reaches you as a back_pressed packet; a second B within 350 ms opens the switcher |
| leaves B | 2 | one B opens the switcher at once, and you never see it |
| takes input | 3 | A, the fingerprint button and the sensor's gestures reach you while your frame is on display |

The values stick: set them once, and every later frame carries them. Do not set
both B flags - "handles B" and "leaves B" are mutually exclusive, and the pair
(bit 1 clear, bit 2 set) is the normal "this app has one screen" case.

While a frame that takes input is on display and nothing of the system's is in
front (switcher, menu, notification, suspended or degraded screen), your window
has input focus: the inputs arrive as input packets and the global Button and
Fingerprint D-Bus signals go quiet. Power stays the system's, and a double B
still opens the switcher.

## Input packets

    flags low byte = code, bit 8 = canceled
    sequence       = serial, 1..n within the current visibility grant
    argument       = CLOCK_MONOTONIC nanoseconds when it happened

| code | event |
|---|---|
| 1 | A down |
| 2 | A up |
| 3 | fingerprint button down |
| 4 | fingerprint button up |
| 5 | swipe up |
| 6 | swipe down |
| 7 | swipe left |
| 8 | swipe right |
| 9 | tap (a light touch on the sensor) |
| 10 | tap hold (a finger resting; may repeat while it rests) |

Every down is followed by its up. Swipes, tap and tap hold have no up. An up with
canceled set means the window lost focus during the press (the switcher opened, a
notification arrived): the press is over, do not act on it.

A click of the fingerprint button also touches the sensor, so a tap usually
follows a fingerprint up by 0.2-0.35 s. If you use the button, ignore a tap that
closely follows it; if you use taps, do not also act on button presses.

## What to build with it

Presses are best effort. A window that stops sending frames gets at most four
more presses and then nothing until it draws again, so answer input by drawing.
A gap in the input serial tells you inputs were dropped.

The four sensible bindings, which is what our weather app uses: A and horizontal
swipes change the view, a tap hides the text, a vertical swipe raises or
dismisses a small card, and B leaves the app to the system.
