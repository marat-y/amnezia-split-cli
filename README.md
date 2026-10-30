# amnezia-split-cli

A safe, agent-friendly CLI for managing site-based split tunneling in the AmneziaVPN desktop app on macOS.

It edits AmneziaVPN's `Conf.ExceptSites` preference through macOS `defaults`, keeps a local JSON copy, creates a backup before applying changes, and relaunches AmneziaVPN when required.

## Requirements

- macOS with AmneziaVPN installed
- Python 3.9 or newer
- Site-based split tunneling available in your AmneziaVPN plan or self-hosted setup

## Installation

```bash
pipx install git+https://github.com/marat-y/amnezia-split-cli.git
```

For development:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

## Usage

```bash
amnezia-split-cli add example.com 192.0.2.1
amnezia-split-cli remove example.com 192.0.2.1
amnezia-split-cli list
amnezia-split-cli list example --json
amnezia-split-cli sync
```

`add` resolves each new hostname to one IPv4 address. `remove` accepts hostnames or IP addresses. `list` reads the local JSON file.

By default, `add`, `remove`, and `sync` merge the local JSON with rules currently stored in AmneziaVPN. Rules added through the GUI are therefore preserved and adopted into the JSON file. To deliberately replace every rule with the JSON contents, use:

```bash
amnezia-split-cli sync --replace
```

Preview changes without writing anything:

```bash
amnezia-split-cli add example.com --dry-run
amnezia-split-cli sync --replace --dry-run
```

Update only the JSON file without changing or restarting AmneziaVPN:

```bash
amnezia-split-cli add example.com --no-restart
```

Back up and restore:

```bash
amnezia-split-cli backup
amnezia-split-cli backup ~/Desktop/amnezia-backup.plist
amnezia-split-cli restore ~/Desktop/amnezia-backup.plist
```

`restore` restores only `Conf.ExceptSites`; other preferences are left unchanged.

## Files and options

The default files are:

- `~/.config/amnezia-split-cli/exceptions.json` — local exception list
- `~/.config/amnezia-split-cli/backup.plist` — automatic preference backup

Use `--file PATH` to select another JSON file and `--backup PATH` to select another automatic backup. Global options go before the subcommand. `XDG_CONFIG_HOME` and `AMNEZIA_SPLIT_CLI_CONFIG_HOME` can override the configuration directory.

Backups contain complete AmneziaVPN preferences and may contain sensitive connection data. They are written with owner-only permissions; do not publish them.

Applying rules relaunches AmneziaVPN and may briefly interrupt the VPN connection. No change is applied when the current rules already match.

## Current limits

- macOS only
- One resolved IPv4 address per added hostname
- No automatic DNS rotation, IPv6, or CIDR expansion
- The app preference format is internal and may change between AmneziaVPN versions

## License

MIT
