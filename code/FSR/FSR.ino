
int FSR_pin1 = A0;    // select the input pin for the potentiometer
int FSR_pin2 = A1;    // select the input pin for the potentiometer
int FSR_pin3 = A2;
int FSR_pin4 = A3;
int FSR_pin5 = A4;
int FSR_pin6 = A5;
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
  float sum_val3 = 0.0;
  float sum_val4 = 0.0;
  float sum_val5 = 0.0;
  float sum_val6 = 0.0;
  float R_FSR1;
  float R_FSR2;
  float R_FSR3;
  float R_FSR4;
  float R_FSR5;
  float R_FSR6;


  for (int ii=0;ii<avg_size;ii++){
    sum_val1+=(analogRead(FSR_pin1)/1023.0)*5000.0; // sum the 10-bit ADC ratio
    sum_val2+=(analogRead(FSR_pin2)/1023.0)*5000.0; // sum the 10-bit ADC ratio
    sum_val3+=(analogRead(FSR_pin3)/1023.0)*5000.0; // sum the 10-bit ADC ratio
    sum_val4+=(analogRead(FSR_pin4)/1023.0)*5000.0; // sum the 10-bit ADC ratio
    sum_val5+=(analogRead(FSR_pin5)/1023.0)*5000.0; // sum the 10-bit ADC ratio
    sum_val6+=(analogRead(FSR_pin6)/1023.0)*5000.0; // sum the 10-bit ADC ratio
    delay(10);
  }
  sum_val1/=avg_size; // take average
  sum_val2/=avg_size; // take average
  sum_val3/=avg_size; // take average
  sum_val4/=avg_size; // take average
  sum_val5/=avg_size; // take average
  sum_val6/=avg_size; // take average

  
  // Serial.println(sum_val1);
  Serial.println(String(sum_val1) + "," + String(sum_val2) + "," + String(sum_val3) + "," + String(sum_val4) + "," + String(sum_val5) + "," + String(sum_val6) + ",mV"); // print to serial port
  delay(10);

}