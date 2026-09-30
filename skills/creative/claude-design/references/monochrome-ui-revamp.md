# Monochrome UI Revamp — Technique Bank

Session-proven techniques for revamping an existing React/vanilla UI with a strict black/grey/white palette.

## When to Use

- User says "black/grey only", "no color", "monochrome", "grayscale"
- Revamping an existing UI's CSS where the current stylesheet is out of sync with components
- Any design task where chromatic hues are explicitly forbidden

## The Monochrome Semantic System

### Brightness Ramp for Status Badges

Map lifecycle states to a 6-step brightness ramp (darkest → brightest):

| State | Treatment | Example |
|-------|-----------|---------|
| Inactive/draft/deleted | Faint text on dark bg, thin border | `bg: #1a1a1a, text: #6e6e6e, border: #262626` |
| Pending review | Mid-grey text, medium border | `bg: #222, text: #a8a8a8, border: #333` |
| Approved | Bright text, strong border, bold | `bg: #222, text: #ededed, border: #4a4a4a` |
| Generating/in-progress | Same as pending + opacity pulse | `animation: badge-pulse 2s infinite` |
| Live/published (highest) | Inverted: white bg, black text | `bg: #ededed, text: #0a0a0a` |
| Rejected/error | Dark bg, strongest border | `bg: #141414, text: #d0d0d0, border: #5a5a5a` |

### Confidence/Severity Dots — Solid-to-Hollow

| Score | Treatment |
|-------|-----------|
| 1.00 (exact) | Solid white dot |
| 0.90-0.99 (high) | Solid light-grey dot |
| 0.70-0.89 (medium) | Solid mid-grey dot |
| < 0.70 (low) | Hollow dot — transparent center, 1.5px border |

### Validation/Diff Severity — Left-Border Weight + Brightness

| Severity | Left border | Text brightness |
|----------|-------------|-----------------|
| Error | 3px solid `#5a5a5a` | Brightest (`#d0d0d0`) |
| Warning | 3px solid `#3a3a3a` | Mid (`#b0b0b0`) |
| Info | 3px solid `#2e2e2e` | Muted (`#999999`) |

### Diff Row Types — Left-Border Thickness

| Type | Treatment |
|------|-----------|
| Added | 2px solid `#555` (stronger grey) |
| Removed | 2px solid `#5a5a5a` (strongest grey) |
| Modified | 2px solid `#3a3a3a` (medium grey) |

Old values: `text-decoration: line-through`, faint colour.
New values: `font-weight: 600`, brightest text.

## Token Setup

```css
:root {
  /* Backgrounds — 6 layers */
  --bg-primary:    #0a0a0a;
  --bg-secondary:  #131313;
  --bg-tertiary:   #1a1a1a;
  --bg-elevated:   #222222;
  --bg-hover:      #262626;
  --bg-inset:      #0d0d0d;

  /* Text — 4 levels */
  --text-primary:   #ededed;
  --text-secondary: #a8a8a8;
  --text-muted:     #6e6e6e;
  --text-faint:     #484848;

  /* Borders — 3 strengths */
  --border:        #262626;
  --border-light:  #333333;
  --border-strong: #4a4a4a;

  /* Semantic — all reference the same greys */
  --ok-text: #ededed;  --ok-bg: #1e1e1e;  --ok-border: #555;
  --warn-text: #b0b0b0; --warn-bg: #181818; --warn-border: #3a3a3a;
  --err-text: #d0d0d0;  --err-bg: #141414;  --err-border: #5a5a5a;
  --info-text: #999999; --info-bg: #161616; --info-border: #2e2e2e;
}
```

## CSS Revamp Workflow (for existing React UIs)

1. **Read every component file** — collect all `className` tokens from JSX
2. **Read the existing CSS** — identify which classes are already styled vs missing
3. **Expect 40-60% missing coverage** — this is normal in fast-moving projects
4. **Write the complete CSS** — cover every class, don't just patch gaps
5. **Run class-coverage check** — use `scripts/check-css-coverage.py` to verify
6. **Build** — run `vite build` or equivalent to confirm no errors
7. **Report** — state what was covered, what was verified

## Key Lessons

- The original CSS being out of sync with JSX is the **norm**, not the exception
- Keep legacy class definitions alongside new ones for backward compat
- `prefers-reduced-motion` should kill pulse/animation on status badges
- Inverted buttons (white bg, black text) read as "primary action" without color
- `accent-color` on checkboxes can be set to `var(--text-primary)` for monochrome
- `color-scheme: dark` on date inputs prevents OS-light-mode date pickers