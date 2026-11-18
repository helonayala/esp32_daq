#!/usr/bin/env python3
"""Versão de terminal do scope.py (sem janela): gera uma forma de onda em VOUT e mostra VIN1/VIN2 no texto.

Usa só os comandos do firmware R e V<mV> (a mesma Scope do scope.py). Ctrl+C (ou o fim da duração) zera a saída.

  python hmi/scope_cli.py --port /dev/cu.usbserial-53220061661                       (saída 0 V, só lê VIN1/VIN2)
  python hmi/scope_cli.py --port ... --shape DC --off 1.0                            (degrau DC de +1 V)
  python hmi/scope_cli.py --port ... --shape square --amp 2 --freq 0.5 --duration 20 (quadrada de ±2 V, 0,5 Hz, 20 s)
Formas: off, DC, square, triangle, sine, sawtooth. Limite de saída: ±10 V.

Teste de laço (VOUT ligado em VIN1 e VIN2, motor DESLIGADO): degraus em sequência e tabela com o erro de cada entrada
  python hmi/scope_cli.py --port ... --steps 0,1,-1,5,-5,9,-9 --dwell 3
"""
import argparse
import time

import numpy as np

from scope import Scope, V_LIM
from hmi import serial_ports


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port")
    ap.add_argument("--rate", type=float, default=None, help="amostras por segundo (padrão: 1000 com esp32_scope, 200 com o firmware antigo)")
    ap.add_argument("--shape", default="off", choices=["off", "DC", "square", "triangle", "sine", "sawtooth"])
    ap.add_argument("--amp", type=float, default=1.0, help="amplitude [V] (padrão 1 V: comece pequeno)")
    ap.add_argument("--off", type=float, default=0.0, help="offset / nível DC [V]")
    ap.add_argument("--freq", type=float, default=0.5, help="frequência [Hz]")
    ap.add_argument("--duration", type=float, default=0.0, help="duração [s] (0 = até Ctrl+C)")
    ap.add_argument("--window", type=float, default=2.0, help="janela das estatísticas [s]")
    ap.add_argument("--steps", help="lista de degraus DC em volts, separados por vírgula (ex.: 0,1,-1,5,-5,9,-9): faz o teste de laço")
    ap.add_argument("--tau", type=float, default=0.0, help="pré-ênfase de borda: polo do filtro de saída [us] (0 = desligada)")
    ap.add_argument("--target", type=float, default=500.0, help="polo alvo da pré-ênfase [us]")
    ap.add_argument("--bits", type=int, default=12, choices=[8, 9, 10, 11, 12], help="resolução do PWM")
    ap.add_argument("--dwell", type=float, default=3.0, help="tempo em cada degrau [s] (padrão 3)")
    a = ap.parse_args()
    if abs(a.off) + (abs(a.amp) if a.shape not in ("off", "DC") else 0.0) > V_LIM:
        raise SystemExit(f"pico de {abs(a.off) + abs(a.amp):.1f} V passa do limite de {V_LIM:g} V")
    port = a.port or (serial_ports() or [None])[0]
    if not port:
        raise SystemExit("nenhuma porta serial encontrada (use --port)")
    if a.steps:
        levels = [float(x) for x in a.steps.split(",")]
        if max(abs(v) for v in levels) > V_LIM - 0.5:
            raise SystemExit(f"degrau acima de {V_LIM - 0.5:g} V não é permitido neste teste")
        sc = Scope(port, a.rate, 10.0)
        sc.configure(a.tau, a.target, a.bits)
        print(f"porta {port} | teste de laço: {levels} V, {a.dwell:g} s cada | Ctrl+C zera a saída")
        print("comando   VIN1 (med)   erro1     VIN2 (med)   erro2    [mediana dos últimos 1,5 s]")
        try:
            for v in levels:
                sc.wave = {"shape": "DC", "amp": 0.0, "off": v, "freq": 1.0}
                time.sleep(a.dwell)
                t, v1, v2, vo = sc.data()
                k = t >= t[-1] - 1.5
                m1, m2 = float(np.median(v1[k])), float(np.median(v2[k]))
                print(f"{v:+7.2f} V  {m1:+9.3f} V  {m1 - v:+7.3f}   {m2:+9.3f} V  {m2 - v:+7.3f}", flush=True)
        except KeyboardInterrupt:
            pass
        finally:
            sc.close()
            print("saída em 0 V, porta fechada")
        return
    sc = Scope(port, a.rate, 10.0)
    sc.configure(a.tau, a.target, a.bits)
    sc.wave = {"shape": a.shape, "amp": a.amp, "off": a.off, "freq": a.freq}
    print(f"porta {port} | {a.shape} amp {a.amp:g} V off {a.off:g} V {a.freq:g} Hz | Ctrl+C zera a saída")
    t0 = time.perf_counter()
    try:
        while a.duration <= 0 or time.perf_counter() - t0 < a.duration:
            time.sleep(0.5)
            t, v1, v2, vo = sc.data()
            if len(t) < 2:
                continue
            k = t >= t[-1] - a.window
            f = lambda v: f"min {v[k].min():+7.3f} max {v[k].max():+7.3f} med {v[k].mean():+7.3f}"  # noqa: E731
            print(f"t={t[-1]:6.1f}s  out {sc.v_out:+6.3f} V | VIN1 {f(v1)} | VIN2 {f(v2)}", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        sc.close()
        print("saída em 0 V, porta fechada")


if __name__ == "__main__":
    main()
