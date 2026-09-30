# Seed extraction + session addenda — 2026-09-12 (evening)

## Seed extraction session record
- User asked for the seed to use on Chunkbase.
- WRONG path (do not repeat): parsed `worlds/Bedrock level/db/*.ldb` and `*.log` with a hand-rolled
  LevelDB reader. Discovered BDS uses trailer compression type 4 = raw DEFLATE (`zlib.decompressobj(-15)`),
  NOT snappy. Parsed 8400+ keys successfully — but `LevelDat` is not a key in the db at all, and the
  .log held only AutonomousEntities/WorldClocks/player records. 15+ tool calls burned.
- RIGHT path: `level.dat` sits in the world dir itself (`worlds/<level-name>/level.dat`), 3052 bytes,
  header = 4-byte version + 4-byte length, then little-endian NBT. `RandomSeed` at offset ~903.
- Result for the live world: seed = `-3276240233532698416` (unsigned: `15170503840176853200`).

## playerssleepingpercentage change
- User asked: only 1 player needs to sleep for night to pass.
- `playerssleepingpercentage=1` appended to server.properties (key absent from default file — must append, not edit).
- Restart required. Waited until log showed all players disconnected before killing the process
  (players were: SKeevo98, StefCTRL, Xom9359). Nobody got dumped mid-session.
- Server bounced cleanly; clients reconnect same IP/port.

## Player names seen this session
SKeevo98 (PS5, joined via BedrockConnect after version upgrade), StefCTRL, Xom9359.

## Current live state (2026-09-12 late)
- Server: 1.26.45.1, survival/normal, port 19132 UDP, ufw open, running indefinitely per user standing order.
- Daily 04:00 backup cron in user crontab; backup dir `~/minecraft-bedrock/backups/`.
- bedrock_server explicitly excluded in `~/.hermes/scripts/kill-stale-dev-servers.sh`.
- Old install `~/minecraft-bedrock/server/` (1.26.20.5) kept for rollback; live install is `server-1.26.45.1/`.