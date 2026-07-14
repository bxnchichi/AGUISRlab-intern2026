import time
from NatNetClient import NatNetClient
# def discover_skeleton_ids(mocap_data):
#     """Callback function that prints visible skeleton details."""
#     if mocap_data.skeleton_data and mocap_data.skeleton_data.skeleton_list:
#         print("\n--- Active Skeletons Found in Stream ---")
#         for skel in mocap_data.skeleton_data.skeleton_list:
#             # skel.id_num is the ID you need for your tracker
#             print(f"Skeleton ID: {skel.id_num} | Contains {len(skel.rigid_body_list)} Bones/Segments")
#         print("----------------------------------------")
#         # Stop the client immediately after finding the IDs
#         client.shutdown()

# def discover_skeleton_ids(mocap_data):
#     # Print out a heartbeat heartbeat so you know frames are arriving
#     print(f"Received Packet - Frame: {mocap_data.frame_number}")
    
#     if mocap_data.skeleton_data and mocap_data.skeleton_data.skeleton_list:
#         print("\n--- Active Skeletons Found ---")
#         for skel in mocap_data.skeleton_data.skeleton_list:
#             print(f"-> Skeleton ID to use: {skel.id_num}")
#         print("------------------------------")
#         client.shutdown()

def discover_skeleton_ids(frame):
    mocap_data = frame["mocap_data"]
    print(f"Received Packet - Frame: {mocap_data.skeleton_data}")
    if mocap_data.skeleton_data:
        for skeleton in mocap_data.skeleton_data.skeleton_list:
            print("Skeleton ID:", skeleton.id_num)
        # client.shutdown()

if __name__ == "__main__":  
    client = NatNetClient()
    client.use_multicast = True
    client.local_ip_address = "127.0.0.1"
    client.server_ip_address = "127.0.0.1"
    
    # Hook up the discovery callback
    client.new_frame_with_data_listener = discover_skeleton_ids     
    
    print("Listening for Motive stream data packets...")

    client.run()
    
    time.sleep(0.006)
    client.shutdown()