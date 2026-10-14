"""Disassembler for the AK992 keyboard MCU firmware (inferred ISA, see ISA.md).

usage: python dis.py fw.bin [start_word end_word] > listing.txt
Word addresses throughout. Mnemonics are hypotheses until marked confirmed in ISA.md.
"""
import sys

# RAM names worked out from usage. Extend as functions get understood.
RAM = {0x00: "IAR", 0x03: "STATUS", 0x04: "MP", 0x0D: "USBA", 0x0E: "USBD", 0x0F: "INTF", 0x40: "PCL"}

# E0xx special ops by exact low byte.
E0_SPECIAL = {0x00: "nop", 0x22: "ret", 0x23: "reti", 0x40: "addpcl a"}

# Read-modify-write and A-op groups by high byte (operand is RAM low byte).
MEM_OPS = {
    0xC0: "mov a, {m}",
    0xC2: "mov.c2 a, {m}",
    0xC4: "add a, {m}",
    0xCA: "sz? {m}",
    0xCE: "sdz {m}",
    0xD2: "adc a, {m}",
    0xD6: "rl {m}",
    0xD8: "swap a, {m}",
    0xDA: "swap {m}",
    0xE2: "mov {m}, a",
    0xE6: "clr {m}",
    0xE8: "cmp a, {m}",
    0xEA: "or {m}, a",
    0xEE: "xor {m}, a",
    0xF2: "op.f2 {m}",
    0xF6: "and {m}, a",
    0xF8: "xor? a, {m}",
    0xFA: "op.fa {m}",
    0xFC: "op.fc {m}",
    0xFE: "op.fe {m}",
}
IMM_OPS = {0x08: "add a, #{i}", 0x12: "sbc a, #{i}", 0x18: "sub a, #{i}", 0x20: "mov a, #{i}",
           0x28: "or a, #{i}", 0x30: "and a, #{i}", 0x38: "xor a, #{i}"}


def ram(m):
    return RAM.get(m, f"[{m:02x}]")


def decode(w, pc=0):
    """Return (text, kind, target). kind: 'jmp', 'call', 'ret', 'tbl', 'skip', or ''.

    JMP/CALL carry 13 bits; the page bit (0x2000) comes from the current pc.
    """
    hi, lo = w >> 8, w & 0xFF
    top3 = w >> 13
    if top3 in (2, 3):
        t = (pc & 0x2000) | (w & 0x1FFF)
        if top3 == 2:
            return f"jmp L{t:04x}", "jmp", t
        return f"call F{t:04x}", "call", t
    if hi == 0x00:
        return f"ret a, #{lo:02x}", "ret", None
    if hi == 0xE0:
        if lo in E0_SPECIAL:
            op = E0_SPECIAL[lo]
            return op, {"ret": "ret", "addpcl a": "tbl"}.get(op, ""), None
        return f"op.e0 {ram(lo)}", "", None
    if 0x80 <= hi <= 0x9F and hi % 2 == 0:
        bit = (hi >> 1) & 7
        # 8x: skip next if bit clear (the next insn runs when the bit is set); 9x: skip if set.
        return f"{'sset' if hi & 0x10 else 'sclr'} {ram(lo)}.{bit}", "skip", None
    if 0xA0 <= hi <= 0xBF and hi % 2 == 0:
        bit = (hi >> 1) & 7
        return f"{'set' if hi & 0x10 else 'clr'} {ram(lo)}.{bit}", "", None
    if hi in MEM_OPS:
        return MEM_OPS[hi].format(m=ram(lo)), "", None
    if hi in IMM_OPS:
        return IMM_OPS[hi].format(i=f"{lo:02x}"), "", None
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
