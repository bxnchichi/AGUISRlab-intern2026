#include "00Library.hpp"
#include "01Constant.hpp"

//-----------------------------------------------------------------------------------------------------------------------------------------
//  ____        _                   _ _               
// / ___| _   _| |__  ___  ___ _ __(_) |__   ___ _ __ 
// \___ \| | | | '_ \/ __|/ __| '__| | '_ \ / _ \ '__|
//  ___) | |_| | |_) \__ \ (__| |  | | |_) |  __/ |   
// |____/ \__,_|_.__/|___/\___|_|  |_|_.__/ \___|_|   
//-----------------------------------------------------------------------------------------------------------------------------------------

//subscribeするときのリスナー準備
class positionsubscribe{
    public:
        geometry_msgs::TwistStamped data;
        positionsubscribe(){
            data.header.stamp = ros::Time::now();
        }
        void callback(const geometry_msgs::TwistStamped &msg){
            this->data = msg;
            glo_position_feedback = msg;
        }
};

class EEFListener{
    public:
        geometry_msgs::PoseStamped data;
        EEFListener(){
            data.header.stamp = ros::Time::now();
        }
        void callback(const geometry_msgs::PoseStamped &msg){
            this->data = msg;
        }
};

// listener for force-torque sensor change coordinate
// sensor X-axis to Robot Y-axis
// sensor Y-axis to Robot -X-axis
class CanonListener{
    public:
        geometry_msgs::WrenchStamped data;
        CanonListener(){
            data.header.stamp = ros::Time::now();
        }
        void callback(const geometry_msgs::WrenchStamped &msg){
            // センサ座標からロボット座標に変換（dataのxはｙの値が入り、data yにはｘのマイナスの値が入る）
            // z方向は圧縮力にする（−１をかける）
            double kore;
            this->data = msg;
            kore = this->data.wrench.force.x;
            this->data.wrench.force.x = this->data.wrench.force.y;
            this->data.wrench.force.y = kore * (-1.0);
            kore = this->data.wrench.torque.x;
            this->data.wrench.torque.x = this->data.wrench.torque.y;
            this->data.wrench.torque.y = kore * (-1.0);
            this->data.wrench.force.z = this->data.wrench.force.z * (-1.0);
            // glo_force_torque_calibrated = msg;
            glo_raw_force = msg.wrench;
        }
};

class CoordinatedForceTorqueListener{
    public:
        geometry_msgs::WrenchStamped data;
        CoordinatedForceTorqueListener(){
            data.header.stamp = ros::Time::now();
        }
        void callback(const geometry_msgs::WrenchStamped &msg){
            //手先角度が変わってもロボットベース座標系に合わせるもの
            // z方向は圧縮力にする（−１をかける）
            //probably Force in Z axis into the compression force which + is pushing and - is pulling
        
            this->data = msg;
            this->data.wrench.force.z = this->data.wrench.force.z * (-1.0);
            glo_force_torque_calibrated = msg;
        }
};

class skeletonRTListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};

class skeletonLTListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};

class skeletonRLListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};

class skeletonLLListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};

class skeletonRGListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};

class skeletonLGListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};

class skeletonHEListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};

class skeletonNEListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};

class skeletonTOListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};

class skeletonCHListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};

class skeletonRSListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};

class skeletonLSListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};

class skeletonLCListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};

class skeletonRHListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};

class skeletonLHListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};

class skeletonRKListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};

class skeletonLKListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};

class skeletonRAListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};

class skeletonLAListener{
    public:
        geometry_msgs::Pose data;
        void callback(const geometry_msgs::Pose &msg){
            this->data = msg;
        }
};
