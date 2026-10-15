# L1/L2 review fixes — pending independent review

## Scope and outcome

Only the L1 fan-mode selection and L2 rollback comparison were changed in
production source. No dependency, official pyintelliclima wheel, deployment,
production configuration, enrollment, Git commit, push, skill or HANDOFF changed.
The optional S1 translation suggestion is intentionally not addressed here.
`PREDEPLOY-VERIFICATION.md` and `tests/test_native_shutdown.py` were already changed
by the separate native-crash investigation when this work began; they were not
edited by this follow-up.

The review's exact original source hashes were verified before editing:

- `custom_components/intelliclima/fan.py`:
  `fd1d534eede3167af121c78070ea5c3194873d0001a1b95713c83d3d0c2c5089`
- `scripts/manage_install.py`:
  `05fe7884715c12710384a1b4b6ce4c737662897abc0a41d5156c20fdcffe1b4c`

### L1

An ECO3 reporting an effective running mode while its stored mode is OFF now
uses its effective direction for explicit positive-speed commands. Non-OFF
stored modes and ECO2 behavior are unchanged; the existing alternate-mode fallback
for an effectively stopped fan is unchanged. Auto and zero-speed routing remain
unchanged. The fix is four lines with explanatory comments.

New HA service tests first reproduced both `turn_on(percentage=75)` and
`set_percentage(75)` sending OFF instead of inward/outward/alternate/sensor. After
the fix, all eight cases pass. Additional regression coverage checks `turn_on()`
without a percentage preserves running direction and derives high speed from the
synthetic boost register. Existing ECO2/ECO3 routing tests continue to pass.
Only command transport is mocked; no device/cloud commands were sent.

### L2

Rollback first fingerprints and validates the entire installed tree, including
cache paths, with the existing symlink/special-file checks. Comparison ignores
only additional regular files immediately inside `__pycache__`, with a standard
`<source>.cpython-<digits>[.opt-1|.opt-2].pyc` name, whose corresponding `.py` source
is recorded in the installed manifest. This is a narrow filename/source allowlist,
not a claim to authenticate bytecode contents. Legacy adjacent `.pyc`, orphan
caches and arbitrary files inside cache directories are not ignored. Source
hashes are still compared exactly. The backup remains byte-exact, including
previous cache bytes; neither install nor backup digest semantics changed.

Six tests first reproduced failure after real `py_compile` generation, covering
optimization levels 0/1/2 and previous component present/absent. They pass after
the fix. Ten additional integrity regressions verify refusal for changed/deleted
source despite a generated cache, unknown cache-directory files, orphan `.pyc`,
adjacent legacy `.pyc`, a `.py` file inside the cache, cache-file and cache-directory
symlinks, a FIFO named as a generated cache, and modified previous-backup cache
bytes. Refusal leaves target and backup present. Previous caches restore exactly.
These ten are preservation/regression tests, not claimed as newly failing REDs.

## Actual commands and results

All commands ran from the standalone repository. For compactness, `$F` and `$O`
below name the actual scratch environment bin directories:

```sh
F="$HOME/.hermes/cache/scratch/eco3-native-fixed-managed/bin"
O="$HOME/.hermes/cache/scratch/eco3-public-managed/bin"
```

The fixed scratch environment has Python 3.14.7, HA 2026.10.1, published
pyintelliclima 0.5.0, pytest 8.4.2, pytest-asyncio 1.2.0 and orjson **3.13.0**.
The original environment retains HA's pinned orjson **3.11.9**.

| Command (environment paths abbreviated as above) | Actual result | Exit |
| --- | --- | --- |
| `$F/python -m pytest tests/test_fan.py -k stale_off -q --tb=short -p no:cacheprovider` before fix | **8 failed**, 17 deselected, 1 upstream warning; actual command mode OFF instead of the effective direction | 1 |
| `$F/python -m pytest tests/test_fan.py -q --tb=short -p no:cacheprovider` immediately after L1 fix | **25 passed**, 1 upstream warning | 0 |
| `$F/python -m pytest tests/test_install.py -k generated_bytecode -q --tb=short -p no:cacheprovider` before fix | **6 failed**, 4 deselected; `Installed files changed; manual review required` | 1 |
| `$F/python -m pytest tests/test_install.py -q --tb=short -p no:cacheprovider` immediately after L2 fix | **10 passed** | 0 |
| `$F/ruff format tests/test_fan.py tests/test_install.py scripts/manage_install.py custom_components/intelliclima/fan.py` | 1 reformatted, 3 unchanged | 0 |
| `$F/python -X faulthandler -m pytest -q --tb=short -p no:cacheprovider` after all regression additions, two fresh processes | **83 passed, 1 warning**, 2.26 s / 2.23 s; normal process termination both times | **0 / 0** |
| `$O/python -m pytest tests/test_install.py tests/test_packaging.py -q --tb=short -p no:cacheprovider` | **29 passed**, 0.22 s | 0 |
| `$F/ruff check .` | All checks passed | 0 |
| `$F/ruff format --check .` | 25 files already formatted | 0 |
| `$F/python -m compileall -q custom_components scripts tests` | No output | 0 |
| `git diff --check` and `git diff --cached --check` (also checked separately) | No whitespace findings | 0 each |
| `uv pip check --python $F/python` | 111 packages; **1 incompatibility: HA requires orjson==3.11.9, installed 3.13.0** | **1** |
| `uv pip check --python $O/python` | 111 packages; all installed packages compatible | 0 |

The warning is upstream HA's deprecated `HomeAssistantApplication` inheritance
from aiohttp `web.Application`. No warning, garbage collection or shutdown was
suppressed. The original-dependency full suite is **not claimed green**: the
separately documented Fragment heap-type lifetime bug remains a release blocker.
The two passing full runs establish integration correctness in the diagnostic
fixed-native environment, not supported production dependency compatibility.

Unchanged dependency-file hashes (matching independent review):

- `requirements-dev.txt`:
  `49b7979cea7efd9f1245b59de9f6e87b7e0fadb21fa0d6b44763edf91f66f0e5`
- `custom_components/intelliclima/manifest.json`:
  `ed8b0caf9be5eed8ca8aefca2dfd8e1266abda9716147df442fcaa2487624837`

Changed-source hashes for parent review:

- `custom_components/intelliclima/fan.py`:
  `15af19bc3bc25479291101b959f83f2c33f3b0be30c6335b2b62efe2dd5168ad`
- `scripts/manage_install.py`:
  `fb37e9b8e2b2ca9ad67bf35ae200229e31d90981867998088cc3551b1f9e3759`
- `tests/test_fan.py`:
  `522e91bb28bec0bd6663b9d0a1a26f7ef8b9747aaeddd43258ff698ff9501e41`
- `tests/test_install.py`:
  `eb28823076ac247722615d9e61ba9877e30dcfbf44d8a39ab40d0070fb1f4e1d`

## Proposed Linux verification — NOT executed

Use a new disposable Linux VM or isolated CI runner, not the installed HA host or
any existing user runtime. Obtain operator approval separately. Transfer only the
reviewed public-source snapshot and synthetic tests; no credentials, HA config,
`.storage`, private parent files, host sockets or cloud-account data. Verify the
snapshot hashes before testing. Use an ordinary nonprivileged user and a fresh
venv with CPython 3.14.7; verify that interpreter version rather than substituting
another one silently. Record Linux distribution, architecture and interpreter
build alongside results.

In that disposable runner, the proposed commands are:

```sh
python3.14 -m venv ./verification-venv
./verification-venv/bin/python -m pip install -r requirements-dev.txt
./verification-venv/bin/python -m pip check
./verification-venv/bin/python -c 'import importlib.metadata as m; print({p: m.version(p) for p in ("homeassistant", "pyintelliclima", "orjson")})'
# Require exactly HA 2026.10.1, pyintelliclima 0.5.0, orjson 3.11.9 here.
# Disable runner egress after dependency retrieval using runner-level isolation.
./verification-venv/bin/python -X faulthandler -m pytest -q --tb=short -p no:cacheprovider
./verification-venv/bin/ruff check .
./verification-venv/bin/ruff format --check .
./verification-venv/bin/python -m compileall -q custom_components scripts tests
```

Do not use an orjson override, alter package metadata, disable the native
regressions or mask the process exit status. Capture each exit code independently;
repeat the full pytest process at least three times and preserve complete logs.
A Linux run may still expose the same native type-ownership defect even if its
allocator does not segfault: a failing ownership regression is a failure, not a
platform-specific waiver. Run packaging/install tests separately if native tests
block the whole suite. Keep the deployment gate blocked until a compatible upstream
HA dependency release or explicitly reviewed backport resolves the pinned native
bug, followed by a fully passing independently reviewed snapshot. This proposal
starts no service, VM, remote job or deployment and changes no user runtime.
