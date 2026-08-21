#!/usr/bin/env bash
set -euo pipefail

workspace="${BIOSHUTTLE_SIM_WS:-$HOME/bioshuttle_sim_ws}"
if [ ! -r "$workspace/install/setup.bash" ]; then
  echo "Simulation workspace is not built. Run simulation/scripts/build_sim.sh first." >&2
  exit 1
fi

source /opt/ros/humble/setup.bash
source "$workspace/install/setup.bash"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

exec ros2 launch bioshuttle_sim bioshuttle_sim.launch.py "$@"
