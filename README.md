# pzmonitor

[![CI](https://github.com/MarioMoura/pzmonitor/actions/workflows/ci.yml/badge.svg)](https://github.com/MarioMoura/pzmonitor/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/MarioMoura/pzmonitor)](https://github.com/MarioMoura/pzmonitor/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A Prometheus exporter for Project Zomboid dedicated servers. Collects server metrics via RCON and exposes them on a `/metrics` endpoint.

![Grafana dashboard — server overview](docs/dashboard-overview.png)

![Grafana dashboard — players and world](docs/dashboard-players.png)

A ready-to-import Grafana dashboard is included at [`grafana/dashboard.json`](grafana/dashboard.json).

## Metrics

- **Server health**: FPS, JVM memory (used/total/max), average update period
- **Players & world**: players online, zombies (loaded/simulated/total), loaded cells, animal instances
- **Daily events**: zombies killed, players killed (by zombie/player/fire), zombified players, burned corpses
- **Network**: bytes sent/received per second, packet loss
- **Operational**: scrape duration, server up/down
- **Characters** (optional, from `players.db`): hours survived, zombie/survivor kills, dead flag, health, stats (hunger, thirst, fatigue, infection, ...), perk levels, position, profession

## Installation

Download the binary for your platform from the [Releases](https://github.com/MarioMoura/pzmonitor/releases) page, then:

```bash
chmod +x pzmonitor
./pzmonitor
```

Or build from source:

```bash
go install github.com/MarioMoura/pzmonitor@latest
```

### Ansible

The repo ships an Ansible collection (`ansible/`) with a `pzmonitor` role that
downloads the release binary and installs a systemd unit.

Add it to your `requirements.yml` (pin the tag to the release you want):

```yaml
collections:
  - name: https://github.com/MarioMoura/pzmonitor.git#ansible
    type: git
    version: v0.2.0
```

Install and use it:

```bash
ansible-galaxy collection install -r requirements.yml
```

```yaml
- hosts: zomboid
  become: true
  roles:
    - role: mariomoura.pzmonitor.pzmonitor
      vars:
        pzmonitor_rcon_password: "{{ rcon_password }}"
```

Useful variables (see `ansible/roles/pzmonitor/defaults/main.yml` for all):

| Variable | Default | Description |
|---|---|---|
| `pzmonitor_version` | release version | Release to download |
| `pzmonitor_user` | `pzmonitor` | User that runs the service (created unless `pzmonitor_create_user: false`) |
| `pzmonitor_install_dir` | `/opt/pzmonitor` | Where the binary lives |
| `pzmonitor_port` | `9103` | Metrics listen port |
| `pzmonitor_rcon_host` / `pzmonitor_rcon_port` | `127.0.0.1` / `27015` | RCON target |
| `pzmonitor_after_unit` | `""` | systemd unit to start after, e.g. `zomboid.service` |
| `pzmonitor_players_db` | `""` | Path to `players.db`; enables character metrics |
| `pzmonitor_env` | `{}` | Extra `PZMONITOR_*` environment variables |

## Configuration

All configuration is done via environment variables:

| Variable | Default | Description |
|---|---|---|
| `PZMONITOR_RCON_HOST` | `127.0.0.1` | RCON server host |
| `PZMONITOR_RCON_PORT` | `27015` | RCON server port |
| `PZMONITOR_RCON_PASSWORD` | *(required)* | RCON password |
| `PZMONITOR_LISTEN_ADDR` | `:9101` | Address for the HTTP metrics server |
| `PZMONITOR_LOG_LEVEL` | `info` | Log level (`debug`, `info`, `warn`, `error`) |
| `PZMONITOR_PLAYERS_DB` | *(unset)* | Path to the server's `players.db` (e.g. `~/Zomboid/Saves/Multiplayer/servertest/players.db`). Enables `pz_character_*` metrics |

### Character metrics

When `PZMONITOR_PLAYERS_DB` is set, every scrape opens the database read-only
(`immutable=1`, so the running server is never blocked) and decodes each saved
character. pzmonitor must be able to read the file, which usually means running
as the same user as the server.

| Metric | Labels | Description |
|---|---|---|
| `pz_character_info` | `username`, `name`, `profession`, `steamid` | Always 1 |
| `pz_character_dead` | `username` | 1 if dead |
| `pz_character_hours_survived` | `username` | In-game hours |
| `pz_character_zombie_kills` / `pz_character_survivor_kills` | `username` | Kill counters |
| `pz_character_health` | `username` | Average body part health, 0-100 |
| `pz_character_stat` | `username`, `stat` | hunger, thirst, fatigue, panic, zombie_infection, ... |
| `pz_character_perk_level` | `username`, `perk` | Skill levels |
| `pz_character_position` | `username`, `axis` | Last saved x/y/z |
| `pz_character_items` | `username` | Item stacks in inventory |
| `pz_players_db_up` / `pz_players_db_scrape_duration_seconds` / `pz_players_db_parse_errors` | | Read health |

The save format is undocumented and changes between builds; parsing was
verified against Build 42.20 (world version 249). A character that fails to
parse still reports `pz_character_info`, `pz_character_dead` and
`pz_character_position` from the table columns.

Copy `.env.example` as a reference:

```bash
cp .env.example .env
```

## Map panels

The dashboard has two Geomap panels (Survivors Map, Live path of a player) that
draw player positions on top of the game map. They need XYZ tiles of a top-down
render of the map, served over HTTP. Two scripts produce them:

- `scripts/tile_cells.py CELLDIR OUTDIR` — from per-cell images (one
  `{cx}_{cy}.webp` per 256x256-tile cell, e.g. the 1024 px "thumbs" published by
  pzfans.com, 4 px per world tile). Bounded memory, zoom 10-19, ~75k tiles.
- `scripts/tile_map.py MAP.jpg OUTDIR` — from one stitched image at 1 px per world
  tile (e.g. the pzmap.org top-down export, 19968x16128 for B42). Zoom 10-18.

Point the dashboard at the tiles by replacing the `${PZMAP_TILES_URL}`
placeholder with the template URL, e.g.
`https://grafana.example/pzmap/{z}/{x}/{y}.webp`, the same way `${DS_PROMETHEUS}`
is replaced. World coordinates are projected onto the equator at 1 m per tile:
`lon = x / 111319.4908`, `lat = -y / 111319.4908`.

## Prometheus

Add a scrape job to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: pzmonitor
    static_configs:
      - targets: ["localhost:9101"]
```

## Built-in server exporter

Build 42 servers ship their own Prometheus endpoint, enabled with a JVM flag
(`-DprometheusPort=9105` in `ProjectZomboid64.json`). It exposes JVM/process
metrics, RakNet network stats, world counters (`game{parameter="players"}`,
`zombies-total`, `loaded-cells`, ...), the same "today" kill counters as RCON
`stats`, and live player positions (`player_x`/`player_y{id,name}`, refreshed
every `MultiplayerStatisticsPeriod` seconds) while players are online.

pzmonitor is complementary, not a replacement: it adds everything that comes
from RCON (player list, mods, server options) and from `players.db`
(per-character stats, deaths, kills, perks, positions of offline players), and
runs outside the JVM so it keeps reporting across server restarts. The
recommended setup scrapes both; the bundled dashboard uses the built-in
endpoint for the live map and pzmonitor for the rest:

```yaml
  - job_name: pzserver
    scrape_interval: 5s
    static_configs:
      - targets: ["localhost:9105"]
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: "player_(x|y)"
        target_label: __name__
        replacement: "pz_player_${1}"
      - source_labels: [name]
        target_label: username
      - regex: "name|id"
        action: labeldrop
```

## Endpoints

- `GET /metrics` - Prometheus metrics
- `GET /healthz` - Health check
