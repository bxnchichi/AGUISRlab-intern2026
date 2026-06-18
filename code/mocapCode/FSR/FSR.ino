
int FSR_pin = A0;    // select the input pin for the potentiometer
int avg_size = 10; // number of analog readings to average
float R_0 = 10000.0; // known resistor value in [Ohms]
float Vcc = 5.0; // supply voltage

void setup() {
  Serial.begin(9600);
}

void loop() {
  float sum_val = 0.0; // variable for storing sum used for averaging
  float R_FSR;
  for (int ii=0;ii<avg_size;ii++){
    sum_val+=(analogRead(FSR_pin)/1023.0)*5.0; // sum the 10-bit ADC ratio
    delay(10);
  }
  sum_val/=avg_size; // take average

  R_FSR = (R_0/1000.0)*((Vcc/sum_val)-1.0); // calculate actual FSR resistance
 
  Serial.println(R_FSR); // print to serial port
  delay(10);
}