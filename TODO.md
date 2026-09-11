# TODO

- [ ] Dashboard: add an `instance` template variable and filter every query with `{instance=~"$instance"}` so multiple servers can share one dashboard
- [ ] Dashboard: "Survivors" table (hours survived, zombie kills, health, dead) from `pz_character_*`
- [ ] Document running one instance per server (distinct `PZMONITOR_LISTEN_ADDR` and Prometheus `instance` label per target)
- [ ] Drop metrics the built-in exporter already provides (player count, `stats` "today" counters) once `-DprometheusPort` is the documented companion; keep RCON player list, mods and `players.db`
