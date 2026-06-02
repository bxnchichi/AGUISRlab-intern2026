#include "include/01Constant.hpp"

// For case of detecting excessive force
struct SafetyRetraction : public std::exception {};

jaka_msgs::ServoMoveEnable enable_state;
    ros::ServiceClient servo_move_enable_client;
    ros::ServiceClient servo_j_client;
    ros::ServiceClient movj;

int main(int argc, char *argv[]){
    //-----------------------------------------------------------------------------------------------------------------------------------------
    //  ___       _ _     ____   ___  ____  
    // |_ _|_ __ (_) |_  |  _ \ / _ \/ ___| 
    //  | || '_ \| | __| | |_) | | | \___ \ 
    //  | || | | | | |_  |  _ <| |_| |___) |
    // |___|_| |_|_|\__| |_| \_\\___/|____/ 
    //-----------------------------------------------------------------------------------------------------------------------------------------
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