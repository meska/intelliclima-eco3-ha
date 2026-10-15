"""Flow error paths and redacted coordinator errors."""

import pytest
from conftest import account, device, setup_account
from pyintelliclima import IntelliClimaAPIError, IntelliClimaAuthError


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (IntelliClimaAuthError("fixture"), "invalid_auth"),
        (IntelliClimaAPIError("fixture"), "cannot_connect"),
    ],
)
async def test_flow_errors(runtime, cloud, error, expected):
    cloud[0].side_effect = error
    flow = await setup_account(runtime)
    assert flow["errors"] == {"base": expected}
    assert not runtime.config_entries.async_entries("intelliclima")


async def test_empty_account(runtime, cloud):
    cloud[0].return_value = account()
    flow = await setup_account(runtime)
    assert flow["errors"] == {"base": "no_devices"}


async def test_duplicate_account(runtime, cloud):
    cloud[0].return_value = account(device())
    await setup_account(runtime)
    await runtime.async_block_till_done()
    flow = await setup_account(runtime)
    assert flow["type"] == "abort" and flow["reason"] == "already_configured"


async def test_errors_do_not_leak_urls(runtime, cloud, caplog):
    cloud[0].return_value = account(device())
    flow = await setup_account(runtime)
    await runtime.async_block_till_done()
    cloud[0].side_effect = IntelliClimaAPIError("https://example.invalid/SECRET_MARKER")
    coordinator = flow["result"].runtime_data.devices_coordinator
    await coordinator.async_refresh()
    assert "SECRET_MARKER" not in caplog.text
    assert "SECRET_MARKER" not in str(coordinator.last_exception)
