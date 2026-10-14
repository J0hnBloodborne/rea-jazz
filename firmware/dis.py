"""Disassembler for the AK992 keyboard MCU firmware (ELAN EM78-family core, 16-bit words).

usage: python dis.py fw.bin [start_word end_word] > listing.txt
Word addresses throughout. Mnemonics follow ELAN's EM78 instruction set (see ISA.md);
the 16-bit encoding was mapped by matching the EM78 opcode order to this firmware.
"""
import sys

# EM78 standard registers plus names worked out from this firmware.
RAM = {0x00: "IAR", 0x01: "TCC", 0x02: "PC", 0x03: "STATUS", 0x04: "RSR", 0x05: "P5", 0x06: "P6",
       0x07: "P7", 0x0B: "PB", 0x0D: "USBA", 0x0E: "USBD", 0x0F: "ISR"}

# E0xx system ops. EM78 sub-opcode s maps to low byte (s & 0x0F) | ((s & 0xF0) << 1).
SYS = {0x00: "nop", 0x01: "daa", 0x02: "contw", 0x03: "slep", 0x04: "wdtc",
       0x20: "eni", 0x21: "disi", 0x22: "ret", 0x23: "reti", 0x24: "contr", 0x40: "tbl"}

# Register ops by high byte (low bit of the high byte is address bit 8).
REG = {
    0xC0: "mov a, {r}", 0xC2: "mov {r}, {r}", 0xC4: "coma {r}", 0xC6: "com {r}",
    0xC8: "inca {r}", 0xCA: "inc {r}", 0xCC: "djza {r}", 0xCE: "djz {r}",
    0xD0: "rrca {r}", 0xD2: "rrc {r}", 0xD4: "rlca {r}", 0xD6: "rlc {r}",
    0xD8: "swapa {r}", 0xDA: "swap {r}", 0xDC: "jza {r}", 0xDE: "jz {r}",
    0xE2: "mov {r}, a", 0xE6: "clr {r}",
    0xE8: "sub a, {r}", 0xEA: "sub {r}, a", 0xEC: "deca {r}", 0xEE: "dec {r}",
    0xF0: "or a, {r}", 0xF2: "or {r}, a", 0xF4: "and a, {r}", 0xF6: "and {r}, a",
    0xF8: "xor a, {r}", 0xFA: "xor {r}, a", 0xFC: "add a, {r}", 0xFE: "add {r}, a",
}
SKIPS = {"djza", "djz", "jza", "jz"}
IMM = {0x08: "sub a, #{k}", 0x18: "add a, #{k}", 0x20: "mov a, #{k}", 0x28: "or a, #{k}",
       0x30: "and a, #{k}", 0x38: "xor a, #{k}"}


def reg(r):
    return RAM.get(r, f"[{r:02x}]")


def decode(w, pc=0):
    """Return (text, kind, target). kind: 'jmp', 'call', 'ret', 'tbl', 'skip', 'unk' or ''."""
    hi, lo = w >> 8, w & 0xFF
    top3 = w >> 13
    if top3 in (2, 3):
        t = (pc & 0x2000) | (w & 0x1FFF)  # page bit from the current pc
        return (f"jmp L{t:04x}", "jmp", t) if top3 == 2 else (f"call F{t:04x}", "call", t)
    if hi == 0x00:
        return f"retl #{lo:02x}", "ret", None
    if hi == 0xE0:
        if lo in SYS:
            op = SYS[lo]
            return op, {"ret": "ret", "reti": "ret", "tbl": "tbl"}.get(op, ""), None
        if 0x05 <= lo <= 0x0F:
            return f"iow {reg(lo)}", "", None
        if 0x25 <= lo <= 0x2F:
            return f"ior {reg(lo - 0x20)}", "", None
        return f".dw {w:04x}  ; sys?", "unk", None
    if hi == 0xE4 and lo == 0:
        return "clra", "", None
    if 0x80 <= hi <= 0xBF and hi % 2 == 0:
        bit = (hi >> 1) & 7
        op = {0x8: "jbc", 0x9: "jbs", 0xA: "bc", 0xB: "bs"}[hi >> 4]
        return f"{op} {reg(lo)}, {bit}", "skip" if op[0] == "j" else "", None
    if hi in REG:
        text = REG[hi].format(r=reg(lo))
        return text, "skip" if text.split()[0] in SKIPS else "", None
    if hi in IMM:
        return IMM[hi].format(k=f"{lo:02x}"), "", None
    return f".dw {w:04x}  ; ?{hi:02x}", "unk", None


def main():
    data = open(sys.argv[1], "rb").read()
    words = [data[2 * i] | data[2 * i + 1] << 8 for i in range(len(data) // 2)]
    start = int(sys.argv[2], 16) if len(sys.argv) > 3 else 0
    end = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x3000
    calls, jumps = set(), set()
    for a, w in enumerate(words[:0x3000]):
        if w >> 13 == 3:
            calls.add((a & 0x2000) | (w & 0x1FFF))
        elif w >> 13 == 2:
            jumps.add((a & 0x2000) | (w & 0x1FFF))
    for a in range(start, end):
        if a in calls:
            print(f"\nF{a:04x}:")
        elif a in jumps:
            print(f"L{a:04x}:")
        text, _, _ = decode(words[a], a)
        print(f"  {a:04x}  {words[a]:04x}   {text}")


if __name__ == "__main__":
    main()
