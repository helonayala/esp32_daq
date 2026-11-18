"""Gera docs/static/pdf/mapa_montagem.pdf: mapa de montagem em escala 1:1 (e 2x) das placas C e A/B.
A placa impressa não tem serigrafia; este PDF faz o papel dela.
Uso:  python tools/gen_assembly_map.py   (precisa de pdflatex; ver o comando de compilação no fim)"""
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gen_build_page import BOM_AB, BOM_C, PT_NAMES  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
PDFDIR = ROOT / "docs" / "static" / "pdf"
BUILD = ROOT / "build"

# tamanho das vistas de cima em mm (página dos PDFs = tamanho da placa)
SIZE = {"pcb_c_top.pdf": (48.72, 52.09), "pcb_ab_top.pdf": (74.09, 72.08)}


def tex_escape(s):
    for a, b in (("&", r"\&"), ("%", r"\%"), ("#", r"\#"), ("_", r"\_"), ("µ", r"$\mu$"), ("Ω", r"$\Omega$"),
                 ("±", r"$\pm$"), ("−", "-"), ("→", r"$\rightarrow$"), ("≥", r"$\geq$"), ("≈", r"$\approx$"), ("×", r"$\times$")):
        s = s.replace(a, b)
    return s


def table(rows):
    out = [r"\begin{longtable}{@{}p{1.4cm}p{4.6cm}p{2.2cm}p{7.4cm}@{}}", r"\toprule Ref. & Peça & Valor & Como colocar \\ \midrule \endhead"]
    for q, part, val, refs, ne, np_ in rows:
        out.append(f"{tex_escape(refs)} & {tex_escape(PT_NAMES.get(part, part))} ({q}) & {tex_escape(val)} & {tex_escape(np_)} \\\\")
    out.append(r"\bottomrule\end{longtable}")
    return "\n".join(out)


def figs(name, label, stack=False):
    w, h = SIZE[name]
    one = (rf"\begin{{minipage}}[t]{{{w + 6:.1f}mm}}\centering\textbf{{1:1}}\\[1mm]"
           rf"\fboxsep=0pt\fbox{{\includegraphics[width={w}mm]{{{name}}}}}\end{{minipage}}")
    two = (rf"\begin{{minipage}}[t]{{{2 * w + 4:.1f}mm}}\centering\textbf{{2$\times$ ({label})}}\\[1mm]"
           rf"\fboxsep=0pt\fbox{{\includegraphics[width={2 * w}mm]{{{name}}}}}\end{{minipage}}")
    if stack:
        return rf"\noindent\hfill{one}\hfill{two}\hfill\null" if (w + 6 + 2 * w + 4) < 185 else rf"\begin{{center}}{two}\\[3mm]{one}\end{{center}}"
    return rf"\noindent{one}\hfill{two}"


TEX = r"""\documentclass[10pt,a4paper]{article}
\usepackage[utf8]{inputenc}\usepackage[T1]{fontenc}\usepackage[brazilian]{babel}
\usepackage[margin=10mm]{geometry}\usepackage{graphicx,booktabs,longtable,array,xcolor}
\pagestyle{empty}\setlength{\parindent}{0pt}
\begin{document}
\section*{Mapa de montagem (escala 1:1)}
\textbf{Imprima em A4 a 100\,\% (``tamanho real'', sem ajustar à página).} A placa impressa \textbf{não tem serigrafia}: este mapa faz o papel dela.
Coloque a placa sobre a figura 1:1 para conferir o tamanho; a figura 2$\times$ é para ler os nomes. Os desenhos mostram o lado de \textbf{cima}, onde vão os componentes.

\vspace{2mm}
\begin{tabular}{@{}p{3.6cm}p{14cm}@{}}
\toprule \textbf{O que procurar} & \textbf{Como colocar} \\ \midrule
Ilha \textbf{quadrada} & é o \textbf{pino 1} (soquetes de CI e cabeçotes). \\
Marca \textbf{+} & eletrolíticos: a perna longa (+) vai no furo do +. \\
Letra \textbf{K} / barra & diodos BAT81: a faixa do corpo (catodo) vai para o lado do K. \\
Entalhe do contorno & soquete DIP-8: o entalhe do soquete fica do lado do entalhe do desenho. \\
Lado reto do contorno & reguladores TO-92: a face plana do componente fica do lado reto. \\
Bornes de parafuso & a entrada do fio vai para a \textbf{borda da placa}; os nomes dos pinos estão escritos junto ao borne. \\
\bottomrule\end{tabular}

\vspace{4mm}
\section*{Placa C: fonte de $\pm$15\,V (48 $\times$ 52\,mm)}
""" + figs("pcb_c_top.pdf", "placa C") + r"""

\vspace{3mm}
\textbf{Bornes da placa C:} $J3$ (embaixo): +15\,V, GND, $-$15\,V (esquerda para direita). $JP$ (em cima): \textbf{GND à esquerda e +5\,V à direita} (a tensão da fonte: 5\,V de carregador de celular, ou 8 a 12\,V).
Cabeçotes $MT$ e $LM$ (colunas no alto): pino 1 em cima; $MT$ = VIN+, VIN$-$, VOUT+, VOUT$-$; $LM$ = IN+, IN$-$, OUT+, OUT$-$. Pontos de teste embaixo: +15\,V, GND, $-$15\,V.
Os reguladores U3 e U4 \textbf{só depois} de ajustar os módulos.

\vspace{2mm}
""" + "@TABLE_C@" + r"""
\newpage
\section*{Placa A/B: entradas, ESP32 e saída (74 $\times$ 72\,mm)}
""" + figs("pcb_ab_top.pdf", "placa A/B", stack=True) + r"""

\vspace{3mm}
\textbf{Bornes da placa A/B:} $J1$ (embaixo, esquerda): VIN1, VIN2, VOUT, GND. $J3$ (embaixo, direita): +15\,V, GND, $-$15\,V (vêm da placa C, mesma ordem).
O contorno grande no meio é o lugar do ESP32 DevKit, com o USB para a \textbf{direita}. O pino VIN do ESP32 \textbf{não é usado}.

\vspace{2mm}
""" + "@TABLE_AB@" + r"""
\end{document}
"""


def main():
    BUILD.mkdir(exist_ok=True)
    tex = TEX.replace("@TABLE_C@", table(BOM_C)).replace("@TABLE_AB@", table(BOM_AB))
    (BUILD / "mapa_montagem.tex").write_text(tex, encoding="utf-8")
    for f in ("pcb_c_top.pdf", "pcb_ab_top.pdf"):
        (BUILD / f).write_bytes((PDFDIR / f).read_bytes())
    print("escrito:", BUILD / "mapa_montagem.tex")
    print("compile com: cd build && latexmk -pdf -interaction=nonstopmode mapa_montagem.tex && cp mapa_montagem.pdf ../docs/static/pdf/")


if __name__ == "__main__":
    main()
