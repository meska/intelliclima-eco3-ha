# Derived from Home Assistant Core; modified formatting/typing. See PROVENANCE.md.
"""Constants for the IntelliClima integration."""

import logging
from datetime import timedelta

LOGGER = logging.getLogger(__package__)

DOMAIN = "intelliclima"

# Update interval
DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)

# Filter status is expensive to compute cloud-side, so it's polled far less often.
FILTER_SCAN_INTERVAL = timedelta(days=1)
