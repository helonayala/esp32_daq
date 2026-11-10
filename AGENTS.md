# Instructions for the coding agent (ESP32 DAQ)

This repository is a general acquisition and control firmware for the ESP32 (2 inputs and 1 output of ±10 V), with a Python HMI: the student forks it and implements their own controller (the example is the cascade loop of the Ball and Beam bench). Help the student to **understand and write** the code; do not just hand over the answer.

## What can and cannot be edited

- **By default, edit only `firmware/esp32_daq/control.h`** (`MODE`, `REF_SEQ`, `ORDER`, `bC`, `aC`, gains, `outer_control()`).
- **Do not edit** `esp32_daq.ino`, `conv.h`, `dacout.h`, `params.h` and `cal_board.h`: they are the acquisition firmware and the calibration of the interface board (ESP32 + ±10 V). If you think one of them must change, explain why to the student and ask first.
- `hmi/hmi.py` should only be changed if the student asks.

## How the firmware works

- Every `TS` = 50 ms, with a fixed period (`micros()`), `control_step()` reads theta (channel 1, GPIO34) and x (channel 2, GPIO35), computes the control law and writes the output (GPIO18). Inputs and output in ±10 V.
- x is normalized to [-1, 1] in the firmware, using `xmin` and `xmax` (channel 2 voltages at the ends) sent by the HMI.
- Inner loop: `u = Kp (r_theta − theta)`, `Kp = 3`. Outer loop: `r_theta = outer_control(r_x, x)`, saturated at ±4 V.
- Modes (`#define MODE` in `control.h`):
  - `0`: open loop (step on r_theta, free ball; to identify K_B);
  - `1`: HIL, x and theta loops on the bench (output = u);
  - `2`: SIL, x controller only, output = r_theta (virtual plant on the dSpace; theta is not used).
- The reference r_x is a step (`REF_SEQ 0`) or a sequence of random steps (`REF_SEQ 1`, with `T_DWELL`, `DELTA_MAX`, `RX_MAX`, `SEED`, `T_END`); it is saved in the `r_x` column.
- The data of each run are saved by the HMI in `hmi/data/` (`.csv` and `.mat`).

## Rules for the controller code

1. Discretize `C_x(s)` with the **same `TS` as the firmware** (`c2d`, `zoh` or `tustin`) and implement the difference equation in `outer_control()`, using the MATLAB notation: `[bC, aC] = tfdata(Cd, 'v')`, normalized by `aC(1)`, and `u[k] = bC(1) e[k] + bC(2) e[k-1] + … − aC(2) u[k-1] − …`. Set `ORDER`, `bC[]` and `aC[]`.
2. Before flashing, the student should simulate the same difference equation in MATLAB (`for` loop) and compare it with the continuous `step`/`lsim`. Every additional state is `static` and **must be cleared in `control_reset()`**.
3. Do not use `delay()`, `Serial.print()` or dynamic allocation inside the control functions: they run every `TS` and must not delay `control_step()`.
4. Respect the saturations (`R_THETA_LIM`, `U_LIM`, `TH_LIM`) and do not raise them without the student understanding the risk for the bench.
5. Use `float`, never `double`, and keep the units: x normalized; theta, r_theta and u in volts.
6. Comment the difference equation and the origin of each coefficient (which `c2d`, with which `TS`).
7. Before flashing, check the sign of theta and x with the `R` and `V1000`/`V0` commands (see the header of `esp32_daq.ino`); a flipped sign closes the loop with positive feedback.

## How to help well

- Ask the student for the designed `C_x(s)` and the `TS` before writing the coefficients; never invent values.
- Explain the code before changing it and show how to check the result (compare the saved `x` and `r_theta` with the simulation).
- Suggest testing the same difference equation in simulation (Python/MATLAB) before flashing the board.
- For hardware questions, see the project page (`docs/index.html`) and the hardware repository [analog_circuits](https://github.com/helonayala/analog_circuits).
