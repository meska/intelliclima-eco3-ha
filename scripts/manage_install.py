"""Install/rollback only the custom component on a mounted HA config directory.

No SSH, network, config-entry editing, dependency installation or restart. Take a
full HA backup and stop Core before applying. A fresh backup directory is required.
"""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "custom_components" / "intelliclima"


def digest_tree(directory):
    """Fingerprint the exact regular files; reject symlinks and special files."""
    if directory.is_symlink():
        raise ValueError("Symlink directory refused")
    if not directory.exists():
        return {}
    result = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink() or (not path.is_dir() and not path.is_file()):
            raise ValueError("Non-regular file refused")
        if path.is_file():
            result[str(path.relative_to(directory))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def target_path(config):
    """Refuse missing config markers and symlinked component containers."""
    config = Path(config).resolve(strict=True)
    if not (config / "configuration.yaml").is_file():
        raise ValueError("Not a HA configuration directory")
    container = config / "custom_components"
    if container.is_symlink():
        raise ValueError("Symlink custom_components refused")
    target = container / "intelliclima"
    digest_tree(target)
    return target


def install(config, backup, source=SOURCE):
    """Back up the existing custom component, stage clean files, verify install."""
    target = target_path(config)
    backup = Path(backup).resolve()
    if backup == target or target in backup.parents or backup in target.parents:
        raise ValueError("Backup must be outside the component path")
    manifest = json.loads((source / "manifest.json").read_text())
    if manifest["domain"] != "intelliclima" or manifest["requirements"] != [
        "pyintelliclima==0.5.0"
    ]:
        raise ValueError("Unexpected source manifest")
    before = digest_tree(target)
    digest_tree(source)
    backup.mkdir(mode=0o700, parents=False, exist_ok=False)
    if target.exists():
        shutil.copytree(target, backup / "previous")
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = target.parent / ".intelliclima-stage"
    if stage.exists() or stage.is_symlink():
        raise ValueError("Staging path already exists")
    shutil.copytree(source, stage, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    after = digest_tree(stage)
    record = {"previous_exists": target.exists(), "before": before, "installed": after}
    (backup / "record.json").write_text(json.dumps(record, indent=2) + "\n")
    if digest_tree(backup / "previous") != before:
        raise RuntimeError("Backup verification failed")
    if target.exists():
        shutil.rmtree(target)
    stage.rename(target)
    if digest_tree(target) != after:
        raise RuntimeError("Install verification failed; restore backup")
    return record


def rollback(config, backup):
    """Refuse rollback if installed files changed; restore byte-for-byte backup."""
    target = target_path(config)
    backup = Path(backup).resolve(strict=True)
    record = json.loads((backup / "record.json").read_text())
    current = digest_tree(target)
    # Validate the entire tree first, including caches: never hide unsafe paths.
    # Ignore only CPython-tagged cache files for a recorded installed .py source.
    # Backup fingerprints remain exact, including any previous cache bytes.
    for relative in list(current):
        path = Path(relative)
        match = re.fullmatch(r"(.+)\.cpython-[0-9]+(?:\.opt-[12])?\.pyc", path.name)
        if path.parent.name == "__pycache__" and match:
            source = str(path.parent.parent / (match[1] + ".py"))
            if source in record["installed"] and relative not in record["installed"]:
                del current[relative]
    if current != record["installed"]:
        raise ValueError("Installed files changed; manual review required")
    if digest_tree(backup / "previous") != record["before"]:
        raise ValueError("Backup changed")
    shutil.rmtree(target)
    if record["previous_exists"]:
        shutil.copytree(backup / "previous", target)
    if digest_tree(target) != record["before"]:
        raise RuntimeError("Rollback verification failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "install", "rollback"])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--reviewed-core-stopped-full-backup", action="store_true")
    args = parser.parse_args()
    target = target_path(args.config)
    if args.action == "check":
        print(
            json.dumps(
                {
                    "existing_files": len(digest_tree(target)),
                    "source_files": len(digest_tree(SOURCE)),
                }
            )
        )
        return
    if not args.reviewed_core_stopped_full_backup or args.backup is None:
        parser.error("Apply requires review, stopped Core, full HA backup and --backup")
    if args.action == "install":
        install(args.config, args.backup)
    else:
        rollback(args.config, args.backup)
    print(args.action + " verified; Core was not restarted")


if __name__ == "__main__":
    main()
