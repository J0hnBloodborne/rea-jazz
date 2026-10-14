"""Self-guided test: does the firmware's music display show up in custom mode (mode 2)?

Run:  python tools/music_custom_test.py
Watch the keyboard and note what you see at each step. Takes about 70 seconds.

Only sends commands already used on this keyboard: set mode (07 FF FF) and music data
(07 23 45 67 89). Both are handled by the firmware without touching its saved settings
except the current mode, which is restored at the end.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ak992  # noqa: E402

MUSIC = bytes([0x07, 0x23, 0x45, 0x67, 0x89])
CUSTOM_MODE = bytes([0x07, 0xFF, 0xFF, 0x01, 0x04, 0x03, 0x00, 0x00])  # mode 2, as the vendor app builds it


def send(kb, packet):
    for _ in range(5):
        try:
            # Bypass the allow-list on purpose: this test exercises the firmware music path.
            buf = ak992.C.create_string_buffer(packet.ljust(kb.report_len, b"\0"), kb.report_len)
            if ak992.hid.HidD_SetFeature(kb.handle, buf, kb.report_len):
                return
        except OSError:
            pass
        time.sleep(0.05)


def stream(kb, style, level, seconds, label):
    print(f"\n>>> {label}")
    end = time.monotonic() + seconds
    last = -1
    while time.monotonic() < end:
        send(kb, MUSIC + bytes([style, level]))
        left = int(end - time.monotonic())
        if left != last:
            print(f"    {left:2d}s", end="\r", flush=True)
            last = left
        time.sleep(0.03)


def main():
    kb = ak992.AK992()
    print("Look at the keyboard. Starting in 5 seconds.")
    time.sleep(5)
    print("\n>>> Custom mode (your Fn preset should appear) - 5s")
    send(kb, CUSTOM_MODE)
    time.sleep(5)
    stream(kb, 1, 0x00, 8, "Style 1, level 0x00: expect ALL keys OFF if the music display works")
    stream(kb, 1, 0xFF, 8, "Style 1, level 0xFF: expect ALL keys ON")
    for bit in range(6):
        stream(kb, 1, 1 << bit, 5, f"Style 1, level 0x{1 << bit:02x}: is exactly ONE ROW lit? which one?")
    stream(kb, 1, 0x80, 5, "Style 1, level 0x80: what is lit?")
    for lv, label in ((0x00, "no columns"), (0x15, "2 columns on the right"), (0x35, "about 9 columns from the right"),
                      (0x55, "about 17 columns from the right"), (0x70, "all columns")):
        stream(kb, 2, lv, 5, f"Style 2, level 0x{lv:02x}: expect a bar: {label}")
    print("\n\n>>> Done. Restoring Breathing.")
    kb.set_mode(ak992.MODES["breathing"], 5, 4)
    kb.close()


if __name__ == "__main__":
    main()
