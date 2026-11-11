"""Generates docs/build.html (bill of materials, English/Portuguese).
Usage: python tools/gen_build_page.py   (writes docs/build.html)"""
import html
import pathlib

OUT = pathlib.Path(__file__).resolve().parent.parent / "docs" / "build.html"


def L(en, pt):
    """A bilingual fragment: both languages in the page, one visible at a time."""
    return f'<span class="en">{en}</span><span class="pt">{pt}</span>'


def LB(en, pt):
    """Block-level bilingual fragment."""
    return f'<div class="en">{en}</div><div class="pt">{pt}</div>'


# ---------------------------------------------------------------- bill of materials
# (qty, part, value, references, note-en, note-pt)
BOM_C = [
    (2, "Resistor 1/4 W", "2 kΩ", "Rl1, Rl2", "test loads of the supply", "cargas de teste da fonte"),
    (2, "Ceramic capacitor", "100 nF", "Cv3, Cw3", "no polarity", "sem polaridade"),
    (4, "Electrolytic capacitor", "10 µF / 25 V", "Cv1, Cv2, Cw1, Cw2", "polarity: follow the + printed on the board (on the negative rail the + goes to GND, the board already shows it)", "polaridade: siga o + impresso na placa (na trilha negativa o + vai ao GND, a placa já mostra)"),
    (1, "Regulator L78L15 (TO-92)", "+15 V", "U3", "flat face matches the silkscreen; pinout: OUT | GND | IN", "face plana igual à serigrafia; pinagem: OUT | GND | IN"),
    (1, "Regulator L79L15 (TO-92)", "−15 V", "U4", "flat face matches the silkscreen; pinout: GND | IN | OUT", "face plana igual à serigrafia; pinagem: GND | IN | OUT"),
    (1, "Screw terminal 5.08 mm, 3 poles", "KRE / KF301", "J3", "+15 V, GND, −15 V (to board A/B); wire entry towards the board edge", "+15 V, GND, −15 V (para a placa A/B); entrada do fio voltada para a borda"),
    (1, "Screw terminal 5.08 mm, 2 poles", "KRE / KF301", "JP", "+5 V and GND from the charger; wire entry towards the board edge", "+5 V e GND do carregador; entrada do fio voltada para a borda"),
    (2, "Male pin header 1×4, 2.54 mm", "", "MT, LM", "short wires to the MT3608 and LM2596 modules", "fios curtos para os módulos MT3608 e LM2596"),
    (3, "Test point / pin", "", "TPp, TPg, TPn", "+15 V, GND, −15 V", "+15 V, GND, −15 V"),
]
BOM_AB = [
    (4, "Resistor 1/4 W", "10 kΩ", "Rs, Rs2, Rp1, Rp2", "", ""),
    (4, "Resistor 1/4 W", "20 kΩ", "R2, R3, R22, R32", "", ""),
    (4, "Resistor 1/4 W", "100 kΩ", "R1, R12, Rpd, Rpu", "", ""),
    (3, "Resistor 1/4 W", "1 kΩ", "Ro, Ro2, Rb", "", ""),
    (1, "Resistor 1/4 W", "2.2 kΩ", "Rf", "", ""),
    (1, "Resistor 1/4 W", "680 Ω", "Ra", "", ""),
    (1, "Resistor 1/4 W", "47 Ω", "Rx", "output series resistor", "resistor em série da saída"),
    (4, "Schottky diode BAT81 (DO-35)", "", "D1, D2, D3, D4", "polarity: the stripe is the cathode and goes to the side marked K", "polaridade: a faixa é o catodo e vai para o lado marcado K"),
    (7, "Ceramic capacitor", "100 nF", "Cd, Cd2, Cd3, Co, Co2, Cp1, Cp2", "no polarity", "sem polaridade"),
    (2, "Electrolytic capacitor", "10 µF / 25 V", "C+, C−", "polarity: follow the + printed on the board (C− sits on the −15 V rail: its + goes to GND, the board already shows it)", "polaridade: siga o + impresso na placa (C− fica na trilha de −15 V: o + vai ao GND, a placa já mostra)"),
    (1, "DIP-8 socket + MCP6002-I/P", "", "U1", "socket notch matches the silkscreen; insert the chip only after the supply test", "o entalhe do soquete é o da serigrafia; coloque o CI só depois do teste da fonte"),
    (1, "DIP-8 socket + TL072", "", "U2", "same as U1", "igual ao U1"),
    (2, "Female socket strip 1×15, 2.54 mm", "", "J4, J5", "for the ESP32 DevKit (30 pins); see the tip on alignment", "para o ESP32 DevKit (30 pinos); veja a dica de alinhamento"),
    (1, "Screw terminal 5.08 mm, 4 poles", "KRE / KF301", "J1", "VIN1, VIN2, VOUT, GND; wire entry towards the board edge", "VIN1, VIN2, VOUT, GND; entrada do fio voltada para a borda"),
    (1, "Screw terminal 5.08 mm, 3 poles", "KRE / KF301", "J3", "+15 V, GND, −15 V (from board C)", "+15 V, GND, −15 V (vindos da placa C)"),
]
EXTRA = [
    ("ESP32 DevKit, 30 pins", 1, "plugs into J4 and J5; its VIN pin is never connected", "encaixa em J4 e J5; o pino VIN dele nunca é ligado"),
    ("Module MT3608 (step-up)", 1, "adjusted to +17.5 V", "ajustado em +17,5 V"),
    ("Module LM2596 adjustable (4 terminals: IN+, IN−, OUT+, OUT−)", 1, "used as inverter, adjusted to −17.5 V", "usado como inversor, ajustado em −17,5 V"),
    ("5 V wall charger, ≥ 1 A, with the USB cable cut", 1, "red = +5 V, black = GND", "vermelho = +5 V, preto = GND"),
    ("USB cable for the ESP32", 1, "power and serial", "alimentação e serial"),
    ("Flexible wire", "—", "C → A/B (3 wires) and modules → C (8 short wires of ≈ 10 cm)", "C → A/B (3 fios) e módulos → C (8 fios curtos de ≈ 10 cm)"),
    ("M3 standoffs 6 mm + M3 screws", "8 + 8", "4 holes on each board", "4 furos em cada placa"),
]
COLORS = [("47 Ω", "yellow · violet · black · gold", "amarelo · violeta · preto · dourado"),
          ("680 Ω", "blue · grey · brown · gold", "azul · cinza · marrom · dourado"),
          ("1 kΩ", "brown · black · red · gold", "marrom · preto · vermelho · dourado"),
          ("2 kΩ", "red · black · red · gold", "vermelho · preto · vermelho · dourado"),
          ("2.2 kΩ", "red · red · red · gold", "vermelho · vermelho · vermelho · dourado"),
          ("10 kΩ", "brown · black · orange · gold", "marrom · preto · laranja · dourado"),
          ("20 kΩ", "red · black · orange · gold", "vermelho · preto · laranja · dourado"),
          ("100 kΩ", "brown · black · yellow · gold", "marrom · preto · amarelo · dourado")]


PT_NAMES = {
    "Resistor 1/4 W": "Resistor 1/4 W", "Ceramic capacitor": "Capacitor cerâmico", "Electrolytic capacitor": "Capacitor eletrolítico",
    "Regulator L78L15 (TO-92)": "Regulador L78L15 (TO-92)", "Regulator L79L15 (TO-92)": "Regulador L79L15 (TO-92)",
    "Screw terminal 5.08 mm, 3 poles": "Borne de parafuso 5,08 mm, 3 polos", "Screw terminal 5.08 mm, 2 poles": "Borne de parafuso 5,08 mm, 2 polos",
    "Screw terminal 5.08 mm, 4 poles": "Borne de parafuso 5,08 mm, 4 polos", "Male pin header 1×4, 2.54 mm": "Barra de pinos macho 1×4, 2,54 mm",
    "Test point / pin": "Ponto de teste / pino", "Schottky diode BAT81 (DO-35)": "Diodo Schottky BAT81 (DO-35)",
    "DIP-8 socket + MCP6002-I/P": "Soquete DIP-8 + MCP6002-I/P", "DIP-8 socket + TL072": "Soquete DIP-8 + TL072",
    "Female socket strip 1×15, 2.54 mm": "Barra de soquetes fêmea 1×15, 2,54 mm",
    "ESP32 DevKit, 30 pins": "ESP32 DevKit, 30 pinos", "Module MT3608 (step-up)": "Módulo MT3608 (step-up)",
    "Module LM2596 adjustable (4 terminals: IN+, IN−, OUT+, OUT−)": "Módulo LM2596 ajustável (4 terminais: IN+, IN−, OUT+, OUT−)",
    "5 V wall charger, ≥ 1 A, with the USB cable cut": "Carregador de parede de 5 V, ≥ 1 A, com o cabo USB cortado",
    "USB cable for the ESP32": "Cabo USB do ESP32", "Flexible wire": "Fio flexível", "M3 standoffs 6 mm + M3 screws": "Espaçadores M3 de 6 mm + parafusos M3",
}


def nm(en):
    return L(html.escape(en), html.escape(PT_NAMES.get(en, en)))


def bom_table(rows):
    out = ['<div class="table-container"><table class="table is-striped is-fullwidth bom"><thead><tr>',
           f'<th class="ok">✓</th><th class="num">{L("Qty", "Qtd")}</th><th>{L("Part", "Peça")}</th><th>{L("Value", "Valor")}</th><th>{L("References", "Referências")}</th><th>{L("Notes", "Observações")}</th></tr></thead><tbody>']
    for q, part, val, refs, ne, np_ in rows:
        note = L(html.escape(ne), html.escape(np_)) if ne else ""
        out.append(f'<tr><td class="ok"><input type="checkbox" aria-label="done"></td><td class="num">{q}</td><td>{nm(part)}</td>'
                   f'<td class="num">{html.escape(val)}</td><td><code>{html.escape(refs)}</code></td><td>{note}</td></tr>')
    out.append('</tbody></table></div>')
    return "\n".join(out)


def extra_table():
    out = [f'<div class="table-container"><table class="table is-striped is-fullwidth bom"><thead><tr><th class="ok">✓</th><th>{L("Item", "Item")}</th><th class="num">{L("Qty", "Qtd")}</th><th>{L("Notes", "Observações")}</th></tr></thead><tbody>']
    for item, q, ne, np_ in EXTRA:
        out.append(f'<tr><td class="ok"><input type="checkbox" aria-label="done"></td><td>{nm(item)}</td><td class="num">{q}</td><td>{L(html.escape(ne), html.escape(np_))}</td></tr>')
    out.append('</tbody></table></div>')
    return "\n".join(out)


def colors_table():
    out = [f'<div class="table-container"><table class="table is-striped"><thead><tr><th>{L("Value", "Valor")}</th><th>{L("4-band code (5 %)", "Código de 4 faixas (5 %)")}</th></tr></thead><tbody>']
    for v, en, pt in COLORS:
        out.append(f'<tr><td class="num">{v}</td><td>{L(en, pt)}</td></tr>')
    out.append('</tbody></table></div>')
    return "\n".join(out)


def steps(items):
    return '<ol class="steps">' + "".join(f"<li>{L(en, pt)}</li>" for en, pt in items) + "</ol>"


NAV = """<nav class="navbar" role="navigation" aria-label="main navigation">
  <div class="navbar-brand">
    <a class="navbar-item" href="./index.html"><strong>ESP32 DAQ</strong></a>
    <a role="button" class="navbar-burger" aria-label="menu" aria-expanded="false">
      <span aria-hidden="true"></span><span aria-hidden="true"></span><span aria-hidden="true"></span>
    </a>
  </div>
  <div class="navbar-menu">
    <div class="navbar-start" style="flex-grow: 1; justify-content: center;">
      <a class="navbar-item" href="#bom">""" + L("Bill of materials", "Lista de componentes") + """</a>
    </div>
    <div class="navbar-end">
      <div class="navbar-item"><div class="buttons has-addons langsw">
        <button class="button is-small" data-set-lang="en">EN</button><button class="button is-small" data-set-lang="pt">PT</button>
      </div></div>
    </div>
  </div>
</nav>"""

HEAD = """<!DOCTYPE html>
<html lang="en" data-lang="en">
<head>
  <meta charset="utf-8">
  <meta name="description" content="ESP32 DAQ: bill of materials for boards A/B and C.">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ESP32 DAQ: bill of materials</title>
  <link href="https://fonts.googleapis.com/css?family=Google+Sans|Noto+Sans|Castoro" rel="stylesheet">
  <link rel="stylesheet" href="./static/css/bulma.min.css">
  <link rel="stylesheet" href="./static/css/index.css">
  <link rel="stylesheet" href="./static/css/daq.css">
  <link rel="icon" href="./static/img/favicon.svg">
  <style>
    html[data-lang="en"] .pt { display: none !important; }
    html[data-lang="pt"] .en { display: none !important; }
    .langsw .button.is-active-lang { background: var(--azul); color: #fff; border-color: var(--azul); }
    table.bom td.ok, table.bom th.ok { width: 2.2rem; text-align: center; }
    table.bom code { white-space: normal; }
    ol.steps { margin-left: 1.4rem; } ol.steps li { margin: .5rem 0; }
    .warn { border-left: 4px solid #c0392b; background: #fdf1ef; padding: .8rem 1rem; border-radius: 0 8px 8px 0; margin: 1.2rem 0; }
    .tools { columns: 2; column-gap: 2rem; } @media (max-width: 768px) { .tools { columns: 1; } }
    @media print { .navbar, footer { display: none; } }
  </style>
  <script defer src="./static/js/fontawesome.all.min.js"></script>
  <script>
    (function () {
      var lang = 'en';
      try { lang = localStorage.getItem('daq-lang') || ((navigator.language || '').toLowerCase().indexOf('pt') === 0 ? 'pt' : 'en'); } catch (e) {}
      function apply(l) {
        document.documentElement.setAttribute('data-lang', l); document.documentElement.lang = l;
        document.querySelectorAll('[data-set-lang]').forEach(function (b) { b.classList.toggle('is-active-lang', b.getAttribute('data-set-lang') === l); });
      }
      document.documentElement.setAttribute('data-lang', lang);
      document.addEventListener('DOMContentLoaded', function () {
        apply(lang);
        document.querySelectorAll('[data-set-lang]').forEach(function (b) {
          b.addEventListener('click', function () { lang = b.getAttribute('data-set-lang'); apply(lang); try { localStorage.setItem('daq-lang', lang); } catch (e) {} });
        });
        var bg = document.querySelector('.navbar-burger'), m = document.querySelector('.navbar-menu');
        bg.addEventListener('click', function () { bg.classList.toggle('is-active'); m.classList.toggle('is-active'); });
        m.querySelectorAll('a.navbar-item').forEach(function (a) { a.addEventListener('click', function () { bg.classList.remove('is-active'); m.classList.remove('is-active'); }); });
      });
    })();
  </script>
</head>
<body>
"""


def build():
    p = []
    p.append(HEAD + NAV)
    p.append(f"""
<section class="hero" id="top"><div class="hero-body"><div class="container is-max-desktop has-text-centered">
  <h1 class="title is-2 publication-title">{L("Bill of materials", "Lista de componentes")}</h1>
  <p class="subtitle is-5">{L("Parts of boards A/B and C", "Peças das placas A/B e C")}</p>
  <p><a class="button is-rounded is-dark" href="./index.html">{L("← Back to the project page", "← Voltar à página do projeto")}</a></p>
</div></div></section>

<section class="section" id="bom"><div class="container is-max-desktop"><div class="content">
  <h2 class="title is-3 section-title has-text-centered">{L("Bill of materials", "Lista de componentes")}</h2>
  <h3>{L("Board C: ±15 V supply (48 × 52 mm)", "Placa C: fonte de ±15 V (48 × 52 mm)")}</h3>
  <figure class="fig w85"><img src="./static/img/asm_c_top.png" alt="Board C, top view with component labels"><figcaption>{L("Board C, top view: each part has its reference printed next to it.", "Placa C, vista de cima: cada peça tem a sua referência impressa ao lado.")}</figcaption></figure>
  {bom_table(BOM_C)}
  <h3>{L("Board A/B: inputs, ESP32 and output (74 × 72 mm)", "Placa A/B: entradas, ESP32 e saída (74 × 72 mm)")}</h3>
  <figure class="fig w85"><img src="./static/img/asm_ab_top.png" alt="Board A/B, top view with component labels"><figcaption>{L("Board A/B, top view. The outline in the middle is where the ESP32 DevKit sits (USB to the right).", "Placa A/B, vista de cima. O retângulo no meio é o lugar do ESP32 DevKit (USB para a direita).")}</figcaption></figure>
  {bom_table(BOM_AB)}
  <h3>{L("Other parts (not on the boards)", "Outros itens (fora das placas)")}</h3>
  {extra_table()}
  <h3>{L("Resistor colour codes", "Código de cores dos resistores")}</h3>
  {colors_table()}
</div></div></section>

<section class="section"><div class="container is-max-desktop">
  <p class="has-text-centered"><a class="button is-rounded is-dark" href="https://github.com/helonayala/analog_circuits"><span class="icon"><i class="fas fa-microchip"></i></span><span>{L("Full hardware design (analog_circuits)", "Projeto completo do hardware (analog_circuits)")}</span></a></p>
</div></section>

<footer class="footer"><div class="container"><div class="content has-text-centered"><p>
  {L("Part of the ", "Parte da ")}<a href="./index.html">ESP32 DAQ</a>{L(" project.", ".")}
</p></div></div></footer>
</body>
</html>
""")
    OUT.write_text("\n".join(p), encoding="utf-8")
    print("escrito:", OUT)


if __name__ == "__main__":
    build()
