# Quick-reply suggestions for data chat apps

Pattern from the company-ama (2026-09-14): after an assistant reply that lists
rows (campaigns, etc.), the user expects clickable chips that send the
obvious follow-up ("performance for THIS campaign") — not a bare "would you
like to see performance details?" question they must type an answer to.

## Priority 1 — the assistant's own option bullets ARE the chips

When the assistant ends a reply with offered options ("Would you like me to:
- Show your overall account performance summary?
- Activate this campaign?"), those bullets must render as clickable chips
verbatim — clicking sends the option text itself. The user corrected this
directly: the recommended quick replies in that situation should have been
"Show Account performance" and "Activate Campaign", not generic follow-ups.

Extractor (client-side, no LLM call):
1. Scan the last assistant message line-by-line for bullets `- / * / •`.
2. Accept a bullet as an option if it ends with `?` OR starts with an
   imperative verb (show|activate|set up|create|check|complete|view|list|add|
   pause|change); reject data lines (leading digits, `|` table rows, <4 chars).
3. Strip `**`, cap at 4 chips, label = text minus trailing `?`,
   message = text verbatim.
4. If any option bullets exist, RETURN THEM ALONE — table-drilldown chips
   are suppressed in this case (the offer list is the actionable content).

## Table/entity chips (fallback priority)

- Derive chips client-side from the last assistant message + tool results —
  NO extra LLM call, so chips appear the instant streaming ends.
- **Extract candidate entities from the markdown TABLE, not bold spans.**
  First hardening attempt read `**bold**` spans only and produced ZERO
  campaign chips, because the model renders table rows with plain (unbolded)
  names — the user came back with "the buttons should be clickable
  suggestions for each campaign name; currently it just suggests Paused
  Campaigns". The working extractor:
  1. Split the reply into lines; take lines starting with `|`.
  2. Split cells, trim, drop empties; need ≥2 cells.
  3. Strip `**` from the first cell (the model sometimes bolds there too).
  4. Skip separator rows (`|---|`), header rows (Campaign/Name/Title),
     cells <2 or >80 chars, and em-dash-only rows.
  5. ALSO scan `**bold**` spans outside tables as a secondary source
     (filter generic bold: counts like "**10 campaigns**", statuses,
     em-dashes) — dedupe against table hits.
  6. Cap at ~3 entities + contextual follow-ups; max 4 chips total.
- Map reply content to follow-ups:
  - has a markdown table or mentions running/paused campaigns → one chip per
    entity ("Show performance for <name>") + "Last 7 days" / "Yesterday"
  - mentions "performance" without a table → "Last 7 days"
  - fallback (nothing matched) → generic performance/campaign-list chips
- Hide while streaming; clear on new chat / conversation switch.

## Rendering

Rounded-full pills above the composer, `text-xs`, hairline border, primary
color on hover, pointer cursor (global CSS rule covers this). Clicking sends
the chip's `message` through the normal send path (same as typing). Verified
E2E flow: list reply → chips appear → click campaign chip → "Show performance
for <name>" streams a real answer.

## Why client-side beats LLM-generated suggestions here

⚠️ **SUPERSEDED 2026-09-15 — this section's conclusion was WRONG in practice.**
The heuristic extractors below shipped, and the user reported the chips as "too
inconsistent" and asked for context-awareness *or removal*. The reasoning above
sounds right (zero latency, zero token cost, covers 90%) but the 10% it misses is
the case the user cares about most, and a heuristic can only ever fall back to
canned chips ("Last 7 days", "Campaign list") regardless of what was just said.
A single extra LLM call against the finished reply (`POST /api/suggestions`,
started the moment the reply text is final — see SKILL.md, and NOT "after the
stream ends", which was corrected 2026-09-18) fixed it outright. See the SKILL.md
section "Quick-reply chips: generate them with an LLM call, NOT a regex" for the
current implementation, and `helper-call-latency.md` for the latency work.

The extractor recipes below are retained only for historical context — do NOT
reimplement them. The one durable lesson they carry: **when a heuristic silently
degrades to a generic fallback, users read it as broken, not as a best-effort.**
If you are tempted to add a canned fallback, that is the signal to escalate to a
model call instead.
