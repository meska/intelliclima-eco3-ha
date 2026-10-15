"""Guarded live read-only check through shipped HA platforms and published client.

Credentials never enter output. No raw responses are saved. The separate installed
HA instance is untouched. Login may update cloud account access metadata.
"""

import argparse
import asyncio
import json
import logging
import os
import shutil
import ssl
import sys
import tempfile
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import aiohttp
import certifi
from homeassistant import loader
from homeassistant.config_entries import ConfigEntries, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.setup import async_setup_component
from pyintelliclima.const import API_BASE_URL, API_MONO
from yarl import URL

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def allowed_request(method, url):
    """Allow only same-origin login, account discovery and status polling."""
    base = URL(API_BASE_URL + API_MONO)
    url = URL(url)
    if method != "POST" or url.origin() != base.origin() or url.query_string:
        return False
    prefix = base.path.rstrip("/") + "/"
    if not url.path.startswith(prefix):
        return False
    path = url.path[len(prefix) :]
    return path.startswith(("user/login/", "casa/elenco3/")) or path == "sync/cronos400"


async def main(credentials, expected):
    logging.disable(logging.CRITICAL)
    if credentials.stat().st_mode & 0o077:
        raise ValueError("Credential file permissions must be 0600")
    creds = dict(
        line.split("=", 1)
        for line in credentials.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    trace = aiohttp.TraceConfig()
    counts = Counter()

    async def guard(session, context, params):
        if not allowed_request(params.method, params.url):
            raise RuntimeError("Disallowed endpoint")
        counts["requests"] += 1

    async def no_redirect(session, context, params):
        raise RuntimeError("Redirects are forbidden")

    trace.on_request_start.append(guard)
    trace.on_request_redirect.append(no_redirect)
    connector = aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=certifi.where()))
    async with aiohttp.ClientSession(
        connector=connector,
        trace_configs=[trace],
        timeout=aiohttp.ClientTimeout(total=40),
    ) as session:
        with tempfile.TemporaryDirectory(
            prefix="intelliclima-readonly-", dir=os.environ.get("TMPDIR")
        ) as directory:
            shutil.copytree(
                ROOT / "custom_components",
                Path(directory) / "custom_components",
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            hass = HomeAssistant(directory)
            loader.async_setup(hass)
            device_registry.async_setup(hass)
            await device_registry.async_load(hass)
            await entity_registry.async_load(hass)
            hass.config_entries = ConfigEntries(hass, {})
            await hass.config_entries.async_initialize()
            await async_setup_component(hass, "intelliclima", {})
            integration = await loader.async_get_integration(hass, "intelliclima")
            assert not integration.is_built_in
            component = await integration.async_get_component()
            from custom_components.intelliclima import config_flow

            with (
                patch.object(component, "async_get_clientsession", return_value=session),
                patch.object(config_flow, "async_get_clientsession", return_value=session),
            ):
                try:
                    await hass.async_start()
                    flow = await hass.config_entries.flow.async_init(
                        "intelliclima", context={"source": "user"}
                    )
                    result = await hass.config_entries.flow.async_configure(
                        flow["flow_id"],
                        {
                            "username": creds["username"].strip(),
                            "password": creds["pwd"].strip(),
                        },
                    )
                    assert result["type"] == "create_entry"
                    await hass.async_block_till_done()
                    entry = result["result"]
                    assert entry.state is ConfigEntryState.LOADED
                    devices = entry.runtime_data.devices_coordinator.data
                    assert (
                        len(devices.ecocomfort3_devices) == expected
                        and not devices.ecocomfort2_devices
                    )
                    assert len(hass.states.async_all("fan")) == expected
                    assert len(hass.states.async_all("sensor")) == expected * 4
                    assert not hass.states.async_all("select") and not hass.states.async_all(
                        "binary_sensor"
                    )
                    summary = {
                        "eco3_units": expected,
                        "fans": expected,
                        "sensors": expected * 4,
                        "available_fans": sum(
                            s.state != "unavailable" for s in hass.states.async_all("fan")
                        ),
                        "requests": counts["requests"],
                        "writes": 0,
                        "custom_integration": True,
                        "unload": await hass.config_entries.async_unload(entry.entry_id),
                    }
                    print(json.dumps(summary, sort_keys=True))
                finally:
                    await hass.async_stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", required=True, type=Path)
    parser.add_argument("--expected-eco3", required=True, type=int)
    args = parser.parse_args()
    try:
        asyncio.run(main(args.credentials, args.expected_eco3))
    except Exception as error:  # noqa: BLE001 - do not leak authenticated URLs
        print("Read-only verification failed: " + type(error).__name__)
        raise SystemExit(1) from None
