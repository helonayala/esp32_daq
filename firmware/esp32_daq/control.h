/* ESP32 DAQ -- cascade control (example: Ball and Beam bench).  IT IS SUGGESTED TO EDIT ONLY THIS FILE.
 *
 *   outer loop:  r_x -> [ outer_control ] -> r_theta     (ball position)
 *   inner loop:  r_theta -> [ inner_control ] -> u       (beam angle), u = motor voltage
 *
 * Inputs:  channel 1 (GPIO34) = theta [V];  channel 2 (GPIO35) = x, normalized to [-1, 1] (see xmin/xmax in the HMI).
 * Output:  GPIO18 = u [V] (+-10 V).
 */
#ifndef CONTROL_H
#define CONTROL_H

/* 0 = OPEN LOOP: only the inner loop (Kp) and a step on r_theta; x(t) is measured to identify K_B.
 * 1 = HIL (x and theta loops): r_theta = outer_control(r_x, x), u = Kp*(r_theta - theta), output = u.
 * 2 = SIL (x controller only): r_theta = outer_control(r_x, x), output = r_theta (theta is not used):
 *     the virtual plant (dSpace) receives r_theta and returns x.                                        */
#define MODE 0

/* Position reference r_x (MODEs 1 and 2):
 * 0 = one step (value set in the HMI, command A);
 * 1 = random step sequence: every T_DWELL s, r_x changes by at most +-DELTA_MAX from the previous step,
 *     limited to +-RX_MAX. The sequence is the same in every run (change SEED for another). Duration: T_END. */
#define REF_SEQ 0
static const float T_DWELL   = 5.0f;      /* REF_SEQ: time between steps [s] */
static const float DELTA_MAX = 0.5f;      /* REF_SEQ: maximum change between consecutive steps */
static const float RX_MAX    = 0.8f;      /* REF_SEQ: maximum |r_x| */
static const uint32_t SEED   = 12345u;    /* REF_SEQ: random generator seed */

static const float TS = 0.05f;            /* sampling period [s]; use the SAME value in c2d */

static const float KP_THETA    = 3.0f;    /* inner loop gain */
static const float R_THETA_LIM = 4.0f;    /* r_theta saturation [V] */
static const float U_LIM       = 10.0f;   /* u saturation [V] (output limit) */
static const float TH_LIM      = 5.0f;    /* maximum |theta| [V]: above it the run is stopped (u = 0) */

static const float T_STEP = 1.0f;         /* instant of the reference step [s] */
static const float RX_DEFAULT  = 0.5f;    /* r_x step (MODEs 1 and 2, REF_SEQ 0) */
static const float RTH_DEFAULT = 1.0f;    /* r_theta step [V] (MODE 0) */
#if MODE == 0
static const float T_END = 8.0f;          /* run duration [s] */
#elif REF_SEQ
static const float T_END = 60.0f;
#else
static const float T_END = 15.0f;
#endif

/* ---------------------------------------------------------------- inner loop */
float inner_control(float r_theta, float theta) {
  return KP_THETA * (r_theta - theta);    /* u [V]; the program saturates it at +-U_LIM */
}

/* ---------------------------------------------------------------- reference r_x */
static uint32_t rng_s;
static int seq_n;
static float seq_r;

static float rand_unit() {                /* xorshift32: number in [-1, 1] */
  rng_s ^= rng_s << 13; rng_s ^= rng_s >> 17; rng_s ^= rng_s << 5;
  return (float)(rng_s & 0xFFFFFFu) / 8388607.5f - 1.0f;
}

/* Called every TS. t = run time [s]; step = value of command A from the HMI. */
float reference_x(float t, float step) {
#if REF_SEQ
  if (t < T_STEP) return 0.0f;
  int n = (int)((t - T_STEP) / T_DWELL);            /* index of the current step */
  while (seq_n < n) {                               /* new step: limited random change */
    seq_n++;
    float r = seq_r + DELTA_MAX * rand_unit();
    seq_r = r > RX_MAX ? RX_MAX : (r < -RX_MAX ? -RX_MAX : r);
  }
  return seq_r;
#else
  return t >= T_STEP ? step : 0.0f;
#endif
}

/* ---------------------------------------------------------------- outer loop (MODEs 1 and 2) */
/* Difference equation of the x controller, obtained from MATLAB c2d:
 *   u[k] = bC(1) e[k] + bC(2) e[k-1] + ... - aC(2) u[k-1] - aC(3) u[k-2] - ...    with aC(1) = 1
 * ORDER = order of the discrete controller (number of poles). The history is cleared in control_reset(). */
#define ORDER 1
static const float bC[ORDER + 1] = { 0.0f, 0.0f };   /* TODO: numerator from tfdata (bC / aC(1)) */
static const float aC[ORDER + 1] = { 1.0f, 0.0f };   /* TODO: denominator from tfdata (aC / aC(1)); aC[0] = 1 */
static float e_h[ORDER + 1];                         /* e[k], e[k-1], ... */
static float u_h[ORDER + 1];                         /* u[k], u[k-1], ... */

void control_reset() {
  for (int i = 0; i <= ORDER; i++) { e_h[i] = 0.0f; u_h[i] = 0.0f; }
  rng_s = SEED; seq_n = -1; seq_r = 0.0f;
}

/* Called every TS. Returns r_theta [V]; the program saturates it at +-R_THETA_LIM
 * (the difference equation keeps the unsaturated value, as in the MATLAB simulation). */
float outer_control(float r_x, float x) {
  for (int i = ORDER; i > 0; i--) { e_h[i] = e_h[i - 1]; u_h[i] = u_h[i - 1]; }   /* shift the history */
  e_h[0] = r_x - x;                                                                /* current error */

  float u = 0.0f;
  for (int i = 0; i <= ORDER; i++) u += bC[i] * e_h[i];
  for (int i = 1; i <= ORDER; i++) u -= aC[i] * u_h[i];
  u_h[0] = u;
  return u;
}

#endif
