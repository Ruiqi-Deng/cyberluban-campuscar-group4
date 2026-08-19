from bioshuttle_a4.state_machine_core import BioShuttleStateMachine, State


def update(machine, now, **kwargs):
    defaults = {
        "new_task": False,
        "arrived_pickup": False,
        "obstacle": False,
        "lid_closed": False,
        "locked": False,
        "arrived_handover": False,
        "handover_done": False,
        "arrived_home": False,
        "error": False,
        "manual_reset": False,
    }
    defaults.update(kwargs)
    return machine.update(now=now, **defaults)


def test_complete_path():
    machine = BioShuttleStateMachine(obstacle_clear_seconds=1.0)

    update(machine, 0.0, new_task=True)
    assert machine.state == State.PICKUP

    update(
        machine,
        1.0,
        arrived_pickup=True,
        lid_closed=True,
        locked=True,
    )
    assert machine.state == State.TRANSIT

    update(machine, 2.0, obstacle=True)
    assert machine.state == State.AVOID

    update(machine, 3.0, obstacle=False)
    assert machine.state == State.AVOID
    update(machine, 4.0, obstacle=False)
    assert machine.state == State.TRANSIT

    update(machine, 5.0, arrived_handover=True)
    assert machine.state == State.HANDOVER

    update(machine, 6.0, handover_done=True)
    assert machine.state == State.RETURN

    update(machine, 7.0, arrived_home=True)
    assert machine.state == State.IDLE


def test_pickup_requires_lid_and_lock():
    machine = BioShuttleStateMachine()
    update(machine, 0.0, new_task=True)

    update(machine, 1.0, arrived_pickup=True, lid_closed=True, locked=False)
    assert machine.state == State.PICKUP

    update(machine, 2.0, arrived_pickup=True, lid_closed=True, locked=True)
    assert machine.state == State.TRANSIT


def test_error_has_highest_priority_and_requires_clear_before_reset():
    machine = BioShuttleStateMachine()
    update(machine, 0.0, new_task=True)
    assert machine.state == State.PICKUP

    update(machine, 1.0, error=True)
    assert machine.state == State.ERROR

    update(machine, 2.0, error=True, manual_reset=True)
    assert machine.state == State.ERROR

    update(machine, 3.0, error=False, manual_reset=True)
    assert machine.state == State.IDLE
