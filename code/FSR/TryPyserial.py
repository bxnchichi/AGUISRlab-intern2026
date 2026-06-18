import serial

import serial
import time
import keyboard

# Configure the serial port (Change 'COM3' to match your Windows device)
port = 'COM7'
baud_rate = 9600

try:
    # Open the serial port
    with serial.Serial(port, baud_rate, timeout=1) as ser:
        print(f"Successfully opened {ser.name}")
        time.sleep(2) # Give the device a moment to initialize
        
        # Send data (must be encoded as bytes)
        # ser.write(b'Hello Device\r\n')
        # print("Data sent.")
        
        # Read the response
        while True:
            line = ser.readline()
            if line:
                # Decode the received bytes back to a string
                Data = line.decode('utf-8').strip()
                V1, V2 = Data.split(',')
                print(f"V FSR1:{V1} V FSR2: {V2}")
                # break
            if keyboard.is_pressed('q'):
                print("\nKey 'q' pressed. Stopping reception.")
                break
            
            
except serial.SerialException as e:
    print(f"Error opening or using port: {e}")
