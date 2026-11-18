#!/usr/bin/env python3
"""HMI for the ESP32 DAQ (e.g. Ball and Beam bench): starts/stops the run, shows r_x, x, r_theta, theta and u live and saves the data.

  python hmi.py                       (detects the ESP32 USB port)
  python hmi.py --port COM5           (or /dev/cu.usbserial-XXXX, /dev/ttyUSB0)
  python hmi.py --selftest            (no window: runs one run, saves it and prints a summary)
  python hmi.py --demo                (no ESP32: simulated signals, to get to know the HMI)

Shortcuts: ESC = stop (u = 0).  Closing the window also stops.
Data are saved in data/daq_YYYYMMDD_HHMMSS.csv and .mat (variables t, r_x, r_theta, x, theta, u, Ts, mode).
"""
import argparse
import collections
import datetime
import json
import pathlib
import sys
import threading
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
CONFIG = HERE / "config.json"                           # xmin/xmax of x (last values used)
MODES = {0: "open loop", 1: "HIL: x and theta loops", 2: "SIL: x controller only"}
FIELDS = ["k", "t", "r_x", "r_theta", "x", "theta", "u"]
TS = 0.05


def serial_ports():
    from serial.tools import list_ports
    ps = list(list_ports.comports())
    pref = [p.device for p in ps if any(s in (p.device + (p.description or "")).lower()
                                        for s in ("usbserial", "slab", "wch", "ttyusb", "ttyacm", "cp210", "ch340", "usb"))]
    return pref or [p.device for p in ps]


class Link:
    """Serial port + reader thread. Lines '#L k,t,r_x,r_theta,x,theta,u' are data; the other '#...' lines are messages."""

    def __init__(self, port):
        import serial
        self.ser = serial.Serial(port, 115200, timeout=0.1)
        time.sleep(2.5)                                        # the ESP32 resets when the port is opened
        self.ser.reset_input_buffer()
        self.lock = threading.Lock()
        self.rows = []
        self.msgs = collections.deque(maxlen=200)
        self.running, self.finished, self.reason = False, False, ""
        self.mode, self.t_end, self.rx, self.rth = 0, 8.0, 0.5, 1.0
        self.reading = None                                    # last reply to R: dict(theta, v2, x)
        self.alive = True
        threading.Thread(target=self._rx, daemon=True).start()
        self.send("S")
        self.send("?")

    def _rx(self):
        buf = b""
        while self.alive:
            try:
                chunk = self.ser.read(2048)
            except Exception:
                break
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                self._line(raw.decode(errors="replace").strip())

    @staticmethod
    def _kv(line):
        return {k: v for k, v in (p.split("=", 1) for p in line.split() if "=" in p)}

    def _line(self, line):
        if line.startswith("#L") and line[2:3].isdigit():
            try:
                v = [float(a) for a in line[2:].split(",")]
            except ValueError:
                return
            if len(v) == len(FIELDS):
                with self.lock:
                    self.rows.append(v)
            return
        if not line.startswith("#"):
            return
        self.msgs.append(line)
        kv = self._kv(line)
        try:
            if line.startswith("#GO"):
                with self.lock:
                    self.rows = []
                self.running, self.finished, self.reason = True, False, ""
                self.mode, self.t_end = int(kv["mode"]), float(kv["t_end"])
            elif line.startswith("#READ"):
                self.reading = {k: float(v) for k, v in kv.items()}
            elif line.startswith("#STATUS"):
                self.mode, self.rx, self.rth = int(kv["mode"]), float(kv["rx"]), float(kv["rth"])
            elif line.startswith("#STOP"):
                self.running, self.finished, self.reason = False, True, line.split()[1]
        except (KeyError, ValueError, IndexError):
            pass

    def send(self, cmd):
        self.ser.write((cmd + "\n").encode())

    def data(self):
        with self.lock:
            return np.array(self.rows) if self.rows else np.zeros((0, len(FIELDS)))

    def close(self):
        try:
            self.ser.write(b"S\n")
        except Exception:
            pass
        self.alive = False


class DemoLink(Link):
    """Simulates the ESP32 (no serial port): a ball (double integrator) under cascade control, with noise and a
    sequence of r_x steps. Same interface as Link; lets you get to know the HMI without hardware."""

    def __init__(self, port=None, speed=1.0):
        self.lock = threading.Lock()
        self.rows = []
        self.msgs = collections.deque(maxlen=200)
        self.running, self.finished, self.reason = False, False, ""
        self.mode, self.t_end, self.rx, self.rth = 1, 30.0, 0.5, 1.0
        self.reading = None
        self.alive = True
        self.speed = speed
        self.xmin, self.xmax = -10.0, 10.0
        self._stop = False

    def send(self, cmd):
        c, arg = cmd[:1], cmd[1:]
        if c == "G" and not self.running:
            self._stop = False
            threading.Thread(target=self._run, daemon=True).start()
        elif c == "S":
            self._stop = True
        elif c == "A":
            self.rx = int(arg) / 1000
        elif c == "H":
            self.rth = int(arg) / 1000
        elif c == "X" and not self.running:
            a, _, b = arg.partition(",")
            self.xmin, self.xmax = int(a) / 1000, int(b) / 1000
        elif c == "R" and not self.running:
            v2 = 0.1 * (self.xmin + self.xmax) + 0.5 * (self.xmax - self.xmin) * np.random.uniform(-1, 1)
            x = 2 * (v2 - self.xmin) / (self.xmax - self.xmin) - 1
            self.reading = {"theta": 0.02, "v2": v2, "x": x}

    def _run(self):
        rng = np.random.default_rng(7)
        KB, kp_th, KP, KD, sat_r = 0.24, 3.0, 9.0, 8.5, 4.0         # plant and x controller (example)
        t_end = self.t_end
        with self.lock:
            self.rows = []
        self.running, self.finished, self.reason = True, False, ""
        x = v = th = 0.0
        r_x = 0.0
        for k in range(int(t_end / TS) + 1):
            if self._stop:
                break
            t = k * TS
            if t >= 1.0 and (t - 1.0) % 5.0 < TS / 2:               # every 5 s: new step (change <= 0.5)
                r_x = float(np.clip(r_x + rng.uniform(-0.5, 0.5), -0.8, 0.8))
            r_th = float(np.clip(KP * (r_x - x) - KD * v, -sat_r, sat_r))
            u = float(np.clip(kp_th * (r_th - th), -10, 10))
            for _ in range(5):                                      # integrate the plant (Euler)
                h = TS / 5
                th += h * (7.0 / kp_th) * u                         # beam: inner loop with a pole at ~7 rad/s
                v += h * KB * th
                x += h * v
                if abs(x) >= 1:
                    x, v = float(np.sign(x)), 0.0
            row = [k, t, r_x, r_th, x + rng.normal(0, 0.004), th + rng.normal(0, 0.01), u]
            with self.lock:
                self.rows.append(row)
            time.sleep(TS / self.speed)
        self.running, self.finished, self.reason = False, True, "S" if self._stop else "end"

    def close(self):
        self.alive = False
        self._stop = True


def save(d, mode, stamp):
    """writes data/daq_<stamp>.csv and .mat with the run d (columns FIELDS)"""
    DATA.mkdir(exist_ok=True)
    base = DATA / f"daq_{stamp}"
    with open(base.with_suffix(".csv"), "w") as f:
        f.write(f"# ESP32 DAQ mode={mode} Ts={TS}\n")
        f.write("t,r_x,r_theta,x,theta,u\n")
        for r in d:
            f.write(",".join(f"{a:.4f}" for a in r[1:]) + "\n")
    msg = f"{base.with_suffix('.csv').name}"
    try:
        from scipy.io import savemat
        savemat(base.with_suffix(".mat"), {"t": d[:, 1], "r_x": d[:, 2], "r_theta": d[:, 3], "x": d[:, 4],
                                           "theta": d[:, 5], "u": d[:, 6], "Ts": TS, "mode": mode})
        msg += " and .mat"
    except Exception as e:                                      # scipy missing or incompatible with numpy
        msg += f" (no .mat: {type(e).__name__})"
    return msg


def run_selftest(link, rx, rth):
    xmin, xmax = load_config()
    link.send(f"X{int(round(xmin * 1000))},{int(round(xmax * 1000))}")
    link.send(f"A{int(round(rx * 1000))}")
    link.send(f"H{int(round(rth * 1000))}")
    link.send("G")
    t0 = time.time()
    while time.time() - t0 < link.t_end + 8 and not link.finished:
        time.sleep(0.1)
    d = link.data()
    if len(d) == 0:
        print("[ERROR] no data received", file=sys.stderr)
        return 1
    print(f"[ok] {len(d)} samples, stop reason: {link.reason}, final x = {d[-1, 4]:.3f}, final theta = {d[-1, 5]:.3f}")
    print("[ok] saved:", save(d, link.mode, datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    return 0


def load_config():
    try:
        c = json.loads(CONFIG.read_text())
        return float(c["xmin"]), float(c["xmax"])
    except (OSError, ValueError, KeyError):
        return -10.0, 10.0


def save_config(xmin, xmax):
    try:
        CONFIG.write_text(json.dumps({"xmin": xmin, "xmax": xmax}))
    except OSError:
        pass


def run_gui(port, demo=False, speed=1.0):
    import tkinter as tk
    from tkinter import ttk
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure

    root = tk.Tk()
    root.title("ESP32 DAQ — HMI")
    st = {"link": None, "stamp": None, "saved_n": -1}
    ERR = "#b00020"

    bar = ttk.Frame(root, padding=6)
    bar.pack(fill="x")
    cb = ttk.Combobox(bar, width=24, values=serial_ports())
    cb.pack(side="left")
    if demo:
        cb.set("simulation (no ESP32)")
    elif port:
        cb.set(port)
    elif cb["values"]:
        cb.current(0)
    v_rx, v_rth = tk.StringVar(value="0.5"), tk.StringVar(value="1.0")
    xmin0, xmax0 = load_config()
    v_xmin, v_xmax = tk.StringVar(value=f"{xmin0:g}"), tk.StringVar(value=f"{xmax0:g}")
    lbl = ttk.Label(bar, text="disconnected", width=64)
    bar2 = ttk.Frame(root, padding=(6, 0, 6, 6))
    bar2.pack(fill="x")
    lbl_read = ttk.Label(bar2, text="", width=48)

    def apply_x():
        """sends xmin/xmax (V, channel 2 voltage) to the firmware, which normalizes x to [-1, 1]"""
        k = st["link"]
        if not k:
            lbl.config(text="connect the port first", foreground=ERR)
            return False
        try:
            a, b = float(v_xmin.get()), float(v_xmax.get())
        except ValueError:
            lbl.config(text="invalid xmin/xmax", foreground=ERR)
            return False
        if b - a <= 0.5:
            lbl.config(text="xmax must be greater than xmin (minimum difference of 0.5 V)", foreground=ERR)
            return False
        k.send(f"X{int(round(a * 1000))},{int(round(b * 1000))}")
        save_config(a, b)
        return True

    def read_now():
        if st["link"]:
            st["link"].reading = None
            st["link"].send("R")

    def use_as(var):
        rd = st["link"].reading if st["link"] else None
        if rd and "v2" in rd:
            var.set(f"{rd['v2']:.3f}")
        else:
            lbl.config(text="click “Read” first (with the ball at the end)", foreground=ERR)

    def connect():
        if st["link"]:
            st["link"].close()
            st["link"] = None
        try:
            st["link"] = DemoLink(speed=speed) if demo else Link(cb.get())
        except Exception as e:                                  # port missing / busy
            lbl.config(text=f"error: {e}", foreground=ERR)
            return
        time.sleep(0.3)
        v_rx.set(f"{st['link'].rx:g}")
        v_rth.set(f"{st['link'].rth:g}")
        lbl.config(text=f"connected — mode {st['link'].mode} ({MODES.get(st['link'].mode, '?')})", foreground="")
        apply_x()

    def start():
        k = st["link"]
        if not k:
            lbl.config(text="connect the port first", foreground=ERR)
            return
        if not apply_x():
            return
        try:
            k.send(f"A{int(round(float(v_rx.get()) * 1000))}")
            k.send(f"H{int(round(float(v_rth.get()) * 1000))}")
        except ValueError:
            lbl.config(text="invalid value", foreground=ERR)
            return
        st["stamp"] = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        st["saved_n"] = -1
        k.send("G")

    def stop():
        if st["link"]:
            st["link"].send("S")

    def save_now():
        k = st["link"]
        if not k or st["stamp"] is None:
            return
        d = k.data()
        if len(d) == 0:
            return
        msg = save(d, k.mode, st["stamp"])
        st["saved_n"] = len(d)
        lbl.config(text="saved: " + msg, foreground="")

    ttk.Button(bar, text="Connect", command=connect).pack(side="left", padx=4)
    ttk.Label(bar, text="  r_x step").pack(side="left")
    ttk.Entry(bar, textvariable=v_rx, width=6).pack(side="left")
    ttk.Label(bar, text="  r_θ step [V]").pack(side="left")
    ttk.Entry(bar, textvariable=v_rth, width=6).pack(side="left")
    ttk.Button(bar, text="Start", command=start).pack(side="left", padx=8)
    ttk.Button(bar, text="Stop", command=stop).pack(side="left")
    ttk.Button(bar, text="Save", command=save_now).pack(side="left", padx=4)
    lbl.pack(side="left", padx=10)

    ttk.Label(bar2, text="x normalization (channel 2 voltage):  xmin [V]").pack(side="left")
    ttk.Entry(bar2, textvariable=v_xmin, width=7).pack(side="left")
    ttk.Label(bar2, text="  xmax [V]").pack(side="left")
    ttk.Entry(bar2, textvariable=v_xmax, width=7).pack(side="left")
    ttk.Button(bar2, text="Apply", command=apply_x).pack(side="left", padx=6)
    ttk.Button(bar2, text="Read", command=read_now).pack(side="left")
    ttk.Button(bar2, text="Read → xmin", command=lambda: use_as(v_xmin)).pack(side="left", padx=2)
    ttk.Button(bar2, text="Read → xmax", command=lambda: use_as(v_xmax)).pack(side="left")
    lbl_read.pack(side="left", padx=10)

    fig = Figure(figsize=(8.5, 6.2), dpi=100)
    ax = fig.subplots(3, 1, sharex=True)
    ln = {}
    spec = [(0, "r_x", "r_x", "#999999", "--"), (0, "x", "x (ball)", "#0072B2", "-"),
            (1, "r_theta", "r_θ", "#999999", "--"), (1, "theta", "θ", "#D55E00", "-"),
            (2, "u", "u", "#009E73", "-")]
    for i, key, name, color, ls in spec:
        ln[key], = ax[i].plot([], [], color=color, ls=ls, lw=1.8, label=name)
    for a, yl in zip(ax, ["x (normalized)", "angle [V]", "u [V]"]):
        a.set_ylabel(yl)
        a.grid(alpha=0.3)
        a.legend(loc="upper left", ncol=2)
    ax[2].set_xlabel("t [s]")
    fig.tight_layout()
    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.get_tk_widget().pack(fill="both", expand=True)

    def tick():
        k = st["link"]
        if k:
            d = k.data()
            if len(d):
                for key, col in (("r_x", 2), ("x", 4), ("r_theta", 3), ("theta", 5), ("u", 6)):
                    ln[key].set_data(d[:, 1], d[:, col])
                for a in ax:
                    a.set_xlim(0, max(k.t_end, 1.0))
                    a.relim()
                    a.autoscale_view(scalex=False)
                canvas.draw_idle()
            if k.reading:
                rd = k.reading
                lbl_read.config(text=f"θ = {rd['theta']:.3f} V   v2 = {rd['v2']:.3f} V   x = {rd['x']:.3f}")
            if k.running:
                lbl.config(text=f"running… t = {d[-1, 1]:.2f} s" if len(d) else "running…", foreground="")
            elif k.finished and st["saved_n"] != len(d) and len(d):
                save_now()
                if k.reason == "theta":
                    lbl.config(text="SAFETY STOP: |θ| above the limit — " + lbl.cget("text"), foreground=ERR)
        root.after(100, tick)

    def close_window(_=None):
        if st["link"]:
            st["link"].close()
        root.destroy()

    root.bind("<Escape>", lambda e: stop())
    root.protocol("WM_DELETE_WINDOW", close_window)
    if port or demo:
        connect()
    tick()
    root.mainloop()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port")
    ap.add_argument("--demo", action="store_true", help="no ESP32: simulated signals")
    ap.add_argument("--speed", type=float, default=1.0, help="simulation speed (--demo)")
    ap.add_argument("--selftest", action="store_true", help="no window: one run, saves it and prints a summary")
    ap.add_argument("--rx", type=float, default=0.5)
    ap.add_argument("--rth", type=float, default=1.0)
    a = ap.parse_args()
    if a.selftest:
        port = a.port or (serial_ports() or [None])[0]
        if not port:
            sys.exit("no serial port found (use --port)")
        link = Link(port)
        try:
            sys.exit(run_selftest(link, a.rx, a.rth))
        finally:
            link.close()
    run_gui(a.port, a.demo, a.speed)


if __name__ == "__main__":
    main()
