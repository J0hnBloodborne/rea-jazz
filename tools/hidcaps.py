# Read-only: enumerate HID interfaces for a VID/PID and print their top-level caps and report IDs.
# usage: python -I hidcaps.py [VID PID]   (hex, default 1A2C 9C00)
import ctypes as C
from ctypes import wintypes as W
import sys

VID, PID = (int(x, 16) for x in (sys.argv[1:3] if len(sys.argv) > 2 else ("1A2C", "9C00")))

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
                ("NumberLinkCollectionNodes", W.USHORT),
                ("NumberInputButtonCaps", W.USHORT), ("NumberInputValueCaps", W.USHORT), ("NumberInputDataIndices", W.USHORT),
                ("NumberOutputButtonCaps", W.USHORT), ("NumberOutputValueCaps", W.USHORT), ("NumberOutputDataIndices", W.USHORT),
                ("NumberFeatureButtonCaps", W.USHORT), ("NumberFeatureValueCaps", W.USHORT), ("NumberFeatureDataIndices", W.USHORT)]

class HIDP_VALUE_CAPS(C.Structure):
    _fields_ = [("UsagePage", W.USHORT), ("ReportID", C.c_ubyte), ("IsAlias", C.c_ubyte),
                ("BitField", W.USHORT), ("LinkCollection", W.USHORT), ("LinkUsage", W.USHORT), ("LinkUsagePage", W.USHORT),
                ("IsRange", C.c_ubyte), ("IsStringRange", C.c_ubyte), ("IsDesignatorRange", C.c_ubyte), ("IsAbsolute", C.c_ubyte),
                ("HasNull", C.c_ubyte), ("Reserved", C.c_ubyte), ("BitSize", W.USHORT), ("ReportCount", W.USHORT),
                ("Reserved2", W.USHORT * 5), ("UnitsExp", W.ULONG), ("Units", W.ULONG),
                ("LogicalMin", W.LONG), ("LogicalMax", W.LONG), ("PhysicalMin", W.LONG), ("PhysicalMax", W.LONG),
                ("UsageMin", W.USHORT), ("UsageMax", W.USHORT), ("x", W.USHORT * 6)]

setupapi.SetupDiGetClassDevsW.restype = C.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [C.POINTER(GUID), W.LPCWSTR, W.HWND, W.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [C.c_void_p, C.c_void_p, C.POINTER(GUID), W.DWORD, C.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [C.c_void_p, C.POINTER(SP_DEVICE_INTERFACE_DATA), C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p]
k32.CreateFileW.restype = W.HANDLE
k32.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE]
hid.HidD_GetPreparsedData.argtypes = [W.HANDLE, C.POINTER(C.c_void_p)]
hid.HidP_GetCaps.argtypes = [C.c_void_p, C.POINTER(HIDP_CAPS)]
# HidP_GetValueCaps(ReportType, ValueCaps, ValueCapsLength, PreparsedData)
hid.HidP_GetValueCaps.argtypes = [C.c_int, C.c_void_p, C.POINTER(W.USHORT), C.c_void_p]
hid.HidD_FreePreparsedData.argtypes = [C.c_void_p]

g = GUID()
hid.HidD_GetHidGuid(C.byref(g))
devs = setupapi.SetupDiGetClassDevsW(C.byref(g), None, None, 0x12)  # PRESENT | DEVICEINTERFACE
INVALID = W.HANDLE(-1).value
i = 0
while True:
    d = SP_DEVICE_INTERFACE_DATA(); d.cbSize = C.sizeof(d)
    if not setupapi.SetupDiEnumDeviceInterfaces(devs, None, C.byref(g), i, C.byref(d)):
        break
    i += 1
    need = W.DWORD()
    setupapi.SetupDiGetDeviceInterfaceDetailW(devs, C.byref(d), None, 0, C.byref(need), None)
    buf = C.create_string_buffer(need.value)
    C.cast(buf, C.POINTER(W.DWORD))[0] = 8 if C.sizeof(C.c_void_p) == 8 else 6
    setupapi.SetupDiGetDeviceInterfaceDetailW(devs, C.byref(d), buf, need, None, None)
    path = C.wstring_at(C.addressof(buf) + 4)
    if f"vid_{VID:04x}&pid_{PID:04x}" not in path.lower():
        continue
    h = k32.CreateFileW(path, 0, 3, None, 3, 0, None)  # access 0: query only, works on keyboards too
    if h == INVALID:
        print(path, "-> open failed", C.get_last_error()); continue
    pp = C.c_void_p()
    if hid.HidD_GetPreparsedData(h, C.byref(pp)):
        caps = HIDP_CAPS(); hid.HidP_GetCaps(pp, C.byref(caps))
        print(path)
        print(f"  UsagePage=0x{caps.UsagePage:04X} Usage=0x{caps.Usage:02X} in={caps.InputReportByteLength} out={caps.OutputReportByteLength} feat={caps.FeatureReportByteLength}")
        for rtype, n, name in ((0, caps.NumberInputValueCaps, "in"), (1, caps.NumberOutputValueCaps, "out"), (2, caps.NumberFeatureValueCaps, "feat")):
            if not n: continue
            arr = (HIDP_VALUE_CAPS * n)(); cnt = W.USHORT(n)
            st = hid.HidP_GetValueCaps(rtype, arr, C.byref(cnt), pp)
            for v in arr[:cnt.value]:
                print(f"    {name}: ReportID=0x{v.ReportID:02X} page=0x{v.UsagePage:04X} bits={v.BitSize} count={v.ReportCount} status=0x{st & 0xFFFFFFFF:08X}")
        hid.HidD_FreePreparsedData(pp)
    k32.CloseHandle(h)
