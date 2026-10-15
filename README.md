# IntelliClima ECO2/ECO3 Cloud for Home Assistant

**Experimental custom integration — not production-ready.** Independent L1/L2
code review does not clear the dependency/runtime gate. Linux GitHub Actions uses
**Home Assistant 2026.10.1**, the unmodified published **pyintelliclima 0.5.0** and
HA's official **orjson 3.11.9** pin, without overrides. Native lifetime regressions
are intentionally enabled and may fail even on Linux without a visible crash.
See [Actions](https://github.com/meska/intelliclima-eco3-ha/actions) for real results,
[PREDEPLOY-VERIFICATION.md](PREDEPLOY-VERIFICATION.md) and
[REVIEW-FIXES.md](REVIEW-FIXES.md) for historical local evidence.

The known upstream [HA issue 185580](https://github.com/home-assistant/core/issues/185580)
affects orjson Fragment lifetime. Diagnostic local tests passed only with orjson
3.13.0, which **violates HA 2026.10.1's dependency requirement**; that experiment is
not a supported production fix. No dependency override, native-test skip, GC
suppression or exit-code masking is shipped. Publication is for review and
experimentation, not an approval to install or deploy. No release is declared.

A custom integration for Fantini Cosmi ECOCOMFORT 2.0 and ECOCOMFORT 3 using
IntelliClima's cloud account. Tested against **Home Assistant 2026.10.1 / Python
3.14.7**. Other versions are not verified. Not an official Fantini Cosmi product.

## Features and boundaries

| Family | Entities |
| --- | --- |
| ECO2 | Fan, temperature, humidity, VOC, mode select, filter-cleaning binary sensor |
| ECO3 | Fan, temperature, humidity, equivalent CO2, vendor air-quality index |

ECO3 equivalent CO2 is **VOC-derived eCO2 (ppm), read from `voc_state`**, not
an NDIR measurement. It deliberately has no HA carbon-dioxide device class.
The unrelated raw `co2` field is unreliable and is not exposed or used.
Do not use eCO2 as a safety alarm or as a substitute for a calibrated CO2 sensor.
ECO2 retains the upstream VOC interpretation; no claim of physical calibration
is made here. Vendor AQI is a proprietary ordinal 1–5, not US/EU outdoor AQI.
Missing/non-numeric/non-finite readings and sentinels (327.67 temperature,
143 humidity, 65535 VOC/eCO2, 143 AQI) become unknown. AQI outside 1–5 and humidity
outside 0–100 are rejected.

ECO3 fan displays effective `mode_state`/`speed_state`, including auto/boost/night
flags. Normal on/off/speed/auto commands route to the correct device generation.
The API acknowledgement is not proof a physical fan changed; the next cloud poll
provides readback. No optimistic state is fabricated. ECO2 control remains on its
own endpoints. ECO3 mode select, calculated filter wear, schedule, calibration,
thresholds, satellite roles, clock and firmware controls are deliberately absent.
Setup, discovery, polling and unload do not issue ventilation commands. ECO2 filter
status uses its read/calculation endpoint only for ECO2 serials.

Cloud poll interval is one minute; ECO2 filter calculation is daily. Offline or
missing ECO3 devices and cloud failures make entities unavailable. Invalid ECO3
running registers make only the fan unavailable. Newly added devices require an
integration reload. No automatic reauthentication flow is implemented; after
persistent authentication failures reconfigure/remove and add the account through
HA, taking care not to duplicate entities or lose automation references.

## Installation (after independent review)

1. Make a full Home Assistant backup and download it securely. Record the existing
   IntelliClima config entry and entity IDs. Backups contain credentials.
2. If using HACS, add `https://github.com/meska/intelliclima-eco3-ha` as a **custom Integration
   repository** and download it. It is not claimed to be listed or HACS-validated.
   Alternatively copy **only `custom_components/intelliclima`** into HA's
   `/config/custom_components/intelliclima`.
3. Check configuration (`ha core check` on HA OS), then restart Core once.
4. Settings → Devices & services → Add integration → IntelliClima ECO2/ECO3 Cloud.
   Enter the existing cloud account. If an IntelliClima entry already exists, do
   not add a second one; reload/use the existing entry after restart instead.
5. Verify expected device/entity counts and availability, without issuing controls.
   Review logs without enabling client debug output. Keep a read-only observation
   period before enabling automations.

This custom component intentionally uses **domain `intelliclima`**, overriding the
built-in integration, not installing beside it. ECO2 unique IDs are preserved;
new ECO3 IDs are prefixed by generation to prevent mixed-family collisions.
Experimental earlier local ECO3 entities are not automatically migrated. HA may
need an entity/device-registry review if such experimental versions were installed.
The published dependency `pyintelliclima==0.5.0` is installed by HA; no local Mac
editable install or patched Core files are required. An existing conflicting
custom component must be backed up and removed/replaced, never merged file by file.

### Optional mounted-config installer

`scripts/manage_install.py` runs on a workstation with a **mounted HA config**;
it does not require Python in the HA SSH add-on and has no SSH/network code.
It never checks/stops/restarts Core itself. Before applying, independently review,
make a full HA backup, and stop Core (a short outage). Choose a fresh backup path
outside the component directory, on the same trusted workstation/mount.

```sh
python scripts/manage_install.py check --config /mounted/ha-config
python scripts/manage_install.py install --config /mounted/ha-config \
  --backup /secure/backups/intelliclima-before \
  --reviewed-core-stopped-full-backup
```

The explicit flag is an operator attestation, not proof Core is stopped or a full
HA backup exists. The helper backs up only the previous custom component and
verifies file hashes; it does **not** back up `.storage` or the entire HA config.
It refuses symlinked component paths, existing backup/staging directories and
unexpected dependency manifests. Keep Core stopped if an installation error occurs;
inspect the preserved backup before recovery. Do not run simultaneously with HACS.

## Rollback

1. Stop Core, keeping the full HA backup secure.
2. If installed with the helper, restore its component snapshot:
   ```sh
   python scripts/manage_install.py rollback --config /mounted/ha-config \
     --backup /secure/backups/intelliclima-before \
     --reviewed-core-stopped-full-backup
   ```
   It refuses rollback if installed or backup files changed, avoiding destruction
   of later updates. Resolve that manually after review, not with a force flag.
3. For manual/HACS installation, remove the custom component folder (or restore the
   exact previously backed-up folder). Check config and start Core.
4. Verify the previous integration. The built-in HA 2026.10.1 integration uses an
   older client and does not provide this ECO3 support; ECO3 entities may remain
   unavailable after rollback. This does not reset or unregister the ventilation
   devices. If config entries/registries were altered, restore the full HA backup
   using HA's backup restore workflow; component rollback alone cannot undo them.

## Cloud, privacy and reliability

This is **cloud polling, not local Wi-Fi/BLE control**. It depends on the vendor's
service, account, Internet connectivity and device firmware. There is no service
SLA; cloud data can be stale. Login can update account access metadata. The HA
config entry stores account credentials in HA's normal storage. Protect the config,
logs and backups. Do not post diagnostics, URLs, serials, MAC addresses or tokens.
The client authentication URL can contain sensitive material: **do not enable
`pyintelliclima` HTTP/debug logging**. Integration-owned expected API-error messages
are redacted. A filter on the published client’s `pyintelliclima.api` logger drops
verbose account/frame logs and replaces warnings/errors with generic text, including
tracebacks. It stays installed through unload to protect later config flows. This
is not a claim that every aiohttp/HA exception or third-party log is safe.
No diagnostics exporter or telemetry service is provided by this repository.

## Development

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m compileall -q custom_components scripts tests
.venv/bin/python -m pip check
```

Tests run actual HA config flows, entries, registries, coordinators, platforms,
services and state machine; only cloud I/O/session acquisition is substituted.
Fixtures are synthetic. Tests must never use a production HA config directory.

Optional authorized live read-only check (creates a temporary local HA runtime,
never changes an installed HA instance):

```sh
.venv/bin/python scripts/live_readonly.py --credentials /secure/account.creds \
  --expected-eco3 2
```

The 0600 file uses `username=...` and `pwd=...`; never put secrets on a command
line or commit the file. Only same-origin POST login/discovery/status endpoints
are allowed; redirects and all command endpoints are blocked. The report contains
counts only, not household identifiers or raw telemetry. The current helper
requires an ECO3-only account for its asserted counts.

Apache-2.0; see [PROVENANCE.md](PROVENANCE.md), LICENSE and NOTICE.
