# The app-window protocol

Source of truth on the device:
/usr/share/lapis-hwserviced/app-window/protocol-v1.json, with a Rust SDK at
/usr/share/lapis-hwserviced/app-window/sdk-rust/. This page is our summary of
what those say, plus what we observed.

## D-Bus interface

Service: ai.pamir.Lapis1
Object: /ai/pamir/Lapis1/AppWindowManager
Interface: ai.pamir.Lapis1.AppWindowManager

| method | signature | returns |
|---|---|---|
| GetCapabilities | () | u q q q s y q y q s |
| GetChromeCapabilities | () | q q q q q |
| GetInputCapabilities | () | u |
| ListIcons | () | as |
| CreateWindow | ssh | o |
| ListWindows | () | a(ouuss) |
| GetPresentationState | () | t s o u u s s |

Read them as:

    GetCapabilities            protocol_version u32, width u16, height u16,
                               stride u16, pixel_format str, max_fps u8,
                               max_title_bytes u16, max_windows u8,
                               icon_catalog_version u16, catalog_sha256 str
    GetChromeCapabilities      safe_area_inset u16, toolbar_x u16, toolbar_y u16,
                               toolbar_width u16, toolbar_height u16
    CreateWindow               title str, icon str, frame_socket fd -> object path
    ListWindows                (path, window_generation, pid, title, icon)
    GetPresentationState       (generation, mode, target_path, window_generation,
                                owner_pid, title, icon)

Observed values on 0.10.0: 400 x 240, stride 50, MONO_1BPP_MSB_FIRST, 40 fps,
title 30 bytes, 24 windows, chrome (4, 0, 215, 400, 25), input capabilities 3
(bit 0 BACK, bit 1 FOCUS), 54 icons.

Presentation modes seen: "window" (an app window is on screen) and
"system-scene" (the shell itself, e.g. the switcher; target path is /).

## Making a window

1. Connect to the system bus. You must be root, or in the lapis-display-client
   group; the daemon checks your D-Bus credentials at CreateWindow.
2. Create a socketpair:

       daemon_end, client_end = socket.socketpair(AF_UNIX, SOCK_SEQPACKET)

   Both ends non-blocking, close-on-exec. A stream socket is refused.
3. Pass daemon_end as a unix fd over D-Bus, and keep client_end.
4. CreateWindow(title, icon, fd) returns an object path of the form
   /ai/pamir/Lapis1/AppWindows/w<window_id>/g<generation>. The window id and
   generation are the numbers in the path; every packet you send repeats them.
5. Wait for the daemon to show you. Creating a window is enough to have it
   presented; you do not ask.

The icon must be one of ListIcons. Titles are 1-30 printable ASCII bytes and are
what the switcher shows, so give the app a human name, not a pid.

The window object path itself is not introspectable - do not expect to call
methods on it. All traffic goes over the frame socket.

## The wire

Little-endian, 56-byte header, magic "LPFW":

| offset | field | type |
|---|---|---|
| 0 | magic | 4 bytes "LPFW" |
| 4 | version | u16 = 1 |
| 6 | kind | u16 |
| 8 | header_len | u16 = 56 |
| 10 | flags | u16 (per-kind) |
| 12 | window_id | u32, nonzero |
| 16 | window_generation | u32, nonzero |
| 20 | visibility_generation | u32 |
| 24 | sequence | u64 |
| 32 | visibility_token | u64 |
| 40 | argument | u64 |
| 48 | payload_len | u32 |
| 52 | reserved_zero | u32 = 0 |

Packet kinds: 1 client_frame, 2 visibility_changed, 3 frame_requested,
4 frame_presented, 5 frame_dropped, 6 closing, 7 back_pressed, 8 input.

### client_frame (client to daemon)

Exactly 12 056 bytes: the header plus 12 000 bytes of pixels.

| field | value |
|---|---|
| flags | bit 0 full frame (required); bit 1 this screen handles B; bit 2 the screen leaves B to the system; bit 3 the screen takes the device input |
| visibility_generation | nonzero, from the last visibility_changed |
| sequence | nonzero, resets to 1 on every new visibility grant |
| visibility_token | nonzero, from the last visible event |
| argument | 0 |
| payload_len | 12 000 |

Pixels: 400x240, 1 bit per pixel, MSB first inside each byte, 50-byte stride,
row 0 first, black = 0, white = 1. numpy writes this directly:

    payload = np.packbits(bits, axis=1).tobytes()   # bits is (240, 400) bool

### visibility_changed (daemon to client)

56 bytes, no payload. flags bit 0 = visible; bits 8..15 = reason.

| reason | meaning |
|---|---|
| 1 | selected - you are on screen, token is nonzero |
| 2 | picker - the switcher is up |
| 3 | system_scene - the shell is showing something |
| 4 | suspended |
| 5 | display_degraded |
| 6 | deselected |

When visible, visibility_token is nonzero and visibility_generation increases.
When hidden, the token is zero and anything you send is discarded.

### frame_requested, frame_presented, frame_dropped

The daemon asks, you answer, once per request:

    visibility_changed(visible, token)
    frame_requested(serial, token)      -> send one client_frame(sequence = 1)
    frame_presented(sequence)           -> wait for the next request
    frame_requested(serial + 1)         -> send client_frame(sequence = 2)
    ...

frame_requested carries a monotonically increasing request serial and, in
argument, the CLOCK_MONOTONIC time it would like the frame by. presented and
dropped echo the client sequence you sent. Drop reasons: 1 superseded,
2 rate_limited, 3 stale_visibility, 4 non_increasing_sequence,
5 display_unavailable.

Send one frame per request. A frame that arrives without a request, or while
hidden, is a protocol error and the window is closed with reason
protocol_violation.

### closing (daemon to client)

flags is the reason: 1 client_requested, 2 process_exited, 3 socket_closed,
4 protocol_violation, 5 service_shutdown, 6 user_closed. When the user closes
your app from the switcher, the daemon sends closing and then SIGTERM, and
SIGKILL two seconds later if you are still there. Save state and exit promptly.

## A minimal frame loop

    while True:
        packet = socket.recv(4096)          # 56 to 12 056 bytes
        kind = unpack(packet).kind
        if kind == VISIBILITY:              # show or hide
            visible = flags & 1
            token = token if visible else 0
            if visible:
                sequence = 0
        elif kind == REQUESTED and visible:
            sequence += 1
            socket.send(header(sequence, token) + payload)
        elif kind == CLOSING:
            break

Rendering is up to you: the daemon does not know or care what you paint.
