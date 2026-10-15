"""Fan services exercise real entity platforms, with only command I/O mocked."""

from unittest.mock import AsyncMock, patch

import pytest
from conftest import account, device, setup_account
from pyintelliclima import FanMode, FanSpeed, IntelliClimaAPIError
from pyintelliclima.api import IntelliClimaEcocomfort2API, IntelliClimaEcocomfort3API


@pytest.mark.parametrize(
    ("mode", "speed", "state", "percentage", "preset"),
    [
        ("4", "18", "on", 50, "auto"),
        ("3", "3", "on", 75, None),
        ("0", "0", "off", 0, None),
        ("3", "35", "on", 100, None),
        ("3", "131", "on", 25, None),
    ],
)
async def test_effective_state(runtime, cloud, mode, speed, state, percentage, preset):
    cloud[0].return_value = account(device(mode_state=mode, speed_state=speed))
    await setup_account(runtime)
    await runtime.async_block_till_done()
    result = runtime.states.get("fan.fixture_3_1")
    assert result.state == state
    assert result.attributes["percentage"] == percentage
    assert result.attributes["preset_mode"] == preset


@pytest.mark.parametrize("generation", [2, 3])
@pytest.mark.parametrize(
    ("service", "payload", "method"),
    [
        ("set_percentage", {"percentage": 75}, "set_mode_speed"),
        ("turn_off", {}, "turn_off"),
        ("set_preset_mode", {"preset_mode": "auto"}, "set_mode_speed_auto"),
        ("turn_on", {"percentage": 25}, "set_mode_speed"),
    ],
)
async def test_service_routing(runtime, cloud, generation, service, payload, method):
    cloud[0].return_value = account(device(generation))
    cls = IntelliClimaEcocomfort3API if generation == 3 else IntelliClimaEcocomfort2API
    other = IntelliClimaEcocomfort2API if generation == 3 else IntelliClimaEcocomfort3API
    with (
        patch.object(
            IntelliClimaEcocomfort2API,
            "get_filter_status",
            AsyncMock(return_value=None),
        ),
        patch.object(cls, method, AsyncMock()) as command,
        patch.object(other, method, AsyncMock()) as wrong,
    ):
        await setup_account(runtime)
        await runtime.async_block_till_done()
        await runtime.services.async_call(
            "fan",
            service,
            {"entity_id": f"fan.fixture_{generation}_1", **payload},
            blocking=True,
        )
        command.assert_awaited_once()
        assert command.await_args.args[0] == device(generation).crono_sn
        if method == "set_mode_speed":
            assert command.await_args.args[1] == FanMode.sensor
            assert command.await_args.args[2] == (
                FanSpeed.medium if payload.get("percentage") == 75 else FanSpeed.sleep
            )
        wrong.assert_not_called()
        cloud[1].assert_not_called()


@pytest.mark.parametrize(
    ("service", "payload", "speed"),
    [
        ("turn_on", {"percentage": 75}, FanSpeed.medium),
        ("set_percentage", {"percentage": 75}, FanSpeed.medium),
        ("turn_on", {}, FanSpeed.high),
    ],
)
@pytest.mark.parametrize("effective_mode", ["1", "2", "3", "4"])
async def test_eco3_stale_off_setpoint_preserves_running_mode(
    runtime, cloud, service, payload, speed, effective_mode
):
    """An explicit positive speed must not replay a stale OFF setpoint."""
    cloud[0].return_value = account(
        device(mode_set=FanMode.off, mode_state=effective_mode, speed_state="35")
    )
    with (
        patch.object(IntelliClimaEcocomfort3API, "set_mode_speed", AsyncMock()) as command,
        patch.object(IntelliClimaEcocomfort2API, "set_mode_speed", AsyncMock()) as wrong,
    ):
        await setup_account(runtime)
        await runtime.async_block_till_done()
        assert runtime.states.get("fan.fixture_3_1").state == "on"
        await runtime.services.async_call(
            "fan", service, {"entity_id": "fan.fixture_3_1", **payload}, blocking=True
        )
        command.assert_awaited_once_with(device().crono_sn, FanMode(effective_mode), speed)
        wrong.assert_not_called()
        cloud[1].assert_not_called()


@pytest.mark.parametrize("failure", ["offline", "missing", "poll_error"])
async def test_unavailable_then_recovers(runtime, cloud, failure):
    cloud[0].return_value = account(device())
    flow = await setup_account(runtime)
    await runtime.async_block_till_done()
    coordinator = flow["result"].runtime_data.devices_coordinator
    if failure == "poll_error":
        cloud[0].side_effect = IntelliClimaAPIError("synthetic transport failure")
    else:
        cloud[0].return_value = (
            account() if failure == "missing" else account(device(online_status=False))
        )
    await coordinator.async_refresh()
    await runtime.async_block_till_done()
    assert runtime.states.get("fan.fixture_3_1").state == "unavailable"
    assert all(s.state == "unavailable" for s in runtime.states.async_all("sensor"))
    cloud[0].side_effect = None
    cloud[0].return_value = account(device())
    await coordinator.async_refresh()
    await runtime.async_block_till_done()
    assert runtime.states.get("fan.fixture_3_1").state == "on"
    cloud[1].assert_not_called()


async def test_bad_running_register_only_fan_unavailable(runtime, cloud):
    cloud[0].return_value = account(device(mode_state="invalid"))
    await setup_account(runtime)
    await runtime.async_block_till_done()
    state = runtime.states.get("fan.fixture_3_1")
    assert state is not None and state.state == "unavailable"
    assert runtime.states.get("sensor.fixture_3_1_temperature").state == "21.5"
