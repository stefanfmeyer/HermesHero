# Cutting helper-call latency in a chat app (quick-reply chips, 2026-09-18)

Worked example: the chips took ~5s to appear after the streamed reply finished.
Repos: `the company/the company-ama` (server, commit `9d1bc13`), `the company/the company-ama-app`
(RN-web client, commit `2e34438`).

## Step 0 — measure the right number, in the right place

The user says "it takes about 5 seconds after the streamed response". Two ways to
measure, and only one answers the question:

- Timing the HTTP call tells you the endpoint's latency.
- Instrumenting the DOM tells you **what the user waits for**, which may include
  client-side sequencing the network timing cannot see. It did here.

The probe sampled, via `page.evaluate` + a polling interval inside the page:
`tLastText` (last time the assistant bubble grew), `tIdle` (turn flipped idle),
`tChips` (first `[data-testid^="suggestion-"]` appeared). The reported number is
`tChips - tLastText`.

Two traps found while writing it:

- **`turnActive` was already true when the probe installed**, giving nonsense
  negative gaps. Don't derive "reply finished" from a turn flag; derive it from
  the last observed growth of the reply text.
- Chip test-ids are `suggestion-<label>`, so a prefix selector
  (`[data-testid^="suggestion-"]`) works while an exact match does not.

## Step 1 — rule out the stream before blaming the helper

Measured the SSE stream directly: first text 3.65s, last text 8.10s, `done`
8.10s. **Last text event → done = 0.01s.** So the reply stream has no dead tail,
and the entire post-reply wait was the suggestions request. Had there been a
multi-second tail here, the fix would have been elsewhere entirely.

This is the check most likely to be skipped, and skipping it means you optimise
the wrong component.

## Step 2 — decompose the endpoint

| component | measured |
|---|---|
| Supabase `getUser` (bearer auth) | 0.37s |
| endpoint with a `<24 char` reply (auth + CORS, short-circuits before the LLM) | 1.12s |
| full endpoint, Sonnet | 3.4-5.0s |

So ~1.1s is fixed per-request overhead and the rest is the model call. That
framing is what makes it obvious that model choice dominates — which is precisely
why it was tempting, and precisely the thing that must not be changed.

## Step 3 — the levers, in order of what actually helped

1. **WHEN the call starts** (biggest win, ~600ms+). It launched only after
   `runStream()` returned, i.e. after the reveal pump drained its backlog — up to
   600ms of cosmetic character animation sitting in the user's critical path for
   a result that only needed the text. Fixed with an `onDone` callback fired at
   the end of the server stream, before the drain.
2. **Token budget.** `maxTokens` plumbed through the provider client; chips
   bounded to 512 instead of inheriting the 4096 chat default.
3. **Parsing.** The brace bug (below) — invisible to latency work, because it
   manifests as missing chips rather than slow ones.

## Result, and the honest attribution

| | before | after (Sonnet restored) |
|---|---|---|
| reply finished → chips | 3.84s / 4.56s | 2.92s / 3.36s |

The model substitution that briefly took it to 1.63-1.87s was reverted at the
owner's instruction (see SKILL.md → "Model choice is a CONSTRAINT"). **Most of
the gain survived the revert**, which is the point worth reporting: the win came
from timing, token budget and parsing — not from swapping the model.

## The parse bug that was silently eating chips

```js
// BROKEN: any prose brace breaks the slice, JSON.parse throws,
// the catch swallows it, and zero chips come back with nothing logged.
const start = cleaned.indexOf("{");
const end = cleaned.lastIndexOf("}");
```

Reproduced deterministically: `"I weighed {x} and here: {json}"` → 0 suggestions.

Fix: try each `{` as a candidate start, find its matching `}` by counting depth
with string-state tracking (so a brace inside a string value doesn't close the
object), return the first candidate that parses to a usable list, bounded to 12
candidates.

Note the naive first fix was **also** wrong: iterating candidate starts while
still slicing to `lastIndexOf("}")` fixed leading prose but broke on a brace
AFTER the JSON (over-extended slice). Depth counting is what handles both.

Mutation-tested: the old implementation returns 0 for the prose-brace,
trailing-brace and brace-in-string cases the new tests cover. A test that passes
against both the old and the new code proves nothing.

## Bugs introduced and caught by measuring

Both looked correct and neither worked:

1. **Stale-state guard.** Replacing the message-length comparison with a
   per-turn counter was necessary because the request now starts mid-stream,
   before the final update is applied.
2. **Double-minted conversation id.** `activeIdRef.current ?? uuid()` computed in
   two places produced two different uuids on a new chat; the chips guard
   rejected its own response, so chips never appeared on a NEW chat (but worked
   on later turns). Fixed by resolving the id once before the stream starts.

After the first of these, the endpoint was returning `200` with 4 chips and the
UI still showed none — which is why the failure was only visible in the DOM
probe, not in any server-side check.

## Verifying the deployed model (not the source)

Reading source proves intent, not what runs. Two false signals:

- The model literal compiles into a webpack **chunk** (`chunks/161.js`), not
  `app/api/suggestions/route.js` — grepping `route.js` gives a false negative.
  Locate the file containing the function and read the compiled body:
  `if(k("anthropic"))return{provider:"anthropic",model:"claude-sonnet-4-5-20250929"}`
- A model-picker list still names the cheaper model, so a bare
  `grep -r haiku` is a false POSITIVE.

Also worth doing: search the built tree for the *other* model's name and explain
every hit, rather than reporting only that a hit exists.
