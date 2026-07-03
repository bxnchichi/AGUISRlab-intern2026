import serial
import time
import keyboard
import pandas as pd
import math
from scipy.signal import butter, filtfilt
import numpy as np
import matplotlib.pyplot as plt

# Configure the serial port (Change 'COM3' to match your Windows device)
port = 'COM7'
baud_rate = 9600
loopTime = 0.185
collected_data = []
limit = []

cutoff_frequency = 5 # カットオフ周波数 5Hz
sampling_frequency = 100  # サンプリング周波数 100Hz


def threshold_reach(sensor_id, value, thresholds):
    return float(value) * (float(value) >= thresholds[sensor_id - 1])

try:
    # Open the serial port
    with serial.Serial(port, baud_rate, timeout=1) as ser:
        print(f"Successfully opened {ser.name}")
        time.sleep(2) # Give the device a moment to initialize
        
        # Send data (must be encoded as bytes)
        # ser.write(b'Hello Device\r\n')
        # print("Data sent.")
        # prevV1 = 0
        # prevV2 = 0
        # Read the response
        while True:
            line = ser.readline()
            if line:
                # Decode the received bytes back to a string
                Data = line.decode('utf-8').strip()
                V1, V2, V3, V4, V5, V6, unit = Data.split(',')
                V1 = float(V1)
                V2 = float(V2)
                V3 = float(V3)
                V4 = float(V4)
                V5 = float(V5)
                V6 = float(V6)
                # calculate Sampling Frequency
                byte = len(Data) + 2
                Time = (byte*10)/baud_rate + loopTime
                freqS = 1/Time
                # print(freqS)
                # print(f"V_SidePalm: {V1}, V_ThumpPalm: {V2}, V_UpperPalm: {V3}, V_Middle: {V4}, V_Index: {V5}, V_Thump: {V6}")
                print('\rFSR Voltage[mV]:', 
                'V_SidePalm={:5.2f}, V_ThumpPalm={:5.2f}, V_UpperPalm={:5.2f}, V_Middle={:5.2f}, V_Index={:5.2f}, V_Thump={:5.2f}'.format(V1, V2, V3, V4, V5, V6),
                end='        ')
                row = {
                    f"V_SidePalm[{unit}]" : V1, # red wire
                    f"V_ThumpPalm[{unit}]" : V2, # yellow wire
                    f"V_UpperPalm[{unit}]" : V3, # green wire
                    f"V_Middle[{unit}]" : V4, # blue wire
                    f"V_Index[{unit}]" : V5, # blue wire with male jumper head
                    f"V_Thumb[{unit}]" : V6, # black wire
                }
                collected_data.append(row)
                # break
            if keyboard.is_pressed('q'):
                print("\nKey 'q' pressed. Stopping reception.")
                break
    df = pd.DataFrame(collected_data)
    # b, a = butter(4, cutoff_frequency/(12/2), btype='low')
    # df["FSR1_filtered"] = filtfilt(b, a, df[f"V_FSR1[{unit}]"])
    # df["FSR2_filtered"] = filtfilt(b, a, df[f"V_FSR2[{unit}]"])

    df.to_csv("synchronized_data.csv", index=False)
    print("Data saved to synchronized_data.csv.")
                
            
except serial.SerialException as e:
    print(f"Error opening or using port: {e}")

