cmake_minimum_required(VERSION 3.8)
project(px_pir_cpp)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# ---- Dependencies ----
find_package(ament_cmake REQUIRED)
find_package(rclcpp      REQUIRED)
find_package(std_msgs    REQUIRED)

# ---- Executable ----
add_executable(pir_watch_node src/pir_watch_node.cpp)
ament_target_dependencies(pir_watch_node rclcpp std_msgs)

# ---- Install ----
install(TARGETS pir_watch_node
  DESTINATION lib/${PROJECT_NAME})

ament_package()
