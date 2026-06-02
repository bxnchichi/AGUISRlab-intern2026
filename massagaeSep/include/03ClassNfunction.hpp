#include "00Library.hpp"
#include "01Constant.hpp"

//-----------------------------------------------------------------------------------------------------------------------------------------
//   ____      _            _       _   _             
//  / ___|__ _| | ___ _   _| | __ _| |_(_) ___  _ __  
// | |   / _` | |/ __| | | | |/ _` | __| |/ _ \| '_ \ 
// | |__| (_| | | (__| |_| | | (_| | |_| | (_) | | | |
//  \____\__,_|_|\___|\__,_|_|\__,_|\__|_|\___/|_| |_|
//-----------------------------------------------------------------------------------------------------------------------------------------

// no idea what this is for
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


//平均を求める関数
double mean(std::vector<double> data) {
    double sum = 0;
    for (auto e : data){
        sum += e;
    }
    return sum / (double)data.size();
}

//偏差の計算
//Calculate bias
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
    bias.wrench.torque.z = mean(torque_z_data)
    glo_bias = bias;

    return bias;
}

//偏差除去
//Remove bias from sensed data probably before using it for control
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

//noise reduction for force-torque data using low-pass filter
//ローパスフィルタ
//Low-pass filter(old version not used) same calculation as LPF_new but for double value
double LPF(double u, double ub, double yb, double cut_fre){
    double Ts = 1 / CONTROL_HZ;  //サンプリング周期
    double T = 1 / (2 * M_PI * cut_fre);  //カットオフ周波数から時定数を求める
    double C_y = (2 * T - Ts) / (2 * T + Ts);   //出力値の方の係数
    double C_u = Ts / (2 * T + Ts); //入力値の方の係数
    double y = C_y * yb + C_u * (u + ub);
    return y;
}

//ローパスフィルタ
//Low-pass filter(new version for vector form)
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

//----------------------------------------------------------------------------------------------------------------------------------------------------------
//  ____        _          _                        
// |  _ \  __ _| |_ __ _  | |_ _   _ _ __   ___     
// | | | |/ _` | __/ _` | | __| | | | '_ \ / _ \    
// | |_| | (_| | || (_| | | |_| |_| | |_) |  __/    
// |____/ \__,_|\__\__,_|  \__|\__, | .__/ \___|    
//                             |___/|_|             
//   ___ ___  _ ____   _____ _ __ ___(_) ___  _ __  
//  / __/ _ \| '_ \ \ / / _ \ '__/ __| |/ _ \| '_ \ 
// | (_| (_) | | | \ V /  __/ |  \__ \ | (_) | | | |
//  \___\___/|_| |_|\_/ \___|_|  |___/_|\___/|_| |_|
//----------------------------------------------------------------------------------------------------------------------------------------------------------

//change form of the orientation storing from RPY to geometry_msgs::Quaternion
geometry_msgs::Quaternion rpy_to_geometry_quat(double roll, double pitch, double yaw){
	tf::Quaternion quat = tf::createQuaternionFromRPY(roll, pitch, yaw);
	geometry_msgs::Quaternion geometry_quat;
	quaternionTFToMsg(quat, geometry_quat);
	return geometry_quat;
}

//not used
//change form of the orientation storing from geometry_msgs::Quaternion to RPY
void geometry_quat_to_rpy(double& roll, double& pitch, double& yaw, geometry_msgs::Quaternion geometry_quat){
	tf::Quaternion quat;
	quaternionMsgToTF(geometry_quat, quat);
	tf::Matrix3x3(quat).getRPY(roll, pitch, yaw);  //rpy are Pass by Reference -> update the value of roll, pitch, yaw (input)
}

//change to ROs::wrenchstamped to string (not used)
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

//change to ROs::posestamped to string (not used)
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

//----------------------------------------------------------------------------------------------------------------------------------------------------------
//  ____           _ _   _                ____            _             _ 
// |  _ \ ___  ___(_) |_(_) ___  _ __    / ___|___  _ __ | |_ _ __ ___ | |
// | |_) / _ \/ __| | __| |/ _ \| '_ \  | |   / _ \| '_ \| __| '__/ _ \| |
// |  __/ (_) \__ \ | |_| | (_) | | | | | |__| (_) | | | | |_| | | (_) | |
// |_|   \___/|___/_|\__|_|\___/|_| |_|  \____\___/|_| |_|\__|_|  \___/|_|
//----------------------------------------------------------------------------------------------------------------------------------------------------------


//位置制御で目標の位置に達したか確認する関数
//Determine if the robot has reached the target position in position control
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

//指定位置まで曲線で動く関数
//move to the target position with spline trajectory (cruve) not linear trajectory
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

//------------------------------------------------------------------------------------------------------------------------------------------
//  _                
// | |    ___   __ _ 
// | |   / _ \ / _` |
// | |__| (_) | (_| |
// |_____\___/ \__, |
//             |___/ 
//------------------------------------------------------------------------------------------------------------------------------------------
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