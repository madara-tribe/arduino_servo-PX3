/**
 * PIR Watch Node — C++ / Telemetrix binary protocol
 * SeamlessTrack-PX / px_pir_cpp package
 *
 * No C++ Telemetrix library exists, so this node implements the
 * relevant subset of the Telemetrix binary protocol over POSIX serial.
 *
 * Firmware : Telemetrix4Arduino.ino (no modification needed)
 * Hardware : SB612B OUT -> Arduino D2
 *
 * Topics published:
 *   /pir/state   std_msgs/Bool    true=detected, false=cleared
 *   /pir/event   std_msgs/String  JSON {event, pin, dur_ms}
 *
 * Parameters:
 *   com_port      (string, default "/dev/ttyACM0")
 *   pir_pin       (int,    default 2)
 *   heartbeat_sec (double, default 5.0)
 *   debounce_ms   (int,    default 50)
 *
 * -----------------------------------------------------------------------
 * Telemetrix binary protocol (relevant subset)
 * -----------------------------------------------------------------------
 * Client -> Server frame:
 *   [packet_length, command, data...]
 *   packet_length = 1 (command only) + number of data bytes
 *
 * Useful commands:
 *   ARE_U_THERE (6):  {1, 6}
 *   SET_PIN_MODE (1): {4, 1, pin, mode, reporting_enabled}
 *     mode: INPUT=0, OUTPUT=1, INPUT_PULLUP=2
 *
 * Server -> Client frame:
 *   [total_bytes_following, report_type, data...]
 *
 * Useful reports:
 *   I_AM_HERE     (6):  [2, 6, arduino_id]
 *   DIGITAL_REPORT(2):  [3, 2, pin, value]
 *   FIRMWARE_REPORT(5): [4, 5, major, minor, patch]
 */

#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/bool.hpp>
#include <std_msgs/msg/string.hpp>

#include <atomic>
#include <chrono>
#include <cstring>
#include <fcntl.h>
#include <iomanip>
#include <mutex>
#include <sstream>
#include <string>
#include <termios.h>
#include <thread>
#include <unistd.h>

// -----------------------------------------------------------------------
// Telemetrix command / report IDs (from Telemetrix4Arduino.ino)
// -----------------------------------------------------------------------
static constexpr uint8_t CMD_SET_PIN_MODE      = 1;
static constexpr uint8_t CMD_ARE_U_THERE       = 6;
static constexpr uint8_t CMD_GET_FIRMWARE      = 5;

static constexpr uint8_t REPORT_DIGITAL        = 2;   // DIGITAL_REPORT
static constexpr uint8_t REPORT_I_AM_HERE      = 6;   // I_AM_HERE
static constexpr uint8_t REPORT_FIRMWARE       = 5;   // FIRMWARE_REPORT

static constexpr uint8_t PIN_MODE_INPUT        = 0;
static constexpr uint8_t REPORTING_ENABLED     = 1;


// -----------------------------------------------------------------------
// PIRWatchNode
// -----------------------------------------------------------------------
class PIRWatchNode : public rclcpp::Node
{
public:
    PIRWatchNode()
    : Node("pir_watch_node"), fd_(-1), running_(false),
      detected_(false), detect_start_{}, detection_count_(0), total_dur_ms_(0)
    {
        // ---- Parameters ----
        declare_parameter<std::string>("com_port",      "/dev/ttyACM0");
        declare_parameter<int>        ("pir_pin",       2);
        declare_parameter<double>     ("heartbeat_sec", 5.0);
        declare_parameter<int>        ("debounce_ms",   50);

        com_port_      = get_parameter("com_port").as_string();
        pir_pin_       = static_cast<uint8_t>(get_parameter("pir_pin").as_int());
        heartbeat_sec_ = get_parameter("heartbeat_sec").as_double();
        debounce_ms_   = get_parameter("debounce_ms").as_int();

        // ---- Publishers ----
        state_pub_ = create_publisher<std_msgs::msg::Bool>  ("/pir/state", 10);
        event_pub_ = create_publisher<std_msgs::msg::String>("/pir/event", 10);

        // ---- Heartbeat timer ----
        // [FIX 1] create_timer() does not exist in ROS2 Foxy.
        // Use create_wall_timer() with an integer-typed chrono duration.
        // std::chrono::duration<double> is rejected; cast to milliseconds first.
        hb_timer_ = create_wall_timer(
            std::chrono::milliseconds(static_cast<int>(heartbeat_sec_ * 1000.0)),
            std::bind(&PIRWatchNode::heartbeat_cb, this));

        // ---- Serial connection ----
        if (!open_serial(com_port_)) {
            throw std::runtime_error("Failed to open serial: " + com_port_);
        }
        RCLCPP_INFO(get_logger(), "Connected to %s", com_port_.c_str());

        // ---- Telemetrix handshake + pin setup ----
        std::this_thread::sleep_for(std::chrono::seconds(2));  // Arduino reset
        if (!telemetrix_handshake()) {
            RCLCPP_WARN(get_logger(), "Handshake failed — continuing anyway");
        }
        set_pin_mode_digital_input(pir_pin_);
        RCLCPP_INFO(get_logger(),
            "PIR watch node ready. pin=D%d, port=%s, heartbeat=%.1fs",
            pir_pin_, com_port_.c_str(), heartbeat_sec_);

        // ---- Reader thread ----
        running_ = true;
        reader_thread_ = std::thread(&PIRWatchNode::read_loop, this);

        start_time_ = std::chrono::steady_clock::now();
    }

    ~PIRWatchNode()
    {
        running_ = false;
        if (fd_ >= 0) { ::close(fd_); fd_ = -1; }
        if (reader_thread_.joinable()) reader_thread_.join();
        print_summary();
    }

private:
    // ===================================================================
    // Serial (POSIX termios)
    // ===================================================================
    bool open_serial(const std::string& port)
    {
        fd_ = ::open(port.c_str(), O_RDWR | O_NOCTTY | O_SYNC);
        if (fd_ < 0) {
            RCLCPP_ERROR(get_logger(), "open(%s): %s", port.c_str(), strerror(errno));
            return false;
        }

        struct termios tty{};
        tcgetattr(fd_, &tty);
        cfsetospeed(&tty, B115200);
        cfsetispeed(&tty, B115200);

        tty.c_cflag  = (tty.c_cflag & ~CSIZE) | CS8;
        tty.c_cflag &= ~(PARENB | CSTOPB | CRTSCTS);
        tty.c_cflag |=  (CLOCAL | CREAD);
        tty.c_lflag &= ~(ICANON | ECHO | ECHOE | ISIG);
        tty.c_iflag &= ~(IXON | IXOFF | IXANY | ICRNL | INLCR);
        tty.c_oflag &= ~OPOST;
        tty.c_cc[VMIN]  = 0;
        tty.c_cc[VTIME] = 10;  // 1s timeout

        tcsetattr(fd_, TCSANOW, &tty);
        return true;
    }

    void serial_write(const uint8_t* buf, size_t n)
    {
        std::lock_guard<std::mutex> lk(write_mtx_);
        ::write(fd_, buf, n);
    }

    // ===================================================================
    // Telemetrix protocol helpers
    // ===================================================================

    // ARE_U_THERE handshake: send {1, 6}, expect [2, 6, arduino_id]
    bool telemetrix_handshake()
    {
        uint8_t cmd[2] = {1, CMD_ARE_U_THERE};
        serial_write(cmd, 2);

        // Wait up to 2 s for I_AM_HERE report
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
        uint8_t buf[16];
        while (std::chrono::steady_clock::now() < deadline) {
            ssize_t n = ::read(fd_, buf, 1);
            if (n < 1) continue;
            uint8_t len = buf[0];
            if (len == 0 || len > sizeof(buf) - 1) continue;
            // Read remaining bytes
            size_t got = 0;
            while (got < len) {
                ssize_t r = ::read(fd_, buf + got, len - got);
                if (r > 0) got += r;
            }
            if (len >= 2 && buf[0] == REPORT_I_AM_HERE) {
                RCLCPP_INFO(get_logger(),
                    "Telemetrix handshake OK (Arduino ID=%d)", buf[1]);
                return true;
            }
        }
        return false;
    }

    // SET_PIN_MODE: {4, 1, pin, INPUT(0), reporting_enabled(1)}
    void set_pin_mode_digital_input(uint8_t pin)
    {
        uint8_t cmd[5] = {4, CMD_SET_PIN_MODE, pin, PIN_MODE_INPUT, REPORTING_ENABLED};
        serial_write(cmd, 5);
        RCLCPP_INFO(get_logger(), "SET_PIN_MODE D%d as digital input (reporting ON)", pin);
    }

    // ===================================================================
    // Reader thread
    // ===================================================================
    void read_loop()
    {
        while (running_ && rclcpp::ok()) {
            uint8_t len_byte = 0;
            ssize_t n = ::read(fd_, &len_byte, 1);
            if (n <= 0) continue;  // timeout or error

            uint8_t len = len_byte;
            if (len == 0 || len > 32) continue;  // sanity check

            // Read exactly `len` bytes
            uint8_t frame[32];
            size_t got = 0;
            while (got < len && running_) {
                ssize_t r = ::read(fd_, frame + got, len - got);
                if (r > 0) got += r;
            }
            if (got < len) break;

            process_report(frame, len);
        }
    }

    // ===================================================================
    // Report dispatcher
    // ===================================================================
    void process_report(const uint8_t* frame, uint8_t len)
    {
        if (len < 1) return;
        const uint8_t report_type = frame[0];

        switch (report_type) {

        case REPORT_DIGITAL:
            // [DIGITAL_REPORT, pin, value]
            if (len >= 3) {
                on_digital_change(frame[1], frame[2]);
            }
            break;

        case REPORT_I_AM_HERE:
            if (len >= 2) {
                RCLCPP_INFO(get_logger(),
                    "I_AM_HERE (Arduino ID=%d)", frame[1]);
            }
            break;

        case REPORT_FIRMWARE:
            if (len >= 4) {
                RCLCPP_INFO(get_logger(),
                    "Firmware v%d.%d.%d", frame[1], frame[2], frame[3]);
            }
            break;

        default:
            break;
        }
    }

    // ===================================================================
    // PIR detection logic (mirrors Python pir_callback)
    // ===================================================================
    void on_digital_change(uint8_t pin, uint8_t value)
    {
        using clock = std::chrono::steady_clock;

        // Debounce
        const auto now = clock::now();
        const auto elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
            now - last_change_t_).count();
        if (elapsed_ms < debounce_ms_) return;
        last_change_t_ = now;

        const std::string ts = now_str();

        if (value == 1 && !detected_.load()) {
            // Rising edge — detection start
            detected_        = true;
            detect_start_    = now;
            detection_count_++;
            RCLCPP_INFO(get_logger(),
                "[%s] PIR DETECTED  (#%d, pin=D%d)",
                ts.c_str(), detection_count_.load(), pin);
            publish_state(true);
            publish_event("detect_start", pin, 0);

        } else if (value == 0 && detected_.load()) {
            // Falling edge — detection end
            detected_ = false;
            const long dur_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                now - detect_start_).count();
            total_dur_ms_ += dur_ms;
            RCLCPP_INFO(get_logger(),
                "[%s] PIR CLEARED   (duration: %.2fs, pin=D%d)",
                ts.c_str(), dur_ms / 1000.0, pin);
            publish_state(false);
            publish_event("detect_end", pin, dur_ms);
        }
    }

    // ===================================================================
    // Heartbeat (ROS timer — runs in executor thread)
    // ===================================================================
    void heartbeat_cb()
    {
        long dur_ms = 0;
        if (detected_.load()) {
            dur_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - detect_start_).count();
        }
        const char* state_str = detected_.load() ? "ACTIVE" : "idle";
        RCLCPP_INFO(get_logger(),
            "PIR heartbeat (%s, dur=%ldms, count=%d)",
            state_str, dur_ms, detection_count_.load());
        publish_event("heartbeat", pir_pin_, dur_ms);
    }

    // ===================================================================
    // Publish helpers
    // ===================================================================
    void publish_state(bool detected)
    {
        std_msgs::msg::Bool msg;
        msg.data = detected;
        state_pub_->publish(msg);
    }

    void publish_event(const std::string& event, uint8_t pin, long dur_ms)
    {
        std::ostringstream oss;
        oss << "{\"event\":\"" << event << "\","
            << "\"pin\":"    << static_cast<int>(pin)   << ","
            << "\"dur_ms\":" << dur_ms << "}";
        std_msgs::msg::String msg;
        msg.data = oss.str();
        event_pub_->publish(msg);
    }

    // ===================================================================
    // Helpers
    // ===================================================================
    static std::string now_str()
    {
        using namespace std::chrono;
        auto tp  = system_clock::now();
        auto ms  = duration_cast<milliseconds>(tp.time_since_epoch()) % 1000;
        std::time_t t = system_clock::to_time_t(tp);
        std::tm tm_s;
        localtime_r(&t, &tm_s);
        std::ostringstream oss;
        oss << std::setfill('0')
            << std::setw(2) << tm_s.tm_hour << ':'
            << std::setw(2) << tm_s.tm_min  << ':'
            << std::setw(2) << tm_s.tm_sec  << '.'
            << std::setw(3) << ms.count();
        return oss.str();
    }

    void print_summary()
    {
        const double elapsed =
            std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - start_time_).count() / 1000.0;
        const int cnt = detection_count_.load();
        const double avg = cnt > 0 ? total_dur_ms_ / static_cast<double>(cnt) / 1000.0 : 0.0;

        std::cout << "\nVALIDATION SUMMARY\n"
                  << std::string(60, '=') << '\n'
                  << "  Total runtime:      " << std::fixed << std::setprecision(1)
                  << elapsed << " seconds\n"
                  << "  Detection count:    " << cnt << '\n'
                  << "  Average duration:   " << std::setprecision(2) << avg << " seconds\n"
                  << "  Total detect time:  " << total_dur_ms_ / 1000.0 << " seconds\n"
                  << std::string(60, '=') << '\n';

        if (cnt > 0)
            std::cout << "\n\u2713 Sensor is working correctly!\n";
        else
            std::cout << "\n\u26A0 No detections. Check wiring and warm-up (~30s).\n";
    }

    // ===================================================================
    // Members
    // ===================================================================
    // Serial
    int           fd_;          // init order 1 (matches ": fd_(-1), ...")
    std::mutex    write_mtx_;
    std::string   com_port_;

    // Params
    uint8_t       pir_pin_;
    double        heartbeat_sec_;
    int           debounce_ms_;

    // Thread
    // [FIX 2] Declare running_ BEFORE detected_ so the declaration order
    // matches the constructor initializer list:
    //   Node(...), fd_(-1), running_(false), detected_(false), ...
    // Mismatched order triggers -Wreorder (warning treated as build noise,
    // but fixing it prevents subtle initialization bugs).
    std::atomic<bool> running_;   // init order 2
    std::thread       reader_thread_;

    // State
    std::atomic<bool>  detected_;  // init order 3
    std::chrono::steady_clock::time_point detect_start_;
    std::chrono::steady_clock::time_point last_change_t_{};
    std::atomic<int>   detection_count_;
    long               total_dur_ms_{0};
    std::chrono::steady_clock::time_point start_time_;

    // ROS
    rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr   state_pub_;
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr event_pub_;
    rclcpp::TimerBase::SharedPtr                        hb_timer_;
};


// -----------------------------------------------------------------------
int main(int argc, char* argv[])
{
    rclcpp::init(argc, argv);
    try {
        auto node = std::make_shared<PIRWatchNode>();
        rclcpp::spin(node);
    } catch (const std::exception& e) {
        RCLCPP_ERROR(rclcpp::get_logger("main"), "Fatal: %s", e.what());
    }
    rclcpp::shutdown();
    return 0;
}
