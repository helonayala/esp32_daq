/* +-10 V output referenced to GND (Arduino Due or ESP32, 3.3 V): 12-bit PWM (Due: D9; ESP32: GPIO18),
 * ~20 kHz -> 2 RC -> TL072.   Vout = G*Vcc*d - Vcc*Rf/Ra  (d = duty 0..1).
 * Calibrated model:  Vout = k*u + b,  u in [-1, 1] (u = 2d - 1);  nominal values in params.h (HB_NOM_K, HB_NOM_B).
 * Wiring: PWM pin -> board PWM input; VOUT -> +-10 V input of the system; common GND. */
#ifndef DACOUT_H
#define DACOUT_H
#include <Arduino.h>
#include "conv.h"

#define DAC_PWM_PERIOD  4096u       /* 12 bits */

#if defined(ARDUINO_ARCH_ESP32)
/* ESP32 (DevKit): LEDC PWM on GPIO18, 12 bits at ~19.5 kHz (80 MHz / 4096) */
#define DAC_PWM_PIN     18
#define DAC_PWM_FREQ    19500u
static inline void dac_init(void) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcAttach(DAC_PWM_PIN, DAC_PWM_FREQ, 12);
#else
    ledcSetup(0, DAC_PWM_FREQ, 12); ledcAttachPin(DAC_PWM_PIN, 0);
#endif
}
static inline void dac_write_duty(uint32_t duty) {
    if (duty > DAC_PWM_PERIOD - 1) duty = DAC_PWM_PERIOD - 1;
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcWrite(DAC_PWM_PIN, duty);
#else
    ledcWrite(0, duty);
#endif
}
#else
/* Arduino Due: PWML4 channel (D9 = PC21), 12 bits at ~20.5 kHz (84 MHz / 4096) */
#define DAC_PWM_CH      4u
#define DAC_PWM_FREQ    20500u
static inline void dac_init(void) {
    pmc_enable_periph_clk(PWM_INTERFACE_ID);
    PWMC_ConfigureClocks((uint32_t)DAC_PWM_FREQ * DAC_PWM_PERIOD, 0, VARIANT_MCK);
    PIO_Configure(PIOC, PIO_PERIPH_B, PIO_PC21B_PWML4, PIO_DEFAULT);
    PWMC_ConfigureChannel(PWM_INTERFACE, DAC_PWM_CH, PWM_CMR_CPRE_CLKA, 0, 0);   /* left aligned, polarity 0 */
    PWMC_SetPeriod(PWM_INTERFACE, DAC_PWM_CH, DAC_PWM_PERIOD);
    PWMC_SetDutyCycle(PWM_INTERFACE, DAC_PWM_CH, DAC_PWM_PERIOD / 2);
    PWMC_EnableChannel(PWM_INTERFACE, DAC_PWM_CH);
}
static inline void dac_write_duty(uint32_t duty) {
    if (duty > DAC_PWM_PERIOD) duty = DAC_PWM_PERIOD;
    PWMC_SetDutyCycle(PWM_INTERFACE, DAC_PWM_CH, duty);
}
#endif

/* u in [-1, 1] -> 12-bit duty */
static inline void dac_apply(float u) {
    float d = (u + 1.0f) * 0.5f;
    if (d < 0.0f) d = 0.0f;
    if (d > 1.0f) d = 1.0f;
    dac_write_duty((uint32_t)(d * (float)DAC_PWM_PERIOD + 0.5f));
}

/* Commands (lines without the '\n'):  U<permil> raw command u = permil/1000 (no calibration);
 *   V<mV> desired output voltage in mV (calibrated); P<mV>/N<mV> stores the measured voltage (mV) at the last U
 *   as the + or - point; with both points, computes k and b. */
typedef struct { hb_cal_t cal; float u_last; float p_u, p_v, n_u, n_v; uint8_t have_p, have_n; } dac_state_t;

static inline long dac_atol(const char *s) {
    long v = 0; int neg = 0;
    if (*s == '-') { neg = 1; s++; } else if (*s == '+') s++;
    while (*s >= '0' && *s <= '9') { v = v * 10 + (*s - '0'); s++; }
    return neg ? -v : v;
}

static inline void dac_state_init(dac_state_t *h) {
    h->cal = hb_nominal(); h->u_last = 0; h->p_u = h->p_v = h->n_u = h->n_v = 0; h->have_p = h->have_n = 0;
    dac_apply(hb_u_from_volts(0.0f, &h->cal));
}

static inline uint8_t dac_command(dac_state_t *h, const char *line) {
    char c = line[0];
    if (c == 'U') { h->u_last = dac_atol(line + 1) / 1000.0f; dac_apply(h->u_last); return 1; }
    if (c == 'V') { dac_apply(hb_u_from_volts(dac_atol(line + 1) / 1000.0f, &h->cal)); return 1; }
    if (c == 'P' || c == 'N') {
        float v = dac_atol(line + 1) / 1000.0f;
        if (c == 'P') { h->p_u = h->u_last; h->p_v = v; h->have_p = 1; }
        else          { h->n_u = h->u_last; h->n_v = v; h->have_n = 1; }
        if (h->have_p && h->have_n) h->cal = hb_cal_two_point(h->n_u, h->n_v, h->p_u, h->p_v);
        return 1;
    }
    return 0;
}
#endif
