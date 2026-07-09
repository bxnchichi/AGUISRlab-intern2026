#include <math.h>

const int NUM_FSR = 6;
int FSR_pins[NUM_FSR] = {A0, A1, A2, A3, A4, A5};
int avg_size = 10; // number of analog readings to average
float R_0 = 10000.0; // known resistor value in [Ohms]
float Vcc = 5.0; // supply voltage
int i = 1;

// Calibration parameters
const float a_list[6] = {
    -1.8719516800859706,
    -1.8590241458147658,
    -1.2959177497683403,
    -1.4011271964139371,
    -1.3035707998955808,
    -1.8508990075743086
};

const float b_list[6] = {
    2.0710733185189127,
    2.0438458995590167,
    1.0333003676988375,
    0.2499510875238671,
    0.3040839221730824,
    1.362867464385802
};

const float Vmax_list[6] = {
    4500,
    4500,
    4500,
    3650,
    3800,
    3200
};

const float limit[NUM_FSR] = {100, 100, 100, 30, 30, 100};



void setup() {
  Serial.begin(9600);
  Serial.println("start");
}

// Convert one FSR voltage (mV) to force
float calculateForce(float voltage, float a, float b, float Vmax)
{
    // Prevent invalid values
    if (voltage < 0.000001f)
    return 0

    if (voltage >= Vmax)
        voltage = Vmax - 0.000001f;

    return pow(10.0,
               (1.0 / a) * log10(Vmax / voltage - 1.0) - (b / a));
}

void loop() {
  float sum_val[NUM_FSR] = {0};
  float force[NUM_FSR];
  // Thresholds for each sensor
  float thresholds[NUM_FSR] = {3, 3, 3, 10, 3, 3};

  // Read and average
  for (int ii = 0; ii < avg_size; ii++) {
      for (int i = 0; i < NUM_FSR; i++) {
          sum_val[i] += (analogRead(FSR_pins[i]) / 1023.0) * 5000.0;
      }
      delay(10);
  }

  // Compute average, apply thresholds and compute force
  for (int i = 0; i < NUM_FSR; i++) {
      sum_val[i] /= avg_size;
      if (sum_val[i] < thresholds[i]) {
        sum_val[i] = 0;
      }
      force[i] = calculateForce(sum_val[i], a_list[i], b_list[i], Vmax_list[i]);
      if (force[i] > limit[i]){
        force[i] = limit[i];
      }
  }
  

  Serial.println(String(sum_val[0]) + "," + String(sum_val[1]) + "," + String(sum_val[2]) + "," + String(sum_val[3]) + "," + String(sum_val[4]) + "," + String(sum_val[5]) + ",mV," + String(force[0]) + "," + String(force[1]) + "," + String(force[2]) + "," + String(force[3]) + "," + String(force[4]) + "," + String(force[5]) + ",N"); // print to serial port
  delay(10);

}