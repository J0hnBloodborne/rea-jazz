# AK992 reverse-engineering notes

Status as of 2026-10-14. Goal: control the AK992 lighting without the vendor app, using a small open-source tool.

## Device

- AJAZZ AK992 enumerates as USB `1A2C:9C00`. Vendor `config.xml` confirms this (`name="A-jazz AK992"`, layout `KB-K102`). A commented 2.4G variant uses PID `7FFF`.
- The second keyboard on this PC (`30FA:1440`) is a different device.
- HID collections on `1A2C:9C00`, from `hidcaps.py` (read-only probe):

| Interface | Usage page / usage | Reports | Role |
|---|---|---|---|
| MI_00 | 0x0001 / 0x06 | in 9, out 2 | boot keyboard |
| MI_01 COL01 | 0x000C / 0x01 | in 3 | consumer keys |
| MI_01 COL02 | 0x0001 / 0x80 | in 2 | system control |
| MI_01 COL03 | 0xFF00 / 0x01 | in 2 | vendor, input only (probably status/notify) |
| MI_01 COL04-06 | 0x0001 / 0x06 | in 8 | NKRO keyboard |
| MI_01 COL07 | 0xFF01 / 0x01 | out 8, feature 8, no report ID | config channel |

## Vendor package

- Zip holds an Inno Setup 6.1 installer. Unpacked with innoextract into `driver/unpacked/app/`.
- `DeviceDriver.exe`: 32-bit MFC app, version "Beta 1.0.3.1". Stores profiles, lighting and macros in SQLite.
- `XYUI.dll`: UI library (exports `KeyboardCtrl::SetLightModeData`, `SetLightSpeed`, and similar).
- `layouts/KB-K102.xml`: 105 keys. Each key has an HID usage `code`, plus `key_index` and `light_index` (0..112). Defaults: mode 5, brightness 5/5, speed 4/5.
- Lighting modes 1-20 (from the `<info>` entries and `language/1033.lan`): 1 Steady, 3 Breathing, 4 Windmill, 5 Neon stream, 6 Streamer, 7 Flowing light and color, 8 Dripping ripples, 9 Brilliant point, 10 Flash away, 11 Shadow disappear, 12 Ripples shining, 13 Rich and honored, 14 Marquee, 15 Rotating storm, 16 Serpentine horse race, 17 Stars twinkle, 18 Retro snake, 19 Diagonal transformation, 20 Sine wave. Mode 2 (custom, `attribute=257`) is commented out. 521 is "Light Off".
- `firmware/700N(0X3B4F)defineV9_20230316.exe`: firmware updater. **Do not run it.**
- `driver/x64/vhidflt.sys` and `vhidflt.inf`: a signed KMDF filter (Shenzhen Xinyao Technology) on `1A2C:9C00 MI_00/MI_01`, plus a `root\vhidev` virtual HID. Its strings show key interception and injection for software macros (`IOCTL_HIDUSBFLT_SET_TABLE`, `NOTIFY_KEYSTATE`, `SET_CACHEABLE_INTERJECT`). It does not handle feature reports, so lighting does not need it. **Not installed.**

## Protocol so far (static, DeviceDriver.exe image base 0x400000)

- HID APIs load at runtime with `GetProcAddress`. The function-pointer slots are `HidD_SetFeature` at `0x56D564` and `HidD_GetFeature` at `0x56D560` (the latter is never called).
- There is one `HidD_SetFeature` call, in the wrapper at `0x4375F0` (`ecx` = this, `[this+0]` = handle, `edx` = buffer, length `0x40`).
- Callers at `0x436118` and `0x436324` copy a caller-built 64-byte packet onto the stack and call the wrapper. The device object is at `[ctx+0x414]`.
- The packet builders sit one level further up. They are the next target.
- Open question: the app passes 64 bytes, but COL07's feature report is 8 bytes (report ID 0 plus 7 data bytes). Either HIDCLASS sends only the first 8, or the app opens another collection. Find the `UP=0x%04X Usage=0x%02X` lookup (format string at `0x54C7A1`) to confirm.
- `WriteFile` at `0x41F7D4` sends 64 bytes with report ID 5. This is probably the `vhidev` virtual device, not the keyboard.

## Protocol from Ghidra decompile (2026-10-14)

Ghidra 12.1.4 is at `C:\Users\Rohaan\tools\ghidra_12.1.4_PUBLIC`. Its `launch.properties` points at the portable JDK in `C:\Users\Rohaan\tools\jdk-21.0.12.1+1`. The analyzed project is in the session scratchpad (`gproj/ak992`). Decompiled builders: scratchpad `builders.c`.

Send path: `FUN_00436070(mgr, pkt, _, devIndex)` sleeps 32 ms, then sends `HidD_SetFeature(h, pkt, 64)`. `FUN_00436270` is the same with a 5 ms sleep (used for music-mode streaming). The packet goes out unchanged, so byte 0 is the report ID, `0x07`.

The app branches on `[dlg+0x4A4] < 200`. config.xml gives the wired AK992 `type="101"`, so it takes the `0x07` path. Type 201 (the 2.4G model) uses `FUN_00436140` with an `BB AA 99 88` header instead.

Commands for the wired AK992. Bytes are listed in send order. The rest of the buffer is zero.

| Bytes | Meaning | Source |
|---|---|---|
| `07 FF FF m b s c x` | Set light mode. `m` = mode-1. `b` = field@0x10 - 1 (probably brightness). `s` = (field@0x20 << 4 \| field@0x14) - 1 (probably direction/speed nibbles). `c` = colour combo index, only if attribute bit 0x100. `x` = field@0x18 (probably the colorful flag). Field names unconfirmed. | `FUN_0041a500` |
| `07 FF FF m p q 00 c` | Mode variant with two raw fields (p, q), used by the custom/colour path | `FUN_0041b310` |
| `07 12 34 56 78 k o` | Per-key custom light: key `k` (light index), `o` = 1 if the key has a colour | `FUN_0041aa80`, `FUN_00421860` |
| `07 12 34 56 78 FE n` | Custom-light mode on, slot `n` (`00` instead of `FE` = off) | `FUN_0041b530`, `FUN_0041a3e0` |
| `07 23 45 67 89 m l` | Music/rhythm light: mode `m`, level `l` (0..255) | `FUN_0041a6d0` |
| `07 F0 AA 00 ...` | Reset to defaults (then sleeps 100 ms) | `FUN_004210e0` |
| `07 01 23 45 67` ... `07 AB CD EF 00` | Begin/end of key-map upload. Body: 16 x 64-byte buffers made of 8-byte chunks `07 88 ...` | `FUN_0041cb30` |
| `07 76 54 32 10 10` then `07 99 ...` chunks, then `07 FE DC BA 00` | Key-function / macro table upload | `FUN_00411e30` |

The 64-byte buffers are built from 8-byte sub-chunks, each starting with `07`. The device's COL07 feature report is only 8 bytes, which suggests HIDCLASS sends just the first 8. For lighting, every command fits in 8 bytes.

### Confirmed 2026-10-14

- COL07 uses report ID `0x07` with 7 data bytes (output and feature, from the fixed `tools/hidcaps.py`).
- `ak992.py mode breathing -b 5` sends `07 FF FF 02 04 03 00 00`, and `HidD_SetFeature` succeeds.
- The light record (`FUN_00405500`, table `t_light_data`) is laid out as: [0] light_id, [1] profile, [2] name, [3] mode, [4] brightness, [5] speed, [6] direction, [7] colorful, [8] colorindex, [9] color_value, [10] config_func, [11] reserved, [12] status.
- So the mode packet is `07 FF FF <mode-1> <brightness-1> <((colorindex<<4)|speed)-1> <slot if config_func&0x100> <direction>`. Brightness and speed are 1..5 in the app.
- Music mode is gated. `FUN_0041a680` feeds `|sample| >> 8` to the music sender only when the music tab is active and the current mode has `config_func & 0x200`. For this model that is only the commented-out `mode="21" attribute="512"`, so the app never sends music packets to the single-light AK992. The visualizer instead varies Steady-mode brightness with the audio.

## Firmware analysis (2026-10-15)

The firmware updater `700N(0X3B4F)defineV9_20230316.exe` carries the image as PE resource `BIN/115`: 32,768 bytes at file offset `0x2C1AC4`. It is not encrypted (entropy 5.5 bits/byte, `FF` padding). The CPU uses 16-bit little-endian instruction words, probably a Holtek-style 8-bit MCU. The partial decode below is inferred from context only: `c0xx`/`c2xx` load, `e0xx`/`e2xx` store, `20xx` A = immediate, `38xx` XOR A with immediate, `30xx` AND A with immediate, `84xx`/`94xx` skip on a bit of a register (`03` is STATUS), `4xxx`/`5xxx` JMP to word `x & 0x1FFF`, `6xxx`/`7xxx` CALL, and `e040` after a masked load is a computed jump through the following table.

Command parser at `0x1BC0`. The first received byte is in RAM `0x70`, and later bytes are read through `[0x0E]`:

| Command | Handler (byte addr) | Notes |
|---|---|---|
| `07 EE DD` | `0x1D52` | Writes `0xAA` to RAM `0xFF`, nothing else. Looks like a bootloader request flag. **Never send.** |
| `07 F0 AA` | `0x3C2C` | Reset |
| `07 FF FF m b s x d` | `0x3528` | Set mode. Rejects mode index > `0x13` (modes 1..20 only), brightness > 5, speed > 5. Out-of-range values fall back to the default (mode 5, Neon stream). |
| `07 01 23 45 67` | `0x1CC8` | Key-map upload begin |
| `07 76 54 32 10` | `0x1CDC` | Macro-table upload begin |
| `07 23 45 67 89 s l` | `0x1C3C` | Music. Style `s & 3`; styles 0/1 copy level `l` into RAM `0xA0..0xB4` (21 columns), styles 2/3 build a bar. |
| `07 88 ...`, `07 99 ...` | | Upload chunks |
| `07 AB CD EF`, `07 FE DC BA DD` | | Upload ends |

`07 12 34 56 78` (per-key custom light) is **not handled** by this firmware.

Hardware tests on the user's keyboard:
- Music packets in mode 21: no response to the level. Mode 21 is out of range and shows Neon stream (a left-to-right flow).
- Music packets in Steady mode, at fixed levels 0/128/255 and styles 1/2: no visible change.
- Per-key begin/set/save, with key byte as LED index or HID code and on = 1 or 0xFF: no change. The user's Fn-recorded preset (mode 2) was untouched. The save packet stalls (NAK) if sent within ~1 ms of the previous packet.
- The mode survives an unplug/replug, so it is stored in non-volatile memory. Frequent `set_mode` calls may wear that memory, so the brightness-pulse visualizer was removed in v0.2.0 and `set_mode` is rate-limited to once per second.
- Feature reports take about 1 ms each.

Conclusion: over USB, this model supports only the 19 built-in animations (modes 1, 3..20), brightness 1..5, speed 1..5, direction, and the on-keyboard custom preset (mode 2). A music or per-key visualizer would need different firmware.

## Firmware disassembly (night of 2026-10-15)

The instruction set is now decoded well enough to read the important routines; see `firmware/ISA.md` and `firmware/dis.py`. The keyboard reports manufacturer "SEMICO" and device version `0x0116`. The image's 16-bit word sum is `0x2B4F`, against `0X3B4F` in the updater's filename.

What the code shows:
- **Settings live in an external I2C EEPROM** (24Cxx-style, device `0xA0`, bit-banged on port `0x0B`), not in MCU flash. The set-mode handler does not write it directly; it raises a flag and a later routine saves. The 1 s rate limit in `ak992.py` stays.
- **LED frame buffer** is RAM `0xA0`-`0xB4`, one byte per keyboard column (21 columns). The scan driver at `0x2000` reads it in 5 phases and drives port `0x05`. Because the user's preset lights single keys inside a column (X but not S), each column byte most likely holds one bit per row. Unconfirmed.
- **Lighting dispatcher** (`0x23D4`): if the music flag (`0xEF`) is set, or the mode is custom (index 1, the Fn preset), it skips all effect code. Otherwise it runs the current mode's effect, which redraws the buffer every frame.
- **Music command** (`0x0E1E`): style 0/1 writes the level byte into all 21 columns; style 2/3 draws a bar of `0x80` columns from the right edge (0, 2, 6, 9, 13, 17 or 21 columns by level). The music flag lasts one frame, so in animated modes the next effect frame overwrites the music data. That explains why the music tests in Steady and mode 21 showed nothing.
- **Untested prediction:** in custom mode (mode 2) nothing overwrites the buffer, so music packets should stay visible. `tools/music_custom_test.py` checks this step by step (all on/off, one bit at a time to find row mapping, bar levels).
- `07 EE DD` sets `0xFF = 0xAA`; the interrupt handler checks that flag before resetting the MCU. This is the update path. Never send it.

### What per-key control would take

With stock firmware: if the test confirms bits = rows, music style 1 gives row control (same pattern in every column) and style 2 gives a column bar. Arbitrary per-key patterns are not reachable over USB.

With patched firmware: a new command that writes one column byte (`[0xA0 + col] = value`) is about 10 instructions, and there is about 8 KB of free code space. Combined with custom mode, that gives full per-key control at USB speed. The hard part is flashing it: the only known route is the vendor updater's protocol through `07 EE DD`. That protocol is not decoded, and a failed update could leave the keyboard unusable until it is reflashed. Do not attempt this without a recovery plan (the MCU's programming pins and a programmer).

## Next steps

1. Set up Ghidra 12.1.x and JDK 21 so REA's decompiler works. Portable zips are in `C:\Users\Rohaan\tools`. Check that they are complete (the Ghidra download may have stopped at 0 bytes). Set `GHIDRA_INSTALL_DIR` and `JAVA_HOME`.
2. Decompile the callers of `0x436118` and `0x436324`. Map the packet byte layout for mode, brightness, speed, colour, direction, and per-key RGB.
3. Done: `ak992.py` opens COL07 and sends 8-byte feature reports. It refuses any prefix not in its allow-list. Never add anything traced to the firmware or upgrade path.
4. Done: Windows GUI app (`ak992_gui.py`), released as an exe.

`tools/hidcaps.py` (fixed probe) and `tools/ghidra_scripts/DecompileRefs.java` are in the repo. The Ghidra project and the earlier `builders.c` dump are in the old session scratchpad, `G:\UsrTemp\claude\f--Documents-rea-jazz\d1186910-4ec5-4f89-a51b-8e98414fc5e8\scratchpad\`. Re-import into a new project if that folder is gone (about 3 minutes).
