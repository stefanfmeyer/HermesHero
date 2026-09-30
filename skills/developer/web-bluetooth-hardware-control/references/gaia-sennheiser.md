# Sennheiser GAIA Protocol Notes

Verified against two independent MIT-licensed RE projects: **m4-companion** (Zhengyang-Liu, macOS RFCOMM) and **OpenMomentum** (ladybridgett, Android RFCOMM). Also informed by a btsnoop-based MTW4 analysis (sandrolucy). Reference implementation: `~/Developer/smart-connect-bt-audio/lib/ble/`.

## Key structural facts

- Vendor ID: `0x0495` (Qualcomm GAIA, used by Sennheiser).
- Command numbering = GAIA V3 bit packing: bits 15-9 feature, bits 8-7 packet type (`00` command, `01` notification, `10` response, `11` error), bits 6-0 command id. So request `0x1a00` → response `0x1b00`; error = response id | `0x0080` (e.g. `0x1b80`).
- Payloads are big-endian where multi-byte.
- Reference projects control over **Bluetooth Classic RFCOMM** (SDP UUID `a2129ff3-081b-4c45-8afe-469d9c4842ec`) — unreachable from browsers. Web Bluetooth path is GAIA over BLE GATT; BLE framing is not publicly documented, hence runtime probing of both candidate framings.

## Framings

- **SPP/RFCOMM style:** `FF 03|04 lenHi lenLo <vendorId:2> <command:2> <payload>` — length counts payload only (total frame = 8 + len). Captured example (battery query): `FF 03 00 00 04 95 06 03`.
- **GAIA v3 GATT style:** `[version(10)<<6 | flags] [sequence] [lenHi] [lenLo] <GAIA packet>` — unfragmented flags = START|END = `0101` → header byte `0x85` for version `10`. Same 8+len total. BLE services to whitelist: `fcd7` (GAIA), `fcf7`, `fcfe` (Sennheiser TWS), `fdff`; data characteristics `f6ce` (v3/v2) and `f6cd` (v1).

## Command table (verified)

| Function | Request | Response | Payload |
| --- | --- | --- | --- |
| Battery | `0x0603` | `0x0703` | `[0..100]` |
| Sound mode get/set | `0x0804` / `0x0803` | `0x0904` / `0x0903` | `0` off, `1` equalizer, `2` podcast, `3` sound personalization |
| BT compatibility mode | `0x0406` | `0x0506` | `0` better audio, `1` better compatibility |
| Sound personalization state | `0x2001` | `0x2101` | `0` not param, `1` calibrating, `2` calibrated, `3` inhibited |
| ANC sub-mode set | `0x1a00` | `0x1b00` | `[mode, state]` — modes: `1` anti-wind, `2` comfort, `3` adaptive; state 0/1 |
| ANC modes get | `0x1a01` | `0x1b01` | repeated `[mode, state]` pairs |
| Transparency level | `0x1a02` / `0x1a03` | `0x1b02` / `0x1b03` | `0..100` (0 = max ANC, 100 = max transparency) |
| ANC enable | `0x1a04` / `0x1a05` | `0x1b04` / `0x1b05` | bool |
| Transparent hearing | `0x1804` / `0x1805` | `0x1904` / `0x1905` | bool |
| EQ config | `0x1000` | `0x1100` | `[bandCount, minGainTenths(s8), maxGainTenths(s8)]` (tenths of dB) |
| EQ band set/get | `0x1001` / `0x1002` | `0x1101` / `0x1102` | `[band, gainTenths(s8)]`; GET payload `[band]`, response may echo band |
| Bass boost | `0x1008` / `0x1009` | `0x1108` / `0x1109` | bool |
| Multipoint list size | `0x1400` | `0x1500` | `[count:2B BE]` |
| Device info | `0x1401` | `0x1501` | `[index, priority, connected, name...NUL]` |
| Connect/disconnect peer | `0x1402` / `0x1403` | `0x1502` / `0x1503` | |
| Own index / max connections | `0x1407` / `0x1409` | `0x1507` / `0x1509` | |

## Verified control sequences

- **Manual max ANC:** TH off (`1804:00`) → ANC on (`1a04:01`) → adaptive off (`1a00:03 00`) → balance `1a02:00`.
- **Adaptive ANC:** TH off → ANC on → `1a00:03 01`.
- **Transparency:** TH off → adaptive off (`1a00:03 00`) → `1a02:<level>` (per btsnoop analysis, level>0 acts as transparency on).
- **Off:** TH off → ANC off (`1a04:00`).
- Every write sequence is followed by fresh reads (battery, ANC enabled, ANC modes, level). SET ACKs (`0x1b04`, `0x1904`) carry **no state semantics** — never infer state from them.

## Behavioral pitfalls from captures

- ANC and transparency pushes are **not guaranteed to be paired** (transparency changes may not push an ANC-state notification) — maintain the two states independently.
- `getTransparentHearing`-style GET responses can return a level value rather than a bool on some firmware — trust notifications and read-backs, validate ranges defensively.
- TWS in-case: RFCOMM refused while docked (Classic path); MTW4 analysis also showed a resident BLE connection can interfere with second-bud handshake — keep sessions short-lived and user-driven in browser context.
- Official app holds the control channel: close the vendor app before connecting from the web app.
