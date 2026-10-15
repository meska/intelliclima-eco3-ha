"""Vertical behavior slices through real HA config entries and state machine."""

from unittest.mock import AsyncMock, patch

from conftest import account, device, setup_account
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from pyintelliclima.api import IntelliClimaEcocomfort2API
from pyintelliclima.intelliclima_types import IntelliClimaFilterStatus


async def test_eco3_config_flow(runtime, cloud):
    poll, transport = cloud
    poll.return_value = account(device())
    result = await setup_account(runtime)
    assert result["type"] == "create_entry", result
    await runtime.async_block_till_done()
    assert result["result"].state is ConfigEntryState.LOADED
    transport.assert_not_called()


async def test_mixed_collision_lifecycle(runtime, cloud):
    poll, transport = cloud
    poll.return_value = account(device(2), device(3))
    status = IntelliClimaFilterStatus("SYNTHETIC", True, None, [], 0.0, False)
    with patch.object(
        IntelliClimaEcocomfort2API, "get_filter_status", AsyncMock(return_value=status)
    ) as filters:
        result = await setup_account(runtime)
        await runtime.async_block_till_done()
        entry = result["result"]
        assert entry.state is ConfigEntryState.LOADED
        assert len(runtime.states.async_all("fan")) == 2
        assert len(runtime.states.async_all("sensor")) == 7
        assert len(runtime.states.async_all("select")) == 1
        assert len(runtime.states.async_all("binary_sensor")) == 1
        registry = dr.async_get(runtime)
        assert len(dr.async_entries_for_config_entry(registry, entry.entry_id)) == 2
        filters.assert_awaited_once_with(device(2).crono_sn)
        transport.assert_not_called()
        await entry.runtime_data.devices_coordinator.async_refresh()
        assert await runtime.config_entries.async_unload(entry.entry_id)
        assert entry.state is ConfigEntryState.NOT_LOADED
        assert all(s.state == "unavailable" for s in runtime.states.async_all("fan"))
        assert all(s.state == "unavailable" for s in runtime.states.async_all("sensor"))
        assert not hasattr(entry, "runtime_data")
        transport.assert_not_called()
