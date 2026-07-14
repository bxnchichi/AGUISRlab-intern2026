# -*- coding : UTF-8 -*-
#Copyright © 2018 Naturalpoint
#
#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at
#
#http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.


# OptiTrack NatNet direct depacketization sample for Python 3.x
#
# Uses the Python NatNetClient.py library to establish a connection (by creating
# a NatNetClient), and receive data via a NatNet connection, decoding it with the
# NatNetClient/MoCapData/DataDescriptions libraries, and extracting skeleton
# (rigid-body-chain) data frame by frame.

from NatNetClient import NatNetClient
import DataDescriptions
import MoCapData
import time


class SkeletonExtractor:
    def __init__(self):
        # --- connection settings (match mocaptodata.py style) ---
        self.server_ip_address = "127.0.0.1"
        self.local_ip_address = "127.0.0.1"
        self.use_multicast = True

        self.streamingClient = NatNetClient()
        self.streamingClient.server_ip_address = self.server_ip_address
        self.streamingClient.local_ip_address = self.local_ip_address
        self.streamingClient.use_multicast = self.use_multicast

        # new_frame_with_data_listener hands us the fully decoded MoCapData
        # object (data_dict["mocap_data"]), which is what carries skeleton_data.
        self.streamingClient.new_frame_with_data_listener = self.onNewFrameWithData

        # Optional: still expose the per-rigid-body callback in case you also
        # want loose (non-skeleton) rigid bodies, same as mocaptodata.py.
        self.streamingClient.rigid_body_listener = self.onRigidBodyReceived

        # Fires once a Data Description packet arrives, giving us bone
        # (rigid body) id -> name mappings so we can look bones up by name
        # (e.g. "LeftHand" / "RightHand") instead of by raw numeric id.
        self.streamingClient.model_definitions_listener = self.onModelDefinitions

        # id_num (bone/rigid body id) -> name, filled in once a data
        # description packet has been received (see request_data_descriptions).
        self.bone_names = {}

        # skeleton_id -> { bone_id: {"pos": [...], "rot": [...] } }
        self.skeletons = {}

        self.frame_number = 0

    # ------------------------------------------------------------------
    # Listeners
    # ------------------------------------------------------------------
    def onRigidBodyReceived(self, id, position, rotation):
        # Left in place for parity with mocaptodata.py; not used for
        # skeleton extraction since skeleton bones arrive via the
        # new_frame_with_data_listener below.
        pass

    def onModelDefinitions(self, data_descriptions):
        """Called once (per request) with a DataDescriptions.DataDescriptions
        object. Populates self.bone_names with id_num -> bone name for every
        bone in every described skeleton."""
        self.set_bone_names_from_description(data_descriptions)

    def onNewFrameWithData(self, data_dict):
        """Called once per frame. data_dict["mocap_data"] is a
        MoCapData.MoCapData instance whose .skeleton_data attribute is a
        MoCapData.SkeletonData holding one MoCapData.Skeleton per tracked
        skeleton asset, each of which holds a list of MoCapData.RigidBody
        (the bones)."""
        self.frame_number = data_dict.get("frame_number", self.frame_number)

        mocap_data = data_dict.get("mocap_data")
        if mocap_data is None:
            return

        skeleton_data = mocap_data.skeleton_data
        if skeleton_data is None:
            return

        self.extract_skeleton_data(skeleton_data)

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------
    def extract_skeleton_data(self, skeleton_data):
        """Populate self.skeletons from a MoCapData.SkeletonData object."""
        current_frame = {}

        for skeleton in skeleton_data.skeleton_list:
            skeleton_id = skeleton.id_num
            bones = {}

            for bone_num, rigid_body in enumerate(skeleton.rigid_body_list):
                bone_name = self.bone_names.get(rigid_body.id_num)
                bones[rigid_body.id_num] = {
                    "bone_index": bone_num,
                    "name": bone_name,
                    "pos": rigid_body.pos,
                    "rot": rigid_body.rot,
                    "tracking_valid": rigid_body.tracking_valid,
                    "error": rigid_body.error,
                }

            current_frame[skeleton_id] = bones

        self.skeletons = current_frame

    # ------------------------------------------------------------------
    # Optional: bone-name lookup via Data Descriptions
    # ------------------------------------------------------------------
    def request_data_descriptions(self):
        """Ask the server for its data descriptions (marker sets, rigid
        bodies, skeletons, etc). NatNetClient prints these out itself; this
        also gives us a chance to remember bone id -> bone name so
        extract_skeleton_data() can attach names to each bone."""
        self.streamingClient.send_request(
            self.streamingClient.command_socket,
            self.streamingClient.NAT_REQUEST_MODELDEF,
            "",
            (self.streamingClient.server_ip_address,
             self.streamingClient.command_port),
        )

    def set_bone_names_from_description(self, data_descriptions):
        """If you capture a DataDescriptions.DataDescriptions object
        (e.g. by extending NatNetClient with your own model-definition
        listener), pass it here to populate self.bone_names so future
        frames include readable bone names."""
        for skeleton_desc in data_descriptions.skeleton_list:
            for rb_desc in skeleton_desc.rigid_body_description_list:
                self.bone_names[rb_desc.id_num] = rb_desc.sz_name

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------
    def get_skeleton(self, skeleton_id):
        """Return {bone_id: {pos, rot, ...}} for one skeleton, or None."""
        return self.skeletons.get(skeleton_id)

    def get_bone(self, skeleton_id, bone_id):
        skeleton = self.get_skeleton(skeleton_id)
        if skeleton is None:
            return None
        return skeleton.get(bone_id)

    def get_all_skeletons(self):
        """Return the full {skeleton_id: {bone_id: {...}}} snapshot."""
        return self.skeletons

    def get_bone_by_name(self, skeleton_id, name_substring):
        """Find a bone whose name contains name_substring (case-insensitive),
        e.g. get_bone_by_name(0, "LeftHand"). Requires bone names to have
        been populated via request_data_descriptions()/onModelDefinitions.
        Returns the bone dict, or None if not found / names not yet known."""
        skeleton = self.get_skeleton(skeleton_id)
        if skeleton is None:
            return None
        needle = name_substring.lower()
        for bone in skeleton.values():
            if bone["name"] and needle in bone["name"].lower():
                return bone
        return None

    def get_hand_positions(self, skeleton_id):
        """Convenience helper: returns {"left": pos_or_None, "right": pos_or_None}
        for the given skeleton, using bone names. Position is a [x, y, z]
        list in the same units/coordinate system as the rest of the stream.
        Returns None entries if bone names haven't been resolved yet (call
        request_data_descriptions() once after run() and give it a moment
        to arrive), or if this skeleton doesn't expose hand bones."""
        left = self.get_bone_by_name(skeleton_id, "LeftHand") or \
            self.get_bone_by_name(skeleton_id, "LHand")
        right = self.get_bone_by_name(skeleton_id, "RightHand") or \
            self.get_bone_by_name(skeleton_id, "RHand")
        return {
            "left": left["pos"] if left else None,
            "right": right["pos"] if right else None,
        }

    # ------------------------------------------------------------------
    def run(self):
        is_running = self.streamingClient.run()
        if not is_running:
            print("ERROR: Could not start streaming client.")
            return False

        time.sleep(1)
        if self.streamingClient.connected() is False:
            print("ERROR: Could not connect properly. Check the connection "
                  "settings (server_ip_address / local_ip_address / "
                  "use_multicast).")
            return False

        # Ask the server for bone names right away so hand/other named
        # lookups work as soon as skeleton frames start arriving.
        self.request_data_descriptions()

        return True


if __name__ == '__main__':
    extractor = SkeletonExtractor()
    if extractor.run():
        try:
            while True:
                time.sleep(0.1)
                for skeleton_id, bones in extractor.get_all_skeletons().items():
                    print("Skeleton %d - %d bones" % (skeleton_id, len(bones)))
                    for bone_id, bone in bones.items():
                        print("  bone %s (%s) pos=%s rot=%s" % (
                            bone_id, bone["name"], bone["pos"], bone["rot"]))
                    hands = extractor.get_hand_positions(skeleton_id)
                    print("  left hand :", hands["left"])
                    print("  right hand:", hands["right"])
        except KeyboardInterrupt:
            pass