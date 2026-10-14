# AK992 MCU instruction set

The AK992 (USB `1A2C:9C00`, manufacturer string "SEMICO") runs an 8-bit MCU with an ELAN EM78-family core and 16-bit little-endian instruction words. The exact part is unknown (no PCB inspection yet). The encoding was mapped from the 32 KB image in the vendor updater (`700N(0X3B4F)defineV9_20230316.exe`, PE resource `BIN/115`). Code occupies words `0x0000`-`0x2FFF`, and the rest is `FF`.

`dis.py` implements this table. To extract the image, take 32,768 bytes from file offset `0x2C1AC4` of the updater. The image is not stored in this repo.

## Instruction set: ELAN EM78 family

The startup code and register map match ELAN's EM78 architecture: R0 indirect data, R1 TCC timer, R2 PC, R3 STATUS (bit 0 C, bit 2 Z), R4 RSR pointer, R5+ ports, RF interrupt status, plus the EM78 system instructions (`CONTW`, `WDTC`, `IOW`, `IOR`, `ENI`, `DISI`, `RETI`, `TBL`). This chip uses 16-bit words, but the opcodes come in the same order as ELAN's documented 13-bit EM78 encoding, so every group could be mapped. With this table, 4 of 12,288 code words remain undecoded (`12xx`, used near the reset code).

References: ELAN "EM78xxx 13-Bit Instruction Set" and "15-Bit Instruction Set" application notes (emc.com.tw).

| Encoding | EM78 instruction |
|---|---|
| `010k kkkk kkkk kkkk` | `JMP k` (page bit 0x2000 from the current PC) |
| `011k kkkk kkkk kkkk` | `CALL k` (same addressing) |
| `00kk` | `RETL #k` |
| `08kk` / `18kk` | `SUB A,#k` / `ADD A,#k` (order inferred from EM78) |
| `20kk` / `28kk` / `30kk` / `38kk` | `MOV` / `OR` / `AND` / `XOR A,#k` |
| `E000` `E001` `E002` `E003` `E004` | `NOP` `DAA` `CONTW` `SLEP` `WDTC` |
| `E005`-`E00F` | `IOW R` (write I/O control register R, e.g. port direction) |
| `E020` `E021` `E022` `E023` `E024` | `ENI` `DISI` `RET` `RETI` `CONTR` |
| `E025`-`E02F` | `IOR R` |
| `E040` | `TBL` (add A to PC: computed jump / lookup table) |
| `C0` `C2` `C4` `C6` | `MOV A,R` `MOV R,R` `COMA R` `COM R` |
| `C8` `CA` `CC` `CE` | `INCA R` `INC R` `DJZA R` `DJZ R` |
| `D0` `D2` `D4` `D6` | `RRCA R` `RRC R` `RLCA R` `RLC R` |
| `D8` `DA` `DC` `DE` | `SWAPA R` `SWAP R` `JZA R` `JZ R` |
| `E2` `E4 00` `E6` | `MOV R,A` `CLRA` `CLR R` |
| `E8` `EA` `EC` `EE` | `SUB A,R` `SUB R,A` `DECA R` `DEC R` |
| `F0` `F2` `F4` `F6` | `OR A,R` `OR R,A` `AND A,R` `AND R,A` |
| `F8` `FA` `FC` `FE` | `XOR A,R` `XOR R,A` `ADD A,R` `ADD R,A` |
| `100 0 bbb 0` R | `JBC R,b` (skip if bit clear) |
| `100 1 bbb 0` R | `JBS R,b` (skip if bit set) |
| `101 0 bbb 0` R | `BC R,b` |
| `101 1 bbb 0` R | `BS R,b` |

The register field is the low byte. The low bit of the high byte would be address bit 8 but is never set in this image.

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
| `EF` | music counter: set to `0xFA` by the music command, decremented once per frame while it skips the effects | high |
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
