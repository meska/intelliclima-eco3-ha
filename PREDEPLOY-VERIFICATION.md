# Pre-deployment verification — review candidate

## Gate: BLOCKED / independent review required

**No deployment, HA restart, repository creation/publication, push, enrollment or
reset was performed.** The standalone source is ready for independent code review,
not approved for production or publication. Its local Git repository has no remote
and no commits. All files are additions, staged only to expose a reviewable diff.

The acceptance contract for review is: support existing ECO2 and ECO3 cloud
accounts, never send ventilation commands at setup/poll/unload, route explicit fan
commands to the correct family, use ECO3 VOC-derived eCO2 from `voc_state` (never
raw `co2`), reject invalid telemetry, keep mixed-generation IDs distinct, and
publish no household data or secrets. Production writes and publication remain
blocked until the parent reviewer explicitly approves and verifies any fixes.

## Environment and dependency

- Real Home Assistant package: **2026.10.1**.
- Python **3.14.7**, macOS ARM64; both Homebrew and uv-managed CPython were tried.
- Published, non-editable **pyintelliclima 0.5.0**, aiohttp **3.14.4**, dacite **1.9.2**.
- Final test tooling: pytest **8.4.2**, pytest-asyncio **1.2.0**, Ruff **0.17.0**.
- Dependency check: **111 installed packages compatible** in the final isolated
  uv-managed environment. No library patch or vendored copy is shipped.
- The same library version's checkout is not identical to the published wheel:
  the latter has a module-level `post_to_session`, not an API-instance helper.
  Tests and live verification use the actual published wheel.

Use `V` for the isolated environment's `bin` directory in the commands below;
no machine-specific path or account credential path is included in this report.

## Executed final checks

| Command | Observed output | Process result |
| --- | --- | --- |
| `$V/python -m pytest -q --tb=short` | **53 passed, 1 warning** (1.69 s), no assertion failures | **SIGSEGV -11**, shell equivalent 139, after summary |
| `$V/ruff check .` | `All checks passed!` | 0 |
| `$V/ruff format --check .` | `23 files already formatted` | 0 |
| `$V/python -m compileall -q custom_components scripts tests` | no output | 0 |
| `$V/uv pip check --python $V/python` | `Checked 111 packages`; `All installed packages are compatible` | 0 |
| `$V/python scripts/live_readonly.py --credentials <secure-file> --expected-eco3 2` | JSON below | **0** |

Final live result, from shipped integration platforms/config flow/coordinators
and unmodified published dependency, using the authorized real cloud account:

```json
{"available_fans": 2, "custom_integration": true, "eco3_units": 2, "fans": 2, "requests": 6, "sensors": 8, "unload": true, "writes": 0}
```

This creates and starts a temporary **local** Home Assistant runtime, performs
real config-flow/setup reads and state registration, verifies entity counts, then
unloads/stops it. It does not connect to, deploy to, or restart the installed HA
server. Six requests are two login/discovery/status cycles (flow and setup).
Same-origin POST-only endpoint guard rejects every command endpoint and redirects.
No raw response, names, serials, MACs or account details were saved or printed.
Login can update the vendor's account-access metadata.

## Native shutdown failure: root cause identified; dependency gate still BLOCKED

The failure is **orjson 3.11.9's `Fragment` heap-type lifetime bug**, not an
IntelliClima fixture, cloud mock or integration defect. HA 2026.10.1 pins that exact
version. Fragment instances do not own a reference to their heap type, so module
finalization can free the type before cached fragments. Later GC dereferences the
freed type's NULL `tp_dealloc`. This is an upstream native use-after-free.

Evidence gathered locally, using only synthetic data:

- Original full-suite reproduction: **53 passed, 1 warning**, followed by SIGSEGV
  (shell exit **139**). Faulthandler identifies finalization/GC and
  `dict_dealloc` / `subtype_clear`, with no Python frame.
- File/subset delta: without changes, `test_runtime.py` (two lifecycle tests)
  exits 0, while the sensor/flow/fan/privacy subsets can crash. In a plain asyncio
  fixture probe, an empty account exits 0; a populated account with only the sensor
  platform crashes; fan/select/binary-sensor-only probes exit 0. Removing pytest or
  replacing session MagicMocks with ordinary callables does not fix the crash.
- Explicit fixture entry unload fixes some subsets, but **the full 54-test process
  still crashes**. That attempted fixture change was reverted; it was not the root
  fix. Pure-Python annotatedyaml / zeroconf imports did not fix the full suite.
- A scratch-only native signal diagnostic plus a pre-finalization object-ID
  snapshot identified the crashing dictionary key as `as_storage_fragment`. Its
  value's type had already been freed (`tp_name` / `tp_dealloc` NULL). No native
  diagnostic, GC modification or shutdown interception is shipped with the repo.
- A minimal reproduction below crashes **without HA, pytest, mocks, network or
  altered GC settings**. Substituting `b'1'` for the Fragment exits 0.
- The new type-ownership regression reports **18 == (18 + 1)** with 3.11.9:
  creating an instance does not increment its heap type's reference count.
- Upstream source comparison confirms the missing ownership operation in
  [3.11.9](https://github.com/ijl/orjson/blob/3.11.9/src/ffi/fragment.rs) and its
  addition in [3.13.0](https://github.com/ijl/orjson/blob/3.13.0/src/ffi/fragment.rs).
  Independent upstream report:
  [Home Assistant issue 185580](https://github.com/home-assistant/core/issues/185580).

Minimal reproduction (normal interpreter finalization is allowed to run):

```python
import orjson
import sys

sys.synthetic_fragment_cycle = [orjson.Fragment(b"1")]
sys.synthetic_fragment_cycle.append(sys.synthetic_fragment_cycle)
```

### Fix verified in an isolated, non-production candidate environment

Only **orjson 3.13.0** replaces 3.11.9. Python remains uv-managed **3.14.7**, HA
remains **2026.10.1**, and published **pyintelliclima 0.5.0** remains unmodified.
No integration-code or fixture changes were necessary. Both new regressions in
`tests/test_native_shutdown.py` fail before the dependency change and pass after it.
The subprocess regression checks the actual exit code with faulthandler enabled;
the type-ownership regression detects the underlying error independently of whether
an OS happens to crash. Neither test is skipped or marked xfail.

Reproduce the isolated dependency experiment (`F` is a new disposable venv, `O` is a
scratch text file containing only `orjson==3.13.0`):

```sh
uv venv --python 3.14.7 "$F"
uv pip install --python "$F/bin/python" -r requirements-dev.txt --override "$O"
"$F/bin/python" -X faulthandler -m pytest -q --tb=short
"$F/bin/ruff" check .
"$F/bin/ruff" format --check .
"$F/bin/python" -m compileall -q custom_components scripts tests
uv pip check --python "$F/bin/python"
```

| Candidate check | Actual output / result |
| --- | --- |
| Full suite, three consecutive fresh processes | **55 passed, 1 warning**; **6.06 s / 1.61 s / 1.59 s**, every process **exit 0** |
| Ruff check | `All checks passed!`, exit 0 |
| Ruff format check | `25 files already formatted`, exit 0 |
| Compileall | no output, exit 0 |
| `uv pip check`, candidate | `Checked 111 packages`; **1 incompatibility**, **exit 1**: `homeassistant` requires `orjson==3.11.9`, but `3.13.0` is installed |
| `uv pip check`, original pinned environment | `Checked 111 packages`; compatible, exit 0; **native shutdown regressions still fail** |
| Local Linux runtime discovery | Docker context exists but OrbStack daemon socket is absent; no podman/limactl/colima command was found. No VM/daemon/service was started, and no remote/production Linux host was used. |

**The native root fix is proven, but a supported installation is still blocked.**
PyPI's current HA version checked during this investigation was 2026.10.1, still
pinning the faulty orjson version. Do not silently override a production HA core
dependency, patch package metadata, or claim `pip check` is green for the candidate.
The repository's requirements and CI are intentionally unchanged: the newly added
regressions expose this upstream blocker in the currently pinned environment.
A compatible upstream HA dependency update (or an explicitly reviewed backport)
is required before all release gates can be green together. There is no `os._exit`,
GC suppression, leaked-reference workaround or swallowed process exit code.

The earlier real-account local HA lifecycle check exited 0, but was not rerun for
this investigation and does not disprove the native lifetime bug. No cloud/VMC
request, deployment, push or publication occurred in this follow-up. GitHub Actions
has not run. Independent parent review and production authorization remain required.

The one test warning is upstream HA's deprecation of inheriting
`HomeAssistantApplication` from `aiohttp.web.Application`, not an integration
warning suppression. HA's normal custom-integration warning is also expected.

## Tests and RED evidence

Tests use actual HA 2026.10.1 config flows, config entries, device/entity registries,
coordinators, entity platforms, services and state machine. Cloud authentication,
poll results and command transport are replaced only for automated offline tests;
the separate live check replaces no API behavior. No ad-hoc fake entity classes
stand in for HA entities. Synthetic fixture data is generated from real client
dataclasses; no private captures are reused.

Observed new vertical RED → passing assertions:

| Slice | Actual RED before fix |
| --- | --- |
| ECO3-only config flow | returned `form` / `no_devices`, not `create_entry` |
| Equivalent CO2 source | only `CO2 raw` value 4 existed; no `Equivalent CO2` 720 ppm |
| Invalid telemetry | 327.67/143/65535 leaked as values; missing/NaN failed entity creation |
| Mixed-family lifecycle/identity | one fan instead of two; duplicate IDs in HA logs |
| Malformed running registers | fan entity absent, instead of unavailable while sensors work |
| Vendor AQI | no AQI entity for the valid/invalid-value matrix |
| Coordinator privacy | a synthetic sensitive URL marker leaked into the error log |
| Upstream client privacy | a synthetic marker leaked at error/info/debug levels |

The inherited ECO3 fan routing/effective-state behavior was already implemented in
an earlier local patch: current on/off/speed/auto routing and effective-state cases
are **regression tests**, not claimed as newly test-first here. They cover both
families, speed flags, cloud failures/offline/disappearance/recovery. ECO2-only
select/filter entities remain restricted to ECO2, including a synthetic account
where ECO2/ECO3 have the same numeric cloud ID. Setup/poll/unload tests guard the
transport against any unexpected request. The mixed lifecycle test verifies unload
returns NOT_LOADED and removes runtime_data; HA retains registry-backed unavailable
restored states, rather than deleting those entity-registry entries.

Deployment helper tests were added **after** the helper, not claimed as TDD.
Earlier fixture bootstrap errors (uninitialized HA registries/network singleton,
wrong helper placement), wrong test expectation for a night bit, and restored-state
unload expectations were corrected before final results. They are not presented as
feature REDs. Strict new-test-first coverage of every packaging/helper line was not
achieved; review this limitation explicitly.

## Installation/rollback verification

The mounted-config helper was exercised only against temporary synthetic config
directories: previous component present/absent, byte-exact rollback, modified
installation refusal, and symlinked component-container refusal. It leaves
`configuration.yaml` intact. It never edits `.storage`, invokes SSH, installs
dependencies, or starts/stops/restarts HA. A full HA backup, stopped Core and
independent review are explicit operator prerequisites, not auto-verified by a flag.

Actual remote backup, `ha core check`, installation, restart, production entity
registry migration, HA OS recovery and HACS download/validation are **not performed**.
README documents manual/HACS installation and rollback, including that restoring
the built-in HA 2026.10.1 integration loses ECO3 support. HACS metadata and a CI
workflow are supplied, but not claimed approved or executed remotely.

## Publication/privacy boundary

Repository includes code, documentation, synthetic tests and upstream Apache-2.0
license/provenance. No APK/firmware/assets/captures, private project runbooks, raw
household responses, credentials or identifying household fixtures were copied.
`.gitignore` excludes credentials, private files, HA storage and backups. A scoped
client-logger privacy filter suppresses account/frame debug/info output and replaces
warning/error details, without modifying the PyPI dependency.

No commit is marked `[verified]`; independent parent review is still pending.

Final local index checks: `git diff --cached --check` exited 0. The scoped staged
source/privacy scan enumerated **35 tracked files**, with **0 findings** for
private-address/household-reference patterns, machine-specific source paths,
credential-assignment patterns, symlinks, private/binary extensions, unsafe
shell/eval/pickle calls. This is a bounded pattern scan, not a formal secret audit.
`git remote` returned no remotes. The evidence checkouts' Git status remained the
same as the initial read; they were not edited by this standalone-artifact task.
