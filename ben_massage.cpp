#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <wchar.h>
#include <vector>
#include <cstring>
#include <iostream> 
#include <fstream>
#include <sstream>
#include <algorithm>
#include <iomanip>
#include <cmath>
#include <thread>

#include <chrono>
#include <ctime>

#include <ros/ros.h>
#include <std_msgs/String.h>
#include <std_msgs/Float64.h>
#include <std_msgs/Int32MultiArray.h>
#include <std_msgs/Float32MultiArray.h>
#include <std_msgs/Int32.h>
#include <std_srvs/Empty.h>
#include <std_srvs/SetBool.h>
#include <geometry_msgs/TwistStamped.h>
#include <geometry_msgs/Pose.h>
#include <geometry_msgs/Twist.h>
#include <geometry_msgs/Vector3.h>
#include <geometry_msgs/WrenchStamped.h>
#include <sensor_msgs/JointState.h>
#include <sensor_msgs/Joy.h>
#include <jaka_msgs/RobotMsg.h>
#include <jaka_msgs/Move.h>
#include <jaka_msgs/ServoMoveEnable.h>
#include <jaka_msgs/ServoMove.h>
#include <jaka_msgs/SetUserFrame.h>
#include <jaka_msgs/SetTcpFrame.h>
#include <jaka_msgs/SetPayload.h>
#include <jaka_msgs/SetCollision.h>
#include <jaka_msgs/ClearError.h>
#include <jaka_msgs/Servo.h>

#include <Eigen/Dense>
#include <Eigen/Core>
#include <Eigen/Geometry>
#include <Eigen/StdVector>

#include <jaka_driver/JAKAZuRobot.h>
#include <jaka_driver/jkerr.h>
#include <jaka_driver/jktypes.h>
#include <jaka_driver/conversion.h>

#include <tf/transform_broadcaster.h>
#define CONTROL_HZ 125.0
//variables for control and CSV file
int end_sign = 0;
double glo_error;
double glo_kp, glo_ki, glo_kd;
int glo_count;
//Init global variables but with ros message types!!
geometry_msgs::Vector3 glo_vel; //in vector form
std::string glo_method;
geometry_msgs::Pose glo_target_pose;
geometry_msgs::TwistStamped glo_position_feedback; //Current Position
geometry_msgs::WrenchStamped glo_force_torque_calibrated;  //Current bias-corrected force-torque
geometry_msgs::WrenchStamped glo_bias;
geometry_msgs::Wrench glo_target_force;  //Target Force
geometry_msgs::Wrench glo_raw_force;  //Force from sensor
geometry_msgs::WrenchStamped glo_force_torque_LPF;    //Low-pass filtered force-torque
geometry_msgs::WrenchStamped glo_recieved_msg;

std::vector<geometry_msgs::Pose> massage_points_forCSV; // Positions for massage saved in CSV

using namespace std;

// 過大な力を検知したときの終了関連
// For case of detecting excessive force
struct SafetyRetraction : public std::exception {};

jaka_msgs::ServoMoveEnable enable_state;
    ros::ServiceClient servo_move_enable_client;
    ros::ServiceClient servo_j_client;
    ros::ServiceClient movj;

//subscribeするときのリスナー準備
//get
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
            this->data = msg;
            this->data.wrench.force.z = this->data.wrench.force.z * (-1.0);
            glo_force_torque_calibrated = msg;
        }
};

class CppCubicSpline{
  public:
    CppCubicSpline(const vector<double> &y){

      InitParameter(y);
    }

    double Calc(double t){
        int j = int(floor(t));
        if(j < 0){
            j = 0;
        }
        else if(j >= a_.size()){
            j = (a_.size() - 1);
        }

        double dt = t - j;
        double result = a_[j] + (b_[j] + (c_[j] + d_[j] * dt) * dt) * dt;
        return result;
    }

  private:
    vector<double> a_;
    vector<double> b_;
    vector<double> c_;
    vector<double> d_;
    vector<double> w_;

    void InitParameter(const vector<double> &y){
      int ndata = y.size() - 1;

      for(int i = 0; i <= ndata; i++){
        a_.push_back(y[i]);
      }

      for(int i = 0; i < ndata; i++){
        if(i == 0){
          c_.push_back(0.0);
        }
        else if(i == ndata){
          c_.push_back(0.0);
        }
        else{
          c_.push_back(3.0 * (a_[i-1] - 2.0 * a_[i] + a_[i+1]));
        }
      }

      for(int i = 0; i < ndata; i++){
        if(i == 0){
          w_.push_back(0.0);
        }
        else{
          double tmp = 4.0 - w_[i-1];
          c_[i] = (c_[i] - c_[i-1]) / tmp;
          w_.push_back(1.0/tmp);
        }
      }

      for(int i = (ndata-1); i > 0; i--){
        c_[i]=c_[i]-c_[i+1]*w_[i];
      }

      for(int i = 0;i <= ndata; i++){
        if(i == ndata){
          d_.push_back(0.0);
          b_.push_back(0.0);
        }
        else{
          d_.push_back((c_[i+1] - c_[i]) / 3.0);
          b_.push_back(a_[i+1] - a_[i] - c_[i] - d_[i]);
        }
      }
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

//位置制御で目標の位置に達したか確認する関数
int check_position(const geometry_msgs::TwistStamped &current_position, const geometry_msgs::Pose target){
    int reached = 0;
    double x, y, z;
    x = abs(current_position.twist.linear.x - target.position.x);
    y = abs(current_position.twist.linear.y - target.position.y);
    z = abs(current_position.twist.linear.z - target.position.z);

    if(x < 1 && y < 1 && z < 1){
        reached = 1;
    }
    return reached;
}

geometry_msgs::Quaternion rpy_to_geometry_quat(double roll, double pitch, double yaw){
	tf::Quaternion quat = tf::createQuaternionFromRPY(roll, pitch, yaw);
	geometry_msgs::Quaternion geometry_quat;
	quaternionTFToMsg(quat, geometry_quat);
	return geometry_quat;
}

void geometry_quat_to_rpy(double& roll, double& pitch, double& yaw, geometry_msgs::Quaternion geometry_quat){
	tf::Quaternion quat;
	quaternionMsgToTF(geometry_quat, quat);
	tf::Matrix3x3(quat).getRPY(roll, pitch, yaw);  //rpy are Pass by Reference
}

// 指定位置までの位置制御を行う関数
void move_position(geometry_msgs::Pose &target_pose, const geometry_msgs::TwistStamped &current_position, ros::Publisher &target_pose_pub, ros::Publisher &method_pub){
    ros::NodeHandle n;
    // 创建一个client，请求"/jaka_driver/linear_move" service
    // service消息类型是jaka_msgs::Move
    ros::ServiceClient client = n.serviceClient<jaka_msgs::Move>("/jaka_driver/linear_move");
    jaka_msgs::Move srv;
    std_msgs::Int32 method_msg;
    // method_msg.data = 8; //move position 8
    // method_pub.publish(method_msg);

    int reached = 0;
    double rpyx = 0.0;
    double rpyy = 0.0;
    double rpyz = 0.0;
    ROS_INFO("bbq3");
    glo_method = "move_position";
    glo_target_pose = target_pose;
    target_pose_pub.publish(target_pose);
    srv.request.pose.push_back(target_pose.position.x);
    srv.request.pose.push_back(target_pose.position.y);
    srv.request.pose.push_back(target_pose.position.z);
    srv.request.pose.push_back(rpyx);
    srv.request.pose.push_back(rpyy);
    srv.request.pose.push_back(rpyz);
    srv.request.mvvelo = 800;
    srv.request.mvacc = 200;
    // 发布service请求
    if (client.call(srv)){
        ROS_INFO("ret: %d", (int)srv.response.ret);
    }
    else{
    	ROS_INFO("bbq6");
        ROS_ERROR("Failed to call service");
        //return 1;
    }
    do{reached = check_position(current_position, target_pose);}
    while(reached != 1);
    std::cout <<"reached"<<std::endl;
    reached = 0;
    srv.request.pose.clear();
    glo_method = "";
    ros::Duration(0.1).sleep();
    // method_msg.data = 0; //owari 0
    // method_pub.publish(method_msg);
}

//平均を求める関数
double mean(std::vector<double> data) {
    double sum = 0;
    for (auto e : data){
        sum += e;
    }
    return sum / (double)data.size();
}

//偏差の計算
geometry_msgs::WrenchStamped calc_bias(std::vector<geometry_msgs::WrenchStamped> msgs) {
    std::vector<double> force_x_data;
    std::vector<double> force_y_data;
    std::vector<double> force_z_data;
    std::vector<double> torque_x_data;
    std::vector<double> torque_y_data;
    std::vector<double> torque_z_data;

    for (auto e : msgs){
        force_x_data.push_back(e.wrench.force.x);
        force_y_data.push_back(e.wrench.force.y);
        force_z_data.push_back(e.wrench.force.z);
        torque_x_data.push_back(e.wrench.torque.x);
        torque_y_data.push_back(e.wrench.torque.y);
        torque_z_data.push_back(e.wrench.torque.z);
    }

    geometry_msgs::WrenchStamped bias;
    bias.wrench.force.x = mean(force_x_data);
    bias.wrench.force.y = mean(force_y_data);
    bias.wrench.force.z = mean(force_z_data);
    bias.wrench.torque.x = mean(torque_x_data);
    bias.wrench.torque.y = mean(torque_y_data);
    bias.wrench.torque.z = mean(torque_z_data);
    glo_bias = bias;

    return bias;
}

//偏差除去
geometry_msgs::WrenchStamped remove_bias(const geometry_msgs::WrenchStamped recieved_msg, const geometry_msgs::WrenchStamped bias) {
    geometry_msgs::WrenchStamped caliblated_msg;
    caliblated_msg.wrench.force.x = recieved_msg.wrench.force.x - bias.wrench.force.x;
    caliblated_msg.wrench.force.y = recieved_msg.wrench.force.y - bias.wrench.force.y;
    caliblated_msg.wrench.force.z = recieved_msg.wrench.force.z - bias.wrench.force.z;
    caliblated_msg.wrench.torque.x = recieved_msg.wrench.torque.x - bias.wrench.torque.x;
    caliblated_msg.wrench.torque.y = recieved_msg.wrench.torque.y - bias.wrench.torque.y;
    caliblated_msg.wrench.torque.z = recieved_msg.wrench.torque.z - bias.wrench.torque.z;
    glo_force_torque_calibrated = caliblated_msg;
    glo_recieved_msg.wrench.force.z = recieved_msg.wrench.force.z;
    glo_bias = bias;
    return caliblated_msg;
}

std::string unpack_wrenchstamped(const geometry_msgs::WrenchStamped &message){
    std::stringstream ss;
    ss << message.wrench.force.x << ","
       << message.wrench.force.y << ","
       << message.wrench.force.z << ","
       << message.wrench.torque.x << ","
       << message.wrench.torque.y << ","
       << message.wrench.torque.z << ",";
    return ss.str();
}

std::string unpack_posestamped(const geometry_msgs::PoseStamped &message){
    std::stringstream ss;
    ss << message.pose.position.x << ","
       << message.pose.position.y << ","
       << message.pose.position.z << ","
       << message.pose.orientation.x << ","
       << message.pose.orientation.y << ","
       << message.pose.orientation.z << ","
       << message.pose.orientation.w << ",";
    return ss.str();
}

//ローパスフィルタ
double LPF(double u, double ub, double yb, double cut_fre){
    double Ts = 1 / CONTROL_HZ;  //サンプリング周期
    double T = 1 / (2 * M_PI * cut_fre);  //カットオフ周波数から時定数を求める
    double C_y = (2 * T - Ts) / (2 * T + Ts);   //出力値の方の係数
    double C_u = Ts / (2 * T + Ts); //入力値の方の係数
    double y = C_y * yb + C_u * (u + ub);
    return y;
}

//ローパスフィルタ
geometry_msgs::Vector3 LPF_new(geometry_msgs::WrenchStamped u, geometry_msgs::Wrench ub, geometry_msgs::Wrench yb, double cut_fre){
    double Ts = 1 / CONTROL_HZ;  //サンプリング周期
    double T = 1 / (2 * M_PI * cut_fre);  //カットオフ周波数から時定数を求める
    double C_y = (2 * T - Ts) / (2 * T + Ts);   //出力値の方の係数
    double C_u = Ts / (2 * T + Ts); //入力値の方の係数
    geometry_msgs::Vector3 calc_force;
    calc_force.x = C_y * yb.force.x + C_u * (u.wrench.force.x + ub.force.x);
    calc_force.y = C_y * yb.force.y + C_u * (u.wrench.force.y + ub.force.y);
    calc_force.z = C_y * yb.force.z + C_u * (u.wrench.force.z + ub.force.z);
    return calc_force;
}

//指定位置まで曲線で動く関数
void move_position_spline(geometry_msgs::Pose &target_pose, const geometry_msgs::TwistStamped &current_position, const geometry_msgs::WrenchStamped &force_torque, const geometry_msgs::WrenchStamped bias, ros::Publisher tcp_vel_publisher, geometry_msgs::Twist tcp_vel_message, double time_move, double height, ros::Publisher &reference_force_pub, ros::Publisher &method_pub){
    int i = 0;
    double cut_off_frequency = 5;
    double error;
    geometry_msgs::Wrench force_torque_before, force_torque_LPF, force_torque_LPF_before;
    geometry_msgs::WrenchStamped force_torque_calibrated;
    geometry_msgs::Wrench target_force;
    geometry_msgs::Pose start_position;
    ros::Rate control_timer(CONTROL_HZ);
    target_force.force.x = 0;
    target_force.force.y = 0;
    target_force.force.z = 8;
    target_force.torque.x = 0;
    target_force.torque.y = 0;
    target_force.torque.z = 0;

    start_position.position.x = current_position.twist.linear.x;
    start_position.position.y = current_position.twist.linear.y;
    start_position.position.z = current_position.twist.linear.z;

    double move_distance = target_pose.position.y - start_position.position.y;  //何 mm 動くか
    ROS_INFO("move_spline");
    glo_method = "move_spline";
    std_msgs::Int32 method_msg;
    // method_msg.data = 1; //移動時は1
    // method_pub.publish(method_msg);

    // enable_state.request.enable = TRUE;
    // servo_move_enable_client.call(enable_state);
    // cout << "ServoMove enable" << endl;
    // ros::Duration(0.3).sleep();

    //calculate spline trajectory
    //始点、中点、終点
    std::vector<double> sy{0, 1, 2};
    //zに関しては中点でheight分高くする
    std::vector<double> sz{start_position.position.z, start_position.position.z + (target_pose.position.z-start_position.position.z)/2-height, target_pose.position.z};
    CppCubicSpline cppCubicSpline(sz);
    std::vector<double> ry;
    std::vector<double> rz;
    double incr = CONTROL_HZ * time_move;

    double height_before = 0.0;
    double highest = 0.0;
    ry.push_back(sy[0]);
    rz.push_back(cppCubicSpline.Calc(sy[0]));
    //始点から終点までループ
    for(int j = 1; j <= incr; j++){
        //スプライン計算
        ry.push_back(sy[0] + 2 * double(j) / incr);
        rz.push_back(cppCubicSpline.Calc(sy[0] + 2 * double(j) / incr));
        tcp_vel_message.linear.x = (target_pose.position.x - start_position.position.x) / 1000 / time_move;
        tcp_vel_message.linear.y = move_distance / 1000 / time_move;
        tcp_vel_message.linear.z = (rz[rz.size()-1]-rz[rz.size()-2])*CONTROL_HZ/1000;//u;
        tcp_vel_publisher.publish(tcp_vel_message);
        reference_force_pub.publish(target_force);
        glo_force_torque_LPF.wrench = force_torque_LPF;
        glo_target_force = target_force;
        glo_error = error;
        glo_vel = tcp_vel_message.linear;
        glo_force_torque_calibrated = force_torque_calibrated;
        force_torque_before = force_torque_calibrated.wrench;
        force_torque_LPF_before = force_torque_LPF;
        control_timer.sleep();
    }
    auto biggest = std::min_element(std::begin(rz), std::end(rz));
    
    // std::cout << "from:\n" << start_position.position
    //             << "\nto:\n" << current_position.twist.linear << std::endl
    //             << "target_pose:\n" << target_pose.position << std::endl
    //             << "max height calculated:\t" << *biggest << std::endl
    //             << "max height irl:\t" << highest << std::endl;
    tcp_vel_message.linear.x = 0;
    tcp_vel_message.linear.y = 0;
    tcp_vel_message.linear.z = 0;
    tcp_vel_publisher.publish(tcp_vel_message);

    // method_msg.data = 0;
    // method_pub.publish(method_msg);
    glo_vel = tcp_vel_message.linear;
    glo_target_force.force.z = 0;
    glo_force_torque_LPF.wrench.force.x = 0;
    glo_force_torque_LPF.wrench.force.y = 0;
    glo_force_torque_LPF.wrench.force.z = 0;
    glo_error = 0;
    glo_count = -1;
    glo_method = "";
    glo_force_torque_calibrated.wrench.force.x = 0;
    glo_force_torque_calibrated.wrench.force.y = 0;
    glo_force_torque_calibrated.wrench.force.z = 0;
    glo_force_torque_calibrated.wrench.torque.x = 0;
    glo_force_torque_calibrated.wrench.torque.y = 0;
    glo_force_torque_calibrated.wrench.torque.z = 0;
}

//目標力まで下降する関数
void touch(geometry_msgs::Wrench &target_force, const geometry_msgs::TwistStamped &current_position, const geometry_msgs::WrenchStamped &force_torque, const geometry_msgs::WrenchStamped bias, ros::Publisher tcp_vel_publisher, geometry_msgs::Twist tcp_vel_message, ros::Publisher &reference_force_pub, ros::Publisher &method_pub){
    int i = 0;
    double cut_off_frequency = 5;
    double error;
    double Kp = 0.006;     //P制御のゲイン
    double Ki = 0.0002;     //Iゲイン
    double Kd = 0.0002;  //Dゲイン
    double de, ie, u, error_before;

    geometry_msgs::Vector3 zeros;
    geometry_msgs::Wrench force_torque_before, force_torque_LPF, force_torque_LPF_before;
    geometry_msgs::WrenchStamped force_torque_calibrated;
    ros::Rate control_timer(CONTROL_HZ);

    ROS_INFO("touch");
    glo_method = "touch";
    std_msgs::Int32 method_msg;
    // method_msg.data = 2; //タッチは２
    // method_pub.publish(method_msg);

    enable_state.request.enable = TRUE;
    servo_move_enable_client.call(enable_state);
    cout << "ServoMove enable" << endl;
    ros::Duration(0.3).sleep();

    do{
        // recieve force torqe force_torque data
        force_torque_calibrated = remove_bias(force_torque, bias);
        std::cout << "force_torque_is: \n" <<force_torque_calibrated << std::endl;
        force_torque_LPF.force = LPF_new(force_torque_calibrated, force_torque_before, force_torque_LPF_before, cut_off_frequency);
        error = target_force.force.z - force_torque_LPF.force.z;
        ROS_INFO_STREAM("control error : " << error);

        de = (error - error_before) * CONTROL_HZ;    //誤差の微分近似
        ie = ie + (error + error_before) / (2 * CONTROL_HZ);

        u = Kp * error + Ki * ie + Kd * de;

        if(u > 0.1){
            u = 0.1;
        }
        if(u < -0.1){
            u = -0.1;
        }

        // send velocity command to robot
        tcp_vel_message.linear.x = 0;
        tcp_vel_message.linear.y = 0;
        tcp_vel_message.linear.z = u;//0.03;
        tcp_vel_publisher.publish(tcp_vel_message);
        ROS_INFO("touch");

        reference_force_pub.publish(target_force);

        //global変数に送る
        glo_vel = tcp_vel_message.linear;
        glo_target_force = target_force;
        glo_force_torque_LPF.wrench = force_torque_LPF;
        glo_error = error;

        force_torque_before = force_torque_calibrated.wrench;
        force_torque_LPF_before = force_torque_LPF;
        error_before = error;
        control_timer.sleep();
    } while (force_torque_LPF.force.z <= target_force.force.z);

    tcp_vel_message.linear.x = 0;
    tcp_vel_message.linear.y = 0;
    tcp_vel_message.linear.z = 0;
    tcp_vel_publisher.publish(tcp_vel_message);

    // method_msg.data = 0; //終了時は0
    // method_pub.publish(method_msg);
    
    glo_vel = tcp_vel_message.linear;
    glo_target_force.force.z = 0;
    glo_force_torque_LPF.wrench.force.x = 0;
    glo_force_torque_LPF.wrench.force.y = 0;
    glo_force_torque_LPF.wrench.force.z = 0;
    glo_error = 0;
    glo_count = -1;
    glo_method = "";
    glo_force_torque_calibrated.wrench.force.x = 0;
    glo_force_torque_calibrated.wrench.force.y = 0;
    glo_force_torque_calibrated.wrench.force.z = 0;
    glo_force_torque_calibrated.wrench.torque.x = 0;
    glo_force_torque_calibrated.wrench.torque.y = 0;
    glo_force_torque_calibrated.wrench.torque.z = 0;
}

void finger_pressing(geometry_msgs::Pose &target_pose, const geometry_msgs::TwistStamped &current_position, geometry_msgs::Wrench target_force, std::string input_csv_path, double Kp, double Ki, double Kd, const geometry_msgs::WrenchStamped &force_torque, const geometry_msgs::WrenchStamped bias, int count, geometry_msgs::Wrench touch_force, ros::Publisher vel_publisher, geometry_msgs::Twist tcp_vel_message, ros::Publisher &target_pose_pub, ros::Publisher &reference_force_pub, ros::Publisher &method_pub, ros::Publisher &count_pub){
    
    ros::Rate control_timer(CONTROL_HZ);
    
    geometry_msgs::Wrench force_torque_before, force_torque_LPF, force_torque_LPF_before, reference_force_buf;
    geometry_msgs::WrenchStamped force_torque_calibrated;
    std_msgs::Int32 method_msg;
    double max_force, error_rate, shear_force;
    // method_msg.data = 4; //finger pressing 4
    // method_pub.publish(method_msg);

    double Kp_buff = Kp;
    double Ki_buff = Ki;
    double Kd_buff = Kd;

    geometry_msgs::Pose evac_pos;   //退避用ポジション
    evac_pos.orientation.x = 0;
    evac_pos.orientation.y = 0;
    evac_pos.orientation.z = 0;
    evac_pos.orientation.w = 1;

    // CSVファイルに基づく力パターンの再現
    std::string str_buf;
    std::ifstream ifs(input_csv_path);
    if(!ifs){
        ROS_ERROR("finger_pressing ERROR: Failed to open file: %s", input_csv_path.c_str());
    }
    ROS_INFO("finger_pressing INFO: Successfully opened file: %s", input_csv_path.c_str());
    ROS_INFO("finger_pressing INFO: Starting CSV-based pressing. Base target force: %.2f N", target_force.force.z);

    for(int i = 0; i < count; i++){
        double de = 0, u = 0, error = 0, reference_force_z = 0;
        glo_count = i;
        int line_count = 0;
        double error_before = 0;
        double ie = 0;

        reference_force_buf = target_force;

        while (getline(ifs, str_buf)){
            line_count++;

            force_torque_calibrated = remove_bias(force_torque, bias);
            force_torque_LPF.force = LPF_new(force_torque_calibrated, force_torque_before, force_torque_LPF_before, 5.0);
            reference_force_z = std::stod(str_buf) * target_force.force.z;
            
            // 120N以上の力が検出されたら退避してこのポイントをスキップ
            if (force_torque_LPF.force.z > 110){
                ROS_WARN("finger_pressing WARNING: Excessive force detected (%.2f N > 120 N). Evacuating and skipping this point.", force_torque_LPF.force.z);
                // evac_pos.position.x = current_position.twist.linear.x;
                // evac_pos.position.y = current_position.twist.linear.y;
                // evac_pos.position.z = current_position.twist.linear.z - 50;
                
                // 速度を停止
                tcp_vel_message.linear.x = 0;
                tcp_vel_message.linear.y = 0;
                tcp_vel_message.linear.z = 0;
                vel_publisher.publish(tcp_vel_message);
                
                // 退避位置に移動
                // move_position(evac_pos, glo_position_feedback, target_pose_pub, method_pub);
                
                ROS_INFO("finger_pressing INFO: Point skipped due to excessive force. Continuing to next point.");
                ifs.clear();
                ifs.seekg(0, std::ios::beg);
            }
            if(reference_force_z < touch_force.force.z){
                //touchより小さいからスキップ
            }
            else{
                if(force_torque_LPF.force.z > 1.1 * reference_force_z){
                    Kp_buff = Kp;
                    Ki_buff = Ki;
                    Kd_buff = Kd;
                }
                else{
                    Kp_buff = Kp;
                    Ki_buff = Ki;
                    Kd_buff = Kd;
                }
                error = reference_force_z - force_torque_LPF.force.z;
                de = (error - error_before) * CONTROL_HZ;
                ie += (error + error_before) / (2 * CONTROL_HZ);
                u = Kp_buff * error + Ki_buff * ie + Kd_buff * de;
                
                shear_force = hypot(force_torque_LPF.force.x, force_torque_LPF.force.y);
                if(shear_force > 30 && u > 0){
                    u = 0;
                }

                if(u > 0.1) u = 0.1;
                if(u < -0.1) u = -0.1;
                
                tcp_vel_message.linear.x = 0;
                tcp_vel_message.linear.y = 0;
                tcp_vel_message.linear.z = u;
                vel_publisher.publish(tcp_vel_message);
                //global変数に送る
                glo_vel = tcp_vel_message.linear;
                glo_target_force = target_force;
                glo_target_force.force.z = reference_force_z;
                glo_force_torque_LPF.wrench = force_torque_LPF;
                glo_error = error;
                ROS_INFO_STREAM(force_torque);
                cout << "shear force: " << shear_force << endl;
                cout << "u: " << u << endl;

                force_torque_before = force_torque_calibrated.wrench;
                force_torque_LPF_before = force_torque_LPF;
                error_before = error;

                reference_force_buf.force.z = reference_force_z;
                reference_force_pub.publish(reference_force_buf);

                if(max_force < force_torque_LPF.force.z){
                    max_force = force_torque_LPF.force.z;
                }

                ROS_INFO("finger pressing");
                glo_method = "finger_pressing";

                control_timer.sleep();
            }
        }
        // method_msg.data = 0; //owari 0
        // method_pub.publish(method_msg);
        
        ROS_INFO("finger_pressing INFO: Finished reading CSV file. Total lines read: %d", line_count);
        
        ifs.clear();
        ifs.seekg (0, std::ios::beg);
    }
}


void kneading(geometry_msgs::Pose &target_pose, const geometry_msgs::TwistStamped &current_position, const geometry_msgs::Wrench target_force, double amplitude_x, double amplitude_y, double w_x, double w_y, double t, const geometry_msgs::WrenchStamped &force_torque, const geometry_msgs::WrenchStamped bias, ros::Publisher vel_publisher, geometry_msgs::Twist tcp_vel_message, double &duration_time, ros::Publisher &target_pose_pub, ros::Publisher &reference_force_pub, ros::Publisher &method_pub){
    int i = 0;
    int j = 0;
    double cut_off_frequency = 5;
    double Kp = 0.001;     //P制御のゲイン
    double Ki = 0.0001;     //Iゲイン
    double Kd = 0.00005;  //Dゲイン
    double error;
    double error_before = 0;    //PID用の前回誤差
    double de = 0;  //誤差の微分
    double ie = 0;  //誤差の積分
    geometry_msgs::Wrench force_torque_before, force_torque_LPF, force_torque_LPF_before;
    geometry_msgs::WrenchStamped force_torque_calibrated;
    ros::Rate control_timer(CONTROL_HZ);
    std_msgs::Int32 method_msg;

    ROS_INFO("kneading");
    glo_method = "kneading";
    std::stringstream ss;
    // method_msg.data = 5; //kneading 5
    // method_pub.publish(method_msg);

    duration_time = 10.0;
    // target_pose.position.z -= 40;   //少し離した位置へ移動
    // move_position(target_pose, current_position, target_pose_pub);
    // target_pose.position.z += 40;

    enable_state.request.enable = TRUE;
    servo_move_enable_client.call(enable_state);
    cout << "ServoMove enable" << endl;
    ros::Duration(0.1).sleep();

    double T_start = ros::Time::now().toSec();

    for(i; i < t * CONTROL_HZ; i++){
        glo_method = "kneading";
        double T_now = ros::Time::now().toSec();
        double T_StoN = T_now - T_start;
        // recieve force torqe sensor data
            force_torque_calibrated = remove_bias(force_torque, bias);  //偏差除去
            force_torque_LPF.force = LPF_new(force_torque_calibrated, force_torque_before, force_torque_LPF_before, cut_off_frequency);

        // calc z-axis velocity command with p-control

        error = target_force.force.z - force_torque_LPF.force.z;
        ROS_INFO_STREAM("control error : " << error);
       
        de = (error - error_before) * CONTROL_HZ;    //誤差の微分近似
        ie = ie + (error + error_before) / (2 * CONTROL_HZ);

        double u = Kp * error + Ki * ie + Kd * de;
        ROS_INFO_STREAM("control u : " << u);

        // calc x-axis sin wave command
        double massage_vel_x = amplitude_x * std::sin(2 * M_PI * w_x * T_StoN );
        // calc y-axis sin wave command
        double massage_vel_y = amplitude_y * std::cos(2 * M_PI * w_y * T_StoN );
        
        //velocity limit
        if(u > 0.1){
            u = 0.1;
        }
        if(u < -0.1){
            u = -0.1;
        }

        if(i > t*CONTROL_HZ-52){
            massage_vel_x = massage_vel_x * (50 - j) / 50;
            massage_vel_y = massage_vel_y * (50 - j) / 50;
            j += 1;
        }        

        // send velocity command to robot
        tcp_vel_message.linear.x = massage_vel_x;
        tcp_vel_message.linear.y = massage_vel_y;
        tcp_vel_message.linear.z = u;
        vel_publisher.publish(tcp_vel_message);
        ROS_INFO_STREAM("control u : " << massage_vel_x);
        ROS_INFO("kneading");

        reference_force_pub.publish(target_force);

        glo_count = i/CONTROL_HZ;
        //global変数に送る
        glo_vel = tcp_vel_message.linear;
        glo_target_force = target_force;
        glo_force_torque_LPF.wrench = force_torque_LPF;
        glo_error = error;

        force_torque_before = force_torque.wrench; //LPF用に今の計測値を保存
        force_torque_LPF_before = force_torque_LPF;   //LPF用に今回のLPF出力を保存
        error_before = error;   //PID用に今回の誤差保存
        control_timer.sleep();
    }

    duration_time=5.0;

    // method_msg.data = 0; //owari 0
    // method_pub.publish(method_msg);

    // move_position(target_pose, current_position, target_pose_pub);
    glo_vel.x = 0;
    glo_vel.y = 0;
    glo_vel.z = 0;
    glo_target_force.force.x = 0;
    glo_target_force.force.y = 0;
    glo_target_force.force.z = 0;
    glo_force_torque_calibrated.wrench.force.z = 0;
    glo_force_torque_LPF.wrench.force.z = 0;
    glo_error = 0;
    glo_method = "";
    glo_force_torque_calibrated.wrench.force.x = 0;
    glo_force_torque_calibrated.wrench.force.y = 0;
    glo_force_torque_calibrated.wrench.force.z = 0;
    glo_force_torque_calibrated.wrench.torque.x = 0;
    glo_force_torque_calibrated.wrench.torque.y = 0;
    glo_force_torque_calibrated.wrench.torque.z = 0;
    glo_kp = 0;
    glo_ki = 0;
    glo_kd = 0;
}

// 複数のPoseデータから位置の平均を計算するヘルパー関数
// 向き(orientation)は最後のデータのものを採用します
geometry_msgs::Pose average_pose_position(const std::vector<geometry_msgs::Pose>& poses, ros::Publisher &method_pub) {
    geometry_msgs::Pose averaged_pose;
    std_msgs::Int32 method_msg;
    double sum_x = 0.0, sum_y = 0.0, sum_z = 0.0;
    int valid_samples = 0; // 有効なサンプルの数をカウントする変数
    geometry_msgs::Quaternion last_valid_orientation; // 最後に見つかった有効な向きを保存する

    // 収集した全サンプルをループ
    for (const auto& pose : poses) {
        // positionのx, y, zのいずれかがNaNでないかチェック
        if (std::isnan(pose.position.x) || std::isnan(pose.position.y) || std::isnan(pose.position.z)) {
            ROS_WARN("NaN sample detected and skipped.");
            continue; // NaNが見つかった場合、このサンプルは無視して次のループへ
        }
        
        // 有効なサンプルだった場合のみ、計算に加える
        sum_x += pose.position.x;
        sum_y += pose.position.y;
        sum_z += pose.position.z;
        last_valid_orientation = pose.orientation; // 有効な向きを更新
        valid_samples++; // 有効サンプル数をインクリメント
    }

    // もし有効なサンプルが一つもなかった場合
    if (valid_samples == 0) {
        ROS_ERROR("No valid samples found to average. Returning zero pose.");
        method_msg.data = 92; //skeleton not found 92
        method_pub.publish(method_msg);
        return averaged_pose; // 安全のため、中身が0のPoseを返す
    }

    // 有効なサンプルの数で割り、平均を計算
    averaged_pose.position.x = sum_x / valid_samples;
    averaged_pose.position.y = sum_y / valid_samples;
    averaged_pose.position.z = sum_z / valid_samples;
    averaged_pose.orientation = last_valid_orientation; // 最後に取得した有効な向きを設定

    return averaged_pose;
}

char is_moderate_force(char force_answer, const geometry_msgs::Wrench target_force, ros::Publisher &method_pub){
    std_msgs::Int32 method_msg;
    // method_msg.data = 13; //moderate force input 13
    // method_pub.publish(method_msg);

    bool end_mark = false;
    while(end_mark == false){
        ROS_INFO("Now the force is %.1f N.", target_force.force.z);
        ROS_INFO("Is the force suitable for you? (y/n)");
        std::cin >> force_answer;

        if(force_answer == 'y'){
            ROS_INFO("OK. Now initiating the plan.");
            ROS_WARN("osita");
            end_mark = true;
        }else if(force_answer == 'n'){
            ROS_INFO("Oh, then let's adjust the force.");
            end_mark = true;
        }else{
            ROS_INFO("It's neither y nor n. Please type again.");
        }
    }
    return force_answer;
}

geometry_msgs::Wrench determine_massage_force(const geometry_msgs::Wrench Target_force, const geometry_msgs::Pose& rh_pose,const geometry_msgs::Pose& rk_pose,const geometry_msgs::TwistStamped &current_position,const geometry_msgs::WrenchStamped &force_torque, const geometry_msgs::WrenchStamped &bias,ros::Publisher &vel_publisher,geometry_msgs::Twist &tcp_vel_message,ros::Publisher &target_pose_pub,ros::Publisher &reference_force_pub,ros::Publisher &method_pub,ros::Publisher &count_pub) {
    ROS_INFO("Starting interactive force decision process...");
    std_msgs::Int32 method_msg;
    method_msg.data = 11; //calibration hajimari 11
    method_pub.publish(method_msg);
    geometry_msgs::Wrench target_force_touch;
    target_force_touch.force.z = 7.0;

    geometry_msgs::Wrench determined_force;
    determined_force = Target_force;   
    char force_answer = ' ';
    bool force_decided = false;

    geometry_msgs::Pose test_press_pose;
    test_press_pose = rh_pose;
    // // Z座標のオフセットを適用 (カメラ座標系からのオフセットと、施術面へのオフセット)
    // test_press_pose.position.z -= 230;//200.0;
    // test_press_pose.position.x -= 15.0; //おしりの横側に行き過ぎたので補正
    do {
        // ROS_INFO("Moving to test press position...");
        geometry_msgs::Pose approach_pose_for_test = test_press_pose;
        // approach_pose_for_test.position.z -= 30.0;
        
        // move_position(approach_pose_for_test, current_position, target_pose_pub, method_pub);
        // touch(target_force_touch, current_position, force_torque, bias, vel_publisher, tcp_vel_message, reference_force_pub, method_pub);
        // finger_pressing(test_press_pose, current_position, determined_force, "/home/isrlab/jaka_ws/src/jaka_driver/TargetForce202512.csv", force_torque, bias, 1, target_force_touch, vel_publisher, tcp_vel_message, target_pose_pub, reference_force_pub, method_pub, count_pub);
        
        ROS_INFO("Returning to pre-press position before asking for feedback...");
        // 最初に移動したアプローチ位置に再度移動する
        // move_position(approach_pose_for_test, current_position, target_pose_pub, method_pub);

        force_answer = is_moderate_force(force_answer, determined_force, method_pub);
        if (force_answer == 'y') {
            force_decided = true;
        } else if (force_answer == 'n') {
            ROS_INFO("Current force is %.1f N. How much force do you want to add? (e.g., 10 or -5):", determined_force.force.z);
            double force_added;
            
            while (!(std::cin >> force_added)) {
                ROS_WARN("Invalid input. Please enter a number.");
                std::cin.clear();
                std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
            }
            determined_force.force.z += force_added;
            if (determined_force.force.z < 5.0) {
                ROS_WARN("It can't be lower than 5 N. Set the force 5.0 N.");
                determined_force.force.z = 5.0;
            }
            if (determined_force.force.z > 110.0) {
                ROS_WARN("It can't be higher than 110 N. Set the force 110 N.");
                determined_force.force.z = 110.0;
            }
            if(force_added >= 0){

            }else{

            }
        }
    } while (!force_decided);

    ROS_INFO("Final massage force is set to %.1f N.", determined_force.force.z);
    
    method_msg.data = 12;
    method_pub.publish(method_msg);

    // ROS_INFO("Force determination finished. Retracting by 80mm.");
    // geometry_msgs::Pose final_escape_pose;
    // final_escape_pose.position.x = glo_position_feedback.twist.linear.x;
    // final_escape_pose.position.y = glo_position_feedback.twist.linear.y;
    // final_escape_pose.position.z = glo_position_feedback.twist.linear.z - 80.0; // 80mm上昇
    
    // // 向きはテストプレスで使ったものと同じにする
    // geometry_msgs::Pose temp_orientation_pose = average_pose_position(rh_pose, method_pub);
    // final_escape_pose.orientation = temp_orientation_pose.orientation;

    // move_position(final_escape_pose, glo_position_feedback, target_pose_pub, method_pub);
   
    return determined_force; 
}

std::string getCurrentTimeStr() {
        // 現在時刻を取得
        auto now = std::chrono::system_clock::now();
        
        // time_t型に変換、ローカルタイムを取得
        std::time_t now_c = std::chrono::system_clock::to_time_t(now);
        std::tm* now_tm = std::localtime(&now_c);

        // フォーマット
        std::stringstream ss;
        ss << std::put_time(now_tm, "%Y%m%d%H%M%S");

        return ss.str();
    }

void save_log_csv(){
    std::string filename = "/home/isrlab/jaka_ws/src/jaka_driver/Ben_massage_log/" + getCurrentTimeStr() + ".csv";
    std::ofstream log(filename);
    if(!log.is_open())
    {
        ROS_ERROR_STREAM("can not open log file");
    }
    log << "Time" << ","
        << "Time(from beginning)" << ","
        << "target pose x" << ","
        << "target pose y" << ","
        << "target pose z" << ","
        << "target orientation x" << ","
        << "target orientation y" << ","
        << "target orientation z" << ","
        << "target orientation w" << ","
        << "tool pose x" << ","
        << "tool pose y" << ","
        << "tool pose z" << ","
        << "tool orientation x" << ","
        << "tool orientation y" << ","
        << "tool orientation z" << ","
        << "vel_x" << ","
        << "vel_y" << ","
        << "vel_z" << ","
        << "bias z" << ","
        << "raw force x" << ","
        << "raw force y" << ","
        << "raw force z" << ","
        << "calibrated force x" << ","
        << "calibrated force y" << ","
        << "calibrated force z" << ","
        << "calibrated torque x" << ","
        << "calibrated torque y" << ","
        << "calibrated torque z" << ","
        << "reference force z" << ","
        << "LPF force x" << ","
        << "LPF force y" << ","
        << "LPF force z" << ","
        << "Kp" << ","
        << "Ki" << ","
        << "Kd" << ","        
        << "error" << ","
        << "method" << ","
        << "count of pushing" << std::endl;
    double T_start = ros::Time::now().toSec();
    ros::Rate control_timer(CONTROL_HZ);
    while(end_sign == 0){
        double T_now = ros::Time::now().toSec();
        double T_StoN = T_now - T_start;
        log << std::fixed << std::setprecision(20) 
        << T_now << "," 
        << T_StoN << "," 
        << glo_target_pose.position.x << "," 
        << glo_target_pose.position.y << "," 
        << glo_target_pose.position.z << "," 
        << glo_target_pose.orientation.x << ","
        << glo_target_pose.orientation.y << ","
        << glo_target_pose.orientation.z << ","
        << glo_target_pose.orientation.w << ","
        << glo_position_feedback.twist.linear.x << ","
        << glo_position_feedback.twist.linear.y << ","
        << glo_position_feedback.twist.linear.z << "," 
        << glo_position_feedback.twist.angular.x << ","
        << glo_position_feedback.twist.angular.y << ","
        << glo_position_feedback.twist.angular.z << ","
        << glo_vel.x << "," 
        << glo_vel.y << "," 
        << glo_vel.z << "," 
        << glo_bias.wrench.force.z << "," 
        << glo_raw_force.force.x << "," 
        << glo_raw_force.force.y << "," 
        << glo_raw_force.force.z << "," 
        << glo_force_torque_calibrated.wrench.force.x << ","
        << glo_force_torque_calibrated.wrench.force.y << ","
        << glo_force_torque_calibrated.wrench.force.z << ","
        << glo_force_torque_calibrated.wrench.torque.x << ","
        << glo_force_torque_calibrated.wrench.torque.y << ","
        << glo_force_torque_calibrated.wrench.torque.z << ","
        << glo_target_force.force.z << "," 
        << glo_force_torque_LPF.wrench.force.x << "," 
        << glo_force_torque_LPF.wrench.force.y << "," 
        << glo_force_torque_LPF.wrench.force.z << "," 
        << glo_kp << "," 
        << glo_ki << "," 
        << glo_kd << "," 
        << -glo_error << "," 
        << glo_method << "," 
        << glo_count << ","
        << glo_recieved_msg.wrench.force.z <<std::endl;
        control_timer.sleep();
    }
}

int main(int argc, char *argv[]){
    ros::init(argc, argv, "massage_demo_node");
    ros::NodeHandle node_handle;
    ros::NodeHandle nh;
    ros::AsyncSpinner spinner(1);
    spinner.start();

    ros::Rate calib_timer(CONTROL_HZ);
    ros::Rate control_timer(CONTROL_HZ);

    //init Listener 
    CanonListener force_torque;
    CoordinatedForceTorqueListener force_torque_coordinated;
    EEFListener end_effector;
    positionsubscribe current_position;
    skeletonRTListener skeletonRT;
    skeletonLTListener skeletonLT;
    skeletonRLListener skeletonRL;
    skeletonLLListener skeletonLL;
    skeletonRGListener skeletonRG;
    skeletonLGListener skeletonLG;
    skeletonHEListener skeletonHE;
    skeletonNEListener skeletonNE;
    skeletonTOListener skeletonTO;
    skeletonCHListener skeletonCH;
    skeletonRSListener skeletonRS;
    skeletonLSListener skeletonLS;
    skeletonLCListener skeletonLC;
    skeletonRHListener skeletonRH;
    skeletonLHListener skeletonLH;
    skeletonRKListener skeletonRK;
    skeletonLKListener skeletonLK;
    skeletonRAListener skeletonRA;
    skeletonLAListener skeletonLA;
    ros::Subscriber force_torque_sub = node_handle.subscribe("/canon_force_torque/force_torque", 1, &CanonListener::callback, &force_torque);
    ros::Subscriber force_torque_coordinated_sub = node_handle.subscribe("/coordinated_force/base_force", 1, &CoordinatedForceTorqueListener::callback, &force_torque_coordinated);
    ros::Subscriber eef_sub = node_handle.subscribe("/tool_pose", 1, &EEFListener::callback, &end_effector);
    ros::Subscriber right_tra_sub = node_handle.subscribe("/right_tra", 1, &skeletonRTListener::callback, &skeletonRT);
    ros::Subscriber left_tra_sub = node_handle.subscribe("/left_tra", 1, &skeletonLTListener::callback, &skeletonLT);
    ros::Subscriber right_glu_sub = node_handle.subscribe("/right_glu", 1, &skeletonRGListener::callback, &skeletonRG);   
    ros::Subscriber left_glu_sub = node_handle.subscribe("/left_glu", 1, &skeletonLGListener::callback, &skeletonLG);
    ros::Subscriber right_lat_sub = node_handle.subscribe("/right_lat", 1, &skeletonRLListener::callback, &skeletonRL);
    ros::Subscriber left_lat_sub = node_handle.subscribe("/left_lat", 1, &skeletonLLListener::callback, &skeletonLL);
    ros::Subscriber head_sub = node_handle.subscribe("/head", 1, &skeletonHEListener::callback, &skeletonHE);
    ros::Subscriber neck_sub = node_handle.subscribe("/neck", 1, &skeletonNEListener::callback, &skeletonNE);
    ros::Subscriber torso_sub = node_handle.subscribe("/torso", 1, &skeletonTOListener::callback, &skeletonTO);
    ros::Subscriber center_waist_sub = node_handle.subscribe("/center_waist", 1, &skeletonCHListener::callback, &skeletonCH);
    ros::Subscriber right_shoulder_sub = node_handle.subscribe("/right_shoulder", 1, &skeletonRSListener::callback, &skeletonRS);
    ros::Subscriber left_shoulder_sub = node_handle.subscribe("/left_shoulder", 1, &skeletonLSListener::callback, &skeletonLS);
    ros::Subscriber left_collar_sub = node_handle.subscribe("/left_collar", 1, &skeletonLCListener::callback, &skeletonLC);
    ros::Subscriber right_hip_sub = node_handle.subscribe("/right_hip", 1, &skeletonRHListener::callback, &skeletonRH);
    ros::Subscriber left_hip_sub = node_handle.subscribe("/left_hip", 1, &skeletonLHListener::callback, &skeletonLH);
    ros::Subscriber right_knee_sub = node_handle.subscribe("/right_knee", 1, &skeletonRKListener::callback, &skeletonRK);
    ros::Subscriber left_knee_sub = node_handle.subscribe("/left_knee", 1, &skeletonLKListener::callback, &skeletonLK);
    ros::Subscriber right_ankle_sub = node_handle.subscribe("/right_ankle", 1, &skeletonRAListener::callback, &skeletonRA);
    ros::Subscriber left_ankle_sub = node_handle.subscribe("/left_ankle", 1, &skeletonLAListener::callback, &skeletonLA);
    ros::Subscriber positions_sub = nh.subscribe("/jaka_driver/tool_position", 10, &positionsubscribe::callback, &current_position);
    //init Publisher
    ros::Publisher target_pose_pub = nh.advertise<geometry_msgs::Pose>("/record/target_pose_pub",1);
    ros::Publisher reference_force_pub = nh.advertise<geometry_msgs::WrenchStamped>("/record/reference_force",1);
    ros::Publisher method_pub = nh.advertise<std_msgs::Int32>("/massage_method",1);
    ros::Publisher count_pub = nh.advertise<std_msgs::Int32MultiArray>("/record/count_pub",1);
    ros::Publisher log_sign_pub=nh.advertise<std_msgs::String>("/record/log_sign_pub",1);

    std::vector<geometry_msgs::WrenchStamped> measured_biases;
    geometry_msgs::WrenchStamped bias;
    std_msgs::String log_sign;
    std::stringstream ss;
    jaka_msgs::Move joint_move;
    int i;
    int skeletal_count;
    
    servo_move_enable_client = nh.serviceClient<jaka_msgs::ServoMoveEnable>("/jaka_driver/servo_move_enable");
    movj = nh.serviceClient<jaka_msgs::Move>("/jaka_driver/joint_move");
    movj.waitForExistence();
    std_msgs::Int32 method_msg;

    
    method_msg.data = 0;
    method_pub.publish(method_msg);

    //ログ保存
    std::thread th1(save_log_csv);

    //初期位置まで移動
    ROS_INFO("Set Initial Point");
    double initial_pos[]={-30 * M_PI / 180, //28.5
                    180 * M_PI / 180,   //179.3
                    -155 * M_PI / 180,  //-154.5
                    65 * M_PI / 180,
                    270 * M_PI / 180,
                    -145 * M_PI / 180};
    for (int i = 0; i < 6; i++){
        joint_move.request.pose.push_back((initial_pos[i]));
    }
    joint_move.request.mvvelo = 0.3;
    joint_move.request.mvacc = 1.0;
    movj.call(joint_move);
    ros::Duration(1).sleep();
    joint_move.request.pose.clear();

    method_msg.data = 1; //hajimari sugu 111
    method_pub.publish(method_msg);

    // 安定した骨格位置を取得するために、数秒間データをサンプリングする
    const double sampling_duration = 2.0; 
    const int sampling_rate_hz = 20;
    const int num_samples = static_cast<int>(sampling_duration * sampling_rate_hz) + 2;

    // 必要な関節データのサンプルを格納するvectorをすべて宣言
    std::vector<geometry_msgs::Pose> rs_samples, ls_samples, neck_samples, to_samples, ch_samples;
    std::vector<geometry_msgs::Pose> rh_samples, rk_samples, lh_samples, lk_samples;
    std::vector<geometry_msgs::Pose> rg_samples, lg_samples;
    
    // メモリを事前に確保
    rs_samples.reserve(num_samples); ls_samples.reserve(num_samples);
    neck_samples.reserve(num_samples); to_samples.reserve(num_samples);
    rh_samples.reserve(num_samples); rk_samples.reserve(num_samples);
    lh_samples.reserve(num_samples); lk_samples.reserve(num_samples);
    rg_samples.reserve(num_samples); lg_samples.reserve(num_samples);
    ch_samples.reserve(num_samples);
    ros::Duration(1).sleep();
    ROS_INFO("Collecting skeletal data and biases for %.1f seconds. Please don't move...", sampling_duration);

    // 骨格情報の保存
    std::ofstream skelton_log("/home/isrlab/jaka_ws/src/jaka_driver/skeleton_sample.csv");
    if(!skelton_log.is_open())
    {
        ROS_ERROR_STREAM("can not open log file");
    }
    // skelton_log << "rs" << "," << "y" << "," << "z" << ","  << "x" << "," << "y" << "," << "z" << ","  << "w" << ","
    // << "ls" <<"," << "y" << "," << "z" << ","  << "x" << "," << "y" << "," << "z" << ","  << "w" << ","
    // << "rh" <<"," << "y" << "," << "z" << ","  << "x" << "," << "y" << "," << "z" << ","  << "w" << ","
    // << "rk" <<"," << "y" << "," << "z" << ","  << "x" << "," << "y" << "," << "z" << ","  << "w" << ","
    // << "lh" <<"," << "y" << "," << "z" << ","  << "x" << "," << "y" << "," << "z" << ","  << "w" << ","
    // << "lk" <<"," << "y" << "," << "z" << ","  << "x" << "," << "y" << "," << "z" << ","  << "w" << ","
    // << "neck" <<"," << "y" << "," << "z" << ","  << "x" << "," << "y" << "," << "z" << ","  << "w" << ","
    // << "to" <<"," << "y" << "," << "z" << ","  << "x" << "," << "y" << "," << "z" << ","  << "w" << ","
    // << "ch" <<"," << "y" << "," << "z" << ","  << "x" << "," << "y" << "," << "z" << ","  << "w" << ","
    // << "rg" <<"," << "y" << "," << "z" << ","  << "x" << "," << "y" << "," << "z" << ","  << "w" << ","
    // << "lg" <<"," << "y" << "," << "z" << ","  << "x" << "," << "y" << "," << "z" << ","  << "w" << std::endl;

    for (i = 0; i < 2 * int(CONTROL_HZ); i++){
        //ros::spinOnce();
        // ROS_INFO_STREAM(force_torque.data);
        measured_biases.push_back(force_torque.data);
        if(skeletal_count % 6 == 0){
            rs_samples.push_back(skeletonRS.data);
            ls_samples.push_back(skeletonLS.data);
            rh_samples.push_back(skeletonRH.data);
            rk_samples.push_back(skeletonRK.data);
            lh_samples.push_back(skeletonLH.data);
            lk_samples.push_back(skeletonLK.data);
            neck_samples.push_back(skeletonNE.data);
            to_samples.push_back(skeletonTO.data);
            ch_samples.push_back(skeletonCH.data);
            rg_samples.push_back(skeletonRG.data);
            lg_samples.push_back(skeletonLG.data);
            std::cout << skeletonRH.data.position << std::endl;
        }
        calib_timer.sleep();
        skeletal_count++;
    }


    // 2秒間計測した骨格の平均から骨格位置を算出
    geometry_msgs::Pose rs_pose = average_pose_position(rs_samples, method_pub);
    geometry_msgs::Pose ls_pose = average_pose_position(ls_samples, method_pub);
    geometry_msgs::Pose rh_pose = average_pose_position(rh_samples, method_pub);
    geometry_msgs::Pose rk_pose = average_pose_position(rk_samples, method_pub);
    geometry_msgs::Pose lh_pose = average_pose_position(lh_samples, method_pub);
    geometry_msgs::Pose lk_pose = average_pose_position(lk_samples, method_pub);
    geometry_msgs::Pose neck_pose = average_pose_position(neck_samples, method_pub);
    geometry_msgs::Pose to_pose = average_pose_position(to_samples, method_pub);
    geometry_msgs::Pose ch_pose = average_pose_position(ch_samples, method_pub);

    //手先の長さ分上げる調整
    rs_pose.position.z -= 210;
    ls_pose.position.z -= 210;
    rh_pose.position.z -= 210;
    rk_pose.position.z -= 210;
    lh_pose.position.z -= 210;
    lk_pose.position.z -= 210;
    neck_pose.position.z -= 210;
    to_pose.position.z -= 210;
    ch_pose.position.z -= 210;

    // 追加の骨格基準点を算出
    // 胸   首から腰までの1/4 (首とtorsoの中点)
    geometry_msgs::Pose chest_pose, waist_pose, right_glutealFold, left_glutealFold;
    chest_pose.position.x = (neck_pose.position.x + to_pose.position.x) / 2.0;
    chest_pose.position.y = (neck_pose.position.y + to_pose.position.y) / 2.0;
    chest_pose.position.z = (neck_pose.position.z + to_pose.position.z) / 2.0;
    chest_pose.orientation = neck_pose.orientation;
    // くびれ   腰から首までの1/4 (腰とtorsoの中点)　多分ここまで骨盤
    waist_pose.position.x = (to_pose.position.x + ch_pose.position.x) / 2.0;
    waist_pose.position.y = (to_pose.position.y + ch_pose.position.y) / 2.0;
    waist_pose.position.z = (to_pose.position.z + ch_pose.position.z) / 2.0;
    waist_pose.orientation = ch_pose.orientation;
    // 尻の下のライン右   尻からくびれまでの距離分下
    right_glutealFold.position.x = rh_pose.position.x - ((waist_pose.position.y - ch_pose.position.y) * (rh_pose.position.x - rk_pose.position.x) / (rh_pose.position.y - rk_pose.position.y));
    right_glutealFold.position.y = rh_pose.position.y - (waist_pose.position.y - ch_pose.position.y);
    right_glutealFold.position.z = rh_pose.position.z;
    right_glutealFold.orientation = rh_pose.orientation;
    // 尻の下のライン左   尻からくびれまでの距離分下
    left_glutealFold.position.x = lh_pose.position.x - ((waist_pose.position.y - ch_pose.position.y) * (lh_pose.position.x - lk_pose.position.x) / (lh_pose.position.y - lk_pose.position.y));
    left_glutealFold.position.y = lh_pose.position.y - (waist_pose.position.y - ch_pose.position.y);
    left_glutealFold.position.z = lh_pose.position.z;
    left_glutealFold.orientation = lh_pose.orientation;
    
    // セリフを言い切るための時間
    ros::Duration(2).sleep();

    // calc bias 力覚偏差計算
    bias = calc_bias(measured_biases);
    ROS_INFO("Data collection complete.");
    ROS_DEBUG_STREAM_NAMED("bias", bias);

    ROS_INFO("pre_pos");
    double pre_pos[]={0 * M_PI / 180,
                    180 * M_PI / 180,
                    -90 * M_PI / 180,
                    0 * M_PI / 180,
                    270 * M_PI / 180,
                    -145 * M_PI / 180};//74.8 * M_PI / 180, 1.6 * M_PI / 180, 90 * M_PI / 180, 110 * M_PI / 180, 92.8 * M_PI / 180, -17 * M_PI / 180};
    for (int i = 0; i < 6; i++){
        joint_move.request.pose.push_back((pre_pos[i]));
    }
    joint_move.request.mvvelo = 0.3;
    joint_move.request.mvacc = 1.0;
    movj.call(joint_move);
    ros::Duration(3).sleep();
    joint_move.request.pose.clear();

    //施術位置への位置制御
    geometry_msgs::Pose Target_pose1;

    double roll = 0, pitch = 0, yaw = 0;
    int push_count = 2;
    int part;
    int touch_area;
    double amplitude_x, amplitude_y;
    double w_x, w_y, t;
    double duration_time = 20.0;
    char force_answer;
    double force_added;
    bool force_decided = false;
    bool force_total_check = false;
    bool force_input_check = false;
    geometry_msgs::Wrench Target_force;
    std::string input_csv_path;
    geometry_msgs::Quaternion quater;
    ros::Publisher vel_publisher = nh.advertise<geometry_msgs::Twist>("velocity",1);
    geometry_msgs::Twist tcp_vel_message;

    Target_force.force.x = 0;
    Target_force.force.y = 0;
    Target_force.force.z = 50;//100;//5;//40;
    Target_force.torque.x = 0;
    Target_force.torque.y = 0;
    Target_force.torque.z = 0;

    ss << 'r';
    log_sign.data = ss.str();
    log_sign_pub.publish(log_sign);
    std::cout << log_sign.data << std::endl;
    roll = 0 * M_PI / 180;
    pitch = 0 * M_PI / 180;
    yaw = 0 * M_PI / 180;
    quater = rpy_to_geometry_quat(roll,pitch,yaw);
    Target_pose1.orientation.x = 0;
    Target_pose1.orientation.y = 0;
    Target_pose1.orientation.z = 0;
    Target_pose1.orientation.w = 1;

        //施術力決定パート (押さないで入力だけ)
        Target_force = determine_massage_force(Target_force, rh_pose, rk_pose,current_position.data,force_torque.data,bias,vel_publisher,tcp_vel_message,target_pose_pub,reference_force_pub,method_pub,count_pub);
        ROS_INFO_STREAM(Target_force);

        // --- 1. 背中の施術パート ---
        ROS_INFO("Now starting back massage part.");
        geometry_msgs::Wrench Back_Target_Force = Target_force; 

        // --- 1. 骨格データから基準点を計算 ---
        if (rs_pose.position.z == 0 || ls_pose.position.z == 0 || neck_pose.position.z == 0 || to_pose.position.z == 0 || chest_pose.position.z == 0 || waist_pose.position.z == 0) {
            ROS_ERROR("Back massage requires Shoulder, Neck, and Torso data. Skipping.");
            return 1;
        }
        geometry_msgs::Wrench target_force_touch, reference_force, current_point_force;
        double pressed_force_z_r[8], pressed_force_z_l[8];
        double pressed_force_rate_z_r[] = {1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0};
        double pressed_force_rate_z_l[] = {1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0};
        double move_time = 0.5;
        double height = 40;
        target_force_touch.force.z = 5.0;   //touchの接触力
        double Kp = 0.0014, Ki = 0.0001, Kd = 0.00005;

        // 肩幅から冠状方向のシフト量を算出
        geometry_msgs::Vector3 v_disp_h_right, v_disp_h_left;
        v_disp_h_right.x = (rs_pose.position.x - neck_pose.position.x) / 4.0;
        v_disp_h_right.y = (rs_pose.position.y - neck_pose.position.y) / 4.0;
        v_disp_h_right.z = (rs_pose.position.z - neck_pose.position.z) / 4.0;
        v_disp_h_left.x = (ls_pose.position.x - neck_pose.position.x) / 5.0;
        v_disp_h_left.y = (ls_pose.position.y - neck_pose.position.y) / 5.0;
        v_disp_h_left.z = (ls_pose.position.z - neck_pose.position.z) / 5.0;
        
        // 僧帽筋下部　広背筋上部
        geometry_msgs::Vector3 bt_disp;    //施術位置移動量
        bt_disp.x = (chest_pose.position.x - to_pose.position.x) / 3;
        bt_disp.y = (chest_pose.position.y - to_pose.position.y) / 3;
        bt_disp.z = (chest_pose.position.z - to_pose.position.z) / 3;
        // 1点目
        Target_pose1.position.x = chest_pose.position.x + v_disp_h_right.x;
        Target_pose1.position.y = chest_pose.position.y + v_disp_h_right.y;
        Target_pose1.position.z = chest_pose.position.z + v_disp_h_right.z;
        Target_pose1.position.x -= bt_disp.x;
        Target_pose1.position.y -= bt_disp.y;
        Target_pose1.position.z -= bt_disp.z;
        
        Target_pose1.position.z -= 110.0;
        
        // ▼▼▼ 背中用の基本の力を設定 ▼▼▼
        geometry_msgs::Wrench back_base_force = Target_force;
        back_base_force.force.z *= 1.0; 
        ROS_INFO("Base force for back massage set to %.1f N", back_base_force.force.z);
        
        // std::string csv_path = "/home/isrlab/jaka_ws/src/jaka_driver/TargetForce202512.csv"; 
        std::string csv_path = "/home/isrlab/jaka_ws/src/jaka_driver/TargetForce202601.csv"; 
        // std::string csv_path = "/home/isrlab/jaka_ws/src/jaka_driver/TargetForce202605.csv"; 
        double push_position_z;
        int lap_num = 3;
        // --- 2. 右背中の3点で指圧を実行 ---
        ROS_INFO("--- Starting Right Back Massage ---");
        geometry_msgs::Pose approach_pose = Target_pose1;
        ROS_INFO_STREAM(approach_pose);

        approach_pose.position.z += 20.0;
        std::cout << i << "th pushing pos" << std::endl;
        move_position(approach_pose, current_position.data, target_pose_pub, method_pub);
        touch(target_force_touch, current_position.data, force_torque.data, bias, vel_publisher, tcp_vel_message, reference_force_pub, method_pub);
        push_position_z = glo_position_feedback.twist.linear.z;
        finger_pressing(Target_pose1, current_position.data, Back_Target_Force, csv_path, Kp, Ki, Kd, force_torque.data, bias, push_count, target_force_touch, vel_publisher, tcp_vel_message, target_pose_pub, reference_force_pub, method_pub, count_pub);

        
        massage_points_forCSV.insert(massage_points_forCSV.end(), Target_pose1);
        // --- 全ての施術が完了した後の最終退避 ---
        ROS_INFO("Back massage finished. Retracting...");

        geometry_msgs::Pose final_escape_pose;
        final_escape_pose.position.x = glo_position_feedback.twist.linear.x;
        final_escape_pose.position.y = glo_position_feedback.twist.linear.y;
        final_escape_pose.position.z = glo_position_feedback.twist.linear.z - 50.0;

        move_position(final_escape_pose, glo_position_feedback, target_pose_pub, method_pub);

    std::ofstream massage_points_log("/home/isrlab/jaka_ws/src/jaka_driver/Ben_massage_log/" + getCurrentTimeStr() + "massage_points.csv");
    if(!skelton_log.is_open())
    {
        ROS_ERROR_STREAM("can not open log file");
    }
    massage_points_log << "," << "x" << "," << "y" << "," << "z" << ","  << "x" << "," << "y" << "," << "z" << ","  << "w" << std::endl;
    massage_points_log << "RS" << "," << rs_pose.position.x << "," << rs_pose.position.y << "," << rs_pose.position.z << "," << rs_pose.orientation.x << ","  << rs_pose.orientation.y << ","  << rs_pose.orientation.z << ","  << rs_pose.orientation.w << std::endl;
    massage_points_log << "LS" << "," << ls_pose.position.x << "," << ls_pose.position.y << "," << ls_pose.position.z << "," << ls_pose.orientation.x << ","  << ls_pose.orientation.y << ","  << ls_pose.orientation.z << ","  << ls_pose.orientation.w << std::endl;
    massage_points_log << "RH" << "," << rh_pose.position.x << "," << rh_pose.position.y << "," << rh_pose.position.z << "," << rh_pose.orientation.x << ","  << rh_pose.orientation.y << ","  << rh_pose.orientation.z << ","  << rh_pose.orientation.w << std::endl;
    massage_points_log << "RK" << "," << rk_pose.position.x << "," << rk_pose.position.y << "," << rk_pose.position.z << "," << rk_pose.orientation.x << ","  << rk_pose.orientation.y << ","  << rk_pose.orientation.z << ","  << rk_pose.orientation.w << std::endl;
    massage_points_log << "LH" << "," << lh_pose.position.x << "," << lh_pose.position.y << "," << lh_pose.position.z << "," << lh_pose.orientation.x << ","  << lh_pose.orientation.y << ","  << lh_pose.orientation.z << ","  << lh_pose.orientation.w << std::endl;
    massage_points_log << "LK" << "," << lk_pose.position.x << "," << lk_pose.position.y << "," << lk_pose.position.z << "," << lk_pose.orientation.x << ","  << lk_pose.orientation.y << ","  << lk_pose.orientation.z << ","  << lk_pose.orientation.w << std::endl;
    massage_points_log << "NE" << "," << neck_pose.position.x << "," << neck_pose.position.y << "," << neck_pose.position.z << "," << neck_pose.orientation.x << ","  << neck_pose.orientation.y << ","  << neck_pose.orientation.z << ","  << neck_pose.orientation.w << std::endl;
    massage_points_log << "TO" << "," << to_pose.position.x << "," << to_pose.position.y << "," << to_pose.position.z << "," << to_pose.orientation.x << ","  << to_pose.orientation.y << ","  << to_pose.orientation.z << ","  << to_pose.orientation.w << std::endl;
    massage_points_log << "CH" << "," << ch_pose.position.x << "," << ch_pose.position.y << "," << ch_pose.position.z << "," << ch_pose.orientation.x << ","  << ch_pose.orientation.y << ","  << ch_pose.orientation.z << ","  << ch_pose.orientation.w << std::endl;
    massage_points_log << "chest" << "," << chest_pose.position.x << "," << chest_pose.position.y << "," << chest_pose.position.z << "," << chest_pose.orientation.x << ","  << chest_pose.orientation.y << ","  << chest_pose.orientation.z << ","  << chest_pose.orientation.w << std::endl;
    massage_points_log << "waist" << "," << waist_pose.position.x << "," << waist_pose.position.y << "," << waist_pose.position.z << "," << waist_pose.orientation.x << ","  << waist_pose.orientation.y << ","  << waist_pose.orientation.z << ","  << waist_pose.orientation.w << std::endl;
    massage_points_log << "right_glutealFold" << "," << right_glutealFold.position.x << "," << right_glutealFold.position.y << "," << right_glutealFold.position.z << "," << right_glutealFold.orientation.x << ","  << right_glutealFold.orientation.y << ","  << right_glutealFold.orientation.z << ","  << right_glutealFold.orientation.w << std::endl;
    massage_points_log << "left_glutealFold" << "," << left_glutealFold.position.x << "," << left_glutealFold.position.y << "," << left_glutealFold.position.z << "," << left_glutealFold.orientation.x << ","  << left_glutealFold.orientation.y << ","  << left_glutealFold.orientation.z << ","  << left_glutealFold.orientation.w << std::endl;

    for (size_t i = 0; i < massage_points_forCSV.size(); i++) {
      massage_points_log << ",";
      massage_points_log << massage_points_forCSV[i].position.x << ",";
      massage_points_log << massage_points_forCSV[i].position.y << ",";
      massage_points_log << massage_points_forCSV[i].position.z << ",";
      massage_points_log << massage_points_forCSV[i].orientation.x << ",";
      massage_points_log << massage_points_forCSV[i].orientation.y << ",";
      massage_points_log << massage_points_forCSV[i].orientation.z << ",";
      massage_points_log << massage_points_forCSV[i].orientation.w << ",";
      massage_points_log << std::endl;
    }
    
     //初期位置に移動
    ROS_INFO("finishied. Now moving to initial position.");
    for (int i = 0; i < 6; i++){
        joint_move.request.pose.push_back((pre_pos[i]));
    }
    joint_move.request.mvvelo = 0.3;
    joint_move.request.mvacc = 1.0;
    movj.call(joint_move);
    ros::Duration(2.5).sleep();
    joint_move.request.pose.clear();

    for (int i = 0; i < 6; i++){
        joint_move.request.pose.push_back((initial_pos[i]));
    }
    joint_move.request.mvvelo = 0.3;
    joint_move.request.mvacc = 1.0;
    movj.call(joint_move);
    ros::Duration(2.5).sleep();
    joint_move.request.pose.clear();

    ROS_INFO_STREAM(glo_bias);

    end_sign = 1;
    th1.join();
    method_msg.data = 401;
    method_pub.publish(method_msg);
    log_sign.data.clear();
    log_sign_pub.publish(log_sign);
    // std::cout << log_sign.data <<std::endl;
    
    ros::Duration(1).sleep();
    method_msg.data = 0;
    method_pub.publish(method_msg);
    return 0;
}