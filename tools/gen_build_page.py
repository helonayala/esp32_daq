"""Generates docs/build.html (bill of materials + soldering guide, English/Portuguese).
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
      <a class="navbar-item" href="#solder">""" + L("Soldering", "Soldagem") + """</a>
      <a class="navbar-item" href="#test">""" + L("Tests", "Testes") + """</a>
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
  <meta name="description" content="ESP32 DAQ build guide: bill of materials and soldering instructions for boards A/B and C.">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ESP32 DAQ: build guide</title>
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
  <h1 class="title is-2 publication-title">{L("Build guide", "Guia de montagem")}</h1>
  <p class="subtitle is-5">{L("Bill of materials and soldering instructions for boards A/B and C", "Lista de componentes e instruções de soldagem das placas A/B e C")}</p>
  <p><a class="button is-rounded is-dark" href="./index.html">{L("← Back to the project page", "← Voltar à página do projeto")}</a></p>
</div></div></section>

<section class="section" id="overview"><div class="container is-max-desktop"><div class="content has-text-justified">
  <h2 class="title is-3 section-title has-text-centered">{L("Before you start", "Antes de começar")}</h2>
  {LB("<p>The interface is built on <strong>two double-sided boards</strong>: <strong>C</strong> (±15 V supply, 48 × 52 mm) and <strong>A/B</strong> (2 inputs, ESP32 sockets and output, 74 × 72 mm). All parts are through-hole and go on the <strong>top side</strong> (the side with the printed labels). Always build and test <strong>board C first</strong>, then A/B.</p>",
       "<p>A interface é montada em <strong>duas placas de dupla face</strong>: <strong>C</strong> (fonte de ±15 V, 48 × 52 mm) e <strong>A/B</strong> (2 entradas, soquetes do ESP32 e saída, 74 × 72 mm). Todas as peças são de furo passante e vão no <strong>lado de cima</strong> (o lado com os nomes impressos). Monte e teste sempre a <strong>placa C primeiro</strong> e depois a A/B.</p>")}
  <div class="warn">{LB("<strong>Plated holes.</strong> If the board was made without plated holes (no copper inside the holes), every pin that touches a trace on the <em>top</em> side must be soldered on <strong>both faces</strong>; otherwise the connection is open. When in doubt, solder both faces on all pins.",
       "<strong>Furos metalizados.</strong> Se a placa foi feita sem furo metalizado (sem cobre dentro dos furos), todo pino que encosta numa trilha do lado de <em>cima</em> precisa ser soldado nas <strong>duas faces</strong>; senão a ligação fica aberta. Na dúvida, solde as duas faces em todos os pinos.")}</div>
  <div class="warn">{LB("<strong>Never connect the VIN pin of the ESP32</strong> to anything, and never apply 5 V to a 3.3 V pin.",
       "<strong>Nunca ligue o pino VIN do ESP32</strong> a nada, e nunca aplique 5 V a um pino de 3,3 V.")}</div>

  <h3>{L("Tools and materials", "Ferramentas e materiais")}</h3>
  <ul class="tools">
    <li>{L("Soldering iron 25–40 W with a fine tip (adjustable ≈ 330–350 °C)", "Ferro de soldar de 25 a 40 W com ponta fina (regulável, ≈ 330–350 °C)")}</li>
    <li>{L("Leaded solder 0.8 mm (60/40 or 63/37) with flux core", "Solda com chumbo 0,8 mm (60/40 ou 63/37) com fluxo")}</li>
    <li>{L("Side cutters, tweezers", "Alicate de corte, pinça")}</li>
    <li>{L("Multimeter (continuity, ohms, DC volts)", "Multímetro (continuidade, ohms, tensão DC)")}</li>
    <li>{L("Desoldering wick or pump", "Malha ou bomba dessoldadora")}</li>
    <li>{L("Isopropyl alcohol and a small brush", "Álcool isopropílico e pincel")}</li>
    <li>{L("Magnifier, tape or a board holder", "Lupa, fita ou suporte para placa")}</li>
    <li>{L("Small flat screwdriver (terminal blocks)", "Chave de fenda pequena (bornes)")}</li>
  </ul>
</div></div></section>

<section class="section" id="bom"><div class="container is-max-desktop"><div class="content">
  <h2 class="title is-3 section-title has-text-centered">{L("Bill of materials", "Lista de componentes")}</h2>
  {LB("<p>Tick each line while you separate the parts. <strong>Measure every resistor with the multimeter</strong> before soldering (the stripes are hard to read); the 4-band codes below are for the 5 % parts, 1 % parts have 5 bands.</p>",
       "<p>Marque cada linha ao separar as peças. <strong>Meça cada resistor com o multímetro</strong> antes de soldar (as faixas são difíceis de ler); os códigos de 4 faixas abaixo valem para os de 5 %, os de 1 % têm 5 faixas.</p>")}
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

<section class="section" id="solder"><div class="container is-max-desktop"><div class="content">
  <h2 class="title is-3 section-title has-text-centered">{L("Soldering", "Soldagem")}</h2>

  <h3>{L("How to make a good joint", "Como fazer uma boa solda")}</h3>
  {steps([
      ("Heat <strong>the pad and the lead together</strong> with the tip for about 1–2 seconds.", "Aqueça <strong>a ilha e o terminal juntos</strong> com a ponta por cerca de 1 a 2 segundos."),
      ("Feed the solder to the joint (not to the iron tip) for 1–2 seconds, until it flows around the lead.", "Encoste a solda na junção (não na ponta do ferro) por 1 a 2 segundos, até ela escorrer em volta do terminal."),
      ("Remove the solder first, then the iron, and <strong>do not move</strong> the part for 2–3 seconds.", "Tire primeiro a solda e depois o ferro, e <strong>não mexa</strong> na peça por 2 a 3 segundos."),
      ("A good joint is shiny and shaped like a small cone. A dull, round blob is a cold joint: reheat it with a little fresh solder.", "Uma boa solda é brilhante e tem forma de pequeno cone. Uma bolinha opaca é solda fria: reaqueça com um pouco de solda nova."),
      ("Trim the leads flush with the joint after soldering. Look for solder bridges between neighbouring pads (use the wick to remove them).", "Corte os terminais rente à solda depois de soldar. Procure pontes de solda entre ilhas vizinhas (use a malha para tirá-las)."),
      ("Never solder an IC directly: the chips (MCP6002, TL072) go into sockets, and only after the supply test.", "Nunca solde um CI direto: os chips (MCP6002, TL072) vão em soquete, e só depois do teste da fonte."),
  ])}

  <h3>{L("Board C: assembly order", "Placa C: ordem de montagem")}</h3>
  {LB("<p>Solder the low parts first and the tall ones last, so the board lies flat on the table.</p>", "<p>Solde primeiro as peças baixas e por último as altas, para a placa ficar apoiada na mesa.</p>")}
  {steps([
      ("<strong>Resistors</strong> Rl1 and Rl2 (2 kΩ).", "<strong>Resistores</strong> Rl1 e Rl2 (2 kΩ)."),
      ("<strong>Ceramic capacitors</strong> Cv3 and Cw3 (100 nF).", "<strong>Capacitores cerâmicos</strong> Cv3 e Cw3 (100 nF)."),
      ("<strong>Test points</strong> TPp, TPg and TPn.", "<strong>Pontos de teste</strong> TPp, TPg e TPn."),
      ("<strong>Male pin headers</strong> MT and LM (long pins up, short pins into the board).", "<strong>Barras de pinos macho</strong> MT e LM (pino longo para cima, pino curto na placa)."),
      ("<strong>Electrolytic capacitors</strong> Cv1, Cv2, Cw1 and Cw2: long lead (+) in the hole marked +. The stripe on the can is the negative lead.", "<strong>Capacitores eletrolíticos</strong> Cv1, Cv2, Cw1 e Cw2: perna longa (+) no furo marcado com +. A faixa no corpo é o terminal negativo."),
      ("<strong>Screw terminals</strong> J3 and JP, with the wire entry towards the board edge. Solder one pin, check that the block sits flat and square, then solder the others.", "<strong>Bornes de parafuso</strong> J3 e JP, com a entrada do fio voltada para a borda da placa. Solde um pino, confira se o bloco está plano e alinhado e então solde os demais."),
      ("<strong>Do not solder the regulators U3 and U4 yet</strong>: first set the two modules (see the tests below).", "<strong>Ainda não solde os reguladores U3 e U4</strong>: primeiro ajuste os dois módulos (veja os testes abaixo)."),
  ])}
  {LB("<p><strong>Modules:</strong> solder about 10 cm of wire on each of the 4 terminals of the MT3608 and of the LM2596, and connect them to the headers pin by pin: <code>MT</code> = VIN+, VIN−, VOUT+, VOUT−; <code>LM</code> = IN+, IN−, OUT+, OUT− (pin 1 has the square pad). The LM2596 electrolytic capacitors must be at least 25 V (the input one sees about 22.5 V in this circuit; 35 V or more is best).</p>",
       "<p><strong>Módulos:</strong> solde cerca de 10 cm de fio em cada um dos 4 terminais do MT3608 e do LM2596 e ligue-os aos cabeçotes pino a pino: <code>MT</code> = VIN+, VIN−, VOUT+, VOUT−; <code>LM</code> = IN+, IN−, OUT+, OUT− (o pino 1 tem a ilha quadrada). Os capacitores eletrolíticos do LM2596 precisam ser de pelo menos 25 V (o de entrada vê cerca de 22,5 V neste circuito; 35 V ou mais é o ideal).</p>")}

  <h3>{L("Board A/B: assembly order", "Placa A/B: ordem de montagem")}</h3>
  {steps([
      ("<strong>Resistors</strong> (all 1/4 W): measure each one and match the reference printed on the board.", "<strong>Resistores</strong> (todos de 1/4 W): meça cada um e confira com a referência impressa na placa."),
      ("<strong>Diodes</strong> D1 to D4 (BAT81): the stripe (cathode) goes to the side marked K. They are small and sensitive to heat: solder quickly.", "<strong>Diodos</strong> D1 a D4 (BAT81): a faixa (catodo) vai para o lado marcado com K. São pequenos e sensíveis ao calor: solde rápido."),
      ("<strong>Ceramic capacitors</strong> (100 nF).", "<strong>Capacitores cerâmicos</strong> (100 nF)."),
      ("<strong>DIP-8 sockets</strong> U1 and U2, with the notch matching the silkscreen. Do not insert the chips yet.", "<strong>Soquetes DIP-8</strong> U1 e U2, com o entalhe como na serigrafia. Ainda não coloque os chips."),
      ("<strong>ESP32 sockets</strong> J4 and J5 (1 × 15 female strips). <em>Tip:</em> plug the strips into the ESP32 first, place the module on the board and solder one pin of each strip; check that everything sits straight and flat, then solder all the other pins. The module acts as a jig, so the spacing between the two rows is exactly right.", "<strong>Soquetes do ESP32</strong> J4 e J5 (barras fêmea 1 × 15). <em>Dica:</em> encaixe as barras no ESP32, apoie o módulo na placa e solde um pino de cada barra; confira se tudo está reto e plano e só então solde os demais pinos. O módulo funciona como gabarito, e o espaçamento entre as duas fileiras fica certo."),
      ("<strong>Electrolytic capacitors</strong> C+ and C−: long lead (+) in the hole marked +.", "<strong>Capacitores eletrolíticos</strong> C+ e C−: perna longa (+) no furo marcado com +."),
      ("<strong>Screw terminals</strong> J1 (4 poles) and J3 (3 poles), with the wire entry towards the board edge.", "<strong>Bornes de parafuso</strong> J1 (4 polos) e J3 (3 polos), com a entrada do fio voltada para a borda da placa."),
      ("Leave the chips <strong>out of the sockets</strong> and the ESP32 <strong>unplugged</strong> until the supply tests are done.", "Deixe os chips <strong>fora dos soquetes</strong> e o ESP32 <strong>desconectado</strong> até acabarem os testes da fonte."),
  ])}

  <h3>{L("Troubleshooting", "Problemas comuns")}</h3>
  <table class="table is-striped is-fullwidth"><thead><tr><th>{L("Problem", "Problema")}</th><th>{L("What to do", "O que fazer")}</th></tr></thead><tbody>
    <tr><td>{L("Solder bridge between two pads", "Ponte de solda entre duas ilhas")}</td><td>{L("Put the wick on the bridge, heat it and pull away. Check with the multimeter in continuity mode.", "Coloque a malha sobre a ponte, aqueça e puxe. Confira com o multímetro em continuidade.")}</td></tr>
    <tr><td>{L("Dull, grainy joint (cold joint)", "Solda opaca e áspera (solda fria)")}</td><td>{L("Reheat with a little fresh solder until it becomes shiny.", "Reaqueça com um pouco de solda nova até ficar brilhante.")}</td></tr>
    <tr><td>{L("Pad lifted from the board", "Ilha levantada da placa")}</td><td>{L("Do not keep heating. Ask for help: the pad can sometimes be reconnected with a short wire.", "Não continue aquecendo. Peça ajuda: às vezes dá para religar a ilha com um fio curto.")}</td></tr>
    <tr><td>{L("A part was placed in the wrong spot or polarity", "Peça no lugar errado ou com polaridade invertida")}</td><td>{L("Desolder with the pump or wick before powering the board. A reversed electrolytic capacitor can burst.", "Dessolde com a bomba ou a malha antes de ligar a placa. Um eletrolítico invertido pode estourar.")}</td></tr>
  </tbody></table>
</div></div></section>

<section class="section" id="test"><div class="container is-max-desktop"><div class="content">
  <h2 class="title is-3 section-title has-text-centered">{L("Tests", "Testes")}</h2>
  {LB("<p>Do the steps in order and <strong>one at a time</strong>. If anything gets hot, the voltage goes above 20 V or the ESP32 resets, disconnect the supply and look for the problem.</p>",
       "<p>Faça os passos em ordem e <strong>um de cada vez</strong>. Se algo esquentar, a tensão passar de 20 V ou o ESP32 reiniciar, desligue a alimentação e procure o problema.</p>")}

  <h3>{L("Board C", "Placa C")}</h3>
  {steps([
      ("<strong>Power off, regulators not soldered.</strong> With the multimeter in ohms: between the +15 V and GND test points the reading must be about 2 kΩ (Rl1) and between −15 V and GND about 2 kΩ (Rl2).", "<strong>Desligada, reguladores não soldados.</strong> Com o multímetro em ohms: entre o ponto de teste +15 V e GND a leitura deve ser de cerca de 2 kΩ (Rl1) e entre −15 V e GND cerca de 2 kΩ (Rl2)."),
      ("Wire the 5 V charger to <code>JP</code> (red = +5 V, black = GND), <strong>straight</strong> to the board (no series resistor and not through the ESP32 VIN pin).", "Ligue o carregador de 5 V em <code>JP</code> (vermelho = +5 V, preto = GND), <strong>direto</strong> na placa (sem resistor em série e sem passar pelo pino VIN do ESP32)."),
      ("<strong>LM2596 (inverter, −17.5 V):</strong> first turn its trimpot to the minimum. Power on and, with the multimeter on pin 2 of U4 (its input pad) against GND, turn the trimpot <strong>half a turn at a time</strong> until −17.5 V. The trimpot has end stops: turning without any change means it has reached the end. If the voltage goes beyond −20 V, switch off.", "<strong>LM2596 (inversor, −17,5 V):</strong> primeiro gire o trimpot dele até o mínimo. Ligue e, com o multímetro no pino 2 do U4 (a ilha de entrada) contra o GND, gire o trimpot <strong>meio giro por vez</strong> até −17,5 V. O trimpot tem fim de curso: girar sem mudar nada significa que chegou ao fim. Se a tensão passar de −20 V, desligue."),
      ("<strong>MT3608 (step-up, +17.5 V):</strong> measure on pin 3 of U3 (its input pad) against GND and adjust the trimpot until +17.5 V.", "<strong>MT3608 (step-up, +17,5 V):</strong> meça no pino 3 do U3 (a ilha de entrada) contra o GND e ajuste o trimpot até +17,5 V."),
      ("<strong>Power off</strong> and solder the regulators U3 (L78L15) and U4 (L79L15) with the flat face matching the silkscreen. Check the pinout of your batch in the datasheet (flat face towards you: L78L15 = OUT | GND | IN; L79L15 = GND | IN | OUT).", "<strong>Desligue</strong> e solde os reguladores U3 (L78L15) e U4 (L79L15) com a face plana como na serigrafia. Confira a pinagem do seu lote no datasheet (face plana para você: L78L15 = OUT | GND | IN; L79L15 = GND | IN | OUT)."),
      ("Power on and measure at the test points: <strong>+15 V = 15.0 ± 0.3 V</strong> and <strong>−15 V = −15.0 ± 0.3 V</strong>. The regulators must not get very hot.", "Ligue e meça nos pontos de teste: <strong>+15 V = 15,0 ± 0,3 V</strong> e <strong>−15 V = −15,0 ± 0,3 V</strong>. Os reguladores não devem esquentar muito."),
  ])}

  <h3>{L("Board A/B", "Placa A/B")}</h3>
  {steps([
      ("<strong>Everything off.</strong> Connect the three wires from <code>J3</code> of board C to <code>J3</code> of board A/B (+15 V, GND, −15 V, same order on both).", "<strong>Tudo desligado.</strong> Ligue os três fios do <code>J3</code> da placa C ao <code>J3</code> da placa A/B (+15 V, GND, −15 V, na mesma ordem nas duas)."),
      ("Power board C and check the ±15 V on the pins of the TL072 socket (U2): pin 8 = +15 V and pin 4 = −15 V, against GND (pin 5).", "Ligue a placa C e confira os ±15 V nos pinos do soquete do TL072 (U2): pino 8 = +15 V e pino 4 = −15 V, contra o GND (pino 5)."),
      ("<strong>Power off</strong>, insert the TL072 (U2) and the MCP6002 (U1) with the notch matching the socket, and plug the ESP32 (USB on the right).", "<strong>Desligue</strong>, coloque o TL072 (U2) e o MCP6002 (U1) com o entalhe como no soquete e encaixe o ESP32 (USB para a direita)."),
      ("Connect the USB to the computer and flash the firmware (see the <a href=\"./index.html#firmware\">project page</a>). In the HMI the command <code>V0</code> must give about 0 V at VOUT, and <code>V1000</code> / <code>V-1000</code> about +1 V / −1 V (measure VOUT against GND).", "Ligue a USB ao computador e grave o firmware (veja a <a href=\"./index.html#firmware\">página do projeto</a>). Na IHM o comando <code>V0</code> deve dar cerca de 0 V em VOUT, e <code>V1000</code> / <code>V-1000</code> cerca de +1 V / −1 V (meça VOUT contra o GND)."),
      ("<strong>Loop test:</strong> connect VOUT to VIN1 and VIN2 and apply steps from −10 V to +10 V in the HMI, checking VOUT with the multimeter: the readings must agree within about 0.4 % of the full scale (80 mV).", "<strong>Teste de laço:</strong> ligue VOUT em VIN1 e VIN2 e aplique degraus de −10 V a +10 V na IHM, conferindo VOUT com o multímetro: as leituras devem concordar com cerca de 0,4 % do fundo de escala (80 mV)."),
      ("Only then connect the bench: VIN1 to the sensor output, VOUT to the actuator input and GND to the common ground of the bench.", "Só então ligue a bancada: VIN1 na saída do sensor, VOUT na entrada do atuador e GND no terra comum da bancada."),
  ])}
  <div class="nota">{LB("The design was validated on a breadboard with the same circuit; the printed boards are the first build, so report any difference you notice.", "O projeto foi validado em protoboard com o mesmo circuito; as placas impressas são a primeira montagem, então avise qualquer diferença que notar.")}</div>
  <p class="has-text-centered"><a class="button is-rounded is-dark" href="https://github.com/helonayala/analog_circuits"><span class="icon"><i class="fas fa-microchip"></i></span><span>{L("Full hardware design (analog_circuits)", "Projeto completo do hardware (analog_circuits)")}</span></a></p>
</div></div></section>

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
