# rea-jazz

An unofficial lighting controller for the AJAZZ AK992 Retro keyboard in its wired single-colour build (USB `1A2C:9C00`). It sets the built-in lighting modes, brightness and speed, and it drives a visualizer that pulses the ice blue backlight with whatever the PC is playing. The HID protocol was reverse-engineered from the vendor Windows app, so the vendor app does not need to be installed and its kernel filter driver is not used.

## Download

A prebuilt `AK992Lighting.exe` is attached to the GitHub Releases page. It is a Windows program. Run it with the keyboard plugged in.

## GUI usage

Start `AK992Lighting.exe`. Pick a mode from the dropdown, set brightness and speed with the sliders, then press Apply. The Reconnect button reopens the config channel if the keyboard was unplugged.

The visualizer button pulses brightness with the audio the PC is currently playing. It records from the default speaker with WASAPI loopback, so it does not use a microphone and does not pick up room sound. The gain slider scales the level, and it can be moved while the visualizer runs. Pressing Stop restores the mode that is selected in the mode box.

## CLI usage

```
python ak992.py info                         show the config channel the tool would use
python ak992.py mode breathing -b 5 -s 3     set a built-in lighting mode
python ak992.py visualize                    pulse the backlight with system audio (Ctrl+C to stop)
python ak992.py visualize --dry-run          same, but print levels instead of sending
```

`mode` takes a name plus optional flags: `-b` brightness 1 to 5, `-s` speed 1 to 5, `-d` effect direction (default 0).

`visualize` takes `--fps` (updates per second, default 25), `--gain` (level multiplier, default 1.0), `--restore` (mode to set on exit, default neon) and `--dry-run` (print the levels without touching the keyboard).

Mode names:

```
steady, breathing, windmill, neon, streamer, flowing, ripples, points,
flash, shadow, ripples-shining, rich, marquee, storm, serpentine, stars,
snake, diagonal, sine
```

## Running from source

Python 3.11.

```
pip install -r requirements.txt
```

`soundcard` and `numpy` are only used by the visualizer. The lighting commands work without them.

To build the exe:

```
pip install pyinstaller
pyinstaller --onefile --windowed --name AK992Lighting --collect-all soundcard ak992_gui.py
```

## How it works

The keyboard exposes a vendor HID collection on interface MI_01 with usage page 0xFF01. The tool opens that collection and sends each command as an 8-byte feature report with report ID 7. A mode change is one packet:

```
07 FF FF <mode-1> <brightness-1> <speed-1> <slot> <direction>
```

These are the same bytes the vendor app builds when a mode is picked in its lighting UI. The vendor music command is only sent to models with a music-capable mode, and the AK992 single-light layout has none, so the visualizer varies the brightness of Steady mode instead. The packet layouts and how they were recovered are in [FINDINGS.md](FINDINGS.md).

The code refuses to send any command prefix it has not traced to the lighting UI. It never reads or writes firmware.

## Compatibility

Tested on the wired single-light AK992, USB `1A2C:9C00`. The 2.4G and RGB variants use a different command header and are not supported.

## License

MIT. Not affiliated with AJAZZ.
