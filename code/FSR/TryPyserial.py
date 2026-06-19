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
loopTime = 0.112
collected_data = []
limit = []



cutoff_frequency = 5 # カットオフ周波数 5Hz
sampling_frequency = 100  # サンプリング周波数 100Hz


import numpy as np

class KalmanCA:

    def __init__(self,
                 measurement_variance,
                 process_variance=100.0,
                 dt=0.111):

        self.dt = dt

        # State:
        # [position, velocity, acceleration]
        self.x = np.zeros(3)

        self.P = np.eye(3)

        self.F = np.array([
            [1, dt, 0.5*dt**2],
            [0,  1,        dt],
            [0,  0,         1]
        ])

        self.H = np.array([
            [1, 0, 0]
        ])

        self.Q = process_variance * np.array([
            [dt**5/20, dt**4/8, dt**3/6],
            [dt**4/8,  dt**3/3, dt**2/2],
            [dt**3/6,  dt**2/2, dt]
        ])

        self.R = np.array([
            [measurement_variance]
        ])

        self.initialized = False

        self.prev_measurement = None
        self.prev_velocity = 0

    def update(self, measurement):

        # Better initialization
        if not self.initialized:

            self.x[0] = measurement

            if self.prev_measurement is not None:

                velocity = (
                    measurement -
                    self.prev_measurement
                ) / self.dt

                acceleration = (
                    velocity -
                    self.prev_velocity
                ) / self.dt

                self.x[1] = velocity
                self.x[2] = acceleration

                self.prev_velocity = velocity

            self.prev_measurement = measurement

            self.initialized = True

            return (
                self.x[0],
                self.x[1],
                self.x[2]
            )

        # Prediction
        self.x = self.F @ self.x

        self.P = (
            self.F @ self.P @ self.F.T
            + self.Q
        )

        # Innovation
        y = measurement - (self.H @ self.x)[0]

        S = (
            self.H @ self.P @ self.H.T
            + self.R
        )

        K = (
            self.P @ self.H.T
            @ np.linalg.inv(S)
        )

        # Update
        self.x = self.x + (K.flatten() * y)

        self.P = (
            np.eye(3)
            - K @ self.H
        ) @ self.P

        return (
            self.x[0],  # filtered signal
            self.x[1],  # velocity
            self.x[2]   # acceleration
        )


try:
    # Open the serial port
    with serial.Serial(port, baud_rate, timeout=1) as ser:
        print(f"Successfully opened {ser.name}")
        time.sleep(2) # Give the device a moment to initialize
        


        # Send data (must be encoded as bytes)
        # ser.write(b'Hello Device\r\n')
        # print("Data sent.")
        prevV1 = 0
        prevV2 = 0
        # Kalman Filter init
        kf1 = KalmanCA(
            measurement_variance=0.822675735,
            process_variance=100.0,
            dt=loopTime
        )

        kf2 = KalmanCA(
            measurement_variance=1.085178137,
            process_variance=100.0,
            dt=loopTime
        )
        # Read the response
        while True:
            line = ser.readline()
            if line:
                # Decode the received bytes back to a string
                Data = line.decode('utf-8').strip()
                V1, V2, unit = Data.split(',')
                V1 = float(V1)
                V2 = float(V2)
                #update Kalman
                V1_kf, V1_rate, V1_accel = kf1.update(V1)
                V2_kf, V2_rate, V2_accel = kf2.update(V2)   
                # calculate Sampling Frequency
                byte = len(Data) + 2
                Time = (byte*10)/baud_rate + loopTime
                freqS = 1/Time
                # print(freqS)
                print(f"V FSR1:{V1} V FSR2: {V2}")
                row = {
                    f"V_FSR1[{unit}]" : V1,
                    f"V_FSR2[{unit}]" : V2,
                    f"V_FSR1_Kalman[{unit}]" : V1_kf,
                    f"V_FSR2_Kalman[{unit}]" : V2_kf
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

