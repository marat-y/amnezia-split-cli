import json
import os
import tempfile
from pathlib import Path

APP_NAME = "amnezia-split-cli"


class ConfigError(Exception):
    pass


def config_dir():
    override = os.environ.get("AMNEZIA_SPLIT_CLI_CONFIG_HOME")
    if override:
        return Path(override).expanduser()
    xdg_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg_home).expanduser() if xdg_home else Path.home() / ".config"
    return base / APP_NAME


def default_list_path():
    return config_dir() / "exceptions.json"


def default_backup_path():
    return config_dir() / "backup.plist"


def load_entries(path):
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as error:
        raise ConfigError(f"Invalid JSON in {path}: {error}") from error
    validate_entries(entries, path)
    return entries


def validate_entries(entries, path):
    if not isinstance(entries, list) or any(
        not isinstance(entry, dict)
        or not isinstance(entry.get("hostname"), str)
        or not isinstance(entry.get("ip"), str)
        for entry in entries
    ):
        raise ConfigError(f"Expected a list of hostname/ip objects in {path}")


def write_entries(path, entries):
    validate_entries(entries, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary_file:
            json.dump(entries, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_path = Path(temporary_file.name)
        mode = path.stat().st_mode if path.exists() else 0o600
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def entries_to_sites(entries):
    return {
        entry["hostname"]: [entry["ip"]] if entry["ip"] else []
        for entry in entries
    }


def sites_to_entries(sites):
    if not isinstance(sites, dict):
        raise ConfigError("Conf.ExceptSites must be a dictionary")
    entries = []
    for hostname, addresses in sites.items():
        if not isinstance(hostname, str) or not isinstance(addresses, list):
            raise ConfigError("Invalid entry in Conf.ExceptSites")
        if any(not isinstance(address, str) for address in addresses):
            raise ConfigError("Invalid IP address in Conf.ExceptSites")
        entries.append({"hostname": hostname, "ip": addresses[0] if addresses else ""})
    return sorted(entries, key=lambda entry: entry["hostname"])


def merge_entries(entries, sites):
    merged = {entry["hostname"]: entry["ip"] for entry in entries}
    for entry in sites_to_entries(sites):
        merged.setdefault(entry["hostname"], entry["ip"])
    return [
        {"hostname": hostname, "ip": merged[hostname]}
        for hostname in sorted(merged)
    ]
