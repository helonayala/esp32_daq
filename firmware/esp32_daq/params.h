/* nominal constants of the input/output conditioning circuits (design values) */
#pragma once
#define NOM_GAIN   0.083333f
#define NOM_OFFSET 1.512500f
#define NOM_VREF   3.3f
#define ADC_COUNTS 4096.0f
/* output: Vout = k*u + b (u in [-1,1]); k = G*Vcc/2, b = k - Vcc*Rf/Ra */
#define HB_NOM_K   10.6182f
#define HB_NOM_B   -0.0582f
