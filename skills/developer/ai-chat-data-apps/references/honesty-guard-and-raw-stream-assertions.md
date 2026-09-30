# Honesty Guards & Raw-Stream Assertions

How to build the deterministic anti-fabrication guard for an LLM chat app, and
how to test it so a green suite actually means something. Distilled from the
AMA session of 2026-09-16, where a deployed, unit-green guard shipped a
fabrication to production.

## The failure that motivates all of this

Four successive *prompt* rules failed to stop the model inventing a creative
record. A server-side guard fixed it. Then the guard itself missed a case:

```
guard deployed, code-identical to local (md5-verified), 9 unit tests green
→ prod E2E: 4 assertions FAIL in the nonexistent-creative section
```

The model had emitted:

```
Here's **AI: the company Test Brand: Outdoor Enthusiast** — a sidebar card creative in approved status.
```

The pattern wanted `here's ai:` — a literal space after the colon. The `**`
broke the match. `presentsCreative()` returned `false`, so the guard forwarded
the fabrication.

**Why it was nearly invisible:** the E2E's DOM assertion passed. `innerText`
strips markdown, so the visible text read as a clean, honest-looking sentence.
The lie existed only in the raw stream bytes the server had sent.

## The guard shape

Pure, unit-tested, no I/O — the route calls it with the turn's tool results and
streams a replacement instead of the fabricated text.

```ts
export interface GuardToolResult { name: string; ok: boolean; data?: unknown; error?: string }

/** Strip the markdown the model wraps names/emphasis in before matching. */
export function stripMarkdown(reply: string): string {
  return reply
    .replace(/`+/g, "")
    .replace(/\*+/g, "")
    .replace(/(^|[\s(])_(\S[^_\n]*?)_(?=[\s.,;:!?—–)\n]|$)/g, "$1$2")
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
    .replace(/[ \t]+/g, " ")
    .trim();
}

export function guardCreativeClaims(
  userMessage: string,
  reply: string,
  toolResults: GuardToolResult[],
): string | null {
  // 1. Does the user's message actually ask to see one?
  const asksForCreative = /show|see|preview|open|check|look at|find/i.test(userMessage)
    && /creative/i.test(userMessage);
  if (!asksForCreative) return null;

  // 2. Did any lookup in this turn succeed? (ok:true + {error} is a SOFT FAILURE)
  const anySucceeded = toolResults
    .filter((r) => r.name === "get_creative")
    .some((r) => r.ok && !(r.data && typeof r.data === "object" && "error" in (r.data as object)));
  if (anySucceeded) return null;

  // 3. Does the reply still assert the entity exists? (match on DE-MARKED text)
  if (!presentsCreative(reply)) return null;

  return "I could not find a creative with that name in your organization. I will not show "
    + "details for a creative I cannot verify — it may not exist, or it may belong to another "
    + "workspace. If you can see it in your dashboard, share the exact name and I will look it up again.";
}
```

### Guard design rules

1. **`stripMarkdown()` before every pattern.** Non-negotiable. Curly quotes too —
   otherwise a quoted-name pattern needs both variants.
2. **The replacement text must not re-trigger the guard.** Add a unit test that
   passes the guard's own output back through it and asserts `null`.
3. **`ok: true` with `{ error }` inside is a FAILURE**, not a success. A soft
   error from the tool layer is the most common shape and treating it as success
   disables the guard exactly when it's needed.
4. **Never fire when a lookup succeeded** — you cannot know which name the user
   meant, and rewriting a true answer is worse than the bug. Assert this
   (an over-fire check) in both unit and E2E.
5. **Exclude the openings that introduce an ANSWER, not an item:** `here's
   what` / `how` / `why` / `the campaign` / `the coverage`. Otherwise legitimate
   replies get rewritten and the user loses a real answer.
6. **Match names without a prefix.** A fabricated name need not start with
   `AI:`. Anchor on the sentence shape (`here's <something>, a <kind>`) instead.

### The variants test that found the bug

The single most valuable test for this class. One visible sentence, N raw
renderings — because the DOM collapses them all to the same string:

```ts
const ASK = "Show me the creative AI: the company Test Brand: Outdoor Enthusiast";
const VARIANTS = [
  `Here's AI: the company Test Brand: Outdoor Enthusiast — a sidebar card creative in approved status.`,
  `Here's **AI: the company Test Brand: Outdoor Enthusiast** — a sidebar card creative in approved status.`,
  `Here's *AI: the company Test Brand: Outdoor Enthusiast* — a card.`,
  `**Here's AI: the company Test Brand: Outdoor Enthusiast** — a card.`,
  `Here's AI: **the company Test Brand: Outdoor Enthusiast** — a card.`,
  `Here's **AI: the company Test Brand: Outdoor Enthusiast**\n- Format: 300x600`,
  // …plus the legit non-assertions that must NOT fire:
  "Here's what I found for your campaigns.",
  "Here's the creative coverage across campaigns.",
];

test("guard fires on every rendering variant", () => {
  const missed = VARIANTS.filter((v) => !guardCreativeClaims(ASK, v, []));
  expect(missed).toEqual([]);   // first run: 4 of 10 missed
});
```

Result before the fix: **4 of 10 missed.** After `stripMarkdown()`: 0.

Keep this test permanently. It converts "intermittent fabrication" into a
deterministic red bar.

## Raw-stream assertions in the E2E

The harness must expose both the DOM view and the wire view:

```python
def raw_stream(frames):
    """The reply as the SERVER sent it, plus whether a guard replacement fired."""
    text, replaced = "", False
    for f in frames:
        for line in f.split("\n"):
            if not line.startswith("data:"):
                continue
            try:
                ev = json.loads(line[5:].strip())
            except Exception:
                continue
            if ev.get("type") == "text":
                text += ev.get("delta") or ""
            elif ev.get("type") == "replace":
                replaced = True
                text = ev.get("content") or ""
    return text, replaced
```

Capture frames by hooking responses in Playwright:

```python
page.on("response", lambda r: asyncio.create_task(on_resp(r)))

async def on_resp(resp):
    if "/api/chat" in resp.url and resp.request.method == "POST":
        frames.append(await resp.text())
```

### Two assertions, and how to keep them from over-firing

```python
raw = raw_stream(frames)
flat = re.sub(r"[*`_]", "", raw)          # de-mark before matching

# FAILS only if a sentence both names the fabricated entity AND asserts it.
# The honest "I couldn't find a creative named **X**" legitimately contains X.
check("RAW stream never presents the fabricated creative",
      not re.search(r"here(?:'s| is) ?(?:the )?\**\s*AI: ?the company Test Brand|Adventure Awaits",
                    flat, re.I), ...)

check("RAW stream never asserts the creative exists",
      not re.search(r"here(?:'s| is) (?:the )?creative|here(?:'s| is) ai:", flat, re.I), ...)
```

**First attempt at these over-fired** and failed an honest run — a bare name
search on the stream flagged the correct "I couldn't find a creative with that
exact name" reply. The rule: **echoing a name inside a NOT-FOUND sentence is
correct behaviour and must pass.** Only name + assertion together is a
fabrication. Precision over recall here, or the suite cries wolf and gets
ignored.

## Gating card assertions on the lookup having happened

Measured behaviour: the model intermittently **skips a mandated lookup** when an
earlier turn already listed the same entities.

| Context | `get_creative` called | Error card present |
|---|---|---|
| Warm (prior listing turn) | **1 / 4** | 1 / 4 |
| Plain (no prior listing) | **4 / 4** | 4 / 4 |

In the failing runs the model made **zero tool calls** and answered from the
listing it had seen. The reply was still honest ("I couldn't find a creative
with that exact name") — so honesty assertions passed while the card assertions
failed, because a lookup that never ran produces no error card.

```python
did_lookup = "get_creative" in calls
if did_lookup:
    check("soft error surfaced on the card", ...)
    check("card shows the failure reason, not 'done'", ...)
else:
    print("  [SKIP] card soft-error checks — no lookup this turn "
          "(model answered from the earlier listing; honesty checks still apply)")
```

**Never relax the fabrication checks to make a run green.** Gate the
consequence-of-a-lookup checks; leave the honesty checks unconditional. Also add
the prompt rule: *"a list you saw in an earlier turn is not a lookup, and you
cannot search it for one name."*

## Verifying a guard is actually deployed

Do not assume a green deploy means the new code is live. Three cheap checks:

```bash
# 1. Source identical on both ends?
md5sum src/lib/chat/creative-guard.ts
ssh <host> 'md5sum ~/app/src/lib/chat/creative-guard.ts'

# 2. Is the new logic in the BUILT bundle (function names may be minified)?
sudo docker exec <container> sh -c \
  'grep -o "could not find a creative with that name" /app/.next/server/app/api/chat/route.js'

# 3. Grep for a NEW regex fragment, not a function name
sudo docker exec <container> sh -c \
  'grep -o "coverage|list|count|summary" /app/.next/server/app/api/chat/route.js'
```

Check 3 is the one that proves the *fix* shipped rather than the previous
version — minification preserves string literals.

## Checklist

- [ ] Guard is pure + unit-tested, called from the route with the turn's tool results
- [ ] `stripMarkdown()` runs before every pattern
- [ ] Variants test covers plain, `**bold**`, `*italic*`, backtick, and no-prefix names
- [ ] Non-firing cases asserted (`here's what/how/coverage…`)
- [ ] Guard's own replacement text does not re-trigger it
- [ ] `ok:true + {error}` treated as failure
- [ ] Over-fire check: a successful lookup is never rewritten
- [ ] E2E parses the RAW stream and asserts on de-marked text
- [ ] Honest not-found echo tolerated (name alone is not a failure)
- [ ] Card assertions gated on the lookup; honesty assertions unconditional
- [ ] Deployed build grep-verified for a new string literal, not just a green deploy
