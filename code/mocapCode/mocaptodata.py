
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
# Uses the Python NatNetClient.py library to establish a connection (by creating a NatNetClient),
# and receive data via a NatNet connection and decode it using the NatNetClient library.

from NatNetClient import NatNetClient
# 0.ライブラリのインポートと変数定義
import socket
import struct
import numpy as np
import time

class simToReal:
    def __init__(self):
        self.target_ip = "192.168.7.5"
        self.target_port = 5027
        self.buffer_size = 4096
        self.data_buf=[]
        self.streamingClient=NatNetClient()
        # self.streamingClient.rigidBodyListener = self.onRigidBodyReceived
        # self.streamingClient.newFrameListener = self.onReceiveNewFrame
        self.streamingClient.rigid_body_listener = self.onRigidBodyReceived
        self.streamingClient.new_frame_listener = self.onReceiveNewFrame
        self.penpos=[0,0,0]
        self.penori=[0,0,0,0]
        self.penvel=0
        self.headpos=[0,0,0]
        self.headori=[0,0,0,0]
        self.penpos_pre=[0,0,0]
        self.ima=time.time()
# 1.ソケットオブジェクトの作成
        # self.tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# 2.サーバに接続
        # self.tcp_client.connect((self.target_ip,self.target_port))
    def onRigidBodyReceived(self, id, position, rotation):
        if id ==40:#pen
            self.penpos=(position)
            self.penori=(rotation)
            # self.penvel=self.velcal(self.penpos)
        elif id==41:
            self.headpos=(position)
            self.headori=(rotation)
          

        else:
            print("Unregistered rigidbody detected!")
        #print(self.penpos)
        
    # def onReceiveNewFrame(self, frameNumber, markerSetCount, unlabeledMarkersCount, rigidBodyCount, skeletonCount, labeledMarkerCount, timecode, timecodeSub, timestamp, isRecording, trackedModelsChanged):
    #     a=9
    # def onReceiveNewFrame(self, frame_number, marker_set_count, unlabeled_markers_count, rigid_body_count, skeleton_count, asset_count, labeled_marker_count, timecode, timecode_sub, timestamp, is_recording, tracked_models_changed):
    #     a=9
    def onReceiveNewFrame(self, data_dict):
        #frameNumber = data_dict["frame_number"]
        # markerSetCount = data_dict["marker_set_count"]
        # unlabeledMarkersCount = data_dict["unlabeled_markers_count"]
        # rigidBodyCount = data_dict["rigid_body_count"]
        #skeletonCount = data_dict["skeleton_count"]
        #labeledMarkerCount = data_dict["labeled_marker_count"]
        #timecode = data_dict["timecode"]
        #timecodeSub = data_dict["timecode_sub"]
        #timestamp = data_dict["timestamp"]
        #isRecording = data_dict["is_recording"]
        #trackedModelsChanged = data_dict["tracked_models_changed"]

        # 必要な処理
        pass


    
    
    def velcal(self,pen_now):
        vel=(pen_now[2]-self.penpos_pre[2])/(time.time()-self.ima)
        self.penpos_pre=pen_now
        self.ima=time.time()
        return vel
    
    def run(self):
        # time.sleep(0.01)
        #print(self.headpos)
        self.streamingClient.run()
# data=np.array([2.5415,3],dtype="double")

# send_data=data.view(np.uint8)
if __name__ == '__main__':
    g=simToReal()
    g.run()
# while True:
    # time.sleep(0.01)
    # print(g.penvel)
# print(send_data)
# 3.サーバにデータを送信
# while True:
    # try:
        # tcp_client.send(send_data)
        # response = tcp_client.recv(1)
        
    # except:
        # print("No")
        # break


