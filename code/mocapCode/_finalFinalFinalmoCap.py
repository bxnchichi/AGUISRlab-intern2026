import time
import keyboard
import pandas as pd
import math
import numpy as np

from FinalFinalMocapCode import GloveData  # adjust import path to wherever GloveData class lives



def quaternion_to_euler_and_matrix(q, degrees=False):  # オイラー角と回転行列を取得
    w, x, y, z = q
    R = [
        [1 - 2 * (y**2 + z**2), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x**2 + z**2), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x**2 + y**2)],
    ]
    yaw = math.atan2(R[1][0], R[0][0])
    pitch = math.asin(-R[2][0])
    roll = math.atan2(R[2][1], R[2][2])
    eul = [yaw, pitch, roll]
    if degrees:
        eul = [math.degrees(angle) for angle in eul]
    return eul, R


# データの保存用リスト
collected_data = []

start_time = time.perf_counter()
last_display_time = start_time
glove_data = GloveData()  # runs mocap.run() internally

# every named hand-element position we want to log each tick
# (all are (x, y, z) tuples/arrays already computed inside the hand class)
HAND_ELEMENTS = [
    "pos",           # wrist
    "thumbPos",
    "indexPos",
    "middlePos",
    "upperPalmPos",
    "sidePalmPos",
    "thumbPalmPos",
]


try:
    while True:
        current_time = time.perf_counter()

        if current_time - last_display_time >= 0.009:  # 0.009秒間隔でモーキャプの値を取得
            last_display_time = current_time
            glove_data.run()  # updates glove_data.RightqHandData internally

            hand = glove_data.RightHandData
            if hand is None:
                # no valid skeleton this tick (occlusion / dropped frame) -- skip
                continue

            # 手首の姿勢クオータニオン (w, x, y, z) -- .orie is [x,y,z,w]
            quaternion = [hand.orie[3], hand.orie[0], hand.orie[1], hand.orie[2]]
            euler_angles_rad, rotation_matrix = quaternion_to_euler_and_matrix(quaternion)

            elements = {name: np.array(getattr(hand, name)) for name in HAND_ELEMENTS}

            print('\rtime', '{:5.2f}'.format(current_time - start_time), '[s]',
                  '{:5.2f}'.format(hand.pos[0]), '[m]',
                  '{:5.2f}'.format(hand.pos[1]), '[m]',
                  '{:5.2f}'.format(hand.pos[2]), '[m]',
                  '{:5.2f}'.format(hand.orie[0]),
                  '{:5.2f}'.format(hand.orie[1]),
                  '{:5.2f}'.format(hand.orie[2]),
                  '{:5.2f}'.format(hand.orie[3]),
                  end='')

            elapsed_time = current_time - start_time
            row = {
                "time": elapsed_time,
                "world_time": current_time,
            }
            for name, pos in elements.items():
                row["%s_x[mm]" % name] = pos[0] * 1000
                row["%s_y[mm]" % name] = pos[1] * 1000
                row["%s_z[mm]" % name] = pos[2] * 1000

            row.update({
                "Wrist_qx": hand.orie[0],
                "Wrist_qy": hand.orie[1],
                "Wrist_qz": hand.orie[2],
                "Wrist_qw": hand.orie[3],
                "Wrist_yaw[rad]": euler_angles_rad[0],
                "Wrist_pitch[rad]": euler_angles_rad[1],
                "Wrist_roll[rad]": euler_angles_rad[2]
            })
            collected_data.append(row)

        if keyboard.is_pressed('q'):
            print("\nKey 'q' pressed. Stopping reception.")
            break


except KeyboardInterrupt:
    print("\nProgram interrupted by Ctrl+C.")

finally:
    # NatNetClient spins up two non-daemon threads (data_thread, command_thread)
    # that loop forever until told to stop -- without this, the process hangs
    # after the CSV is written instead of actually exiting.
    glove_data.mocap.streamingClient.shutdown()
 
df = pd.DataFrame(collected_data)
df.to_csv("synchronized_hand_data.csv", index=False)
print("Data saved to synchronized_hand_data.csv.")
 