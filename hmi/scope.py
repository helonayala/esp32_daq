#!/usr/bin/env python3
"""Oscilloscope for the ESP32 DAQ board: rolling window of VIN1/VIN2 and a waveform generator on VOUT (no control loop).

Uses only the firmware's idle commands:  R (reads channel 1 and 2)  and  V<mV> (sets the output voltage).
Starts reading as soon as it opens; rolling window of the last WINDOW seconds.
With the firmware esp32_scope (115200 baud at boot, raised automatically) the ESP32 generates the waveform and samples by itself (1 kS/s by default, jitter-free time);
with the old firmware esp32_daq the PC generates it and polls with R/V (about 200 S/s). Detected automatically.

  python scope.py                     (detects the ESP32 USB port)
  python scope.py --port COM11 --rate 200 --window 10

Closing the window sets the output to 0 V.
"""
import argparse
import collections
import re
import threading
import time

import numpy as np

from hmi import serial_ports

READ_RE = re.compile(r"#READ theta=(-?[\d.]+) v2=(-?[\d.]+)")
V_LIM = 10.0                                                     # output command limit [V]


STREAM_RE = re.compile(r"#S(\d+),(-?\d+),(-?\d+),(-?\d+)")
SHAPE_ID = {"off": 0, "DC": 1, "square": 2, "triangle": 3, "sine": 4, "sawtooth": 5}


class Scope:
    """Serial link with two modes, chosen automatically:
    - STREAM (firmware esp32_scope, baud rate negotiated up to 921600): the ESP32 generates the waveform and samples at its own rate FS and sends the
      data in bursts; the time of sample k is k/FS (no PC/USB jitter).
    - LEGACY (firmware esp32_daq, 115200 baud): a sampler thread sends 'V<mV>' + 'R' every 1/rate s; reader parses '#READ'."""

    def __init__(self, port, rate, window, legacy=False):
        import serial
        self.stream = False
        self.baud = 115200
        if not legacy:
            self.ser = serial.Serial(port, 115200, timeout=0.05)
            time.sleep(2.5)                                      # the ESP32 resets when the port is opened
            self.ser.reset_input_buffer()
            self.ser.write(b"?\n")
            time.sleep(0.4)
            self.stream = b"#SCOPE" in self.ser.read(400)
            if self.stream:                                      # try to raise the baud rate (firmware reverts if we fail)
                for b in (921600, 460800, 230400):
                    self.ser.write(f"B{b}\n".encode())
                    self.ser.flush()
                    time.sleep(0.15)
                    self.ser.baudrate = b
                    self.ser.reset_input_buffer()
                    self.ser.write(b"?\n")
                    time.sleep(0.3)
                    if b"#SCOPE" in self.ser.read(400):
                        self.baud = b
                        break
                    time.sleep(3.2)                              # the firmware went back to 115200
                    self.ser.baudrate = 115200
                    self.ser.reset_input_buffer()
            else:
                self.ser.close()
        if not self.stream:                                      # old firmware: 115200 baud, R/V polling
            self.ser = serial.Serial(port, 115200, timeout=0.05)
            time.sleep(2.5)
            self.ser.reset_input_buffer()
            self.ser.write(b"S\n")
        self.rate = float(rate) if rate else (min(1000.0, 0.8 * self.baud / 260.0) if self.stream else 200.0)
        self.dt = 1.0 / self.rate
        n = int(window * self.rate * 1.5) + 10
        self.lock = threading.Lock()
        self.t, self.v1, self.v2, self.vo = (collections.deque(maxlen=n) for _ in range(4))
        self._wave = {"shape": "off", "amp": 3.0, "off": 0.0, "freq": 0.5}
        self.v_out = 0.0                                         # last output [V]
        self.pending = collections.deque()                       # legacy: (send time, output) of each R not yet answered
        self.t0 = time.perf_counter()
        self.alive = True
        self.lost = 0                                            # samples missing in the stream (k gaps)
        self._k_last = -1
        self.info = ""                                           # last #STAT line of the firmware
        threading.Thread(target=self._reader, daemon=True).start()
        if self.stream:
            self.ser.write(f"M{int(self.rate)}\n".encode())
            threading.Thread(target=self._keepalive, daemon=True).start()
        else:
            threading.Thread(target=self._sampler, daemon=True).start()

    @property
    def wave(self):
        return self._wave

    @wave.setter
    def wave(self, w):
        self._wave = w
        if self.stream:
            v = lambda x: int(round(x * 1000))                   # noqa: E731
            self.send(f"W{SHAPE_ID[w['shape']]},{v(w['amp'])},{v(w['off'])},{v(w['freq'])}")

    def configure(self, tau_us=0, target_us=500, bits=12):
        """Output-filter parameters (stream firmware only): edge pre-emphasis E<tau>,<target> (tau 0 = off) and PWM bits Q<bits>."""
        if not self.stream:
            return
        if bits != 12:
            self.send(f"Q{int(bits)}")
        if tau_us > 0:
            self.send(f"E{int(tau_us)},{int(target_us)}")

    def send(self, cmd):
        try:
            self.ser.write((cmd + "\n").encode())
        except Exception:
            pass

    def _keepalive(self):
        while self.alive:
            self.send("K")
            time.sleep(0.5)

    def out_value(self, t):
        w = self.wave
        if w["shape"] == "off":
            return 0.0
        if w["shape"] == "DC":
            v = w["off"]
        else:
            ph = (t * w["freq"]) % 1.0
            if w["shape"] == "square":
                s = 1.0 if ph < 0.5 else -1.0
            elif w["shape"] == "sine":
                s = float(np.sin(2 * np.pi * ph))
            elif w["shape"] == "sawtooth":
                s = 2 * ph - 1
            else:                                                # triangle
                s = 4 * ph - 1 if ph < 0.5 else 3 - 4 * ph
            v = w["off"] + w["amp"] * s
        return max(-V_LIM, min(V_LIM, v))

    def _sampler(self):
        nxt = time.perf_counter()
        while self.alive:
            t = time.perf_counter() - self.t0
            self.v_out = self.out_value(t)
            self.pending.append((t, self.v_out))
            try:
                self.ser.write(f"V{int(round(self.v_out * 1000))}\nR\n".encode())
            except Exception:
                break
            nxt += self.dt
            d = nxt - time.perf_counter()
            if d > 0:
                time.sleep(d)
            else:
                nxt = time.perf_counter()                       # fell behind: resynchronize

    def _reader(self):
        buf = b""
        while self.alive:
            try:
                buf += self.ser.read(1024)
            except Exception:
                break
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.decode(errors="replace").strip()
                if self.stream:
                    ms = STREAM_RE.match(line)
                    if ms:
                        k = int(ms.group(1))
                        if self._k_last >= 0 and k > self._k_last + 1:
                            self.lost += k - self._k_last - 1
                        self._k_last = k
                        with self.lock:
                            self.t.append(k / self.rate)
                            self.v1.append(int(ms.group(2)) / 1000.0)
                            self.v2.append(int(ms.group(3)) / 1000.0)
                            self.vo.append(int(ms.group(4)) / 1000.0)
                            self.v_out = int(ms.group(4)) / 1000.0
                    elif line.startswith("#STAT") or line.startswith("#STOPPED"):
                        self.info = line
                    continue
                m = READ_RE.match(line)
                if m and self.pending:
                    ts, vo = self.pending.popleft()
                    with self.lock:
                        self.t.append(ts)
                        self.v1.append(float(m.group(1)))
                        self.v2.append(float(m.group(2)))
                        self.vo.append(vo)

    def data(self):
        with self.lock:
            return np.array(self.t), np.array(self.v1), np.array(self.v2), np.array(self.vo)

    def close(self):
        self.alive = False
        time.sleep(0.1)
        try:
            self.ser.write(b"M0\nV0\nS\n" if self.stream else b"V0\nS\n")
            self.ser.flush()
            self.ser.close()
        except Exception:
            pass


def run(port, rate, window, init=None, legacy=False, edge=(0, 500), bits=12):
    import tkinter as tk
    from tkinter import ttk
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure

    sc = Scope(port, rate, window, legacy)
    sc.configure(edge[0], edge[1], bits)
    rate = sc.rate
    root = tk.Tk()
    root.title(f"ESP32 DAQ — scope ({port}) — " + (f"STREAM {rate:g} S/s (firmware esp32_scope)" if sc.stream else f"legacy {rate:g} S/s (firmware esp32_daq)"))

    box = ttk.LabelFrame(root, text=" Board output (VOUT): waveform generated by the PC ", padding=6)
    box.pack(fill="x", padx=6, pady=6)
    row1, row2, row3 = ttk.Frame(box), ttk.Frame(box), ttk.Frame(box)
    row3.pack(fill="x", pady=(0, 6))                             # step row (on top)
    row1.pack(fill="x")
    row2.pack(fill="x", pady=(4, 0))
    v_shape = tk.StringVar(value="off")
    v_amp, v_off, v_freq = tk.StringVar(value="3"), tk.StringVar(value="0"), tk.StringVar(value="0.5")
    ttk.Label(row1, text="Function:").pack(side="left")
    for s in ("off", "DC", "square", "triangle", "sine", "sawtooth"):
        ttk.Radiobutton(row1, text=s, value=s, variable=v_shape).pack(side="left", padx=4)
    for label, var in (("amplitude [V]", v_amp), ("offset / DC [V]", v_off), ("frequency [Hz]", v_freq)):
        ttk.Label(row2, text=label).pack(side="left")
        ttk.Entry(row2, textvariable=var, width=8).pack(side="left", padx=(2, 12))
    bar = row2
    lbl = ttk.Label(box, text="")

    def apply(_=None):
        try:
            w = {"shape": v_shape.get(), "amp": float(v_amp.get()), "off": float(v_off.get()),
                 "freq": float(v_freq.get())}
        except ValueError:
            lbl.config(text="invalid value", foreground="#b00020")
            return
        if w["freq"] <= 0:
            lbl.config(text="freq must be > 0", foreground="#b00020")
            return
        sc.wave = w
        if w["shape"] in ("off", "DC"):
            lbl.config(text=f"applied: {w['shape']}", foreground="")
        else:
            spp = rate / w["freq"]                               # output samples per period
            warn = "  ABOVE NYQUIST (rate/2): aliasing!" if w["freq"] > rate / 2 else ""
            lbl.config(text=f"applied: {w['shape']} {w['freq']:g} Hz (period {1 / w['freq']:g} s, "
                            f"{spp:.1f} samples/period){warn}", foreground="#b00020" if warn else "")

    ttk.Button(bar, text="Apply (Enter)", command=apply).pack(side="left", padx=8)
    lbl.pack(fill="x", pady=(4, 0))
    root.bind("<Return>", apply)
    v_shape.trace_add("write", lambda *_: apply())

    # ---- step: DC level on VOUT, independent of the function selector below
    v_step = tk.StringVar(value="0")

    def step(val=None):
        try:
            v = float(v_step.get().replace(",", ".")) if val is None else float(val)
        except ValueError:
            lbl.config(text="invalid step value", foreground="#b00020")
            return
        v = max(-V_LIM, min(V_LIM, v))
        v_step.set(f"{v:g}")
        v_off.set(f"{v:g}")
        v_shape.set("DC")                                       # the trace applies it
        apply()
        lbl.config(text=f"STEP: VOUT = {v:+.3f} V (DC)", foreground="")

    if init:                                                     # start with a waveform already on (--shape ...)
        v_amp.set(f"{init['amp']:g}")
        v_off.set(f"{init['off']:g}")
        v_freq.set(f"{init['freq']:g}")
        v_shape.set(init["shape"])                               # the trace applies it

    ttk.Label(row3, text="Step [V]:", font=("", 10, "bold")).pack(side="left")
    e_step = ttk.Entry(row3, textvariable=v_step, width=8)
    e_step.pack(side="left", padx=4)
    e_step.bind("<Return>", lambda e: (step(), "break")[1])
    ttk.Button(row3, text="Go", command=step).pack(side="left", padx=(0, 12))
    for lv in (-9, -5, -2.5, 0, 2.5, 5, 9):
        ttk.Button(row3, text=f"{lv:+g}", width=5, command=lambda lv=lv: step(lv)).pack(side="left", padx=1)

    row5 = ttk.Frame(box)
    row5.pack(fill="x", pady=(6, 0))
    v_auto, v_win = tk.BooleanVar(value=True), tk.StringVar(value=f"{window:g}")
    ttk.Checkbutton(row5, text="auto time window (about 5 periods)", variable=v_auto).pack(side="left")
    ttk.Label(row5, text="  or fixed window [s]").pack(side="left")
    e_win = ttk.Entry(row5, textvariable=v_win, width=6)
    e_win.pack(side="left", padx=(2, 6))
    e_win.bind("<KeyRelease>", lambda e: v_auto.set(False))

    stats = ttk.Label(root, text="", padding=(6, 0), font=("Consolas", 10))
    stats.pack(fill="x")

    fig = Figure(figsize=(9, 6), dpi=100)
    ax = fig.subplots(2, 1, sharex=True)
    l1, = ax[0].plot([], [], color="#0072B2", lw=1.5, label="VIN1 (ch 1)")
    l2, = ax[0].plot([], [], color="#D55E00", lw=1.2, ls="--", label="VIN2 (ch 2)")
    lo, = ax[1].plot([], [], color="#009E73", lw=1.5, drawstyle="steps-post", label="VOUT (command)")
    for a, yl in zip(ax, ["inputs [V]", "output [V]"]):
        a.set_ylabel(yl)
        a.grid(alpha=0.3)
        a.legend(loc="upper left", ncol=2)
    ax[1].set_xlabel("t [s]")
    fig.tight_layout()
    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.get_tk_widget().pack(fill="both", expand=True)

    def tick():
        t, v1, v2, vo = sc.data()
        if len(t):
            tn = t[-1]
            w = sc.wave
            try:
                win = float(v_win.get().replace(",", "."))
            except ValueError:
                win = window
            if v_auto.get():                                     # periodic shape: show about 5 periods
                win = min(window, max(0.2, 5.0 / w["freq"])) if w["shape"] not in ("off", "DC") else window
            win = max(0.05, win)
            keep = t >= tn - win
            t, v1, v2, vo = t[keep], v1[keep], v2[keep], vo[keep]
            l1.set_data(t, v1)
            l2.set_data(t, v2)
            lo.set_data(t, vo)
            for a in ax:
                a.set_xlim(max(0.0, tn - win), max(win, tn))
                a.relim()
                a.autoscale_view(scalex=False)
            fs = (len(t) - 1) / (t[-1] - t[0]) if len(t) > 1 else 0.0

            def st(v):                                           # statistics over the whole window
                mid = 0.5 * (v.min() + v.max())                  # high/low = median of the samples above/below mid
                hi, lo_ = v[v >= mid], v[v < mid]
                return (f"min {v.min():+7.3f}  max {v.max():+7.3f}  mean {v.mean():+7.3f}  |  "
                        f"high {np.median(hi):+7.3f}  low {np.median(lo_) if len(lo_) else v.min():+7.3f}")
            stats.config(text=(f"window {t[-1] - t[0]:4.1f} s, {len(t)} samples, {fs:.1f} S/s,  out {sc.v_out:+.3f} V  lost {sc.lost}  {sc.info}\n"
                               f"VIN1 [V]  {st(v1)}\nVIN2 [V]  {st(v2)}"))
            canvas.draw_idle()
        root.after(100, tick)

    def close_window():
        sc.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close_window)
    tick()
    root.mainloop()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port")
    ap.add_argument("--rate", type=float, default=None, help="samples per second (default: 1000 with firmware esp32_scope, 200 with the old one)")
    ap.add_argument("--legacy", action="store_true", help="force the old R/V polling mode (firmware esp32_daq, 115200 baud)")
    ap.add_argument("--window", type=float, default=10.0, help="window length [s] (default 10)")
    ap.add_argument("--shape", choices=["off", "DC", "square", "triangle", "sine", "sawtooth"],
                    help="start with this output waveform already on")
    ap.add_argument("--amp", type=float, default=3.0, help="amplitude [V] of --shape")
    ap.add_argument("--off", type=float, default=0.0, help="offset / DC level [V] of --shape")
    ap.add_argument("--freq", type=float, default=0.5, help="frequency [Hz] of --shape")
    ap.add_argument("--tau", type=float, default=0.0, help="output filter pole [us] for the edge pre-emphasis (0 = off; the board's RC measures ~2000)")
    ap.add_argument("--target", type=float, default=500.0, help="pre-emphasis target pole [us] (smaller = sharper edges)")
    ap.add_argument("--bits", type=int, default=12, choices=[8, 9, 10, 11, 12], help="PWM resolution (12 = 19.5 kHz ... 10 = 78 kHz)")
    a = ap.parse_args()
    port = a.port or (serial_ports() or [None])[0]
    if not port:
        raise SystemExit("no serial port found (use --port)")
    init = {"shape": a.shape, "amp": a.amp, "off": a.off, "freq": a.freq} if a.shape else None
    run(port, a.rate, a.window, init, a.legacy, (a.tau, a.target), a.bits)


if __name__ == "__main__":
    main()
