# Tauri desktop shell for Classic-RFCOMM GAIA devices (Windows)

Session-proved continuation of the Web Bluetooth path (smart-connect-bt-audio, Sept 2026).
Read this when the browser path is closed (device control plane is Bluetooth Classic only)
and a Tauri desktop app is the chosen escape hatch.

## Architecture that worked

- Same Next.js UI, same `lib/ble/` protocol layer (gaia.ts, sennheiser.ts, gaia-framing.ts).
- Add a **transport abstraction** (`transport.ts`) with two impls: `web-bluetooth` (existing
  GaiaClient, endpoint+framing probing) and `tauri-rfcomm` (fixed `spp-style` framing, no probing).
- React hook checks `isTauri()` (presence of `window.__TAURI_INTERNALS__`) and swaps transports.
  Desktop connect = `listGaiaDevices()` → `gaia_connect` → Rust emits `gaia-rx`/`gaia-closed`
  events (byte arrays) → same resynchronizing RX parser as BLE.
- Rust owns the socket; frontend never touches Bluetooth in desktop mode.

## Windows transport (windows crate 0.61, WinRT)

GAIA SDP UUID: `a2129ff3-081b-4c45-8afe-469d9c4842ec`. Build GUID via
`GUID::from_u128(0xa2129ff3_081b_4c45_8afe_469d9c4842ec)` (FromUuid takes GUID **by value**).

Verified API surface (docs.rs 404s for these feature-gated modules — check crate source, see below):

- `RfcommDeviceService::GetDeviceSelector(&RfcommServiceId)` → AQS string, service-filtered.
  There is **no** `GetDeviceSelectorForCachedInstancesForServiceId` in the crate.
- `DeviceInformation::FindAllAsyncAqsFilter(&HSTRING)` → enumerate paired instances.
- `RfcommDeviceService::FromIdAsync(&HSTRING)` → resolves directly (no Option unwrap).
- Socket params live on the service: `service.ConnectionHostName()` + `service.ConnectionServiceName()`
  (**not** `ServiceName()`). `service.Device()` is already the `BluetoothDevice` (call `.Name()` on it).
- `StreamSocket::ConnectAsync(&HostName, &HSTRING)` → `IAsyncAction`.
- Property **setters are `SetXxx`**: `reader.SetInputStreamOptions(InputStreamOptions::Partial)`,
  never `InputStreamOptions(value)` (that's the getter).
- WinRT async calls return `Result<IAsyncOperation<T>>` — **two error layers**:
  `.map_err(..)?.get()?` or `.map_err(..).and_then(|op| op.get())`. Calling `.get()` directly
  on the Result is a compile error.
- WinRT interface wrappers are `!Send` (`NonNull<c_void>` inside `IUnknown`). For single-owner
  objects (input stream → exactly one reader thread; DataWriter behind a Mutex) use:

  ```rust
  struct SendWrapper<T>(T);
  unsafe impl<T> Send for SendWrapper<T> {}
  ```

  **Rust 2021 disjoint-capture trap:** inside `thread::spawn(move || { ... input.0 ... })`
  the closure captures the FIELD (`IInputStream`), not the wrapper → still !Send. Fix: cross a
  function boundary so the whole wrapper moves: `thread::spawn(move || reader_loop(app, cancel, input))`
  where `reader_loop(..., input: SendWrapper<IInputStream>)`, then destructure inside (`let SendWrapper(input) = input;`).
- Reader loop: `DataReader::CreateDataReader(&input)`, `SetInputStreamOptions(Partial)`,
  `LoadAsync(buf.len())` → `n == 0` means closed, `ReadBytes(&mut buf[..n])`, emit `gaia-rx` per chunk.
- Cargo.toml: windows dep is `[target.'cfg(windows)'.dependencies]` with features
  `Devices_Bluetooth`, `Devices_Bluetooth_Rfcomm`, `Devices_Enumeration`, `Foundation`,
  `Networking`, `Networking_Sockets`, `Storage`, `Storage_Streams`. Ship a `gaia_stub.rs`
  (include!-based `#[cfg]` swap) so the crate compiles on Linux/macOS.

## Checking Windows-only Rust from a Linux box (huge time-saver)

1. `rustup target add x86_64-pc-windows-msvc`
2. `cargo check --target x86_64-pc-windows-msvc` — compiles (no linking), so ALL
   windows-crate API errors surface locally, before any CI round-trip.
3. tauri-build's build script then panics: `tauri-winres ... NotAttempted("llvm-rc")` →
   `sudo apt-get install llvm` (provides `/usr/bin/llvm-rc`) and re-run. That's the only blocker;
   after it, `Finished` means the Windows side is compile-clean.

## Verifying crate APIs without docs.rs (404s on feature-gated modules)

Crate downloads are **gzipped tarballs** (not zip): fetch
`https://static.crates.io/crates/<name>/<name>-<version>.crate`, open with
`tarfile.open(mode="r:gz")`, then regex `pub fn (\w+)\(([^)]*)\)` inside the module
`src/Windows/Devices/Bluetooth/Rfcomm/mod.rs` etc. Pin the exact version from `Cargo.lock`
(or crates.io `/versions`) — patch versions differ (0.61.1 vs 0.61.3 bit us).
Note: `windows` crate resolves minor-version-up within the semver range (0.61.3 for "0.61"),
so verify against the LOCKED version CI will use, and commit `src-tauri/Cargo.lock`.

## CI: GitHub Actions Windows build (no gh auth, no API token)

- `tauri-apps/tauri-action@v0` works, but its failure annotation is just "exit code 1".
- Unauthenticated `api.github.com` **job logs are 403 even for public repos**, and check-run
  `output.summary` came back empty. What DOES work without auth:
  1. **The run/job web pages render annotations server-side**: fetch
     `https://github.com/<owner>/<repo>/actions/runs/<id>/job/<jobId>` and regex the HTML
     (strip tags, look between "Annotations" and the footer). Use to read failure messages.
  2. **Emit errors yourself**: replace tauri-action with inline steps —
     `npx tauri build --target x86_64-pc-windows-msvc 2>&1 | Tee-Object tauri-build.log`,
     and on `$LASTEXITCODE -ne 0` print each tail line with `::error::<line>` (becomes an
     annotation visible on the run page) and append to `$env:GITHUB_STEP_SUMMARY`.
  3. Job success/failure is plain text on the job page ("succeeded ... in 7m 18s").
  Careful reading the run-LIST page: adjacent older failed runs also carry `x-circle-fill`
  icons — confirm on the job page, not the list.
- `npm ci` + steps need: Node 22, `dtolnay/rust-toolchain@stable`, `swatinem/rust-cache@v2`
  with `workspaces: src-tauri`, artifact upload from
  `src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/*.exe`.
- **API rate limit**: unauthenticated api.github.com is 60/hr per IP — CI polling loops burn
  it fast. Poll sparsely or scrape the web pages above.

## CI pitfalls that cost round-trips this session

- **`VAR=1 cmd` POSIX env syntax fails on Windows runners.** Use `cross-env` in the npm script.
- **`npx tauri` must resolve**: add `@tauri-apps/cli` as a real devDependency (npx fetch failed in CI).
- **Workflow `paths:` filters silently skip runs** — a package.json-only commit did not
  trigger `paths: [src-tauri/**, app/**, lib/**]`. Symptom: no run exists for the SHA at all
  (check `?head_sha=`). Fix: drop the path filter, or always touch a watched path.
- Workflow trigger shape: keep `on: push: branches: [main]` + `workflow_dispatch`; empty
  commits also dispatch it if you need a re-run.
- Next.js side: `build:export` script gated by env (`cross-env TAURI_BUILD=1 next build`),
  `next.config.ts` adds `output: 'export'` only when that env is set — so Vercel keeps the
  normal server build and Tauri gets `out/`. Verify both builds locally before pushing.

## Runtime expectations (Windows, user-facing)

- Headphones must be **OS-paired in Windows Bluetooth settings** first (app enumerates cached
  RFCOMM services; it cannot pair).
- Only one app can hold the GAIA RFCOMM link — close the official Sennheiser Smart Control.
- Headphones out of the case; first connect may trigger a Windows consent prompt.
- Connect error surface should mention the Smart-Control-holds-the-link case.
