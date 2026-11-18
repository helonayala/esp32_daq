"""General block diagram of the ESP32 +-10 V interface (docs/static/img/block_diagram.svg).

Hand-written SVG (no dependencies).  Usage:  python tools/gen_figs.py
"""
import pathlib

OUT = pathlib.Path(__file__).resolve().parent.parent / "docs" / "static" / "img"
INK, BLUE, ORANGE = "#1b1b1b", "#0b5394", "#b45f06"


class Svg:
    def __init__(self, w, h, ox=0):
        self.w, self.h, self.ox, self.e = w, h, ox, []

    def add(self, s):
        self.e.append(s)

    def line(self, pts, color=INK, wd=2):
        self.add('<polyline points="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linejoin="round"/>'
                 % (" ".join(f"{x},{y}" for x, y in pts), color, wd))

    def text(self, x, y, s, anchor="middle", size=17, color=INK, weight="normal"):
        for i, ln in enumerate(s.split("\n")):
            self.add(f'<text x="{x}" y="{y + i * (size + 3)}" text-anchor="{anchor}" font-size="{size}" '
                     f'fill="{color}" font-weight="{weight}">{ln}</text>')

    def save(self, name, title):
        body = "\n".join(self.e)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-self.ox} 0 {self.w} {self.h}" '
               f'font-family="Helvetica, Arial, sans-serif" role="img"><title>{title}</title>'
               f'<rect x="{-self.ox}" width="100%" height="100%" fill="white"/>\n{body}\n</svg>\n')
        (OUT / name).write_text(svg)


def blocos():
    """general block diagram of the interface: ESP32, output, inputs, supply and the bench (any +-10 V system)"""
    s = Svg(1010, 440, ox=70)
    GREEN = "#2a8550"
    def box(x, y, w, h, title, sub="", fill="white", color=INK):
        s.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{color}" stroke-width="2.5"/>')
        s.text(x + w / 2, y + 28, title, size=18, weight="bold", color=color)
        if sub:
            s.text(x + w / 2, y + 54, sub, size=15)
    def head(x, y, dx, dy, color):
        a = {(1, 0): [(x, y), (x - 12, y - 6), (x - 12, y + 6)], (-1, 0): [(x, y), (x + 12, y - 6), (x + 12, y + 6)],
             (0, 1): [(x, y), (x - 6, y - 12), (x + 6, y - 12)], (0, -1): [(x, y), (x - 6, y + 12), (x + 6, y + 12)]}[(dx, dy)]
        s.add('<polygon points="%s" fill="%s"/>' % (" ".join(f"{px},{py}" for px, py in a), color))
    # ESP32
    box(340, 50, 220, 290, "ESP32 DevKit", "3.3 V · 12-bit ADC\n12-bit PWM", "#e3f3e9", GREEN)
    for y, t in ((150, "D18 (PWM)"), (255, "D34 (A0)"), (315, "D35 (A1)")):
        s.text(352, y + 5, t, anchor="start", size=15)
    # supply, output, inputs
    box(20, 14, 250, 62, "±15 V supply", "generated from the 5 V", "#fbe9e7", "#b23a2f")
    box(20, 110, 250, 100, "Output", "PWM → 2 RC → TL072\nVo = 6.44·Vdac − 10.7 V", "#fdf0dc", ORANGE)
    box(20, 230, 250, 130, "2 inputs", "divider + level shift + clamps\n+ MCP6002 follower\n(±10 V → 0–3.3 V)", "#e6eefa", BLUE)
    s.line([(145, 76), (145, 102)], "#b23a2f"); head(145, 110, 0, 1, "#b23a2f")
    s.line([(-60, 45), (12, 45)], "#555"); head(18, 45, 1, 0, "#555")
    s.text(-60, 34, "5 V", anchor="start", size=15, color="#555", weight="bold")
    s.text(-60, 66, "charger", anchor="start", size=13, color="#555")
    # bench
    box(680, 60, 230, 280, "Bench / system", "any system with\n±10 V inputs and outputs", "#ececec", "#555")
    s.text(795, 160, "±10 V input\n(actuator)", size=15)
    s.text(795, 270, "±10 V outputs\n(sensors)", size=15)
    # PWM: ESP32 -> output
    s.line([(340, 150), (278, 150)], BLUE); head(272, 150, -1, 0, BLUE)
    s.text(300, 140, "PWM", size=14, color=BLUE)
    # VOUT: output -> bench (over the top)
    s.line([(270, 130), (305, 130), (305, 28), (795, 28), (795, 52)], ORANGE, 2.5); head(795, 60, 0, 1, ORANGE)
    s.text(545, 20, "VOUT (±10 V)", size=15, color=ORANGE, weight="bold")
    # sensors -> inputs (underneath)
    s.line([(795, 340), (795, 392), (145, 392), (145, 370)], GREEN, 2.5); head(145, 362, 0, -1, GREEN)
    s.text(470, 384, "sensors (±10 V) → VIN1, VIN2", size=15, color=GREEN, weight="bold")
    # inputs -> ESP32
    for y in (255, 315):
        s.line([(270, y), (326, y)], GREEN); head(338, y, 1, 0, GREEN)
    s.text(304, 245, "0–3.3 V", size=14, color=GREEN)
    s.text(470, 424, "Common GND: ESP32, board, supply and bench (single point)", size=15, color="#555")
    s.save("block_diagram.svg", "Block diagram: ESP32, output, inputs, ±15 V supply and bench")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    blocos()
    print("ok:", sorted(p.name for p in OUT.glob("*.svg")))
