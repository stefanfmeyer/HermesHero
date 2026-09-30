# GAIA / Sennheiser Protocol Reference

Condensed from reverse-engineering projects (m4-companion, OpenMomentum, MTW4 btsnoop notes, SpaceTravel-Protocol). All verified against at least one byte-level capture; the core command table against two independent MIT implementations. Cite these upstreams in any derived code.

## Command word packing (GAIA V3)

```
Bit 15-9: Feature ID (7 bits)
Bit 8-7:  Packet type (00 command / 01 notification / 10 response / 11 error)
Bit 6-0:  Command ID (7 bits)
```

- Query response = `cmd | 0x0100` (e.g. `0x0603` -> `0x0703`)
- Error response = success response id with `0x0080` set (e.g. `0x1b80`)
- Sennheiser vendor id: `0x0495`

## Wire framings

### SPP-style (RFCOMM captures; app sends 0x03, device often answers 0x04 — parse by structure, not type byte)

```
FF 03|04 lenHi lenLo vendorHi vendorLo cmdHi cmdLo payload...
```
- `len` = payload length only; full frame = 8 + len bytes.

### GAIA v3 over GATT (browser path)

```
ver/flags seq lenHi lenLo vendorHi vendorLo cmdHi cmdLo payload...
```
- `ver/flags` = `(version << 6) | flags`; unfragmented = start|end → `0x85` for v3.
- Same `8 + len` total. Long payloads fragment with start / continue / end flags.

Captured example (MTW4, SPP framing): `FF 03 00 00 04 95 06 03` = battery query, zero payload.
Battery notification: `FF 04 00 03 04 95 06 83 50 50 3C` = L 80% / R 80% / case 60%.

## Sennheiser MOMENTUM 4 command table (vendor 0x0495)

| Function | Request | Response | Payload |
| --- | --- | --- | --- |
| Battery | 0x0603 | 0x0703 | percentage 0-100 |
| Sound mode get/set | 0x0804 / 0x0803 | 0x0904 / 0x0903 | mode: 0 off / 1 equalizer / 2 podcast / 3 sound personalization |
| BT compat mode | 0x0406 | 0x0506 | 0 better audio / 1 better compatibility |
| Sound personalization profile state | 0x2001 | 0x2101 | 0 not parameterized / 1 calibrating / 2 calibrated / 3 activation inhibited |
| ANC enable set/get | 0x1a04 / 0x1a05 | 0x1b04 / 0x1b05 | bool (SET ACK has no state semantics) |
| ANC sub-mode set / get list | 0x1a00 / 0x1a01 | 0x1b00 / 0x1b01 | `[mode, state]` pairs; modes: 1 anti-wind, 2 comfort, 3 adaptive |
| Transparency level set/get | 0x1a02 / 0x1a03 | 0x1b02 / 0x1b03 | 0-100 (0 = max ANC, 100 = max transparency) |
| Transparent hearing set/get | 0x1804 / 0x1805 | 0x1904 / 0x1905 | bool |
| EQ config get | 0x1000 | 0x1100 | `[bandCount, minGainTenths(s8), maxGainTenths(s8)]` |
| EQ band set | 0x1001 | 0x1101 | `[bandIndex, gainTenths(s8)]` |
| EQ band get | 0x1002 | 0x1102 | `[bandIndex?, gainTenths]` (echo byte optional) |
| Bass boost set/get | 0x1008 / 0x1009 | 0x1108 / 0x1109 | bool |

## Payload encodings (byte-exact)

- **EQ band write:** `[index, round(clamp(gainDb) * 10) as int8]` — gain in tenths of dB, signed byte, clamped to device-reported range. Example: band 2, -3.5 dB → `02 DD`.
- **EQ config parse:** min/max are `int8 / 10` (dB). Momentum 4 reports 5 bands, -10..+10 dB.
- **ANC mode write:** `[mode, state]`; adaptive on = `03 01`, adaptive off = `03 00`.
- **Multipoint device list** (feature 0x14): listSize 0x1400/0x1500 (count = u16 BE), deviceInfo 0x1401/0x1501 (`[index, priority, connected, name... NUL-terminated]`), connect/disconnect 0x1402/0x1403, ownIndex 0x1407, maxConnections 0x1409, connectionStatus 0x1404.

## Control sequences (from m4-companion MomentumControlPlan)

- **Manual max ANC:** transparent-hearing off → ANC on → adaptive sub-mode `03 00` → transparency level 0.
- **Adaptive ANC:** TH off → ANC on → adaptive `03 01`.
- **Transparency:** TH off → adaptive `03 00` → transparency level N.
- **Off:** TH off → ANC disabled.
- Always finish a write sequence with fresh queries: battery, ANC enabled, ANC modes, transparency level, TH state. Update UI only from read-back results.

## State-machine lessons (MTW4 btsnoop captures)

1. ANC on/off and transparency on/off are physically exclusive but the device does NOT push consistent pairs — transparency toggles often arrive without an ANC push. Keep independent flags; derive UI tri-state (transparency / ANC / off) from flags, never from one variable.
2. SET ACKs (`0x1b04`, `0x1904`) carry empty payloads — useless for state.
3. The transparency "get" (`0x1903`) answers with a level value (constant 0x32 in captures), not an on/off — misreading this makes the UI stick.
4. Behavior discipline of the official app: one persistent connection, no polling after init (push-driven), no aggressive auto-reconnect, control commands only on user action.

## BLE service discovery (browser)

- GAIA BLE service: `0xFCD7` (some stacks expose `F6CD`/`F6CE`/`FCFE` variants).
- Data characteristics: `F6CE` (GAIA v3/v2, notifications + writes), `F6CD` (v1 legacy).
- If the standard service is absent, enumerate all services/characteristics and log them to the console — never fail silently.
- Sennheiser MTW4 note: the official app deliberately uses Classic RFCOMM; a persistent BLE connection can interfere with TWS second-bud handshake. Keep BLE sessions short/user-driven where feasible.

### Real-hardware MOMENTUM 4 Wireless BLE inventory (captured 2026-09-29 via Web Bluetooth on the live app)

```
180a{2a23 2a24 2a26 2a27 2a28 2a29 2a2a 2a50}   standard Device Information
180f{2a19}                                       standard Battery Level
fcfe{6333133b 6333133c 6333133d 63331379}        Sennheiser proprietary companion service
```

- **No GAIA `f6cd`/`f6ce` endpoints exist on MOMENTUM 4.** Do not assume they do; match on the actual inventory.
- `fcfe` with `6333xxxx` characteristics is Sennheiser's own BLE companion surface (same service family the MTW4 notes describe for BLE telemetry). These are the only vendor-specific BLE characteristics MOMENTUM 4 exposes — the candidates for any BLE control channel.
- The standard Battery Service (`180f`/`2a19`, `readValue` → single byte %) works over BLE **independent of the control channel** — always wire it, it is the one guaranteed feature when control turns out Classic-only.

## Model support reality check

- MOMENTUM 4 Wireless: GAIA command table above verified against two independent implementations (over Classic RFCOMM). Over BLE, the device exposes only the fcfe companion service (see inventory above); whether GAIA rides it is decided per-device by the runtime probe — if no candidate endpoint answers a GAIA query, control is Classic-only and unreachable from any browser. Battery + device info over BLE still work.
- TWS range (TW4 etc.): RFCOMM-documented; BLE support unverified — rely on the runtime framing probe + protocol console to classify a device on first contact.
- Devices exposing GAIA only over Classic RFCOMM are unreachable from any browser — detect and tell the user instead of failing silently.
