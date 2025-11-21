// inference.cpp
#include <chrono>
#include <memory>
#include <opencv2/opencv.hpp>
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/float32.hpp"

using namespace std::chrono;

class InferenceNode : public rclcpp::Node {
public:
  InferenceNode() : Node("inference") {
    declare_parameter<int>("device_index", 0);
    declare_parameter<int>("width", 640);
    declare_parameter<int>("height", 480);
    declare_parameter<int>("fps", 60);

    int dev = get_parameter("device_index").as_int();
    int w   = get_parameter("width").as_int();
    int h   = get_parameter("height").as_int();
    int fps = get_parameter("fps").as_int();

    pub_ = create_publisher<std_msgs::msg::Float32>("abs_angle", 10);

    cap_.open(dev, cv::CAP_V4L2);
    if (!cap_.isOpened()) cap_.open(dev);
    if (!cap_.isOpened()) throw std::runtime_error("Failed to open camera");
    cap_.set(cv::CAP_PROP_FRAME_WIDTH,  w);
    cap_.set(cv::CAP_PROP_FRAME_HEIGHT, h);
    cap_.set(cv::CAP_PROP_FPS,          fps);

    auto period = std::chrono::milliseconds(1000 / std::max(1, fps));
    timer_ = create_wall_timer(period, std::bind(&InferenceNode::tick, this));

    RCLCPP_INFO(get_logger(), "inference started (dev=%d %dx%d@%dfps)", dev, w, h, fps);
  }

private:
  void tick() {
    cv::Mat frame;
    if (!cap_.read(frame) || frame.empty()) return;

    // TODO: run YOLO and compute the true angle here:
    float x_angle_deg = 90.0f;

    std_msgs::msg::Float32 m;
    m.data = x_angle_deg;
    pub_->publish(m);
  }

  rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr pub_;
  rclcpp::TimerBase::SharedPtr timer_;
  cv::VideoCapture cap_;
};

int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<InferenceNode>());
  rclcpp::shutdown();
  return 0;
}
