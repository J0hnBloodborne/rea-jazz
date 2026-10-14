# AK992 MCU instruction set (inferred)

The AK992 (USB `1A2C:9C00`, manufacturer string "SEMICO") runs an 8-bit accumulator MCU with 16-bit little-endian instruction words. No datasheet was found. Everything below was inferred from the 32 KB image in the vendor updater (`700N(0X3B4F)defineV9_20230316.exe`, PE resource `BIN/115`). Code occupies words `0x0000`-`0x2FFF`, and the rest is `FF`.

`dis.py` implements this table. To extract the image, take 32,768 bytes from file offset `0x2C1AC4` of the updater. The image is not stored in this repo.

Confidence: **high** = confirmed by several independent uses or by decoding known data, **medium** = consistent in every use checked, **low** = guess.

## Control flow

| Encoding | Meaning | Confidence | Evidence |
|---|---|---|---|
| `010k kkkk kkkk kkkk` | `jmp` to `(pc & 0x2000) \| k` | high | Command parser branches land on the matching handlers |
| `011k kkkk kkkk kkkk` | `call` (same addressing) | high | 231 targets; `E022` precedes 87 of them |
| `E022` | `ret` | high | As above |
| `E023` | `reti` | high | Ends the interrupt handler after context restore |
| `00xx` | `ret a, #xx` (return a literal) | high | The table at `0x030B` decodes to the device's HID report descriptor |
| `E040` | add A to the program counter (computed jump into the next table) | high | 82 uses, each followed by a `jmp` or `ret a,#` table |
| `E000` | `nop` | high | Padding, and delay slots in the I2C routines |

## Immediate operations

| Encoding | Meaning | Confidence |
|---|---|---|
| `20xx` | A = #xx | high |
| `30xx` | A &= #xx | high (masks before computed jumps) |
| `38xx` | A ^= #xx | high (the command parser compares this way) |
| `28xx` | A \|= #xx | medium |
| `08xx` | A += #xx | medium |
| `18xx` | A -= #xx | medium |
| `12xx` | subtract with borrow, immediate | low |

## Memory operations (`xx` is a RAM/SFR address)

| Encoding | Meaning | Confidence | Evidence |
|---|---|---|---|
| `C0xx` | A = [xx] | high | |
| `E2xx` | [xx] = A | high | |
| `E6xx` | [xx] = 0 | medium-high | Block clears; the set-mode handler clears the music counter |
| `CExx` | decrement [xx], skip next if zero | high | Delay and loop counters (`sdz; jmp back`) |
| `D6xx` | rotate [xx] left | high | The I2C byte-send loop shifts its data byte with it |
| `D8xx` | A = nibble-swap([xx]) | medium | Interrupt context restore |
| `DAxx` | nibble-swap [xx] in place | medium | Interrupt context restore |
| `E8xx` | compare A with [xx] (sets C and Z) | medium | Followed by a carry test 185 times |
| `F8xx` | compare for equality (sets Z) | medium | |
| `F6xx` | [xx] &= A | high | Clears interrupt-flag bits with an inverted mask |
| `EExx` | [xx] ^= A | medium | Clears the music counter in the dispatcher |
| `CAxx` | test or increment [xx], can skip | low | |
| `FExx`, `EAxx`, `F2xx`, `FAxx`, `FCxx`, `C4xx`, `D2xx` | read-modify-write ops, exact op unknown | low | |
| `E0xx` (other low bytes) | moves to or from special registers in the low address range | low | `E02B`/`E00B` read and write the port-B shadow in the I2C code |

## Bit operations (`b` = bits 1-3 of the high byte)

| Encoding | Meaning | Confidence |
|---|---|---|
| `100 0 bbb 0` `xx` | skip next if [xx].b is clear | high |
| `100 1 bbb 0` `xx` | skip next if [xx].b is set | high |
| `101 0 bbb 0` `xx` | clear [xx].b | high |
| `101 1 bbb 0` `xx` | set [xx].b | high |

## Registers

| Address | Use | Confidence |
|---|---|---|
| `00` | indirect data register (reads/writes the address in `04`) | high |
| `03` | STATUS: bit 0 = C, bit 2 = Z | high |
| `04` | memory pointer for `00` | high |
| `05` | LED column/row drive port (bits 2-6) | medium |
| `0B` | I2C to the settings EEPROM: bit 0 = SDA, bit 1 = SCL | high |
| `0D`, `0E` | USB controller address and data | high |
| `0F` | interrupt flags (the handler dispatches on bits 0, 1, 2, 3, 5, 7) | high |
| `10` | bit 7 = global interrupt enable | medium |
| `70` | first byte of a received USB command (also used as scratch) | high |
| `A0`-`B4` | 21-byte LED frame buffer, one byte per keyboard column | high |
| `EF` | music-frame flag: set to `0xFA` by the music command, cleared after one frame | medium |
| `FC`, `FD`, `FE` | current mode index, brightness, speed | high |
| `FF` | update-request flag (`0xAA` after `07 EE DD`) | high |

## Program map (word addresses)

| Address | Routine |
|---|---|
| `0000` | reset vector: `jmp 04C9` |
| `0001` | single interrupt entry: saves A/STATUS/`10`/`04`, dispatches on `0F` |
| `030B` | HID report descriptor table |
| `0DD8`-`0EB0` | USB vendor command parser (first byte in `70`) |
| `0E1E` | music command: style 0/1 fills the buffer, style 2/3 draws a bar from the right |
| `0EA9` | `07 EE DD`: sets `FF = 0xAA` |
| `1A94` | set mode: stores mode/brightness/speed, rejects mode index > `0x13`, flags a save |
| `1E16` | `07 F0 AA`: reset |
| `2000`-`21BD` | LED scan driver, 5 phases over the 21 column bytes |
| `23D4` | lighting dispatcher: music frame or custom mode skips the effects, otherwise jumps through the table at `23DB` by mode |
| `2B4C`-`2C66` | save settings and LED buffer to the I2C EEPROM (device `0xA0`) |
| `2C68`-`2D17` | load settings from the EEPROM |
| `2D4F`-`2DBD` | I2C start/stop/ack/byte-send/byte-receive |
