import argparse
import json
import os
import plistlib
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

LIST_PATH = Path.home() / "Downloads" / "amnezia-ru-domains.json"
DOMAIN = "org.amneziavpn.AmneziaVPN"
APP = "AmneziaVPN"
BACKUP_PATH = Path.home() / "Library" / "Preferences" / f"{DOMAIN}.backup.plist"


class CliError(Exception):
    pass


def load_entries():
    try:
        entries = json.loads(LIST_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as error:
        raise CliError(f"некорректный JSON в {LIST_PATH}: {error}") from error

    if not isinstance(entries, list) or any(
        not isinstance(entry, dict)
        or not isinstance(entry.get("hostname"), str)
        or not isinstance(entry.get("ip"), str)
        for entry in entries
    ):
        raise CliError(f"ожидался список объектов hostname/ip в {LIST_PATH}")
    return entries


def write_entries(entries):
    LIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=LIST_PATH.parent,
            prefix=f".{LIST_PATH.name}.",
            delete=False,
        ) as temporary_file:
            json.dump(entries, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_path = Path(temporary_file.name)
        if LIST_PATH.exists():
            os.chmod(temporary_path, LIST_PATH.stat().st_mode)
        os.replace(temporary_path, LIST_PATH)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


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


def quit_amnezia():
    subprocess.run(
        ["osascript", "-e", f'quit app "{APP}"'],
        capture_output=True,
    )
    for _ in range(40):
        if subprocess.run(["pgrep", "-x", APP], capture_output=True).returncode:
            return
        time.sleep(0.25)
    raise CliError("Amnezia не закрылась — список не записан")


def sync_amnezia(entries):
    original_preferences = export_preferences()
    sites = {entry["hostname"]: [entry["ip"]] for entry in entries}
    if original_preferences.get("Conf.ExceptSites") == sites:
        print(f"в Amnezia уже актуально ({len(sites)})")
        return

    BACKUP_PATH.write_bytes(plistlib.dumps(original_preferences))
    quit_amnezia()
    try:
        preferences = dict(original_preferences)
        preferences["Conf.ExceptSites"] = sites
        import_preferences(preferences)
    except Exception:
        import_preferences(original_preferences)
        raise
    finally:
        subprocess.run(["open", "-a", APP], check=True)
    print(f"в Amnezia {len(sites)} записей, приложение перезапущено")


def persist_and_sync(entries, original_entries):
    write_entries(entries)
    try:
        sync_amnezia(entries)
    except Exception:
        write_entries(original_entries)
        raise


def normalize_host(host):
    normalized = host.strip().rstrip(".").lower()
    if not normalized:
        raise CliError("пустое имя хоста")
    return normalized


def resolve(host):
    try:
        return socket.gethostbyname(host)
    except OSError as error:
        raise CliError(f"не резолвится: {host}") from error


def add_hosts(hosts):
    original_entries = load_entries()
    entries = list(original_entries)
    known = {entry["hostname"] for entry in entries}
    added = []
    skipped = []
    for raw_host in hosts:
        host = normalize_host(raw_host)
        if host in known:
            skipped.append(host)
            continue
        entries.append({"hostname": host, "ip": resolve(host)})
        known.add(host)
        added.append(host)

    if added:
        persist_and_sync(entries, load_entries())
    print(f"добавлено: {', '.join(added) or '—'}")
    if skipped:
        print(f"уже было: {', '.join(skipped)}")


def remove_hosts(hosts):
    entries = load_entries()
    targets = [normalize_host(host) for host in hosts]
    target_set = set(targets)
    removed = [
        entry
        for entry in entries
        if entry["hostname"] in target_set or entry["ip"] in target_set
    ]
    if not removed:
        print(f"не найдено: {', '.join(targets)}")
        return

    remaining = [entry for entry in entries if entry not in removed]
    persist_and_sync(remaining, entries)
    removed_names = [entry["hostname"] for entry in removed]
    print(f"удалено: {', '.join(removed_names)}")
    removed_targets = {
        value for entry in removed for value in (entry["hostname"], entry["ip"])
    }
    missing = [target for target in targets if target not in removed_targets]
    if missing:
        print(f"не найдено: {', '.join(missing)}")


def list_entries(filter_text):
    entries = sorted(load_entries(), key=lambda entry: entry["hostname"])
    if filter_text:
        needle = filter_text.lower()
        entries = [
            entry
            for entry in entries
            if needle in entry["hostname"].lower() or needle in entry["ip"]
        ]
    for entry in entries:
        print(f"{entry['hostname']}\t{entry['ip']}")
    print(f"всего: {len(entries)}")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="amnezia",
        description="Управление сайтовыми исключениями AmneziaVPN",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    add_parser = commands.add_parser("add", help="добавить хосты в исключения")
    add_parser.add_argument("hosts", nargs="+", metavar="HOST")
    add_parser.set_defaults(handler=lambda args: add_hosts(args.hosts))

    remove_parser = commands.add_parser("remove", help="удалить хосты или IP из исключений")
    remove_parser.add_argument("hosts", nargs="+", metavar="HOST")
    remove_parser.set_defaults(handler=lambda args: remove_hosts(args.hosts))

    list_parser = commands.add_parser("list", help="показать исключения")
    list_parser.add_argument("filter", nargs="?", help="подстрока имени хоста или IP")
    list_parser.set_defaults(handler=lambda args: list_entries(args.filter))

    sync_parser = commands.add_parser("sync", help="применить JSON-список к Amnezia")
    sync_parser.set_defaults(handler=lambda args: sync_amnezia(load_entries()))
    return parser


def run():
    args = build_parser().parse_args()
    try:
        args.handler(args)
    except (CliError, OSError, subprocess.CalledProcessError) as error:
        print(f"ошибка: {error}", file=sys.stderr)
        return 1
    return 0


def main():
    raise SystemExit(run())
