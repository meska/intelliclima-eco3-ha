"""Static package and read-only endpoint boundary contracts."""

import json
from pathlib import Path

import pytest
from awesomeversion import AwesomeVersion
from pyintelliclima.const import API_BASE_URL, API_MONO

from scripts.live_readonly import allowed_request

ROOT = Path(__file__).resolve().parents[1]


def test_packaging():
    manifest = json.loads((ROOT / "custom_components/intelliclima/manifest.json").read_text())
    assert manifest["requirements"] == ["pyintelliclima==0.5.0"]
    assert AwesomeVersion(manifest["version"]).valid
    assert manifest["version"] == "0.5.0.post1"
    assert manifest["domain"] == "intelliclima"
    assert manifest["iot_class"] == "cloud_polling"
    assert not (ROOT / "custom_components/intelliclima/_vendor").exists()
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert hacs["homeassistant"] == "2026.10.1"


@pytest.mark.parametrize(
    "path",
    [
        "eco3/send/",
        "eco/send/",
        "eco3/filters/",
        "user/register/",
        "sync/cronos400?extra=1",
    ],
)
def test_readonly_blocks_writes(path):
    assert not allowed_request("POST", API_BASE_URL + API_MONO + path)


@pytest.mark.parametrize(
    "path", ["sync/cronos400", "user/login/synthetic", "casa/elenco3/synthetic"]
)
def test_readonly_allows_read_endpoints(path):
    assert allowed_request("POST", API_BASE_URL + API_MONO + path)
    assert not allowed_request("GET", API_BASE_URL + API_MONO + path)
    assert not allowed_request("POST", "https://example.invalid/" + path)
