# rea-jazz

An unofficial lighting controller for the AJAZZ AK992 Retro keyboard in its wired single-colour build (USB `1A2C:9C00`). It sets the built-in lighting modes, brightness and speed. The HID protocol was reverse-engineered from the vendor Windows app, so the vendor app does not need to be installed and its kernel filter driver is not used.

## Download

A prebuilt `AK992Lighting.exe` is attached to the GitHub Releases page. It is a Windows program. Run it with the keyboard plugged in.

## GUI usage

Start `AK992Lighting.exe`. Pick a mode from the dropdown, set brightness and speed with the sliders, then press Apply. The Reconnect button reopens the config channel if the keyboard was unplugged.


## CLI usage

```
python ak992.py info                         show the config channel the tool would use
python ak992.py mode breathing -b 5 -s 3     set a built-in lighting mode
```

`mode` takes a name plus optional flags: `-b` brightness 1 to 5, `-s` speed 1 to 5, `-d` effect direction (default 0).


Mode names:

```
steady, breathing, windmill, neon, streamer, flowing, ripples, points,
flash, shadow, ripples-shining, rich, marquee, storm, serpentine, stars,
snake, diagonal, sine
```

## Running from source

Python 3.11. There are no third-party dependencies.

To build the exe:

```
pip install pyinstaller
pyinstaller --onefile --windowed --name AK992Lighting ak992_gui.py
```

## How it works

The keyboard exposes a vendor HID collection on interface MI_01 with usage page 0xFF01. The tool opens that collection and sends each command as an 8-byte feature report with report ID 7. A mode change is one packet:

```
07 FF FF <mode-1> <brightness-1> <speed-1> <slot> <direction>
```

These are the same bytes the vendor app builds when a mode is picked in its lighting UI. The packet layouts, the firmware's command parser and how they were recovered are in [FINDINGS.md](FINDINGS.md).

The code refuses to send any command prefix it has not traced to the lighting UI, and it hard-blocks `07 EE`, which the firmware treats as a bootloader request. It never reads or writes firmware.

The keyboard stores the current mode in non-volatile memory. To avoid wearing that memory out, `set_mode` runs at most once per second.

## What this model cannot do

The single-light AK992 firmware has no per-key lighting command and no lighting mode that shows music data. Both were tested on hardware. A music visualizer or per-key effects would need different firmware, and this project does not flash firmware.

## Compatibility

Tested on the wired single-light AK992, USB `1A2C:9C00`. The 2.4G and RGB variants use a different command header and are not supported.

## License

MIT. Not affiliated with AJAZZ.
