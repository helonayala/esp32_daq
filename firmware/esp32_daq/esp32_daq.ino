/* ESP32 DAQ -- acquisition and control with 2 inputs and 1 output of +-10 V (ESP32 DevKit, Arduino-ESP32 core 3.x).
 * It is suggested NOT to edit this file: the control code is in control.h.
 *
 * Wiring:  VIN1 (GPIO34) = channel 1;  VIN2 (GPIO35) = channel 2;  VOUT (GPIO18) = output;  common GND.   Inputs and output in +-10 V.
 * Example (Ball and Beam): channel 1 = theta (beam angle), channel 2 = x (ball position), output = u (motor) or r_theta (MODE 2).
 *
 * The output stays at 0 V after boot. Nothing runs until the G command. Automatic stop: |theta| > TH_LIM (MODEs 0 and 1) or end of the run.
 *
 * Normalized x:  x = 2 (v2 - xmin)/(xmax - xmin) - 1, with v2 the channel 2 voltage and xmin, xmax the voltages at the ends.
 *
 * Serial commands (115200, terminated by \n):
 *   G        starts the run                S        stops (output = 0)        ?  status
 *   R        reads theta, v2 and x (idle)  X<a>,<b> sets xmin = a mV and xmax = b mV (x normalization)
 *   A<n>     r_x step = n/1000             H<n>     r_theta step = n mV
 *   V<mV>    output voltage, idle (signal test)                              (V0 turns it off)
 * Output at each step:  #L k,t,r_x,r_theta,x,theta,u
 */
#include <string.h>
#include "conv.h"
#include "dacout.h"
#include "control.h"

#define BAUD   115200
#define ADC_OS 32                                        // ADC readings per sample (trimmed mean)
#define TS_US  ((uint32_t)(TS * 1e6f + 0.5f))

static cal_t cal1, cal2;
static dac_state_t hb;
static bool running = false;
static uint32_t k_step, t_next, overruns;
static float x_min = -10.0f, x_max = 10.0f;              // channel 2 voltages at the two ends (command X)
static float rx_cmd = RX_DEFAULT, rth_cmd = RTH_DEFAULT; // reference steps (commands A and H)
static char line_buf[32];
static uint8_t line_len;

static float block_average(uint8_t pin) {                // ADC: sorts ADC_OS readings and averages the middle half
  static uint16_t v[ADC_OS];
  for (uint8_t i = 0; i < ADC_OS; i++) v[i] = (uint16_t)ADC_READ(pin);
  for (uint8_t i = 1; i < ADC_OS; i++) {
    uint16_t x = v[i]; int8_t j = i - 1;
    while (j >= 0 && v[j] > x) { v[j + 1] = v[j]; j--; }
    v[j + 1] = x;
  }
  uint32_t acc = 0; const uint8_t q = ADC_OS / 4;
  for (uint8_t i = q; i < ADC_OS - q; i++) acc += v[i];
  return (float)acc / (float)(ADC_OS - 2 * q);
}

static inline float sat(float v, float lim) { return v > lim ? lim : (v < -lim ? -lim : v); }
static inline void output_volts(float volts) { dac_apply(hb_u_from_volts(volts, &hb.cal)); }
static inline float read_theta() { return vin_from_counts(block_average(ADC_PIN_A0), &cal1); }
static inline float read_v2()    { return vin_from_counts(block_average(ADC_PIN_A1), &cal2); }
static inline float normalize_x(float v2) { return 2.0f * (v2 - x_min) / (x_max - x_min) - 1.0f; }
static inline float read_x()     { return normalize_x(read_v2()); }

static void stop_run(const char *reason) {
  output_volts(0.0f);
  running = false;
  Serial.printf("#STOP %s k=%u overruns=%u\n", reason, (unsigned)k_step, (unsigned)overruns);
}

static void start_run() {
  control_reset();
  k_step = 0; overruns = 0;
  running = true;
  Serial.printf("#GO mode=%d ts=%.3f t_end=%.1f t_step=%.2f rx=%.3f rth=%.3f\n", MODE, TS, T_END, T_STEP, rx_cmd, rth_cmd);
  Serial.println("#FMT k,t,r_x,r_theta,x,theta,u");
  t_next = micros() + TS_US;
}

// ---------------------------------------------------------------- one control step (every TS)
static void control_step() {
  float theta = read_theta();
  float x     = read_x();
  float t     = k_step * TS;

#if MODE != 2
  if (fabsf(theta) > TH_LIM) { stop_run("theta"); return; }
#endif
  if (t > T_END)             { stop_run("end");   return; }

#if MODE == 0
  bool stepped = (t >= T_STEP);
  float r_x = 0.0f;                                             // open loop: no position reference
  float r_theta = stepped ? rth_cmd : 0.0f;                     // open loop: step directly on r_theta
#else
  float r_x = reference_x(t, rx_cmd);                           // step (HMI) or random sequence (REF_SEQ)
  float r_theta = outer_control(r_x, x);                        // outer loop (your x controller)
#endif
  r_theta = sat(r_theta, R_THETA_LIM);
#if MODE == 2
  float u = r_theta;                                            // SIL: the output is r_theta (the virtual plant closes the loop)
#else
  float u = sat(inner_control(r_theta, theta), U_LIM);          // inner loop
#endif
  output_volts(u);

  Serial.printf("#L%u,%.2f,%.4f,%.4f,%.4f,%.4f,%.4f\n", (unsigned)k_step, t, r_x, r_theta, x, theta, u);

  k_step++;
  t_next += TS_US;
  if ((int32_t)(micros() - t_next) > (int32_t)TS_US) { overruns++; t_next = micros(); }
}

// ---------------------------------------------------------------- commands
static void handle_line(const char *s) {
  char c = s[0];
  if (c == 'S') { if (running) stop_run("S"); else output_volts(0.0f); Serial.println("#OK"); }
  else if (c == 'G') { if (!running) start_run(); }
  else if (c == 'A') { rx_cmd = dac_atol(s + 1) / 1000.0f; Serial.printf("#OK rx=%.3f\n", rx_cmd); }
  else if (c == 'H') { rth_cmd = dac_atol(s + 1) / 1000.0f; Serial.printf("#OK rth=%.3f\n", rth_cmd); }
  else if (c == 'R' && !running) { float th = read_theta(), v2 = read_v2(); Serial.printf("#READ theta=%.3f v2=%.3f x=%.3f\n", th, v2, normalize_x(v2)); }
  else if (c == 'X' && !running) {
    const char *comma = strchr(s, ',');
    float a = dac_atol(s + 1) / 1000.0f, b = comma ? dac_atol(comma + 1) / 1000.0f : a;
    if (b - a > 0.5f) { x_min = a; x_max = b; Serial.printf("#OK xmin=%.3f xmax=%.3f\n", x_min, x_max); }
    else Serial.println("#? xmax must be greater than xmin (minimum difference of 0.5 V)");
  }
  else if (c == '?') Serial.printf("#STATUS running=%d mode=%d ts=%.3f rx=%.3f rth=%.3f xmin=%.3f xmax=%.3f\n", running, MODE, TS, rx_cmd, rth_cmd, x_min, x_max);
  else if (!running && dac_command(&hb, s)) Serial.println("#OK");
  else Serial.println("#?");
}

static void read_serial() {
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n' || ch == '\r') {
      if (line_len) { line_buf[line_len] = 0; line_len = 0; handle_line(line_buf); }
    } else if (line_len < sizeof(line_buf) - 1) line_buf[line_len++] = ch;
  }
}

void setup() {
  Serial.begin(BAUD);
  analogReadResolution(12);
  analogSetPinAttenuation(ADC_PIN_A0, ADC_11db);
  analogSetPinAttenuation(ADC_PIN_A1, ADC_11db);
  cal1 = cal_nominal();
  cal2 = cal_nominal_ch2();
  dac_init();
  dac_state_init(&hb);                                           // output at 0 V
  delay(300);
  Serial.printf("#DAQ ready: mode=%d ts=%.3f. Output at 0 V; send G to start.\n", MODE, TS);
}

void loop() {
  read_serial();
  if (running && (int32_t)(micros() - t_next) >= 0) control_step();
}
