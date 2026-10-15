"""Guard the native fragment lifetime used by HA's registry/state caches."""

import subprocess
import sys

import orjson


def test_fragment_owns_reference_to_heap_type():
    """A heap-type instance must keep its type alive, including at shutdown."""
    before = sys.getrefcount(orjson.Fragment)
    fragment = orjson.Fragment(b"1")
    assert sys.getrefcount(type(fragment)) == before + 1
    del fragment
    assert sys.getrefcount(orjson.Fragment) == before


def test_fragment_cycle_finalizes_cleanly():
    """Reproduce the crash without HA, pytest fixtures, I/O or GC changes."""
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "faulthandler",
            "-c",
            "import orjson, sys; "
            "sys.synthetic_fragment_cycle = [orjson.Fragment(b'1')]; "
            "sys.synthetic_fragment_cycle.append(sys.synthetic_fragment_cycle)",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
