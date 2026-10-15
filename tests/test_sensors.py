"""ECO3 equivalent CO2 must come from voc_state, never co2."""

import pytest
from conftest import account, device, setup_account


async def test_eco3_equivalent_co2(runtime, cloud):
    cloud[0].return_value = account(device(voc_state="720", co2="4"))
    flow = await setup_account(runtime)
    await runtime.async_block_till_done()
    assert flow["type"] == "create_entry"
    sensors = runtime.states.async_all("sensor")
    equivalent = [
        s for s in sensors if s.attributes.get("friendly_name", "").endswith("Equivalent CO2")
    ]
    assert len(equivalent) == 1, sensors
    state = equivalent[0]
    assert state.state == "720.0"
    assert state.attributes["unit_of_measurement"] == "ppm"
    assert state.attributes.get("device_class") != "carbon_dioxide"
    assert not any("raw" in s.attributes.get("friendly_name", "").lower() for s in sensors)


@pytest.mark.parametrize(
    ("field", "raw", "suffix"),
    [
        ("tamb", "327.67", "temperature"),
        ("rh", "143", "humidity"),
        ("voc_state", "65535", "equivalent_co2"),
        ("voc_state", "", "equivalent_co2"),
        ("voc_state", None, "equivalent_co2"),
        ("tamb", "NaN", "temperature"),
        ("rh", "-1", "humidity"),
        ("rh", "101", "humidity"),
    ],
)
async def test_invalid_measurement_is_unknown(runtime, cloud, field, raw, suffix):
    cloud[0].return_value = account(device(**{field: raw}))
    await setup_account(runtime)
    await runtime.async_block_till_done()
    state = runtime.states.get("sensor.fixture_3_1_" + suffix)
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1", "1.0"),
        ("5", "5.0"),
        ("143", "unknown"),
        ("0", "unknown"),
        ("6", "unknown"),
        (None, "unknown"),
    ],
)
async def test_vendor_air_quality_index(runtime, cloud, raw, expected):
    cloud[0].return_value = account(device(aqi=raw))
    await setup_account(runtime)
    await runtime.async_block_till_done()
    state = runtime.states.get("sensor.fixture_3_1_air_quality_index")
    assert state is not None
    assert state.state == expected
    assert "device_class" not in state.attributes
