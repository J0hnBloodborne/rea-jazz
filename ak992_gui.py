"""Tkinter GUI for the AJAZZ AK992 keyboard backlight."""
import threading
import tkinter as tk
from tkinter import ttk

from ak992 import AK992, MODES, BRIGHTNESS_MAX, SPEED_MAX

PRETTY = {name.replace("-", " ").title(): name for name in MODES}
DEFAULT_MODE = "Neon" if "Neon" in PRETTY else next(iter(PRETTY))


class App:
    def __init__(self, root):
        self.root = root
        self.kb = None
        self.lock = threading.Lock()

        root.title("AK992 Lighting")
        root.geometry("420x230")
        root.resizable(False, False)

        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")

        self.status = tk.StringVar(value="")
        self.mode_name = tk.StringVar(value=DEFAULT_MODE)
        self.brightness = tk.DoubleVar(value=BRIGHTNESS_MAX)
        self.speed = tk.DoubleVar(value=4)
        self.bright_text = tk.StringVar(value=str(int(BRIGHTNESS_MAX)))
        self.speed_text = tk.StringVar(value="4")

        self._build()
        self.connect()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build(self):
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        top = ttk.Frame(outer)
        top.pack(fill="x")
        ttk.Label(top, textvariable=self.status, anchor="w", wraplength=290).pack(
            side="left", fill="x", expand=True)
        ttk.Button(top, text="Reconnect", command=self.connect).pack(side="right")

        light = ttk.LabelFrame(outer, text="Lighting", padding=10)
        light.pack(fill="x", pady=(10, 0))
        light.columnconfigure(1, weight=1)

        ttk.Label(light, text="Mode").grid(row=0, column=0, sticky="w", pady=2)
        self.mode_box = ttk.Combobox(light, textvariable=self.mode_name,
                                     state="readonly", values=list(PRETTY))
        self.mode_box.grid(row=0, column=1, columnspan=2, sticky="ew", pady=2)

        ttk.Label(light, text="Brightness").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Scale(light, from_=1, to=BRIGHTNESS_MAX, variable=self.brightness,
                  command=lambda v: self._on_scale(self.brightness, self.bright_text)
                  ).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Label(light, textvariable=self.bright_text, width=3, anchor="e").grid(
            row=1, column=2, sticky="e")

        ttk.Label(light, text="Speed").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Scale(light, from_=1, to=SPEED_MAX, variable=self.speed,
                  command=lambda v: self._on_scale(self.speed, self.speed_text)
                  ).grid(row=2, column=1, sticky="ew", padx=6)
        ttk.Label(light, textvariable=self.speed_text, width=3, anchor="e").grid(
            row=2, column=2, sticky="e")

        ttk.Button(light, text="Apply", command=self.apply).grid(
            row=3, column=0, columnspan=3, sticky="ew", pady=(10, 0))

    def _on_scale(self, var, textvar):
        textvar.set(str(int(round(float(var.get())))))

    def _brightness(self):
        return int(round(float(self.brightness.get())))

    def _speed(self):
        return int(round(float(self.speed.get())))

    def connect(self):
        with self.lock:
            if self.kb is not None:
                try:
                    self.kb.close()
                except Exception:
                    pass
                self.kb = None
            try:
                self.kb = AK992()
            except Exception as exc:
                self.status.set(str(exc))
                return
        self.status.set("Connected")

    def apply(self):
        name = PRETTY.get(self.mode_name.get())
        if name is None:
            return
        self._send_mode(name, self._brightness(), self._speed())

    def _send_mode(self, name, brightness, speed):
        try:
            with self.lock:
                if self.kb is None:
                    raise RuntimeError("not connected")
                self.kb.set_mode(MODES[name], brightness, speed, 0)
            self.status.set(f"Connected | {name.replace('-', ' ').title()} b={brightness} s={speed}")
        except Exception as exc:
            self.status.set(f"{type(exc).__name__}: {exc}")

    def on_close(self):
        with self.lock:
            if self.kb is not None:
                try:
                    self.kb.close()
                except Exception:
                    pass
                self.kb = None
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
