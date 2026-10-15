"""Synthetic data and a real Home Assistant runtime; only cloud I/O is replaced."""

import shutil
from dataclasses import fields
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant import loader
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pyintelliclima import (
    FanMode,
    FanSpeed,
    IntelliClimaAPI,
    IntelliClimaDevices,
    IntelliClimaECO2,
    IntelliClimaECO3,
)
from pyintelliclima.intelliclima_types import IntelliClimaModelType

ROOT = Path(__file__).resolve().parents[1]


def device(generation=3, index=1, **changes):
    cls = IntelliClimaECO3 if generation == 3 else IntelliClimaECO2
    values = {f.name: "0" for f in fields(cls)}
    values.update(
        id=str(index),
        crono_sn=f"F{generation}{index:06X}",
        model=IntelliClimaModelType(f"ECO{generation}", f"ECO{generation}"),
        name=f"Fixture {generation} {index}",
        mac=f"02:00:00:00:{generation:02x}:{index:02x}",
        macwifi=f"02:00:00:01:{generation:02x}:{index:02x}",
        mode_set=FanMode.sensor,
        speed_set=FanSpeed.auto,
        mode_state="4",
        speed_state="18",
        online_status=True,
        tamb="21.5",
        rh="55",
        voc_state="650",
        co2="3",
        aqi="2",
        fw="synthetic",
    )
    values.update(changes)
    return cls(**values)


def account(*devices):
    return IntelliClimaDevices(
        {d.id: d for d in devices if isinstance(d, IntelliClimaECO2)},
        {},
        {d.id: d for d in devices if isinstance(d, IntelliClimaECO3)},
    )


@pytest.fixture
async def runtime(tmp_path):
    shutil.copytree(ROOT / "custom_components", tmp_path / "custom_components")
    hass = HomeAssistant(str(tmp_path))
    loader.async_setup(hass)
    hass.config_entries = ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()
    from homeassistant.helpers import device_registry, entity_registry

    device_registry.async_setup(hass)
    await device_registry.async_load(hass)
    await entity_registry.async_load(hass)
    await async_setup_component(hass, "intelliclima", {})
    integration = await loader.async_get_integration(hass, "intelliclima")
    component = await integration.async_get_component()
    from aiohttp import ClientSession

    from custom_components.intelliclima import config_flow

    async with ClientSession() as session:
        with (
            patch.object(component, "async_get_clientsession", return_value=session),
            patch.object(config_flow, "async_get_clientsession", return_value=session),
        ):
            try:
                await hass.async_start()
                yield hass
            finally:
                await hass.async_stop()


@pytest.fixture
def cloud():
    from types import SimpleNamespace

    poll = SimpleNamespace(return_value=None, side_effect=None)
    calls = []

    async def authenticate(api):
        return True

    async def get_status(api):
        if poll.side_effect is not None:
            raise poll.side_effect
        return poll.return_value

    async def transport(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("unexpected network or device write")

    def assert_not_called():
        assert not calls

    transport.assert_not_called = assert_not_called
    with (
        patch.object(IntelliClimaAPI, "authenticate", authenticate),
        patch.object(IntelliClimaAPI, "get_all_device_status", get_status),
        patch("pyintelliclima.api.post_to_session", transport),
    ):
        yield poll, transport


async def setup_account(hass):
    flow = await hass.config_entries.flow.async_init("intelliclima", context={"source": "user"})
    return await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"username": "synthetic", "password": "synthetic"}
    )
