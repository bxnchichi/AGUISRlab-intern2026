import socket
import struct
import time
import select
import keyboard
import pandas as pd
import math
import numpy as np


# UDP通信の設定
UDP_IP = "127.0.0.1"
UDP_PORT = 12345

# ソケットの作成
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

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

try:
    while True:
        readable, _, _ = select.select([sock], [], [], 0.001)

        if sock in readable:
            # UDPデータの受信（bytes型）
            udp_data, addr = sock.recvfrom(1024)
            latest_data = struct.unpack('7d', udp_data)

        current_time = time.perf_counter()

        if current_time - last_display_time >= 0.009:#0.009秒間隔でモーキャプの値と最新のセンサの値を取得
            last_display_time = current_time
    
            
            if latest_data is not None:
                # quaternion = [mocap_data2.penori[3],mocap_data2.penori[0],mocap_data2.penori[1],mocap_data2.penori[2],]  # クオータニオン (w, x, y, z)
                # euler_angles_rad, rotation_matrix = quaternion_to_euler_and_matrix(quaternion)  # ラジアンでオイラー角と回転行列を計算
                # # 回転行列をnumpy配列に変換
                # rotation_matrix_np = np.array(rotation_matrix)
                # er = np.array([0, 0, 0.16])#ペン状座標系からみたペン先ベクトル＝rigid_bodyとペン先の位置関係
                # pe = np.array([mocap_data2.penpos[0], mocap_data2.penpos[1], mocap_data2.penpos[2]])#rigid_bodyの位置ベクトル
                # r = np.dot(rotation_matrix_np, er) + pe#rは基準座標系から見たペン先位置

                # g = er = np.array([0, 0, -m*9.81])
                # transpose_rotation_matrix_np = rotation_matrix_np.T#回転行列の転置
                # eg = np.dot(transpose_rotation_matrix_np, g) #差し引く重力成分

                ##ローパスフィルタ

                Fx = latest_data[1]
                Fy = latest_data[2]
                Fz = latest_data[3]
                LPF_Fx = lowpass_filter(prev_x, Fx, cutoff_frequency, sampling_frequency)
                LPF_Fy = lowpass_filter(prev_y, Fy, cutoff_frequency, sampling_frequency)
                LPF_Fz = lowpass_filter(prev_z, Fz, cutoff_frequency, sampling_frequency)
                prev_x = LPF_Fx
                prev_y = LPF_Fy
                prev_z = LPF_Fz
                # Fcx = Fx - eg[0]#重力成分の差し引き
                # Fcy = Fy - eg[1]
                # Fcz = Fz - eg[2]
                # LPF_Fcx = LPF_Fx - eg[0]
                # LPF_Fcy = LPF_Fy - eg[1]
                # LPF_Fcz = LPF_Fz - eg[2]

                force_magnitude = math.sqrt(LPF_Fx**2+LPF_Fy**2+LPF_Fy**2)
                if force_magnitude > judge:#線を引いてる回数の判定
                    if touch == None:
                        count = count + 1
                    touch = count
                else:
                    touch = None
                
                # #ペン先速度の算出
                # velo_x = (r[0] - pensaki_prex)*1000/0.01
                # velo_y = (r[1] - pensaki_prey)*1000/0.01
                # velo_z = (r[2] - pensaki_prez)*1000/0.01
                # velo_xyz = math.sqrt((r[0] - pensaki_prex)**2+(r[1] - pensaki_prey)**2+(r[2] - pensaki_prez)**2)*1000/0.01
                # pensaki_prex = r[0]
                # pensaki_prey = r[1]
                # pensaki_prez = r[2]

                # #headとの相対距離
                # pensaki_reretive_x = (r[0] - mocap_data2.headpos[0])*1000
                # pensaki_reretive_y = (r[1] - mocap_data2.headpos[1])*1000
                # pensaki_reretive_z = (r[2] - mocap_data2.headpos[2])*1000

                # # センサデータを表示
                # print('\rtime', '{:5.2f}'.format(current_time - start_time), '[s]',
                # '{:5.2f}'.format(mocap_data2.penpos[0]), '[m]',
                # '{:5.2f}'.format(mocap_data2.penpos[1]), '[m]',
                # '{:5.2f}'.format(mocap_data2.penpos[2]), '[m]',
                # '{:5.2f}'.format(mocap_data2.penori[0]),
                # '{:5.2f}'.format(mocap_data2.penori[1]),
                # '{:5.2f}'.format(mocap_data2.penori[2]),
                # '{:5.2f}'.format(mocap_data2.penori[3]),
                # 'Force: Fx={:5.2f}, Fy={:5.2f}, Fz={:5.2f}'.format(latest_data[1], latest_data[2], latest_data[3]),
                # end='')

                # モーションキャプチャデータとセンサデータを統合
                elapsed_time = current_time - start_time
                row = {

                    "time": elapsed_time,
                    "world_time": current_time,
                    # "Penpos_x[mm]": mocap_data2.penpos[0]*1000,
                    # "Penpos_y[mm]": mocap_data2.penpos[1]*1000,
                    # "Penpos_z[mm]": mocap_data2.penpos[2]*1000,
                    # "Pensaki_x[mm]": r[0]*1000,
                    # "Pensaki_y[mm]": r[1]*1000,
                    # "Pensaki_z[mm]": r[2]*1000,
                    # "Pensaki_relative_x[mm]": pensaki_reretive_x,
                    # "Pensaki_relative_y[mm]": pensaki_reretive_y,
                    # "Pensaki_relative_z[mm]": pensaki_reretive_z,
                    # "velo_x[mm/s]": velo_x,
                    # "velo_y[mm/s]": velo_y,
                    # "velo_z[mm/s]": velo_z,
                    # "velo_xyz[mm/s]": velo_xyz,
                    # "Pen_qx": mocap_data2.penori[0],
                    # "Pen_qy": mocap_data2.penori[1],
                    # "Pen_qz": mocap_data2.penori[2],
                    # "Pen_qw": mocap_data2.penori[3],
                    # "Pen_yaw[rad]": euler_angles_rad[0],
                    # "Pen_pitch[rad]": euler_angles_rad[1],
                    # "Pen_roll[rad]": euler_angles_rad[2],
                    # "Headpos_x[mm]": mocap_data2.headpos[0]*1000,
                    # "Headpos_y[mm]": mocap_data2.headpos[1]*1000,
                    # "Headpos_z[mm]": mocap_data2.headpos[2]*1000,
                    # "Headori_0": mocap_data2.headori[0],
                    # "Headori_1": mocap_data2.headori[1],
                    # "Headori_2": mocap_data2.headori[2],
                    # "Headori_3": mocap_data2.headori[3],
                    "Fx": Fx,
                    "Fy": Fy,
                    "Fz": -1*Fz,#Z方向は，圧縮を正にするためにマイナスをかけている
                    "LPF_Fx": LPF_Fx,
                    "LPF_Fy": LPF_Fy,
                    "LPF_Fz": -1*LPF_Fz,
                    "Mx": latest_data[4],
                    "My": latest_data[5],
                    "Mz": latest_data[6],
                    # "Fcx": Fcx,
                    # "Fcy": Fcy,
                    # "Fcz": -1*Fcz,
                    # "LPF_Fcx": LPF_Fcx,
                    # "LPF_Fcy": LPF_Fcy,
                    # "LPF_Fcz": -1*LPF_Fcz,
                    # "egx": eg[0],
                    # "egy": eg[1],
                    # "egz": eg[2],
                    "force_magnitude": force_magnitude,
                    "touch_count": touch,
                }
                collected_data.append(row)  # 格納用リストに追加

        if keyboard.is_pressed('q'):
            print("\nKey 'q' pressed. Stopping reception.")
            break

except KeyboardInterrupt:
    print("\nProgram interrupted by Ctrl+C.")
finally:
    sock.close()

# CSVファイルに保存
df = pd.DataFrame(collected_data)
df.to_csv("synchronized_data.csv", index=False)
print("Data saved to synchronized_data.csv.")