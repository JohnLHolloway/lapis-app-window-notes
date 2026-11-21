#!/usr/bin/env python3
"""Minimal Lapis app window: create a window, draw frames, handle input.

This is the shortest complete client for the on-device screen. It draws a
test card, answers frame requests for a few seconds, then closes cleanly.

Run it on a Lapis:

    python3 examples/minimal_app.py --seconds 5

Requires PyGObject (Gio) and membership of the lapis-display-client group.
"""

from __future__ import annotations

import argparse
import re
import socket
import struct
import time

from gi.repository import Gio, GLib

SERVICE = "ai.pamir.Lapis1"
MANAGER_PATH = "/ai/pamir/Lapis1/AppWindowManager"
MANAGER_IFACE = "ai.pamir.Lapis1.AppWindowManager"

WIDTH, HEIGHT, STRIDE = 400, 240, 50
FRAME_BYTES = STRIDE * HEIGHT          # 12 000
HEADER_BYTES = 56
HEADER = struct.Struct("<4sHHHHIIIQQQII")

KIND_CLIENT_FRAME = 1
KIND_VISIBILITY = 2
KIND_REQUESTED = 3
KIND_PRESENTED = 4
KIND_DROPPED = 5
KIND_CLOSING = 6
KIND_BACK = 7
KIND_INPUT = 8

FLAG_FULL = 1 << 0        # every frame must set this
FLAG_BACK_INPUT = 1 << 1  # this screen handles B
FLAG_LEAVES_BACK = 1 << 2 # one B opens the app switcher
FLAG_TAKES_INPUT = 1 << 3 # A, the fingerprint button and gestures reach us


def pack(bits: list[list[int]]) -> bytes:
    """Row-major bits to 1bpp bytes, MSB first, 1 = white."""
    out = bytearray(FRAME_BYTES)
    for y in range(HEIGHT):
        row = bits[y]
        for x in range(0, WIDTH, 8):
            byte = 0
            for bit in range(8):
                if row[x + bit]:
                    byte |= 0x80 >> bit
            out[y * STRIDE + x // 8] = byte
    return bytes(out)


def test_card() -> bytes:
    bits = [[1] * WIDTH for _ in range(HEIGHT)]
    for y in range(HEIGHT):
        for x in range(WIDTH):
            border = x < 3 or y < 3 or x >= WIDTH - 3 or y >= HEIGHT - 3
            checker = ((x // 8) + (y // 8)) % 2 == 0 and 20 < x < 180 and 40 < y < 160
            if border or checker:
                bits[y][x] = 0
    return pack(bits)


class App:
    def __init__(self, seconds: float):
        self.seconds = seconds
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.manager = Gio.DBusProxy.new_sync(
            connection=self.bus,
            flags=Gio.DBusProxyFlags.NONE,
            info=None,
            name=SERVICE,
            object_path=MANAGER_PATH,
            interface_name=MANAGER_IFACE,
            cancellable=None,
        )
        self.socket = None
        self.window_id = 0
        self.generation = 0
        self.visibility_generation = 0
        self.visibility_token = 0
        self.visible = False
        self.sequence = 0
        self.frames = 0
        self.payload = test_card()

    def call(self, method, signature, arguments, fds=None):
        params = GLib.Variant(signature, arguments)
        if fds is None:
            return self.manager.call_sync(
                method_name=method, parameters=params, flags=Gio.DBusCallFlags.NONE,
                timeout_msec=5000, cancellable=None,
            )
        reply, _ = self.manager.call_with_unix_fd_list_sync(
            method_name=method, parameters=params, flags=Gio.DBusCallFlags.NONE,
            timeout_msec=5000, fd_list=fds, cancellable=None,
        )
        return reply

    def open(self):
        caps = self.call("GetCapabilities", "()", ()).unpack()
        print("screen", caps[1], "x", caps[2], "stride", caps[3], caps[4],
              "fps", caps[5], "title bytes", caps[6], "windows", caps[7])
        print("chrome", self.call("GetChromeCapabilities", "()", ()).unpack())
        print("input capabilities", self.call("GetInputCapabilities", "()", ()).unpack()[0])

        daemon_end, client_end = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        daemon_end.setblocking(False)
        client_end.setblocking(False)
        fd_list = Gio.UnixFDList.new()
        fd_list.append(daemon_end.fileno())
        reply = self.call("CreateWindow", "(ssh)", ("Minimal", "sun", 0), fds=fd_list)
        path = reply.unpack()[0]
        daemon_end.close()
        self.socket = client_end
        match = re.search(r"/w(\d+)/g(\d+)$", path)
        self.window_id, self.generation = int(match.group(1)), int(match.group(2))
        print("window", path)

    def send_frame(self):
        self.sequence += 1
        flags = FLAG_FULL | FLAG_BACK_INPUT | FLAG_LEAVES_BACK | FLAG_TAKES_INPUT
        packet = HEADER.pack(
            b"LPFW", 1, KIND_CLIENT_FRAME, HEADER_BYTES, flags,
            self.window_id, self.generation, self.visibility_generation,
            self.sequence, self.visibility_token, 0, len(self.payload), 0,
        ) + self.payload
        try:
            self.socket.send(packet)
            self.frames += 1
        except BlockingIOError:
            self.sequence -= 1

    def read(self, *_):
        while True:
            try:
                packet = self.socket.recv(4096)
            except BlockingIOError:
                return True
            except OSError:
                return False
            if not packet:
                return False
            magic, version, kind, header_len, flags, window, generation, vis_gen, seq, token, argument, payload_len, reserved = HEADER.unpack(
                packet[:HEADER_BYTES]
            )
            if magic != b"LPFW":
                continue
            if kind == KIND_VISIBILITY:
                self.visible = bool(flags & 1)
                self.visibility_generation = vis_gen
                self.visibility_token = token if self.visible else 0
                if self.visible:
                    self.sequence = 0
                    print("visible (reason", flags >> 8, ")")
            elif kind == KIND_REQUESTED and self.visible:
                self.send_frame()
            elif kind in (KIND_PRESENTED, KIND_DROPPED):
                pass
            elif kind == KIND_INPUT:
                print("input code", flags & 0xFF)
            elif kind == KIND_BACK:
                print("back pressed")
            elif kind == KIND_CLOSING:
                print("closing (reason", flags, ")")
                return False
        return True

    def run(self):
        self.open()
        GLib.io_add_watch(self.socket.fileno(), GLib.IO_IN | GLib.IO_HUP, self.read)
        loop = GLib.MainLoop()
        GLib.timeout_add(int(self.seconds * 1000), lambda: (loop.quit(), False)[1])
        loop.run()
        print("frames sent:", self.frames)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=5.0)
    args = parser.parse_args()
    App(args.seconds).run()
