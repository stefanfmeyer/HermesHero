# Common JS / ESM / Async Gotchas

Concrete, recurring foot-guns hit while building Node.js + ESM projects. Each entry is one bug pattern, what it looks like, and the minimal fix. Read this before refactoring sync → async, before adding `await` to anything, and before wiring up a new module loader.

## 1. `await` in a non-`async` function (ESM, the silent killer)

The first line of a function decides whether `await` is legal. If you add an `await` to a body, the function declaration must change too — and every caller (including inline arrows) must follow.

```js
// BEFORE — fine while sync
function runJob(job, buffer, filename, mimetype) {
  ...
  if (parsedRecords.length === 0) {
    records = [await pickSampleRecord()];  // <-- SyntaxError: Unexpected reserved word
  }
}

// AFTER — make it async, and any caller that doesn't already await needs updating
async function runJob(job, buffer, filename, mimetype, agencyTemplate = null) {
  ...
  if (parsedRecords.length === 0) {
    records = [await pickSampleRecord()];
  }
}
```

**Also bites Express route handlers:**

```js
// WRONG — async work in a sync route handler
router.post("/", (req, res) => {
  const tmplResult = await db.templates.find({ agencyId });  // SyntaxError
});

// RIGHT — handler signature must change too
router.post("/", async (req, res) => {
  const tmplResult = await db.templates.find({ agencyId });
});
```

**The "split-and-await" refactor pattern** that avoids needing a top-level `async` for a function that *sometimes* awaits: extract the awaiting part into its own helper, and call it from the sync caller.

```js
// Sync function stays sync, but only because we extracted the async work.
function runJob(...) {
  // ...sync stuff...
  return runJobFinish(job, parsedRecords, filename, mock);  // async helper
}

async function runJobFinish(job, parsedRecords, filename, mock) {
  // ...async stuff that does the pickSampleRecord + setStage + write result...
}
```

`runJob` doesn't need to know `runJobFinish` is async — JS auto-unwraps the returned promise when the caller awaits it. If the caller is fire-and-forget (no `await`), the promise just runs in the background. This is the lowest-impact way to introduce `await` into a previously sync flow.

## 2. PG / database calls require pool-as-promise, not sync

A pool-returning helper that reads env vars and constructs a client **must return a promise**, because the dynamic `import("pg")` is async. Every caller needs `await` on the pool helper.

```js
// WRONG — sync function that "uses" await internally
function getPool() {
  if (_pool) return _pool;
  return loadPg().then(({ Pool }) => {  // returns a promise
    _pool = new Pool({ ... });
    return _pool;
  });
}

// Then every caller writes `const pool = getPool()` and the query is broken
// because `pool` is a Promise, not a Pool.
```

**Fix:** every caller does `const pool = await getPool();`. Lint will not catch this for you — the runtime silently tries to call `pool.query(...)` on a Promise and explodes with `TypeError: pool.query is not a function`.

**Pattern check:** any helper that uses dynamic `import()`, `fs.promises`, `fetch`, or any async work should return a Promise. Search for `getXxx()` calls and confirm each one is `await`ed.

## 3. `process.env` is not available in browser / Vite

In a Vite-built React app, `process.env.X` is `undefined` at build time. Use `import.meta.env.VITE_X` instead, and prefix the variable with `VITE_` so Vite exposes it to the client bundle.

```js
// WRONG — silently undefined in production build
const API_KEY = process.env.VITE_API_KEY;

// RIGHT — Vite replaces this at build time
const API_KEY = import.meta.env.VITE_API_KEY;
```

The rule: anything that needs to land in the client bundle starts with `VITE_`. Anything else stays server-side.

## 4. PDF.js worker bundling (Vite + ESM)

PDF.js needs its worker file loaded as a separate script. In Vite, the `?url` suffix on a deep import gives you a stable worker URL that survives bundling:

```js
const pdfjsLib = await import("pdfjs-dist");
try {
  const workerUrl = (await import("pdfjs-dist/build/pdf.worker.min.mjs?url")).default;
  pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;
} catch {
  // Fallback if ?url isn't supported (some build setups)
  pdfjsLib.GlobalWorkerOptions.workerSrc = "https://unpkg.com/pdfjs-dist@<version>/build/pdf.worker.min.mjs";
}
```

**Lazy-load the whole library** so a non-PDF IO never pays the 365kB JS cost. Dynamic `import()` is your friend.

**Always cancel in-flight renders** when the user navigates pages. Two `page.render()` calls on the same canvas will corrupt the output; the second one must be `.cancel()`-ed before the third starts.

```js
if (renderTaskRef.current) {
  renderTaskRef.current.cancel();
}
const renderTask = page.render({ canvasContext: ctx, viewport });
renderTaskRef.current = renderTask;
await renderTask.promise;  // may throw RenderingCancelledException — that's fine
```

## 5. Duplicate object keys via spread

Easy to write, ESLint catches it as `no-dupe-keys`:

```js
// WRONG
const next = {
  id: newId,
  ...record,    // record might have its own id
  id: newId,    // this is the one that "wins" but the lint error remains
};
```

**Fix:** put the spread first, then the explicit override.

```js
const next = {
  ...record,
  id: newId,
};
```

If you genuinely meant the spread to overwrite (e.g. you want `id` to be the freshly-minted one), this is the cleanest form.

## 6. `case` blocks with `const`/`let` need braces

ESLint's `no-case-declarations` rule blocks lexical declarations directly inside `case` arms. Wrap the case body in `{}`.

```js
// WRONG
case "modifying":
  const li = diffResult.lineItemChanges || {};  // <-- ESLint error
  break;

// RIGHT
case "modifying": {
  const li = diffResult.lineItemChanges || {};
  break;
}
```

The other case arms in the same `switch` can stay brace-less, or you can brace them all for consistency.

## 7. `Object.prototype.hasOwnProperty` direct call

ESLint's `no-prototype-builtins` blocks `obj.hasOwnProperty(key)` because `obj` might shadow the prototype method. Use the safe form:

```js
// WRONG
if (!ORDER.hasOwnProperty(res.type)) { ... }

// RIGHT
if (!Object.prototype.hasOwnProperty.call(ORDER, res.type)) { ... }
```

For a known-safe object (a plain literal you defined), you can also `Object.create(null)` the source, but the prototype form is universal.

## 8. Express handler that needs to await before responding

If the route handler isn't `async` but the *implementation* of the work needs async, you'll get a race condition where `res.json()` runs before the work completes. Make the handler `async` and `await` the work, even if you're not using the result.

```js
// RACY — res.json() runs immediately, runJob() runs in background
router.post("/", (req, res) => {
  runJob(job, buffer, filename);  // returns a promise we drop on the floor
  res.status(202).json({ data: { jobId, ... } });
});

// OK as long as runJob doesn't need to complete before res.json
// is acceptable (fire-and-forget jobs).
```

This is actually **fine** for a job-style API (202 Accepted) where you want to return immediately and let the work continue. It's only wrong when the response *depends* on the work completing.

## 9. Foreground terminal commands that look like servers

Vite, webpack-dev-server, and any long-lived dev server will be flagged as "long-lived" by the runtime even when invoked with `build` (not `dev`). The runtime doesn't parse the command — it just notices the process didn't exit.

**Workaround for `vite build`:**

```bash
# Set background=true, then poll/wait for the result with the process tool.
terminal(command="cd pkg && npx vite build 2>&1 | tail -15", background=true, timeout=90)
process(action='wait', session_id=<id>, timeout=90)
```

Same applies to `tsc --watch`, `webpack --watch`, `pytest -x` (sometimes), and any command that watches for file changes.

## 10. Duplicate dependency entries in `package.json`

When you add a new dep via `patch`, the change may be applied before you also update `package-lock.json`. The runtime's `npm install --workspace=<pkg>` will then resolve a different version than what's pinned. Always:

1. Edit `package.json` to add the dep + version range
2. Run `npm install --workspace=<pkg>` to update `package-lock.json`
3. Commit both files together

If you commit only the `package.json` change, the next CI run that does a fresh `npm ci` will fail to find the dep.

## Summary Cheat-Sheet

| Symptom | Cause | Fix |
|---------|-------|-----|
| `SyntaxError: Unexpected reserved word` (await) | Forgot `async` on a function you added `await` to | Make function `async`; check all callers |
| `TypeError: pool.query is not a function` | Forgot `await` on a Promise-returning helper | `const pool = await getPool();` |
| Variable is `undefined` in production React build | Used `process.env.X` instead of `import.meta.env.VITE_X` | Rename, prefix with `VITE_`, use `import.meta.env` |
| PDF.js renders corrupt output on rapid page changes | Didn't cancel in-flight render | `renderTask.cancel()` before next render |
| ESLint `no-dupe-keys` | Spread + same key set twice | Put spread first, then override |
| ESLint `no-case-declarations` | `const` directly in `case` arm | Wrap in `{}` |
| `cd X && ...` fails in PowerShell | Cross-platform shell incompatibility | Use Node `spawn` with `cwd` (see `cross-platform-npm-scripts` skill) |
| "command appears to be a long-lived server" | Runtime misreads `vite build` / `tsc --watch` | Run in `background=true` mode, then `process(action='wait')` |
