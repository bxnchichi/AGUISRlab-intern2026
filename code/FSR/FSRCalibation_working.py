import socket
import struct
import time
import select
import keyboard
import pandas as pd
import math
import numpy as np
import serial


# UDP通信の設定
UDP_IP = "127.0.0.1"
UDP_PORT = 12345

# Configure the serial port for Leptrino force-torque sensor (Change 'COM3' to match your Windows device)
port = 'COM8'
baud_rate = 9600

# ソケットの作成
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

# Serial communication with Arduino (See in device maneger for port)
port = 'COM7'
baud_rate = 9600
loopTime = 0.112 #program loop time



def lowpass_filter(prev_data, current_data, cutoff_freq, sample_freq):
    # フィルタ係数 alpha の計算
    dt = 1 / sample_freq  # サンプリング周期
    alpha = dt / (dt + 1 / (2 * math.pi * cutoff_freq))  # カットオフ周波数に基づく係数

    # フィルタの適用
    filtered_data = alpha * current_data + (1 - alpha) * prev_data
    
    return filtered_data

# データの保存用リスト
collected_data = []  # 'data'を避けて、格納用のリスト変数名を変更

# UDPでデータ受信
start_time = time.perf_counter()
last_display_time = start_time
latest_data = None
cutoff_frequency = 5  # カットオフ周波数 5Hz
sampling_frequency = 100  # サンプリング周波数 100Hz
prev_x = 0.0
prev_y = 0.0
prev_z = 0.0
count = 0
judge = 0.2
touch = None
prevLine = None

try:
    ser = serial.Serial(port, baud_rate, timeout=1)
    print(f"Successfully opened {ser.name}")
    time.sleep(2) # Give the device a moment to initialize
    while True:
        # Read Leptrino
        readable, _, _ = select.select([sock], [], [], 0.001)
        if sock in readable:
            # UDPデータの受信（bytes型）
            udp_data, addr = sock.recvfrom(1024)
            latest_data = struct.unpack('7d', udp_data)

        # Read Arduino
        if  ser.in_waiting:
            line = ser.readline().decode('utf-8', errors='ignore').strip()

        current_time = time.perf_counter()

        if current_time - last_display_time >= 0.009:#0.009秒間隔でモーキャプの値と最新のセンサの値を取得
            last_display_time = current_time

            if line == prevLine:
                continue
            if line:
                V1, V2, V3, V4, V5, V6, unit = line.split(',')
            else:
                continue

            if latest_data is not None:
                # Leptrino Force Sensor
                Fx = latest_data[1]
                Fy = latest_data[2]
                Fz = latest_data[3]
                LPF_Fx = lowpass_filter(prev_x, Fx, cutoff_frequency, sampling_frequency)
                LPF_Fy = lowpass_filter(prev_y, Fy, cutoff_frequency, sampling_frequency)
                LPF_Fz = lowpass_filter(prev_z, Fz, cutoff_frequency, sampling_frequency)
                prev_x = LPF_Fx
                prev_y = LPF_Fy
                prev_z = LPF_Fz
                force_magnitude = math.sqrt(LPF_Fx**2+LPF_Fy**2+LPF_Fz**2)
                if force_magnitude > judge:#線を引いてる回数の判定
                    if touch == None:
                        count = count + 1
                    touch = count
                else:
                    touch = None

                # FSR glove
                V1 = float(V1)
                V2 = float(V2)
                V3 = float(V3)
                V4 = float(V4)
                V5 = float(V5)
                V6 = float(V6)

                

                
                print(f'\rtime {current_time - start_time:.2f} [s], Force: Fx={latest_data[1]:.2f}, Fy={latest_data[2]:.2f}, Fz={latest_data[3]:.2f}, FMagn = {force_magnitude:.2f}', 
                      f'FSR Voltage[{unit}]: V_SidePalm={V1:.2f}, V_ThumbPalm={V2:.2f}, V_UpperPalm={V3:.2f}, V_Middle={V4:.2f}, V_Index={V5:.2f}, V_Thumb={V6:.2f}', 
                      end='')

                # Combine Data
                elapsed_time = current_time - start_time
                row = {

                    "time": elapsed_time,
                    "world_time": current_time,
                    "Fx": Fx,
                    "Fy": Fy,
                    "Fz": -1*Fz,#(compression +)Z方向は，圧縮を正にするためにマイナスをかけている
                    "LPF_Fx": LPF_Fx,
                    "LPF_Fy": LPF_Fy,
                    "LPF_Fz": -1*LPF_Fz,
                    "Mx": latest_data[4],
                    "My": latest_data[5],
                    "Mz": latest_data[6],
                    "force_magnitude": force_magnitude,
                    "touch_count": touch,
                    f"V_SidePalm[{unit}]" : V1, # red wire
                    f"V_ThumbPalm[{unit}]" : V2, # yellow wire
                    f"V_UpperPalm[{unit}]" : V3, # green wire
                    f"V_Middle[{unit}]" : V4, # blue wire
                    f"V_Index[{unit}]" : V5, # blue wire with male jumper head
                    f"V_Thumb[{unit}]" : V6, # black wire
                }
                collected_data.append(row)  # 格納用リストに追加

                line = prevLine

        if keyboard.is_pressed('q'):
            print("\nKey 'q' pressed. Stopping reception.")
            break

except KeyboardInterrupt:
    print("\nProgram interrupted by Ctrl+C.")
except serial.SerialException as e:
    print(f"Error opening or using port: {e}")
finally:
    sock.close()

# CSVファイルに保存
df = pd.DataFrame(collected_data)
filename = "Data/FSRCalibration/TestInfo3/Testinfo6.csv"
# filename = "Data/FSRCalibration/TryStaticData3/TryStaticSensor6.csv"
df.to_csv(filename, index=False)
print(f"Data saved to {filename}")

# qqqqqq