---
name: web-bluetooth-hardware-control
description: Build browser apps that control Bluetooth hardware (headphones, earbuds, BLE peripherals) via Web Bluetooth. Covers the Chrome optionalServices whitelist trap, GAIA protocol (Qualcomm/Sennheiser/ANC headphones), transport probing for undocumented protocols, and hydration-safe capability UI.
trigger: User asks for browser-based control of Bluetooth devices — Web Bluetooth, BLE GATT, GAIA protocol, Sennheiser/Qualcomm headphone control, ANC/EQ over Bluetooth from a web app, or reports "No Services found in device" / React #418 in a Web Bluetooth app.
tags: [web-bluetooth, ble, gatt, gaia, sennheiser, bluetooth, hardware, browser-apis]
---

# Web Bluetooth Hardware Control

Class-level patterns for browser apps that talk to Bluetooth hardware. Reference implementation: `~/Developer/smart-connect-bt-audio` (Next.js, Sennheiser control over GAIA — protocol layer in `lib/ble/`, protocol notes in `references/gaia-sennheiser.md`).

## The Chrome `optionalServices` Whitelist Trap (most important)

Chrome **hides every BLE service not pre-declared** in `requestDevice({ optionalServices: [...] })`. If the device's control service UUID is missing from the list, `getPrimaryServices()` returns nothing and Chrome reports **"No Services found in device"** — which looks like the headphones have no services but is actually the browser filtering them.

**Rules:**
1. Whitelist the full family of candidate service UUIDs, not just the one you hope for. For Qualcomm/Sennheiser hardware: `0xfcd7` (GAIA), `0xfcf7`, `0xfcfe` (Sennheiser TWS), `0xfdff`, plus `battery_service` and `device_information`.
2. On discovery failure, enumerate and log **every visible service + its characteristics with properties** (`write|writeWithoutResponse|notify`) to an on-screen console before erroring. The inventory tells you exactly which UUID to add.
3. `navigator.bluetooth.getAvailability()` is unreliable for feature detection — test `!!navigator.bluetooth` and handle runtime errors from `requestDevice()` itself.

## Error Messages to Map (Chrome throws these)

| Chrome error | Meaning | User fix |
| --- | --- | --- |
| `Web Bluetooth API globally disabled` | Browser-level flag off (Brave default, some Linux builds) | `chrome://flags` → enable Web Bluetooth → relaunch |
| `User cancelled the requestDevice() chooser` | Picker dismissed | Retry |
| `No Services found in device` | optionalServices whitelist gap (see above) | App-side fix: add UUID |
| `GATT Server is disconnected` | Device dropped link / went out of range | Reconnect, keep official vendor app closed |

Surface these as actionable copy, never raw `e.message`.

## Undocumented-Protocol Strategy

When the device protocol is reverse-engineered (not officially documented):

1. **Mine existing RE projects first** (GitHub repo search beats web search; MIT-licensed reference implementations give byte-exact command tables). For Sennheiser GAIA: m4-companion (macOS/RFCOMM) and OpenMomentum (Android/RFCOMM).
2. **Know the transport ceiling:** Web Bluetooth = BLE GATT only. If the RE projects used Bluetooth Classic RFCOMM (SPP), their *framing* won't apply but their *command layer* will (GAIA commands are transport-independent).
3. **Probe framings at runtime:** implement every candidate framing, probe with a harmless read (battery query) at connect, adopt whichever yields a valid packet. Log every TX/RX byte to an on-screen console — this is how you debug with zero hardware access.
4. **Serialize strictly:** one outstanding request at a time, bounded timeouts, validate vendor ID + response ID + payload length, read state back after every write sequence. Never send unknown/destructive commands; keep firmware updates out of scope.

## React/Next.js Integration

- Capability UI (banners, disabled connect buttons driven by `navigator.bluetooth`) must be **gated behind a `mounted` flag**: `const [mounted, setMounted] = useState(false); useEffect(() => setMounted(true), []); const supported = mounted && !!navigator.bluetooth;`. Server and client disagree on browser APIs; reading them during render trips React hydration error #418 (`args[]=HTML`), which only shows up minified in production. Rule: any boolean derived from a browser API passes through `mounted &&` before influencing rendered output.
- Web Bluetooth requires a **secure context**: HTTPS or localhost. Vercel deploys work out of the box; note the site still fails at `requestDevice` in browsers without the API — handle it in the connect error path.
- Device picker requires a **user gesture** — wire it to a button click, never auto-connect on load.

## Verification Without Hardware

Protocol/codec logic is testable headlessly: round-trip frame→parse tests against byte patterns quoted in RE project captures, plus parser validation tests (malformed payloads, out-of-range values, error-response bit `0x0080`). Keep it as a script (e.g. `npx tsx scripts/verify-protocol.ts`) and run it in CI or pre-push. See `scripts/` in the reference repo for a worked example with 28 checks.

See `references/gaia-sennheiser.md` for the Sennheiser/GAIA protocol specifics (command table, framings, ANC/EQ payload layouts).
