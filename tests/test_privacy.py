"""The unmodified upstream client logs authenticated URLs on network failures."""

import logging

from conftest import account, device, setup_account


async def test_upstream_logs_are_redacted(runtime, cloud, caplog):
    cloud[0].return_value = account(device())
    await setup_account(runtime)
    await runtime.async_block_till_done()
    with caplog.at_level(logging.DEBUG, logger="pyintelliclima.api"):
        logger = logging.getLogger("pyintelliclima.api")
        logger.error("Authentication failed: %s", "SENSITIVE_SYNTHETIC_MARKER")
        logger.info("Login with Intelliclima user: %s", "SENSITIVE_SYNTHETIC_MARKER")
        logger.debug("Sending command: %s", "SENSITIVE_SYNTHETIC_MARKER")
    assert "SENSITIVE_SYNTHETIC_MARKER" not in caplog.text
    assert "IntelliClima client error details withheld for privacy" in caplog.text
