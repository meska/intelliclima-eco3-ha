"""No real HA configuration is touched by deployment tests."""

import os
import py_compile

import pytest

from scripts.manage_install import digest_tree, install, rollback


@pytest.mark.parametrize("existing", [True, False])
def test_install_rollback(tmp_path, existing):
    config = tmp_path / "config"
    config.mkdir()
    (config / "configuration.yaml").write_text("synthetic: true")
    target = config / "custom_components/intelliclima"
    if existing:
        target.mkdir(parents=True)
        (target / "old.txt").write_text("synthetic previous component")
    before = digest_tree(target)
    backup = tmp_path / "backup"
    install(config, backup)
    assert (target / "manifest.json").is_file()
    rollback(config, backup)
    assert digest_tree(target) == before
    assert target.exists() == existing
    assert (config / "configuration.yaml").read_text() == "synthetic: true"


@pytest.mark.parametrize("existing", [True, False])
@pytest.mark.parametrize("optimize", [0, 1, 2])
def test_generated_bytecode_allows_rollback(tmp_path, existing, optimize):
    """Normal CPython caches do not constitute a source update."""
    config = tmp_path / "config"
    config.mkdir()
    (config / "configuration.yaml").write_text("synthetic: true")
    target = config / "custom_components/intelliclima"
    if existing:
        target.mkdir(parents=True)
        (target / "old.py").write_text("OLD = True\n")
        # Previous cache bytes are backup data, not ignorable install changes.
        py_compile.compile(str(target / "old.py"), doraise=True)
    before = digest_tree(target)
    backup = tmp_path / "backup"
    install(config, backup)
    py_compile.compile(str(target / "const.py"), doraise=True, optimize=optimize)
    rollback(config, backup)
    assert digest_tree(target) == before
    assert target.exists() == existing


def test_modified_install_blocks_rollback(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "configuration.yaml").write_text("synthetic: true")
    backup = tmp_path / "backup"
    install(config, backup)
    (config / "custom_components/intelliclima/manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="Installed files changed"):
        rollback(config, backup)


@pytest.mark.parametrize(
    "change",
    [
        "source",
        "missing_source",
        "unknown_cache",
        "orphan_cache",
        "legacy_pyc",
        "cache_source",
        "cache_symlink",
        "cache_dir_symlink",
        "cache_fifo",
        "backup",
    ],
)
def test_cache_never_hides_tampering(tmp_path, change):
    """Allowlisted caches must not weaken source, backup or path integrity."""
    config = tmp_path / "config"
    config.mkdir()
    (config / "configuration.yaml").write_text("synthetic: true")
    target = config / "custom_components/intelliclima"
    target.mkdir(parents=True)
    (target / "old.py").write_text("OLD = True\n")
    py_compile.compile(str(target / "old.py"), doraise=True)
    backup = tmp_path / "backup"
    install(config, backup)
    cache = target / "__pycache__"
    compiled = py_compile.compile(str(target / "const.py"), doraise=True)
    if change == "source":
        (target / "const.py").write_text("CHANGED = True\n")
    elif change == "missing_source":
        (target / "const.py").unlink()
    elif change == "unknown_cache":
        (cache / "notes.txt").write_text("user data")
    elif change == "orphan_cache":
        (cache / "unknown.cpython-314.pyc").write_bytes(b"user data")
    elif change == "legacy_pyc":
        (target / "const.pyc").write_bytes(b"user data")
    elif change == "cache_source":
        (cache / "user.py").write_text("USER = True\n")
    elif change == "cache_symlink":
        os.unlink(compiled)
        os.symlink(backup / "previous/old.py", compiled)
    elif change == "cache_dir_symlink":
        os.unlink(compiled)
        cache.rmdir()
        cache.symlink_to(backup / "previous", target_is_directory=True)
    elif change == "cache_fifo":
        os.unlink(compiled)
        os.mkfifo(compiled)
    else:
        # Even a previous generated cache is protected by the exact backup digest.
        previous_cache = next((backup / "previous/__pycache__").glob("*.pyc"))
        previous_cache.write_bytes(b"modified backup")
    with pytest.raises(ValueError):
        rollback(config, backup)
    assert target.exists()
    assert (backup / "record.json").is_file()


def test_symlink_refused(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "configuration.yaml").write_text("synthetic: true")
    (config / "custom_components").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="Symlink"):
        install(config, tmp_path / "backup")
