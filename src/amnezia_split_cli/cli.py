import argparse
import json
import socket
import subprocess
import sys
from pathlib import Path

from .amnezia import (
    AmneziaError,
    apply_entries,
    backup_preferences,
    export_preferences,
    read_plist,
)
from .config import (
    ConfigError,
    default_backup_path,
    default_list_path,
    load_entries,
    merge_entries,
    sites_to_entries,
    write_entries,
)


def normalize_host(host):
    normalized = host.strip().rstrip(".").lower()
    if not normalized:
        raise ConfigError("Hostname cannot be empty")
    return normalized


def resolve(host):
    try:
        return socket.gethostbyname(host)
    except OSError as error:
        raise ConfigError(f"Cannot resolve {host}") from error


def current_preferences():
    preferences = export_preferences()
    sites = preferences.get("Conf.ExceptSites", {})
    sites_to_entries(sites)
    return preferences


def persist(args, entries, original_entries, preferences, create_backup=True):
    if args.dry_run:
        print(f"Dry run: {len(entries)} entries; no files or settings changed")
        return
    write_entries(args.file, entries)
    if args.no_restart:
        print(f"Wrote {len(entries)} entries to {args.file}; AmneziaVPN was not changed")
        return
    try:
        changed = apply_entries(
            entries,
            preferences,
            args.backup,
            create_backup=create_backup,
        )
    except Exception:
        write_entries(args.file, original_entries)
        raise
    if changed:
        print(f"Applied {len(entries)} entries and relaunched AmneziaVPN")
    else:
        print(f"AmneziaVPN already has these {len(entries)} entries")


def add_hosts(args):
    original_entries = load_entries(args.file)
    preferences = current_preferences()
    entries = merge_entries(
        original_entries,
        preferences.get("Conf.ExceptSites", {}),
    )
    known = {entry["hostname"] for entry in entries}
    added = []
    skipped = []
    for raw_host in args.hosts:
        host = normalize_host(raw_host)
        if host in known:
            skipped.append(host)
            continue
        entries.append({"hostname": host, "ip": resolve(host)})
        known.add(host)
        added.append(host)
    entries.sort(key=lambda entry: entry["hostname"])
    persist(args, entries, original_entries, preferences)
    print(f"Added: {', '.join(added) or 'none'}")
    if skipped:
        print(f"Already present: {', '.join(skipped)}")


def remove_hosts(args):
    original_entries = load_entries(args.file)
    preferences = current_preferences()
    entries = merge_entries(
        original_entries,
        preferences.get("Conf.ExceptSites", {}),
    )
    targets = [normalize_host(host) for host in args.hosts]
    target_set = set(targets)
    removed = [
        entry
        for entry in entries
        if entry["hostname"] in target_set or entry["ip"] in target_set
    ]
    remaining = [entry for entry in entries if entry not in removed]
    if removed:
        persist(args, remaining, original_entries, preferences)
    removed_names = [entry["hostname"] for entry in removed]
    print(f"Removed: {', '.join(removed_names) or 'none'}")
    removed_targets = {
        value for entry in removed for value in (entry["hostname"], entry["ip"])
    }
    missing = [target for target in targets if target not in removed_targets]
    if missing:
        print(f"Not found: {', '.join(missing)}")


def list_entries(args):
    entries = load_entries(args.file)
    if args.filter:
        needle = args.filter.lower()
        entries = [
            entry
            for entry in entries
            if needle in entry["hostname"].lower() or needle in entry["ip"]
        ]
    if args.json:
        json.dump(entries, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return
    for entry in entries:
        print(f"{entry['hostname']}\t{entry['ip']}")
    print(f"Total: {len(entries)}")


def sync_entries(args):
    original_entries = load_entries(args.file)
    preferences = current_preferences()
    if args.replace:
        entries = original_entries
    else:
        entries = merge_entries(
            original_entries,
            preferences.get("Conf.ExceptSites", {}),
        )
    persist(args, entries, original_entries, preferences)


def create_backup(args):
    backup_preferences(args.output)
    print(f"Backup written to {args.output}")


def restore_backup(args):
    original_entries = load_entries(args.file)
    restored = read_plist(args.input)
    if "Conf.ExceptSites" not in restored:
        raise AmneziaError(f"Backup {args.input} has no Conf.ExceptSites")
    entries = sites_to_entries(restored["Conf.ExceptSites"])
    preferences = current_preferences()
    args.no_restart = False
    persist(args, entries, original_entries, preferences, create_backup=False)


def add_apply_options(parser):
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show the result without writing files or settings",
    )
    parser.add_argument(
        "--no-restart",
        action="store_true",
        help="only update JSON; do not change or restart AmneziaVPN",
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="amnezia-split-cli",
        description="Manage AmneziaVPN site-based split tunneling on macOS",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=default_list_path(),
        help=f"exceptions JSON file (default: {default_list_path()})",
    )
    parser.add_argument(
        "--backup",
        type=Path,
        default=default_backup_path(),
        help=f"automatic backup path (default: {default_backup_path()})",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    add_parser = commands.add_parser("add", help="add hosts to exceptions")
    add_parser.add_argument("hosts", nargs="+", metavar="HOST")
    add_apply_options(add_parser)
    add_parser.set_defaults(handler=add_hosts)

    remove_parser = commands.add_parser("remove", help="remove hosts or IPs from exceptions")
    remove_parser.add_argument("hosts", nargs="+", metavar="HOST")
    add_apply_options(remove_parser)
    remove_parser.set_defaults(handler=remove_hosts)

    list_parser = commands.add_parser("list", help="list exceptions from JSON")
    list_parser.add_argument("filter", nargs="?", help="substring of a hostname or IP")
    list_parser.add_argument("--json", action="store_true", help="print a JSON array")
    list_parser.set_defaults(handler=list_entries)

    sync_parser = commands.add_parser("sync", help="merge JSON with current AmneziaVPN rules")
    sync_parser.add_argument(
        "--replace",
        action="store_true",
        help="replace all AmneziaVPN rules instead of merging",
    )
    add_apply_options(sync_parser)
    sync_parser.set_defaults(handler=sync_entries)

    backup_parser = commands.add_parser("backup", help="back up AmneziaVPN preferences")
    backup_parser.add_argument("output", nargs="?", type=Path, default=default_backup_path())
    backup_parser.set_defaults(handler=create_backup)

    restore_parser = commands.add_parser("restore", help="restore exceptions from a backup")
    restore_parser.add_argument("input", nargs="?", type=Path, default=default_backup_path())
    restore_parser.add_argument("--dry-run", action="store_true")
    restore_parser.set_defaults(handler=restore_backup)
    return parser


def run(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except (ConfigError, AmneziaError, OSError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


def main():
    raise SystemExit(run())
