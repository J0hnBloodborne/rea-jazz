"""AJAZZ AK992 (wired, USB 1A2C:9C00) lighting control without the vendor app.

Protocol reversed from the vendor DeviceDriver.exe; see FINDINGS.md.
Only commands traced to the lighting UI are allowed to be sent.

usage:
  python ak992.py info                         show the config channel the tool would use
  python ak992.py mode breathing -b 5 -s 3     set a built-in lighting mode
"""
import argparse
import ctypes as C
import sys
import time
from ctypes import wintypes as W

VID, PID = 0x1A2C, 0x9C00
CONFIG_USAGE_PAGE, CONFIG_USAGE = 0xFF01, 0x01
REPORT_ID = 0x07

# Command prefixes seen in the vendor app's lighting code. send() refuses anything else.
ALLOWED_PREFIXES = {
    "mode": bytes([0x07, 0xFF, 0xFF]),  # FUN_0041a500: set light mode
}

# Firmware handler for 07 EE DD sets a 0xAA flag that looks like a bootloader request. Never send it.
NEVER_SEND_PREFIXES = (bytes([0x07, 0xEE]),)

# The keyboard saves the mode to non-volatile memory, so frequent mode changes could wear it out.
# set_mode() refuses to run more often than this.
MIN_MODE_INTERVAL = 1.0

# Mode numbers from layouts/KB-K102.xml, names from language/1033.lan.
MODES = {
    "steady": 1, "breathing": 3, "windmill": 4, "neon": 5, "streamer": 6, "flowing": 7,
    "ripples": 8, "points": 9, "flash": 10, "shadow": 11, "ripples-shining": 12, "rich": 13,
    "marquee": 14, "storm": 15, "serpentine": 16, "stars": 17, "snake": 18, "diagonal": 19, "sine": 20,
}
BRIGHTNESS_MAX = SPEED_MAX = 5

hid = C.WinDLL("hid")
setupapi = C.WinDLL("setupapi")
k32 = C.WinDLL("kernel32", use_last_error=True)


class GUID(C.Structure):
    _fields_ = [("D1", W.DWORD), ("D2", W.WORD), ("D3", W.WORD), ("D4", C.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(C.Structure):
    _fields_ = [("cbSize", W.DWORD), ("Guid", GUID), ("Flags", W.DWORD), ("Reserved", C.c_void_p)]


class HIDP_CAPS(C.Structure):
    _fields_ = [("Usage", W.USHORT), ("UsagePage", W.USHORT),
                ("InputReportByteLength", W.USHORT), ("OutputReportByteLength", W.USHORT),
                ("FeatureReportByteLength", W.USHORT), ("Reserved", W.USHORT * 17),
                ("Counts", W.USHORT * 10)]


setupapi.SetupDiGetClassDevsW.restype = C.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [C.POINTER(GUID), W.LPCWSTR, W.HWND, W.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [C.c_void_p, C.c_void_p, C.POINTER(GUID), W.DWORD,
                                                 C.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [C.c_void_p, C.POINTER(SP_DEVICE_INTERFACE_DATA),
                                                      C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [C.c_void_p]
k32.CreateFileW.restype = W.HANDLE
k32.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE]
k32.CloseHandle.argtypes = [W.HANDLE]
hid.HidD_GetPreparsedData.argtypes = [W.HANDLE, C.POINTER(C.c_void_p)]
hid.HidD_FreePreparsedData.argtypes = [C.c_void_p]
hid.HidP_GetCaps.argtypes = [C.c_void_p, C.POINTER(HIDP_CAPS)]
hid.HidD_SetFeature.argtypes = [W.HANDLE, C.c_void_p, W.ULONG]
hid.HidD_SetFeature.restype = W.BOOLEAN

INVALID_HANDLE = W.HANDLE(-1).value
GENERIC_RW = 0x80000000 | 0x40000000
SHARE_RW = 0x1 | 0x2
OPEN_EXISTING = 3


def _hid_paths():
    g = GUID()
    hid.HidD_GetHidGuid(C.byref(g))
    devs = setupapi.SetupDiGetClassDevsW(C.byref(g), None, None, 0x12)  # PRESENT | DEVICEINTERFACE
    try:
        i = 0
        while True:
            d = SP_DEVICE_INTERFACE_DATA()
            d.cbSize = C.sizeof(d)
            if not setupapi.SetupDiEnumDeviceInterfaces(devs, None, C.byref(g), i, C.byref(d)):
                return
            i += 1
            need = W.DWORD()
            setupapi.SetupDiGetDeviceInterfaceDetailW(devs, C.byref(d), None, 0, C.byref(need), None)
            buf = C.create_string_buffer(need.value)
            C.cast(buf, C.POINTER(W.DWORD))[0] = 8 if C.sizeof(C.c_void_p) == 8 else 6
            setupapi.SetupDiGetDeviceInterfaceDetailW(devs, C.byref(d), buf, need, None, None)
            yield C.wstring_at(C.addressof(buf) + 4)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(devs)


def _caps(handle):
    pp = C.c_void_p()
    if not hid.HidD_GetPreparsedData(handle, C.byref(pp)):
        return None
    caps = HIDP_CAPS()
    hid.HidP_GetCaps(pp, C.byref(caps))
    hid.HidD_FreePreparsedData(pp)
    return caps


class AK992:
    """Handle on the keyboard's vendor config collection (MI_01 COL07)."""

    def __init__(self):
        tag = f"vid_{VID:04x}&pid_{PID:04x}"
        for path in _hid_paths():
            if tag not in path.lower():
                continue
            h = k32.CreateFileW(path, GENERIC_RW, SHARE_RW, None, OPEN_EXISTING, 0, None)
            if h == INVALID_HANDLE:
                continue
            caps = _caps(h)
            if caps and caps.UsagePage == CONFIG_USAGE_PAGE and caps.Usage == CONFIG_USAGE:
                self.handle, self.path, self.report_len = h, path, caps.FeatureReportByteLength
                self._last_mode = float("-inf")
                return
            k32.CloseHandle(h)
        raise RuntimeError("AK992 config channel (1A2C:9C00, usage page 0xFF01) not found. Is it plugged in?")

    def close(self):
        k32.CloseHandle(self.handle)

    def send(self, packet: bytes):
        if any(packet.startswith(p) for p in NEVER_SEND_PREFIXES):
            raise ValueError(f"refusing to send blocked command {packet.hex(' ')}")
        if not any(packet.startswith(p) for p in ALLOWED_PREFIXES.values()):
            raise ValueError(f"refusing to send untraced command {packet.hex(' ')}")
        if len(packet) > self.report_len:
            raise ValueError(f"packet is {len(packet)} bytes, report is {self.report_len}")
        buf = C.create_string_buffer(packet.ljust(self.report_len, b"\0"), self.report_len)
        if not hid.HidD_SetFeature(self.handle, buf, self.report_len):
            raise OSError(C.get_last_error(), f"HidD_SetFeature failed for {packet.hex(' ')}")

    def set_mode(self, mode: int, brightness: int = 5, speed: int = 4, direction: int = 0):
        """Same packet the vendor app sends when a mode is picked (brightness and speed are 1..5)."""
        if mode not in MODES.values():
            raise ValueError(f"unknown mode {mode}")
        wait = self._last_mode + MIN_MODE_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_mode = time.monotonic()
        brightness = max(1, min(BRIGHTNESS_MAX, brightness))
        speed = max(1, min(SPEED_MAX, speed))
        self.send(ALLOWED_PREFIXES["mode"] + bytes([mode - 1, brightness - 1, speed - 1, 0, direction & 0xFF]))




def cmd_info(_):
    kb = AK992()
    print(f"config channel: {kb.path}")
    print(f"feature report length: {kb.report_len} bytes (report ID 0x{REPORT_ID:02X} expected)")
    kb.close()


def cmd_mode(args):
    kb = AK992()
    try:
        kb.set_mode(MODES[args.name], args.brightness, args.speed, args.direction)
    finally:
        kb.close()



def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("info").set_defaults(func=cmd_info)
    m = sub.add_parser("mode", help="set a built-in lighting mode")
    m.add_argument("name", choices=MODES)
    m.add_argument("-b", "--brightness", type=int, default=5, help="1..5 (default 5)")
    m.add_argument("-s", "--speed", type=int, default=4, help="1..5 (default 4)")
    m.add_argument("-d", "--direction", type=int, default=0, help="effect direction (default 0)")
    m.set_defaults(func=cmd_mode)
    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
