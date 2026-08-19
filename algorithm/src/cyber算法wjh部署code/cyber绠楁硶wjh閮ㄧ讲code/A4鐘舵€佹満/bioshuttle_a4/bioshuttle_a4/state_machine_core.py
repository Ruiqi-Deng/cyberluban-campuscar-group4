"""ROS-independent core for the BioShuttle seven-state machine."""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


class State(IntEnum):
    """State codes defined by the BioShuttle V3 manual."""

    IDLE = 0
    PICKUP = 1
    TRANSIT = 2
    AVOID = 3
    HANDOVER = 4
    RETURN = 5
    ERROR = 6


@dataclass(frozen=True)
class Transition:
    """A completed state transition."""

    previous: State
    current: State
    reason: str


class BioShuttleStateMachine:
    """Seven-state BioShuttle state machine.

    Level signals:
      obstacle, lid_closed, locked, error

    Event/arrival signals:
      new_task, arrived_pickup, arrived_handover,
      handover_done, arrived_home, manual_reset
    """

    def __init__(self, obstacle_clear_seconds: float = 1.0) -> None:
        if obstacle_clear_seconds < 0.0:
            raise ValueError("obstacle_clear_seconds must be >= 0")

        self.state = State.IDLE
        self.obstacle_clear_seconds = float(obstacle_clear_seconds)
        self._obstacle_clear_since: Optional[float] = None

    def _transition(self, new_state: State, reason: str) -> Transition:
        previous = self.state
        self.state = new_state
        self._obstacle_clear_since = None
        return Transition(previous=previous, current=new_state, reason=reason)

    def update(
        self,
        *,
        now: float,
        new_task: bool = False,
        arrived_pickup: bool = False,
        obstacle: bool = False,
        lid_closed: bool = False,
        locked: bool = False,
        arrived_handover: bool = False,
        handover_done: bool = False,
        arrived_home: bool = False,
        error: bool = False,
        manual_reset: bool = False,
    ) -> Optional[Transition]:
        """Evaluate inputs once and return a transition when one occurs."""

        # Any-state fault transition has the highest priority.
        if error and self.state != State.ERROR:
            return self._transition(State.ERROR, "检测到异常")

        if self.state == State.ERROR:
            # Reset is accepted only after the external error signal is cleared.
            if manual_reset and not error:
                return self._transition(State.IDLE, "异常已清除，人工复位")
            return None

        if self.state == State.IDLE:
            if new_task:
                return self._transition(State.PICKUP, "收到新任务")

        elif self.state == State.PICKUP:
            # The V3 manual requires arrival + lid closed + lock closed.
            if arrived_pickup and lid_closed and locked:
                return self._transition(
                    State.TRANSIT,
                    "到达取件点，箱盖已关闭且电子锁已锁闭",
                )

        elif self.state == State.TRANSIT:
            # Obstacle handling has priority over destination arrival.
            if obstacle:
                return self._transition(State.AVOID, "检测到障碍物")
            if arrived_handover:
                return self._transition(State.HANDOVER, "到达接驳点")

        elif self.state == State.AVOID:
            if obstacle:
                self._obstacle_clear_since = None
            else:
                if self._obstacle_clear_since is None:
                    self._obstacle_clear_since = now

                clear_duration = now - self._obstacle_clear_since
                if clear_duration >= self.obstacle_clear_seconds:
                    return self._transition(
                        State.TRANSIT,
                        f"障碍物连续消失 {self.obstacle_clear_seconds:.1f} 秒",
                    )

        elif self.state == State.HANDOVER:
            if handover_done:
                return self._transition(State.RETURN, "交接完成")

        elif self.state == State.RETURN:
            if arrived_home:
                return self._transition(State.IDLE, "到达充电点/起点")

        return None
