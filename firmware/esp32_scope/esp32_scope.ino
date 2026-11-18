/* ESP32 SCOPE -- signal generator + 2-channel scope firmware (ESP32 DevKit, Arduino-ESP32 core 3.x).
 * Separate sketch from esp32_daq: to go back to the student firmware, just flash firmware/esp32_daq again.
 *
 * The firmware samples VIN1 (GPIO34) and VIN2 (GPIO35) and updates VOUT (GPIO18) at its own fixed rate FS (timer in micros()),
 * generating the output waveform itself. The data go to the PC in bursts every REP_MS (another rate), as text lines
 * "#S<k>,<vin1 mV>,<vin2 mV>,<vout mV>": the time of sample k is exactly k/FS, so USB/PC jitter does not matter.
 *
 * Commands (boot 115200 baud, B<baud> raises it; terminated by \n):
 *   M<fs>   starts streaming at fs Hz (10..4000); M0 stops           K  keep-alive (stream stops if silent for 2 s)
 *   W<shape>,<amp mV>,<off mV>,<freq mHz>   shape: 0 off, 1 DC, 2 square, 3 triangle, 4 sine, 5 sawtooth
 *   E<tau us>[,<target us>]  edge pre-emphasis: inverts the output filter (2 poles of tau, ~2000 us measured) and replaces it by
 *              a faster one (target, default tau/4); the PWM saturates at +-10.4 V. 0 = off
 *   Q<bits>    PWM resolution 8..12 bits (frequency = 80 MHz / 2^bits: 12 -> 19.5 kHz ... 10 -> 78 kHz)
 *   B<baud>    switch the UART speed (e.g. B921600); reverts to 115200 after 3 s if the PC does not confirm with '?'
 *   P<ms>      burst period (default 20)     V<mV> static output (idle)     R read VIN1/VIN2 (idle)     S stop + 0 V     ? status
 */
#include <Arduino.h>
#include "conv.h"

#define BAUD       115200           // boot baud; B<baud> negotiates a faster one at run time
#define V_LIM_MV   10000            // waveform limit [mV]
#define V_HW_MV    10400            // hard limit after pre-emphasis [mV]
#define ADC_N      6                // ADC readings per channel per sample (min and max discarded, mean of the rest: kills single-sample glitches)
#define RING       1024
#define WDG_MS     2000
/* Edge pre-emphasis defaults at boot (also set at run time by E<tau>,<target>): EDGE_TAU_US = pole of the output RC (0 = off). */
#define EDGE_TAU_US    0
#define EDGE_TARGET_US 500
#define PWM_BITS       12

static cal_t cal1, cal2;
static uint32_t baud_revert_at = 0;
static hb_cal_t hcal;
static uint8_t pwm_bits = 12;

static void pwm_set_bits(uint8_t b) {
  if (b < 8) b = 8; if (b > 12) b = 12;
  pwm_bits = b;
  ledcDetach(18);
  ledcAttach(18, 80000000UL >> b, b);
}
static void output_volts(float v) {
  float u = hb_u_from_volts(v, &hcal);
  float d = (u + 1.0f) * 0.5f;
  d = d < 0 ? 0 : (d > 1 ? 1 : d);
  ledcWrite(18, (uint32_t)(d * (float)(1u << pwm_bits) + 0.5f));
}

static float read_ch(uint8_t pin, const cal_t *k) {
  uint32_t acc = 0, lo = 0xFFFFFFFF, hi = 0;
  for (uint8_t i = 0; i < ADC_N; i++) { uint32_t m = analogReadMilliVolts(pin); acc += m; if (m < lo) lo = m; if (m > hi) hi = m; }
  float counts = ((float)(acc - lo - hi) / (ADC_N - 2)) * 4096.0f / 3300.0f;
  return vin_from_counts(counts, k);
}

// ---- stream state
static bool streaming = false;
static uint32_t fs = 1000, k_s, t_next, per_us, over, drop, last_rx, t_rep, rep_ms = 20, t_stat;
static uint8_t shape = 0; static float amp = 0, off = 0, freq = 0.5f, phase = 0, tau = 0, tau_t = 0, lp1 = 0, lp2 = 0;
static int16_t rb[RING][3]; static uint16_t head, tail;
static uint32_t k_sent;

static float waveform() {                                  // output voltage [V] at the current phase, then advances it
  float s;
  switch (shape) {
    case 0: return 0.0f;
    case 1: s = 0; break;
    case 2: s = phase < 0.5f ? 1.0f : -1.0f; break;
    case 3: s = phase < 0.5f ? 4 * phase - 1 : 3 - 4 * phase; break;
    case 4: s = sinf(6.2831853f * phase); break;
    default: s = 2 * phase - 1; break;
  }
  float v = off + (shape == 1 ? 0.0f : amp * s);
  phase += freq / (float)fs; if (phase >= 1.0f) phase -= 1.0f;
  float lim = V_LIM_MV / 1000.0f;
  return v > lim ? lim : (v < -lim ? -lim : v);
}

static void stop_stream(const char *why) {
  streaming = false; output_volts(0.0f);
  Serial.printf("#STOPPED %s k=%u over=%u drop=%u\n", why, (unsigned)k_s, (unsigned)over, (unsigned)drop);
}

static void sample_tick() {
  float v = waveform();
  float vc = v;
  if (tau > 0) {                                            // inverse of the output 2 RC (2 equal poles, time constant tau) times a faster
    float dt = 1.0f / (float)fs, a = dt / (tau_t * 1e-6f + dt), g = tau / tau_t - 1.0f;   // 2-pole target (tau_t): 2 lead-lag stages
    lp1 += a * (vc - lp1); float s1 = vc + g * (vc - lp1);
    lp2 += a * (s1 - lp2); vc = s1 + g * (s1 - lp2);
  }
  float hw = V_HW_MV / 1000.0f;
  output_volts(vc > hw ? hw : (vc < -hw ? -hw : vc));
  float v1 = read_ch(ADC_PIN_A0, &cal1), v2 = read_ch(ADC_PIN_A1, &cal2);   // read after the update: sees the new level one ADC time later
  uint16_t nx = (head + 1) % RING;
  if (nx == tail) drop++;
  else { rb[head][0] = (int16_t)lroundf(v1 * 1000); rb[head][1] = (int16_t)lroundf(v2 * 1000); rb[head][2] = (int16_t)lroundf(v * 1000); head = nx; }
  k_s++;
  t_next += per_us;
  if ((int32_t)(micros() - t_next) > (int32_t)per_us) { over++; t_next = micros(); }
}

static void flush_ring() {
  static char out[RING * 24 / 4];
  size_t n = 0; uint16_t cnt = 0;
  while (tail != head && n < sizeof(out) - 32) {
    n += snprintf(out + n, 32, "#S%u,%d,%d,%d\n", (unsigned)k_sent, rb[tail][0], rb[tail][1], rb[tail][2]);
    k_sent++; tail = (tail + 1) % RING; cnt++;
  }
  if (n) Serial.write((const uint8_t *)out, n);
}

static long atol_(const char *s) {
  long v = 0; int neg = 0;
  if (*s == '-') { neg = 1; s++; } else if (*s == '+') s++;
  while (*s >= '0' && *s <= '9') { v = v * 10 + (*s - '0'); s++; }
  return neg ? -v : v;
}
static const char *next_field(const char *s) { const char *c = strchr(s, ','); return c ? c + 1 : s + strlen(s); }

static void handle_line(const char *s) {
  last_rx = millis();
  char c = s[0];
  if (baud_revert_at && (c == '?' || c == 'K' || c == 'M')) baud_revert_at = 0;   // PC confirmed the new baud rate
  if (c == 'K') return;
  if (c == 'M') {
    long f = atol_(s + 1);
    if (f <= 0) { if (streaming) stop_stream("M0"); else Serial.println("#OK"); return; }
    if (f < 10) f = 10; if (f > 4000) f = 4000;
    fs = f; per_us = 1000000UL / fs; k_s = 0; k_sent = 0; head = tail = 0; over = drop = 0; phase = 0; lp1 = lp2 = 0;
    t_next = micros() + per_us; t_rep = millis(); t_stat = millis(); streaming = true;
    Serial.printf("#GO fs=%u rep=%u bits=%u tau=%.0f\n", (unsigned)fs, (unsigned)rep_ms, pwm_bits, tau);
  }
  else if (c == 'W') {
    shape = (uint8_t)atol_(s + 1); const char *p = next_field(s);
    amp = atol_(p) / 1000.0f; p = next_field(p); off = atol_(p) / 1000.0f; p = next_field(p);
    long fm = atol_(p); freq = fm > 0 ? fm / 1000.0f : 0.001f;
    phase = 0; if (!streaming) output_volts(shape == 1 ? off : 0.0f);
    Serial.printf("#OK W shape=%u amp=%.3f off=%.3f freq=%.3f\n", shape, amp, off, freq);
  }
  else if (c == 'B') {
    long b = atol_(s + 1);
    if (b >= 9600 && b <= 2000000) { Serial.printf("#OK baud=%ld\n", b); Serial.flush(); Serial.updateBaudRate(b); baud_revert_at = millis() + 3000; if (!baud_revert_at) baud_revert_at = 1; }
  }
  else if (c == 'E') {                                       // E<tau us>[,<tau_target us>]  (target default tau/4)
    tau = (float)atol_(s + 1); if (tau < 0) tau = 0;
    const char *p = next_field(s); tau_t = *p ? (float)atol_(p) : tau / 4.0f;
    if (tau_t < 100) tau_t = 100; if (tau_t > tau) tau_t = tau;
    lp1 = lp2 = 0; Serial.printf("#OK tau=%.0f us target=%.0f us\n", tau, tau_t);
  }
  else if (c == 'Q') { pwm_set_bits((uint8_t)atol_(s + 1)); output_volts(0.0f); Serial.printf("#OK bits=%u pwm=%lu Hz\n", pwm_bits, 80000000UL >> pwm_bits); }
  else if (c == 'P') { long p = atol_(s + 1); rep_ms = p < 2 ? 2 : (p > 200 ? 200 : p); Serial.printf("#OK rep=%u\n", (unsigned)rep_ms); }
  else if (c == 'S') { if (streaming) stop_stream("S"); else { output_volts(0.0f); Serial.println("#OK"); } }
  else if (c == 'V' && !streaming) { output_volts(atol_(s + 1) / 1000.0f); Serial.println("#OK"); }
  else if (c == 'R' && !streaming) {
    float a = read_ch(ADC_PIN_A0, &cal1), b = read_ch(ADC_PIN_A1, &cal2);
    Serial.printf("#READ theta=%.3f v2=%.3f x=%.3f\n", a, b, b / 10.0f);
  }
  else if (c == '?') Serial.printf("#SCOPE streaming=%d fs=%u rep=%u bits=%u tau=%.0f\n", streaming, (unsigned)fs, (unsigned)rep_ms, pwm_bits, tau);
  else Serial.println("#?");
}

static char lb[48]; static uint8_t ll;
static void read_serial() {
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n' || ch == '\r') { if (ll) { lb[ll] = 0; ll = 0; handle_line(lb); } }
    else if (ll < sizeof(lb) - 1) lb[ll++] = ch;
  }
}

void setup() {
  hcal = hb_nominal(); cal1 = cal_nominal(); cal2 = cal_nominal_ch2();
  tau = EDGE_TAU_US; tau_t = EDGE_TARGET_US;
  pwm_set_bits(PWM_BITS); output_volts(0.0f);                      // 0 V as early as possible
  analogReadResolution(12);
  analogSetPinAttenuation(ADC_PIN_A0, ADC_11db);
  analogSetPinAttenuation(ADC_PIN_A1, ADC_11db);
  Serial.setTxBufferSize(16384);
  Serial.begin(BAUD);
  delay(300);
  Serial.printf("#SCOPE ready baud=%d. Output at 0 V; M<fs> starts streaming.\n", BAUD);
}

void loop() {
  read_serial();
  if (baud_revert_at && (int32_t)(millis() - baud_revert_at) >= 0) { Serial.updateBaudRate(BAUD); baud_revert_at = 0; }
  if (!streaming) return;
  if (millis() - last_rx > WDG_MS) { stop_stream("watchdog"); return; }
  uint8_t guard = 4;
  while (guard-- && (int32_t)(micros() - t_next) >= 0) sample_tick();
  if (millis() - t_rep >= rep_ms) { t_rep += rep_ms; flush_ring(); }
  if (millis() - t_stat >= 1000) { t_stat += 1000; Serial.printf("#STAT k=%u over=%u drop=%u\n", (unsigned)k_s, (unsigned)over, (unsigned)drop); }
}
