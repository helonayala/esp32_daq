/* Calibration measured on the board (VOUT -> VIN loop, multimeter on VOUT). Each board has its own.
 * Output: Vout = CAL_K * u + CAL_B  (u in [-1, 1], u = 2*duty - 1).
 * Input:  Vn = CAL_OFFSET + CAL_GAIN * Vin  (Vn = voltage at the ADC pin).
 * To use the nominal design values instead, comment out USE_CAL_BOARD. */
#ifndef CAL_BOARD_H
#define CAL_BOARD_H
#define USE_CAL_BOARD 1

#if defined(ARDUINO_ARCH_ESP32)
/* ESP32 DevKit (GPIO18 PWM, GPIO34 input), 20 Oct 2026: output u = +-0.9 -> +9.56 V and -9.61 V (multimeter);
 * input Vin = -10 V and +10 V (medians of 5000 blocks: 857.2 and 2928.6 counts). ADC read with analogReadMilliVolts,
 * 64 readings per block (trimmed mean). */
/* Recalibrated on 20 Oct 2026 on a breadboard with 2 channels (VOUT on VIN1 and VIN2; multimeter: -10.00 / 0 -0.017 / +9.96 V
 * for commands -10 / 0 / +10 V; inputs: counts 841.0 and 2919.0 (channel 1), 844.6 and 2914.9 (channel 2)). */
#define CAL_K      10.629f
#define CAL_B      -0.045f
#define CAL_GAIN    0.08388f
#define CAL_OFFSET  1.5167f
#define CAL2_GAIN   0.08356f
#define CAL2_OFFSET 1.5165f
#else
/* Arduino Due (D9 PWM, A0 input), 19 Oct 2026: output u = +-0.9 -> +9.66 V and -9.60 V;
 * input Vin = -10 V and +10 V (counts 849.2 and 2894.8). Maximum loop error after calibration: 48 mV. */
#define CAL_K      10.700f
#define CAL_B       0.030f
#define CAL_GAIN    0.08240f
#define CAL_OFFSET  1.5086f
#endif
#endif
