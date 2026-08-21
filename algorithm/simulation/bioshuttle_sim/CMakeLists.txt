cmake_minimum_required(VERSION 3.8)
project(bioshuttle_sim)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY launch urdf worlds config
  DESTINATION share/${PROJECT_NAME}
)

install(
  PROGRAMS
    scripts/bioshuttle_state_machine.py
    scripts/sim_apriltag_localizer.py
    scripts/sim_gps_node.py
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
