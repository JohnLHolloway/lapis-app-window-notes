# Things that cost us an evening

Written down so the next app does not have to rediscover them.

## It is a pull system

You never push frames. The daemon asks for one, you answer with one, it reports
presented or dropped, then it asks again. Sending without a request, or while
hidden, is a protocol violation and closes the window.

The practical consequence: your frame rate is your render speed. We render a
400x240 scene with numpy in about 8 ms and get roughly 12-15 frames per second
because the request only comes after the previous frame is resolved. The daemon
would allow 40.

## Sequence numbers reset on every show

visibility_changed with visible=true starts a new grant: sequence goes back to 1,
and the old visibility_token is dead. A frame carrying the previous grant's
sequence or token is dropped as stale.

## Frames are 12 056 bytes, and 12 000 of them are pixels

    struct.pack("<4sHHHHIIIQQQII", b"LPFW", 1, 1, 56, flags,
                window_id, generation, visibility_generation,
                sequence, visibility_token, 0, len(payload), 0)

One call per frame on a SOCK_SEQPACKET socket keeps the packet atomic. Do not
write header and payload separately.

## Polarity

1 = white, 0 = black. numpy's packbits gives you MSB-first packing for free:

    np.packbits(bits, axis=1).tobytes()     # (240, 400) bool -> 12 000 bytes

Because it is one bit, gradients have to be dithered. An 8x8 ordered dither with
a little fixed grain reads as texture rather than grey, and pushing values to
the extremes (near-black to black, near-white to white) keeps large areas clean.

## Listen to the chrome

    GetChromeCapabilities -> (4, 0, 215, 400, 25)

The last 25 rows are the system toolbar; anything you draw there is covered. Keep
4 px clear at the edges. Our first layout put the clock at y=200 and watched half
of it disappear.

## One window per process, and no way to close someone else's

Creating a second window from a second process is allowed and shows up in the
switcher as a second entry with the same title - which looks like a bug to the
person holding the device. There is no D-Bus verb to close another process's
window. Use a lock file, and refuse to start if a window with your title already
exists (ListWindows tells you).

## Closing is two-phase

closing(flags=6 user_closed) arrives, then SIGTERM, then SIGKILL after two
seconds. Do not reconnect on service_shutdown - it can also mean the user closed
you. Exit, and let the switcher reopen you.

## Titles and icons are part of the UI

The title is what the switcher shows, 1-30 printable ASCII bytes. The icon must be
a name from ListIcons (54 of them: sun, moon, clock, terminal, globe...). An
invalid icon is refused at CreateWindow.

## Gio argument marshalling

In our environment PyGObject asserted
"g_dbus_proxy_new_sync: assertion 'g_variant_is_object_path (object_path)'" when
the service, path and interface came from module-level constants, and the
identical call with inline string literals worked. Keyword arguments everywhere,
strings written at the call site, and call_with_unix_fd_list_sync for
CreateWindow. If you see that assert, this is almost certainly why.

## Do not attach ancillary data

Client frames must not carry SCM_CREDENTIALS or any other control message; the
daemon rejects them. A plain socket.send() is correct. The daemon's own messages
do carry credentials, so you can trust who is on the other end.

## No backlight

The panel is reflective. There is nothing to dim at night and nothing to turn
up in the sun; brightness is a property of the room. Contrast is the only lever,
so design in ink and paper rather than in greys.
