# Replicating the Gemini web UI design (proven recipe, 2026-09-14)

Verified recipe from restyling AMA (Next.js 15 + Tailwind v4) to match
Gemini's mobile + settings screenshots. Use when asked to "replicate this
design exactly" from screenshots of Gemini or a similar Google surface.

## Font: Google Sans, self-hosted

Gemini uses **Google Sans** (Google's proprietary UI font). It IS fetchable
from the public Google Fonts CSS endpoint with a browser User-Agent, and the
latin woff2 files can be self-hosted (no license file needed for internal
tooling; for public products prefer a licensed equivalent):

1. Fetch the CSS with a browser UA (curl's default UA returns nothing):
   `curl -s -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36" \
   "https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500&display=swap"`
2. The response lists many unicode-range @font-face blocks. Grab the latin
   (U+0000-00FF) block's URL per weight, e.g.:
   - 400: `https://fonts.gstatic.com/s/googlesans/v70/4UasrENHsxJlGDuGo1OIlJfC6l_24rlCK1Yo_Iqcsih3SAyH6cAwhX9RPiIUvQ.woff2`
   - 500: `https://fonts.gstatic.com/s/googlesans/v70/4UasrENHsxJlGDuGo1OIlJfC6l_24rlCK1Yo_Iqcsih3SAyH6cAwhX9RPjIUvQ.woff2`
3. Download into `public/` (`GoogleSans-400.woff2`, `GoogleSans-500.woff2`)
   and declare `@font-face` in globals.css with `font-display: swap`.
   Fallback stack: `"Google Sans", "Product Sans", system-ui, ...`.
4. Verify with a computed-style probe in Playwright:
   `getComputedStyle(document.body).fontFamily.split(',')[0]` must be
   `"Google Sans"`.

## Design tokens (Gemini light theme, extracted)

> **User override (2026-09-14, later batch):** the user rejected the cool-grey
> surface after living with it — "remove the light blue faded bg, it should
> be white". Final shipped tokens: `--background: #ffffff`, `--sidebar:
> #ffffff`, `--muted: #f2f2f2` (neutral grey, not blue-grey). Keep the rest
> of the Gemini palette; if replicating for the user, default to the white
> surface variant.

```css
--background: #ffffff;         /* was #f0f4f9; user demanded pure white */
--card: #ffffff;               /* composer pill, tool cards, assistant bubble */
--foreground: #1f1f1f;
--muted: #f2f2f2;              /* was #e9eef6 (blue-grey) — neutralized */
--muted-foreground: #444746;
--border: #dde3ea;
--primary: #0b57d0;            /* Google blue 700-ish, for links/active */
--accent: #c4e7ff;             /* circular send button bg */
--accent-soft: #d3e3fd;        /* active nav item, avatar */
radius scale: 28px for composer pill + buttons ("rounded-full" at h-10+),
28px for chat bubbles, 16px (rounded-2xl) for cards.
```

Dark-mode counterparts (Gemini dark): background #131314, card #1e1f20,
primary #a8c7fa, accent-soft #0842a0, foreground #e3e3e3.

## Layout anatomy (what to copy where)

Main chat (mobile screenshot):
- Top bar: round white hamburger button (shadow-[0_1px_3px_rgba(0,0,0,0.08)])
  → inline "AmA Flash ˅" model dropdown (18px text) → pencil + avatar right.
- Empty state: centered logo (72px) + "Where should we start?" at
  32–40px font-normal, with a **radial blue glow at the bottom of the
  viewport only**: `radial-gradient(120% 90% at 50% 115%,
  rgba(167,203,250,0.55) 0%, rgba(233,242,252,0.35) 45%, transparent 70%)`.
- Composer: white 28px-radius pill, NO border, soft dual shadow; `+` icon
  left inside the pill; circular accent-bg send button right; placeholder
  "Ask <product>"; borderless textarea inside.

Settings sidebar (second screenshot):
- "AmA" title (22px medium) + round ✕ close button.
- "New chat" as a filled muted pill item with pencil icon; "Search chats"
  as a plain item with magnifier.
- "Recent" section label (muted), empty state text verbatim pattern:
  "No saved chats / Recent chats will appear here so that you can continue
  them later".
- Bottom row pinned with border-t: avatar circle, name + secondary action,
  settings gear. Active nav item = accent-soft fill, pill radius.

Chat content: user message = muted (#f2f2f2 in the shipped white variant)
rounded-[28px] bubble, right-aligned; assistant response = white `bg-card`
rounded-[28px] bubble with the same soft shadow as tool cards (user explicitly
requested white assistant bubbles, NOT plain text on surface); tool cards =
white rounded-2xl with faint shadow instead of bordered boxes. Assistant
"thinking" indicator = circular spinner (`animate-spin rounded-full border-2
border-x-muted border-t-primary`), never a pulsing rectangle — the user read
the blue pulse as a stuck request. Input placeholder pattern: "Ask Me
Anything" (user's exact wording), not "Ask <product>".

## Verification

- Mobile Playwright run (390×844, is_mobile=True) asserting
  `scrollWidth == innerWidth` before and after a real conversation, textarea
  computed font-size 16px, and screenshots of home / drawer / chat.
- Desktop screenshot at 1440×900 for the two-column layout.
- Vision-compare each element named in the reference against the screenshot;
  report every mismatch before claiming done.