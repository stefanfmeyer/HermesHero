---
name: js-string-padding-fixed-width-tables
description: Fix JS string padding bugs in fixed-width currency tables
---

# JS String Padding for Fixed-Width Tables

## The Bug
When formatting numeric values in fixed-width table columns, chaining `.padEnd()` or `.padStart()` directly after `.toFixed()` can cause alignment collapse:

```js
// BROKEN — outputs "£334.41" with no padding
`£${val.toFixed(2).padEnd(10)}`

// BROKEN — value is a number, padEnd does nothing
`£${(value).padEnd(10)}`
```

## Root Cause
- `Number.prototype.toFixed(2)` returns a **string** (e.g., `"334.41"`)
- But `padEnd()` on a number silently coerces to string first — the real issue is the `£` symbol sitting **outside** the padding, so the column width calculation is wrong
- Column width was 10, but `£` + 10-char value = 11 chars visible, so alignment collapsed

## The Fix
```js
// CORRECT — pad the numeric string BEFORE prepending the currency symbol
// Use padStart() for right-aligned currency (standard)
` £${val.toFixed(2).toString().padStart(10)}`  // " £   334.41"
```

## Column Width Rules
- `£` symbol sits **outside** the padding (prepended, not inside)
- For a 10-char value field + 1 for £ = **11 total column chars**
- Use `padStart()` for right-aligned numeric values (standard for currency)
- Use `padEnd()` for left-aligned text fields

## Pattern for Table Row Formatting
```js
const val = 334.41;
const formatted = ` £${val.toFixed(2).toString().padStart(10)}`;
// " £   334.41" — 10 chars after the £
```

## Files This Pattern Appears In
- `scripts/weekly-review.js` — rebalance plan table (qty, value, current%, target%)
- `scripts/generate-signals.js` — signal reasoning lines
- `scripts/03-check-exits.js` — exit price display
