import os
import plistlib
import subprocess
import tempfile
import time
from pathlib import Path

from .config import entries_to_sites

DOMAIN = "org.amneziavpn.AmneziaVPN"
APP = "AmneziaVPN"


class AmneziaError(Exception):
    pass


def export_preferences():
    result = subprocess.run(
        ["defaults", "export", DOMAIN, "-"],
        capture_output=True,
        check=True,
    )
    return plistlib.loads(result.stdout)


def import_preferences(preferences):
    subprocess.run(
        ["defaults", "import", DOMAIN, "-"],
        input=plistlib.dumps(preferences),
        check=True,
    )


def write_plist(path, preferences):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary_file:
            plistlib.dump(preferences, temporary_file)
            temporary_path = Path(temporary_file.name)
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def read_plist(path):
    try:
        with path.open("rb") as plist_file:
            return plistlib.load(plist_file)
    except (OSError, plistlib.InvalidFileException) as error:
        raise AmneziaError(f"Cannot read backup {path}: {error}") from error


def backup_preferences(path):
    preferences = export_preferences()
    write_plist(path, preferences)
    return preferences


def quit_amnezia():
    subprocess.run(
        ["osascript", "-e", f'quit app "{APP}"'],
        capture_output=True,
    )
    for _ in range(40):
        if subprocess.run(["pgrep", "-x", APP], capture_output=True).returncode:
            return
        time.sleep(0.25)
    raise AmneziaError("AmneziaVPN did not quit; preferences were not changed")


def apply_entries(entries, original_preferences, backup_path, create_backup=True):
    sites = entries_to_sites(entries)
    if original_preferences.get("Conf.ExceptSites") == sites:
        return False
    if create_backup:
        write_plist(backup_path, original_preferences)
    quit_amnezia()
    try:
        preferences = dict(original_preferences)
        preferences["Conf.ExceptSites"] = sites
        import_preferences(preferences)
    except Exception:
        import_preferences(original_preferences)
        raise
    finally:
        subprocess.run(["open", "-a", APP], check=False)
    return True
