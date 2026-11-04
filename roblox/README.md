# enx-ambard — Roblox (Rojo)

Каркас Roblox-игры под [Rojo](https://rojo.space): код живёт в файлах, а Rojo синхронизирует его в Roblox Studio.

Пример внутри — **сбор монет**: на карте появляются монеты, игрок собирает их, очки видны в таблице лидеров, монеты появляются снова.

## Структура

```
roblox/
├── default.project.json   # как папки отображаются в Studio
├── rokit.toml             # версии инструментов (rojo, selene, stylua)
└── src/
    ├── server/  -> ServerScriptService.Server
    │   ├── Leaderstats.server.luau   # таблица лидеров «Coins»
    │   └── Coins.server.luau         # спавн и сбор монет
    ├── client/  -> StarterPlayer.StarterPlayerScripts.Client
    │   └── CoinEffects.client.luau   # вращение монет и «+1» на экране
    └── shared/  -> ReplicatedStorage.Shared
        └── Config.luau               # настройки (кол-во монет, радиус и т.д.)
```

`ReplicatedStorage.Remotes.CoinCollected` (RemoteEvent) создаётся из `default.project.json`.

## Как запустить

1. Установите [Rokit](https://github.com/rojo-rbx/rokit), затем в папке `roblox`:
   ```bash
   rokit install
   ```
2. В Roblox Studio установите плагин Rojo (Plugins → Manage Plugins или через `rojo plugin install`).
3. Запустите сервер синхронизации:
   ```bash
   rojo serve
   ```
4. В Studio откройте пустой Baseplate → вкладка Plugins → **Rojo** → **Connect**.
5. Нажмите **Play** — по карте разбросаны монеты.

Собрать файл места без Studio: `rojo build -o game.rbxl`.

## Проверка кода

```bash
selene src
stylua --check src
```
