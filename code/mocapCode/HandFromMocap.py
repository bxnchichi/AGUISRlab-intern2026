import time
import math
import queue
from NatNetClient import NatNetClient
import MoCapData
# Right Hand ID = 0, Left Hand ID = 1
class SynchronizedFullHandTracker:
    def __init__(self, skeleton_id: int = 0, hand_bone_index: int = 1, local_ip: str = "127.0.0.1", server_ip: str = "127.0.0.1", use_multicast: bool = True):
        """
        Tracks the waist, upper hand spatial metrics, and all detailed finger kinematics.
        :param skeleton_id: The ID of the skeleton asset assigned in Motive.
        :param hand_bone_index: The specific bone index corresponding to the wrist/hand root.
        """
        self.skeleton_id = skeleton_id
        self.hand_bone_index = hand_bone_index
        self.local_ip = local_ip
        self.server_ip = server_ip
        self.use_multicast = use_multicast
        
        self.client = NatNetClient()
        self.client.local_ip_address = self.local_ip
        self.client.server_ip_address = self.server_ip
        self.client.use_multicast = self.use_multicast
        
        
        self.data_queue = queue.Queue()
    @staticmethod
    def _quaternion_to_euler(q):
        """Converts quaternion [qx, qy, qz, qw] to Euler degrees (Roll, Pitch, Yaw)."""
        qx, qy, qz, qw = q
        sinr_cosp = 2 * (qw * qx + qy * qz)
        cosr_cosp = 1 - 2 * (qx * qx + qy * qy)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        sinp = 2 * (qw * qy - qz * qx)
        pitch = math.copysign(math.pi / 2, sinp) if abs(sinp) >= 1 else math.asin(sinp)
        siny_cosp = 2 * (qw * qz + qx * qy)
        cosy_cosp = 1 - 2 * (qy * qy + qz * qz)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        return [math.degrees(roll), math.degrees(pitch), math.degrees(yaw)]
    def _extract_metrics(self, mocap_data: MoCapData.MoCapData):
        if not mocap_data.skeleton_data:
            return None
        # Find desired skeleton
        target_skeleton = None
        for skeleton in mocap_data.skeleton_data.skeleton_list:
            if skeleton.id_num == self.skeleton_id:
                target_skeleton = skeleton
                break
        if target_skeleton is None:
            return None
        if len(target_skeleton.rigid_body_list) == 0:
            return None
        # ------------------------
        # Waist (Root Bone)
        # ------------------------
        waist_bone = target_skeleton.rigid_body_list[0]
        waist_pos = waist_bone.pos
        waist_quat = waist_bone.rot
        # ------------------------
        # Hand
        # ------------------------
        hand_pos = [0.0, 0.0, 0.0]
        hand_quat = [0.0, 0.0, 0.0, 1.0]
        hand_euler = [0.0, 0.0, 0.0]
        if len(target_skeleton.rigid_body_list) > self.hand_bone_index:
            hand_bone = target_skeleton.rigid_body_list[self.hand_bone_index]
            hand_pos = list(hand_bone.pos)
            hand_quat = list(hand_bone.rot)      # [qx,qy,qz,qw]
            hand_euler = self._quaternion_to_euler(hand_quat)
        # ------------------------
        # Finger joints
        # ------------------------
        finger_joint_angles = {}
        for i, bone in enumerate(target_skeleton.rigid_body_list):
            # Skip waist and hand root
            if i == 0 or i == self.hand_bone_index:
                continue
            euler = self._quaternion_to_euler(bone.rot)
            finger_joint_angles[f"Bone_{i}_Roll"] = euler[0]
            finger_joint_angles[f"Bone_{i}_Pitch"] = euler[1]
            finger_joint_angles[f"Bone_{i}_Yaw"] = euler[2]
        # ------------------------
        # Flat record
        # ------------------------
        return {
            "Motive_Timestamp": time.time(),
            "Frame": mocap_data.frame_number,
            # Waist
            "Waist_X": waist_pos[0],
            "Waist_Y": waist_pos[1],
            "Waist_Z": waist_pos[2],
            "Waist_Qx": waist_quat[0],
            "Waist_Qy": waist_quat[1],
            "Waist_Qz": waist_quat[2],
            "Waist_Qw": waist_quat[3],
            # Hand Position
            "Hand_X": hand_pos[0],
            "Hand_Y": hand_pos[1],
            "Hand_Z": hand_pos[2],
            # Hand Quaternion
            "Hand_Qx": hand_quat[0],
            "Hand_Qy": hand_quat[1],
            "Hand_Qz": hand_quat[2],
            "Hand_Qw": hand_quat[3],
            # Hand Euler
            "Hand_Roll": hand_euler[0],
            "Hand_Pitch": hand_euler[1],
            "Hand_Yaw": hand_euler[2],
            # Finger Joints
            **finger_joint_angles,
        }
    def _internal_frame_callback(self, mocap_data: MoCapData.MoCapData):
        # print(type(mocap_data))
        # print(mocap_data)
        record = self._extract_metrics(mocap_data)
        if record:
            self.data_queue.put(record)
    def start(self):
        print(f"Connecting to Motive Stream ({self.server_ip})...")
        return self.client.run()
    def get_latest_data(self, block=False, timeout=None):
        try:
            return self.data_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None
    def stop(self):
        print("Stopping stream client...")
        self.client.shutdown()