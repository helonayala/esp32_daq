/* ADC -> input voltage conversion and two-point calibration (plain C, no dependencies).
 * Conditioning model:  Vn = offset + gain * Vin
 * 12-bit ADC: code = floor(V * 4096 / Vref)  ->  V = (code + 0.5) * Vref / 4096
 * (the two-point calibration absorbs either convention.)                                      */
#ifndef CONV_H
#define CONV_H
#include "params.h"
#include "cal_board.h"

typedef struct { float gain; float offset; } cal_t;

static inline float counts_to_volts(float counts) { return (counts + 0.5f) * NOM_VREF / ADC_COUNTS; }

#ifdef USE_CAL_BOARD
static inline cal_t cal_nominal(void) { cal_t k = { CAL_GAIN, CAL_OFFSET }; return k; }
#else
static inline cal_t cal_nominal(void) { cal_t k = { NOM_GAIN, NOM_OFFSET }; return k; }
#endif

/* channel 2: same circuit as channel 1 -> starts with the same calibration; redo it if needed */
#ifdef CAL2_GAIN
static inline cal_t cal_nominal_ch2(void) { cal_t k = { CAL2_GAIN, CAL2_OFFSET }; return k; }
#else
static inline cal_t cal_nominal_ch2(void) { return cal_nominal(); }
#endif

static inline float vin_from_counts(float counts, const cal_t *k) {
    return (counts_to_volts(counts) - k->offset) / k->gain;
}

/* c1, c2: mean counts measured with Vin = vin1, vin2 */
static inline cal_t cal_two_point(float c1, float vin1, float c2, float vin2) {
    float v1 = counts_to_volts(c1), v2 = counts_to_volts(c2);
    cal_t k;
    k.gain = (v2 - v1) / (vin2 - vin1);
    k.offset = v1 - k.gain * vin1;
    return k;
}


/* ADC reading in "12-bit counts" (0..4095 for 0..3.3 V), the same on both platforms.
 * Due: analogRead (12 bits). ESP32: analogReadMilliVolts (uses the factory ADC calibration), converted to counts. */
#if defined(ARDUINO_ARCH_ESP32)
#define ADC_PIN_A0 34   /* GPIO34 = ADC1_CH6, input only */
#define ADC_PIN_A1 35   /* GPIO35 = ADC1_CH7, input only */
#define ADC_READ(pin) ((uint32_t)((float)analogReadMilliVolts(pin) * 4096.0f / 3300.0f + 0.5f))
#else
#define ADC_PIN_A0 A0
#define ADC_PIN_A1 A1
#define ADC_READ(pin) ((uint32_t)analogRead(pin))
#endif

/* ---- +-10 V analog output (PWM + filter + TL072):  Vout = k*u + b,  u in [-1, 1] ---- */
typedef struct { float k; float b; } hb_cal_t;

#ifdef USE_CAL_BOARD
static inline hb_cal_t hb_nominal(void) { hb_cal_t c = { CAL_K, CAL_B }; return c; }
#else
static inline hb_cal_t hb_nominal(void) { hb_cal_t c = { HB_NOM_K, HB_NOM_B }; return c; }
#endif

static inline float hb_u_from_volts(float v, const hb_cal_t *c) {
    float u = (v - c->b) / c->k;
    return u > 1.0f ? 1.0f : (u < -1.0f ? -1.0f : u);
}

/* (u1, v1), (u2, v2): raw commands and mean voltages measured with the multimeter */
static inline hb_cal_t hb_cal_two_point(float u1, float v1, float u2, float v2) {
    hb_cal_t c;
    c.k = (v2 - v1) / (u2 - u1);
    c.b = v1 - c.k * u1;
    return c;
}
#endif
