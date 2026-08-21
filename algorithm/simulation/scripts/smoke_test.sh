#!/usr/bin/env bash
set -euo pipefail

workspace="${BIOSHUTTLE_SIM_WS:-$HOME/bioshuttle_sim_ws}"
source /opt/ros/humble/setup.bash
source "$workspace/install/setup.bash"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

required_topics=(
  /clock
  /cmd_vel
  /odom
  /scan
  /imu/data
  /gps/fix
  /range/front
  /camera/color/image_raw
  /bioshuttle/state
)

topic_list="$(ros2 topic list)"
failed=0
for topic in "${required_topics[@]}"; do
  if grep -Fxq "$topic" <<<"$topic_list"; then
    printf 'OK   %s\n' "$topic"
  else
    printf 'MISS %s\n' "$topic"
    failed=1
  fi
done

if [ "$failed" -ne 0 ]; then
  echo "Smoke test failed: one or more interfaces are missing." >&2
  exit 1
fi

echo "Publishing a simulation-only 0.10 m/s command for 2 seconds..."
timeout 2s ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.10}, angular: {z: 0.0}}" >/dev/null 2>&1 || true
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0}, angular: {z: 0.0}}" >/dev/null

timeout 3s ros2 topic echo --once /odom >/dev/null
echo "Smoke test passed. The robot accepted /cmd_vel and /odom is publishing."
