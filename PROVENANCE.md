# Provenance and changes

License: Apache-2.0; see LICENSE and NOTICE. No DCO sign-off or CLA signature
has been asserted on behalf of any person.

Integration sources are derived from Home Assistant Core
`a53dcbfaf2bba63018224b21ed3e4e7287dbfbb6`, directory
`homeassistant/components/intelliclima` (Apache-2.0). Lifecycle `__init__.py`
uses the bool-return setup/unload contract from the published HA 2026.10.1
integration. Advanced dev-only lifecycle helpers were not transplanted.

Modified Python files carry change notices. ECO3 entity/fan support was developed
locally before this standalone package; its existing behavior is regression-tested,
not falsely presented as new test-first development in this repository.
New vertical REDs were observed for ECO3-only flow, eCO2 source, invalid sensor
values, mixed-family identity collision, malformed fan registers, vendor AQI,
and error redaction. Deployment helper tests were added after the helper.

The dependency is the unmodified published PyPI `pyintelliclima==0.5.0`.
No vendored client, editable dependency, extracted application asset, firmware,
network capture, or household fixture is included. The client checkout and wheel
have different internal helper placement; the shipped code uses public APIs.
See the dependency's own distribution for its license and contributors.

Synthetic fixtures are constructed from dataclass field definitions; their names,
serials, account strings and locally administered MAC addresses are invented.
They are not redacted live captures. Cloud telemetry is not saved in this repo.
