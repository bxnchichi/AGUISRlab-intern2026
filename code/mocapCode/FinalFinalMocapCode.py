from SkeletonExtractor import SkeletonExtractor as Glove
import numpy as np
from scipy.spatial.transform import Rotation
import time
import keyboard
import serial
# from copy import deepcopy

FingerTipLength = 0.02


def point_along_bone(
    position,
    quaternion,
    prev_quaternion,
    distance,
    axis="x",
    min_angle=90,
    max_angle=200,
):
    """
    Calculate a fingertip point along a bone, choosing the direction
    (+axis or -axis) that best matches the angle constraint with
    the previous bone orientation.

    Parameters
    ----------
    position : (3,)
        Bone position.

    quaternion : (4,)
        Current bone quaternion [x, y, z, w].

    prev_quaternion : (4,)
        Previous bone quaternion [x, y, z, w].

    distance : float
        Offset distance.

    axis : str or array-like
        Local axis ("x", "y", "z") or custom vector.

    min_angle, max_angle : float
        Acceptable angle (degrees) between previous and current directions.

    Returns
    -------
    np.ndarray
        Tip position.

    float
        Selected angle (degrees).

    np.ndarray
        Selected world direction.
    """

    position = np.asarray(position, dtype=float)

    rot = Rotation.from_quat(quaternion)
    prev_rot = Rotation.from_quat(prev_quaternion)

    if isinstance(axis, str):
        axis = axis.lower()
        axis_map = {
            "x":  np.array([1, 0, 0]),
            "-x": np.array([-1, 0, 0]),
            "y":  np.array([0, 1, 0]),
            "-y": np.array([0, -1, 0]),
            "z":  np.array([0, 0, 1]),
            "-z": np.array([0, 0, -1]),
        }
        local_axis = axis_map[axis]
    else:
        local_axis = np.asarray(axis, dtype=float)
        local_axis /= np.linalg.norm(local_axis)

    # Previous bone direction
    prev_dir = prev_rot.apply(local_axis)

    # Candidate directions
    candidates = [
        rot.apply(local_axis),
        rot.apply(-local_axis)
    ]

    best_dir = None
    best_angle = None
    best_error = np.inf

    for d in candidates:
        d /= np.linalg.norm(d)

        angle = np.degrees(
            np.arccos(
                np.clip(np.dot(prev_dir, d), -1.0, 1.0)
            )
        )

        # Prefer directions inside the desired range
        if min_angle <= angle <= max_angle:
            error = 0
        else:
            error = min(abs(angle - min_angle), abs(angle - max_angle))

        if error < best_error:
            best_error = error
            best_angle = angle
            best_dir = d
    tip = position + distance * best_dir
    return tip

def _subtract_tuple(a, b):
    return tuple(np.asarray(a) - np.asarray(b))

class hand:
    def __init__(self, Skeleton):
        self.skele = dict(Skeleton) # Bones Dict
        self.pos = self.skele[min(self.skele)]["pos"] # position of Wrist
        self.orie = self.skele[min(self.skele)]["rot"] # orientation of Wrist
        self.startBoneID = sorted(self.skele)[1] # StartID of all bone data
        self.wrist_id = min(self.skele) # capture before _extract_finger_tip
        self._extract_finger_tip()
        self.thumbPos = self.skele[1000]
        self.indexPos = self.skele[1001]
        self.middlePos = self.skele[1002]
        self.upperPalmPos = self._extract_finger_palm(6, 9) # 6: MiddleFingerStart, 9: RingFingerStart
        self.sidePalmPos = self._extract_finger_palm(self.wrist_id - self.startBoneID, 12) 
        self.thumbPalmPos = self._extract_finger_palm(self.wrist_id - self.startBoneID, 0) 

    def _extract_finger_tip(self):
        for i in range(3):
            bone_id = self.startBoneID + 2 + 3*i
            # print(bone_id)
            self.skele[1000 + i] = tuple(map(float, point_along_bone(self.skele[bone_id]["pos"], self.skele[bone_id]["rot"], self.skele[bone_id-1]["rot"], FingerTipLength, axis = "x")))
    def _extract_finger_palm(self, Num1, Num2):
        pos1 = self.skele[self.startBoneID + Num1]['pos']
        pos2 = self.skele[self.startBoneID + Num2]['pos']
        return tuple((a + b) / 2 for a, b in zip(pos1, pos2))
    def __sub__(self, other):
        result = hand.__new__(hand)
        result.__dict__ = self.__dict__.copy()

        # Positions
        result.pos = _subtract_tuple(self.pos, other.pos)
        result.thumbPos = _subtract_tuple(self.thumbPos, other.thumbPos)
        result.indexPos = _subtract_tuple(self.indexPos, other.indexPos)
        result.middlePos = _subtract_tuple(self.middlePos, other.middlePos)
        result.upperPalmPos = _subtract_tuple(self.upperPalmPos, other.upperPalmPos)
        result.sidePalmPos = _subtract_tuple(self.sidePalmPos, other.sidePalmPos)
        result.thumbPalmPos = _subtract_tuple(self.thumbPalmPos, other.thumbPalmPos)

        # Relative orientation
        r_self = Rotation.from_quat(self.orie)
        r_other = Rotation.from_quat(other.orie)
        result.orie = (r_other.inv() * r_self).as_quat()

        return result
            

class GloveData:
    def __init__(self):
        self.mocap = Glove()
        self.start_time=time.perf_counter()
        self.initTime=time.perf_counter()
        self.end_time=0
        self.RightHandID = 0
        # self.LeftHandID = 1 (check before run)
        self.mocap.run()
        while True:
            self.RightHandSkeleton = self.mocap.get_skeleton(self.RightHandID)
            if self.RightHandSkeleton:
                break
            time.sleep(0.01)
        self.RightHandDataInit = hand(self.RightHandSkeleton)
        self.RightHandData = None
        
    def update(self):
        skeleton = self.mocap.get_skeleton(self.RightHandID)
        if not skeleton:
            return   # keep last good self.RightHandData
        self.RightHandSkeleton = skeleton
        self.RightHandData = hand(self.RightHandSkeleton) - self.RightHandDataInit
    def run(self):
        self.start_time=time.perf_counter()
        self.jikan=time.perf_counter()-self.initTime
        self.update()
        self.end_time=time.perf_counter()

