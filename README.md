# amnezia-cli

CLI для сайтовых исключений AmneziaVPN на macOS. Исходный список — `~/Downloads/amnezia-ru-domains.json`; после изменений CLI обновляет настройки и перезапускает Amnezia.

## Установка

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
ln -sfn "$PWD/.venv/bin/amnezia-cli" ~/.local/bin/amnezia-cli
```

## Команды

```bash
amnezia-cli add example.com 192.0.2.1
amnezia-cli remove example.com 192.0.2.1
amnezia-cli list
amnezia-cli list example
amnezia-cli sync
```

`add` резолвит хост в IPv4 и пропускает уже существующие имена. `remove` находит записи по имени хоста или IP. `sync` применяет текущий JSON-файл без изменения списка. Перед записью настроек создаётся `~/Library/Preferences/org.amneziavpn.AmneziaVPN.backup.plist`.

Совместимость со старым интерфейсом: `amnezia-sync HOST…` вызывает `amnezia-cli add`, а `amnezia-sync` без аргументов — `amnezia-cli sync`.
