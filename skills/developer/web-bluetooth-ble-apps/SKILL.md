---
name: web-bluetooth-ble-apps
description: Build browser apps that control BLE hardware (headphones, earbuds, wearables) over Web Bluetooth — GATT transports, dual-framing probing for undocumented protocols, reverse-engineered command tables (GAIA/Sennheiser), TypeScript typings and serialization pitfalls, and no-hardware protocol verification. Includes the Tauri/WinRT-RFCOMM desktop-shell escape hatch for devices whose control plane is Bluetooth Classic only.
trigger: Building or extending a web app that talks to Bluetooth/BLE hardware from the browser — Web Bluetooth API, GATT services/characteristics, vendor control protocols (GAIA, Sennheiser/Sonova, Qualcomm), or porting a native (RFCOMM) device controller to a web app. Also when a Web Bluetooth app proves the device's control plane is Classic-only and a Tauri desktop shell (WinRT RFCOMM via the windows crate) is the next step.
tags: [web-bluetooth, ble, gatt, hardware, typescript, nextjs, protocol]
---

# Web Bluetooth / BLE Hardware Control Apps

Class playbook for browser apps that connect to BLE peripherals (worked example: an unofficial Sennheiser BLE control app; Next.js App Router + monochrome theme).

## Hard constraints (know these before writing code)

1. **Web Bluetooth speaks BLE GATT only.** It cannot reach Bluetooth Classic RFCOMM/SPP. Many vendor control apps (including Sennheiser's official app and most RE projects) use Classic RFCOMM — those codebases give you the *application-layer* protocol but NOT a usable transport. The browser path must ride the device's BLE GATT control service, which may be less documented. State this honestly in the README instead of pretending full parity.
2. **Chrome/Edge/Opera desktop only.** No Firefox/Safari. Secure context required: HTTPS or localhost. Gate the UI on `!!navigator.bluetooth` and show an explanatory banner when absent.
   - **"Web Bluetooth API globally disabled"** — `requestDevice()` rejects with this exact message when the browser ships Web Bluetooth switched OFF at the flags level (Brave default; common on Linux Chromium builds). Map this error to concrete user steps in the UI instead of surfacing the raw message: enable `chrome://flags` → Web Bluetooth (or `edge://flags`, Brave `brave://flags/#enable-web-bluetooth`) and relaunch. Also map "User cancelled/user denied" to a calm "picker closed without selecting" message. Error-message mapping for `requestDevice()` rejections belongs in the client's connect path.
3. **`lib.dom.d.ts` has no Web Bluetooth types.** Ship your own minimal `web-bluetooth.d.ts` (see `references/` pattern in the repo). Do not fight it with `any` everywhere.
4. **Device must be OS-paired first.** Web Bluetooth picks among already-paired/advertised devices; the app cannot pair at the OS level. Say so in the UI copy.
5. **When the BLE probe fails, the verdict may be "Classic-only" — and that's terminal for browsers.** If the full endpoint×framing probe (see below) gets no GAIA answer on any characteristic, don't iterate on BLE guesses forever: the device's control plane may be Bluetooth Classic RFCOMM only (verified for MOMENTUM 4: BLE inventory is only `180a`/`180f`/`fcfe`, all fcfe endpoints silent to GAIA; BLE stays useful for battery via `180f/2a19`). Report the verdict honestly, then the realistic path is a **Tauri desktop shell with a Rust WinRT RFCOMM transport** — see `references/tauri-rfcomm-windows.md` for the full architecture (transport abstraction beside Web Bluetooth, windows-crate API map, Linux cross-check of Windows-only code, GitHub Actions Windows installer pipeline). Keep the web app deployed: it still serves BLE-capable models and battery reads.

## Transport design for undocumented protocols

The winning pattern (verified this class of project):

- **Endpoint × framing probe, not single-endpoint probe.** First contact with a device whose BLE control surface is unknown: collect ALL candidate endpoints (classic GAIA data characteristics **plus** every write/notify/indicate-capable characteristic of vendor-proprietary services found in the inventory), then for each candidate: `startNotifications()` first, send a harmless query (battery) under framing A then framing B, and the first endpoint that answers a valid response settles endpoint AND framing in one step. Clean up (removeEventListener + stopNotifications) on every failed candidate. Never probe framing on one hardcoded endpoint — the endpoint itself is usually the unknown (MOMENTUM 4 ships its vendor surface under `fcfe{6333xxxx}`, not GAIA's `f6cd/f6ce`).
  - SPP-style frame: `FF 03|04 lenHi lenLo <vendorId:2><cmd:2><payload>` (len = payload only; full frame = 8 + len).
  - GAIA v3 GATT frame: `ver/flags seq lenHi lenLo <vendorId:2><cmd:2><payload>` — ver/flags = `(version<<6)|flags`, unfragmented = start|end (e.g. `0x85` for v3). Same 8+len math.
- **Byte-level protocol console in the UI.** Log every TX/RX frame as hex plus decode notes. For undocumented hardware this is not a debug nicety — it is how first-contact with a new model gets diagnosed, and how community reports become support. Include a "paste this log into an issue" hint. Put the compact service inventory **into the thrown error message too** (users screenshot the banner, not the console).
- **Resynchronizing RX parser.** Chunks arrive fragmented and concatenated. Keep a `number[]` buffer; scan for sync markers, decode complete frames, splice consumed bytes, keep the remainder. Never assume one notification = one packet.
- **One outstanding request at a time.** Chain exchanges through a promise queue; per-request timeout; match responses by exact response-command id; treat `responseId | 0x0080` as the GAIA error form.
- **Read back after every write.** UI state must come from device queries, never from optimistic writes. SET ACKs are often payload-less and carry no state semantics.
- **requestDevice filters:** filter by the control service UUID plus `namePrefix` entries for the vendor's product lines, with `optionalServices` including the control service (Chrome refuses services not declared there).

## Vendor protocol knowledge (GAIA family)

Qualcomm GAIA underlies many headphones (Sennheiser, Moondrop, etc.). Command word packing: bits 15-9 feature, bits 8-7 packet type (00 command / 01 notification / 10 response / 11 error), bits 6-0 id. Responses are typically `cmd | 0x0100`. Vendor id for Sennheiser GAIA: `0x0495`.

Full Sennheiser command table (ANC, adaptive, transparency, EQ, bass boost, sound modes, battery) and framing byte maps: see `references/gaia-sennheiser-protocol.md`.

Upstream MIT-licensed RE references worth citing in code comments and README: `Zhengyang-Liu/m4-companion` (macOS RFCOMM), `ladybridgett/openpmv` (Android RFCOMM), `sandrolucy/Sennheiser-MOMENTUM-TW4-widget-gaia-protocol` (btsnoop captures incl. BLE note), `pubglite55/SpaceTravel-Protocol` (GAIA V3 feature map). Verify command IDs against at least two independent projects before trusting one.

## TypeScript / Web API pitfalls

- `writeValue`/`writeValueWithResponse` reject `Uint8Array<ArrayBufferLike>` (type error vs `BufferSource`) on newer TS libs. Fix: copy bytes into a fresh `Uint8Array` and pass `copy.buffer`.
- Spreading/iterating `Uint8Array` (`[...u8]`) fails below ES2015 target — Next 15 defaults to ES2017 so it's fine in-app, but standalone `tsc` runs may differ; prefer `Array.from(u8)` or index loops in protocol files.
- **Chrome keeps `characteristic.properties` flags on the prototype** — `Object.keys(char.properties)` returns `[]` (inventory logs full of empty `[]`). Enumerate the known property names explicitly instead: `['broadcast','read','writeWithoutResponse','write','notify','indicate','authenticatedSignedWrites','reliableWrite','writableAuxiliaries'].filter(n => p[n] === true)`.
- Never call `writeValue` on a characteristic that only supports write-without-response (and vice versa) — check `properties` and degrade gracefully.
- React state from notifications: apply updates in a single `onNotification` handler via one reducer-style updater; keep the raw `GaiaClient` in a `useRef`, never in state.

## Device picker pitfalls

- **"Headphones don't show up" in the Chrome picker** is almost always the site's own filters (name prefixes / service filter). Idle headphones also stop advertising. Ship a **"Scan all BLE devices"** secondary button (`{ acceptAllDevices: true, optionalServices: [...] }`) as a fallback, and tell the user to wake the headphones (tap a button) before scanning.
- The device must already be OS-paired; Web Bluetooth only picks among advertised/paired devices. Keep that in UI copy, not just the README.

## Next.js interop pitfalls

- **Dev server and `next build` share `.next`.** Running a production build while `next dev` is serving corrupts the dev server (blank pages, HTTP 500, ENOENT on `_buildManifest.js` tmp files). One at a time: kill dev → `next build` → `next start`, or restart dev after building. Do NOT `rm -rf .next` while dev runs.
- `npm run start` fails with "Could not find a production build" if `.next` was deleted after the last build — rebuild first.
- Turbopack multi-lockfile warning: point `turbopack.root` at the project in `next.config.ts`.
- Scaffolding into an existing (possibly empty) GitHub repo: `create-next-app` needs a target dir and answers prompts interactively — pipe `printf 'No\n'` for the Turbopack question, use `--skip-install --disable-git --no-eslint --no-tailwind --app --ts --no-src-dir`, generate into `scaffold/` then move files into the repo root and write `package.json` manually (correct name/description).

## Verification without hardware

Protocol logic is testable with plain TypeScript + `tsx`, no device needed:

1. Assert TX frame bytes against byte-captured traffic from RE write-ups (e.g. `FF 03 00 00 04 95 06 03` for a GAIA battery query).
2. Round-trip: frame → decodeStream → compare command/vendor/payload.
3. Feed known RX captures (including ones split across two notifications) through the parser.
4. Unit-test every payload parser's happy path AND rejection path (bad lengths, out-of-range values, odd-length payloads).
5. Wire as `scripts/verify-protocol.ts`, run `npx tsx scripts/verify-protocol.ts`, keep `next build` as the type gate (standalone tsc misses tsconfig paths/plugins).

**Push discipline (bit me this session):** NEVER chain `npm run build 2>&1 | grep -E "✓|..."` into `&& git commit && git push` — grep succeeds on its matched pattern, so the push fired while the build was still FAILING (Type error). Verify builds with an explicit status check on the *build command's exit code* (`npm run build && git push` unconditionally chains only success; or check `git log`/deploy status after). A broken commit on `main` of an auto-deploying repo goes live to production within a minute.

## Unofficial hardware app conventions (the user's requirements)

- README and app footer MUST carry the trademark/warranty disclaimer (vendor + chip owner, "not affiliated / not endorsed", marks used only to identify compatible hardware). the user asked for this explicitly — never omit.
  - **Copy-paste pitfall (the user corrected this):** when adapting the disclaimer from the RE reference project, replace the SUBJECT. Shipping "OpenMomentum is independent..." verbatim in your app's README is wrong — it must read "This app is independent and is not affiliated with...". Check the first noun of the disclaimer before pushing.
- No accounts, no telemetry, nothing leaves the machine; profiles live in localStorage.
- Never ship firmware-update commands in unofficial tools (firmware brick risk; all RE references refuse it too).
- State model discipline: maintain related toggles (ANC on/off, transparency level, transparent hearing) as independent flags — devices do not push consistent pairs; one state variable produces stuck UIs.

## Deploying these apps (Vercel, no CLI auth)

- the user's Vercel has **GitHub integration on the personal account**: pushing to `main` deploys `https://<repo-name>.vercel.app/` automatically with zero CLI setup. If the local `vercel` CLI is unauthenticated (empty token in `~/.local/share/com.vercel.cli/auth.json`) and no `VERCEL_TOKEN` exists anywhere, do NOT block on credentials or paste a token into chat — just push, then verify the deployment via the **public GitHub deployments API** (no auth needed for public repos): `GET /api.github.com/repos/<owner>/<repo>/deployments` → check latest deployment SHA matches your push and its statuses state is `success`. Wait ~45s after push before checking.
- First real-hardware test happens on the Vercel HTTPS URL (secure context works there; `localhost` also works). Expect the "globally disabled" browser-flag error on first connect attempt (see constraint 2 above) — have the flags fix ready in your reply.

## Repo reference

Working exemplar: `~/Developer/smart-connect-bt-audio` (github yourusername/smart-connect-bt-audio, personal key `id_ed25519_personal`). Protocol layer `lib/ble/` (gaia.ts, gaia-framing.ts, gaia-client.ts, sennheiser.ts, use-headphones.ts), UI `app/page.tsx`, verification `scripts/verify-protocol.ts`.

## Files

- `references/gaia-sennheiser-protocol.md` — full GAIA/Sennheiser command table, framing byte maps, payload encodings, control sequences, state-machine lessons, BLE service UUIDs.
- `references/tauri-rfcomm-windows.md` — Tauri desktop shell for Classic-only devices: transport abstraction, windows-crate 0.61 RFCOMM API map (verified signatures), Send-wrapper pattern, Linux `cargo check --target x86_64-pc-windows-msvc` setup (llvm-rc), crates.io source inspection trick, GitHub Actions Windows installer pipeline + unauthenticated CI log/debug techniques.
