import time
from NatNetClient import NatNetClient

def check_bone(data_descs):
    print("Skeletons found:")

    for skeleton in data_descs.skeleton_list:
        print("Skeleton:", skeleton.name)

        for rb in skeleton.rigid_body_description_list:
            print(rb.id_num, rb.name, rb.parent_id)

if __name__ == "__main__":
    client = NatNetClient()
    client.local_ip_address = "127.0.0.1"
    client.server_ip_address = "127.0.0.1"
    client.use_multicast = True
    
    # Assign the structural description callback listener
    client.data_description_listener = check_bone
    
    print("Listening for Motive structural definitions...")
    client.run()
    
    # Keep main execution thread alive long enough to catch the broadcast packet
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        client.shutdown()