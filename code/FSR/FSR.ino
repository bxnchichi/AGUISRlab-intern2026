
int FSR_pin1 = A0;    // select the input pin for the potentiometer
int FSR_pin2 = A3;
int avg_size = 10; // number of analog readings to average
float R_0 = 10000.0; // known resistor value in [Ohms]
float Vcc = 5.0; // supply voltage
int i = 1;



void setup() {
  Serial.begin(9600);
  Serial.println("start");
}

void loop() {
  float sum_val1 = 0.0; // variable for storing sum used for averaging
  float sum_val2 = 0.0;
  float R_FSR1;
  float R_FSR2;

  for (int ii=0;ii<avg_size;ii++){
    sum_val1+=(analogRead(FSR_pin1)/1023.0)*5000.0; // sum the 10-bit ADC ratio
    sum_val2+=(analogRead(FSR_pin2)/1023.0)*5000.0; // sum the 10-bit ADC ratio
    delay(10);
  }
  sum_val1/=avg_size; // take average
  sum_val2/=avg_size; // take average
  // For Resistor on gnd
  // R_FSR1 = (R_0/1000.0)*((Vcc/sum_val1)-1.0); // calculate actual FSR resistance
  // R_FSR2 = (R_0/1000.0)*((Vcc/sum_val2)-1.0); // calculate actual FSR resistance
  // For Resistor on VCC
  // R_FSR = (R_0/1000) * (Vcc/sum_val)-1.0
  
  // Serial.println(sum_val1);
  Serial.println(String(sum_val1) + "," + String(sum_val2) + ",mV"); // print to serial port
  delay(10);

}