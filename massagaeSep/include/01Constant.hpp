#ifndef INCLUDE_CONSTANT_HPP
#define INCLUDE_CONSTANT_HPP
#include "00Library.hpp"

#define CONTROL_HZ 125.0
//variables for control and CSV file
extern int end_sign;
extern double glo_error;
extern double glo_kp, glo_ki, glo_kd;
extern int glo_count;
//Init global variables but with ros message types!!
extern geometry_msgs::Vector3 glo_vel; //in vector form
extern std::string glo_method;
extern geometry_msgs::Pose glo_target_pose;
extern geometry_msgs::TwistStamped glo_position_feedback; //Current Position
// wrench contains force and torque in x, y, z
extern geometry_msgs::WrenchStamped glo_force_torque_calibrated;  //Current bias-corrected force-torque
extern geometry_msgs::WrenchStamped glo_bias;
extern geometry_msgs::Wrench glo_target_force;  //Target Force
extern geometry_msgs::Wrench glo_raw_force;  //Force from sensor
extern geometry_msgs::WrenchStamped glo_force_torque_LPF;  //Low-pass filtered force-torque
extern geometry_msgs::WrenchStamped glo_recieved_msg;

extern std::vector<geometry_msgs::Pose> massage_points_forCSV; // Positions for massage saved in CSV
#endif // INCLUDE_CONSTANT_HPP

// #ifndef INCLUDE_CONSTANT_HPP
// #define INCLUDE_CONSTANT_HPP
// #include "00Library.hpp"

// #define CONTROL_HZ 125.0
// //variables for control and CSV file
// int end_sign = 0;
// double glo_error;
// double glo_kp, glo_ki, glo_kd;
// int glo_count;
// //Init global variables but with ros message types!!
// geometry_msgs::Vector3 glo_vel; //in vector form
// std::string glo_method;
// geometry_msgs::Pose glo_target_pose;
// geometry_msgs::TwistStamped glo_position_feedback; //Current Position
// // wrench contains force and torque in x, y, z
// geometry_msgs::WrenchStamped glo_force_torque_calibrated;  //Current bias-corrected force-torque
// geometry_msgs::WrenchStamped glo_bias;
// geometry_msgs::Wrench glo_target_force;  //Target Force
// geometry_msgs::Wrench glo_raw_force;  //Force from sensor
// geometry_msgs::WrenchStamped glo_force_torque_LPF;  //Low-pass filtered force-torque
// geometry_msgs::WrenchStamped glo_recieved_msg;

// std::vector<geometry_msgs::Pose> massage_points_forCSV; // Positions for massage saved in CSV

// using namespace std;
// #endif // INCLUDE_CONSTANT_HPP