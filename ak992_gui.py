"""Tkinter GUI for the AJAZZ AK992 keyboard backlight."""
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

from ak992 import AK992, MODES, BRIGHTNESS_MAX, SPEED_MAX, audio_levels

PRETTY = {name.replace("-", " ").title(): name for name in MODES}
DEFAULT_MODE = "Neon" if "Neon" in PRETTY else next(iter(PRETTY))


class App:
    def __init__(self, root):
        self.root = root
        self.kb = None
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self.levels = queue.Queue()
        self._gain = 1.0
        self._closing = False

        root.title("AK992 Lighting")
        root.geometry("420x360")
        root.resizable(False, False)

        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")

        self.status = tk.StringVar(value="")
        self.mode_name = tk.StringVar(value=DEFAULT_MODE)
        self.brightness = tk.DoubleVar(value=BRIGHTNESS_MAX)
        self.speed = tk.DoubleVar(value=4)
        self.gain = tk.DoubleVar(value=1.0)
        self.bright_text = tk.StringVar(value=str(int(BRIGHTNESS_MAX)))
        self.speed_text = tk.StringVar(value="4")
        self.gain_text = tk.StringVar(value="1.00")

        self._build()
        self.connect()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(50, self.poll_levels)

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

        viz = ttk.LabelFrame(outer, text="Visualizer", padding=10)
        viz.pack(fill="x", pady=(10, 0))
        viz.columnconfigure(1, weight=1)

        self.start_btn = ttk.Button(viz, text="Start visualizer", command=self.toggle_visualizer)
        self.start_btn.grid(row=0, column=0, columnspan=3, sticky="ew")

        ttk.Label(viz, text="Gain").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Scale(viz, from_=0.5, to=3.0, variable=self.gain,
                  command=self._on_gain).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Label(viz, textvariable=self.gain_text, width=5, anchor="e").grid(
            row=1, column=2, sticky="e")

        self.bar = ttk.Progressbar(viz, orient="horizontal", mode="determinate", maximum=255)
        self.bar.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))

    def _on_scale(self, var, textvar):
        textvar.set(str(int(round(float(var.get())))))

    def _on_gain(self, value):
        self._gain = float(value)
        self.gain_text.set(f"{self._gain:.2f}")

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

    def toggle_visualizer(self):
        if self.thread is not None and self.thread.is_alive():
            self.stop_visualizer()
        else:
            self.start_visualizer()

    def start_visualizer(self):
        if self.kb is None:
            self.connect()
        if self.kb is None:
            return
        try:
            import numpy  # noqa: F401
            import soundcard  # noqa: F401
        except Exception as exc:
            self.status.set(f"audio unavailable: {exc}")
            return
        self._gain = float(self.gain.get())
        self.gain_text.set(f"{self._gain:.2f}")
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._visualize, daemon=True)
        self.thread.start()
        self.start_btn.configure(text="Stop visualizer")
        self.status.set("Visualizer running")

    def stop_visualizer(self):
        self.stop_event.set()
        thread = self.thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self.thread = None
        self.start_btn.configure(text="Start visualizer")
        self.bar["value"] = 0
        self.apply()

    def _post(self, kind, payload=None):
        if kind == "level" and self.levels.qsize() > 4:
            return
        self.levels.put_nowait((kind, payload))

    def poll_levels(self):
        try:
            while True:
                kind, payload = self.levels.get_nowait()
                if kind == "level":
                    self.bar["value"] = payload
                elif kind == "error":
                    self.status.set(f"Visualizer stopped: {payload}")
                elif kind == "done":
                    self.start_btn.configure(text="Start visualizer")
        except queue.Empty:
            pass
        if not self._closing:
            self.root.after(50, self.poll_levels)

    def _visualize(self):
        smooth = 0.0
        last_b = None
        last_time = 0.0
        try:
            for raw in audio_levels():
                if self.stop_event.is_set():
                    break
                # Gain is applied here so slider changes take effect while running.
                level = min(255, int(raw * self._gain))
                if level > smooth:
                    smooth = level
                else:
                    smooth = smooth * 0.7 + level * 0.3
                b = 1 + round(smooth / 255 * (BRIGHTNESS_MAX - 1))
                now = time.monotonic()
                if b != last_b and now - last_time >= 1.0 / 25:
                    last_b = b
                    last_time = now
                    with self.lock:
                        if self.kb is None:
                            break
                        self.kb.set_mode(MODES["steady"], b, 4, 0)
                self._post("level", level)
        except Exception as exc:
            self._post("error", str(exc))
        finally:
            self._post("done")

    def on_close(self):
        self._closing = True
        self.stop_event.set()
        thread = self.thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        self.thread = None
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
