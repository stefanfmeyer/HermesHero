# Disabling a feature "for now" (worked example: dark mode)

Companion to Step 8.21 / 8.22 of SKILL.md. Captured from the AMA RN app
(2026-09-18), which was made light-only on request.

## The request, and why the obvious reading is wrong

> "Please remove dark mode for now. Just comment it out 🙂 remove the toggle
> button too"

The obvious reading is "delete the toggle". **That does not disable dark mode.**
The scheme was resolved as:

```ts
const device = useColorScheme();
const scheme: Scheme = override ?? (device === "dark" ? "dark" : "light");
```

So with no stored override, the scheme followed the **operating system**. Deleting
the button removed the user's only *exit* from dark mode while leaving dark mode
fully active for anyone whose OS was in dark mode — the worst of both outcomes.

**Rule: a feature-disable request means "make the capability unreachable", which
is not the same as "remove the element".** Enumerate the resolution chain
(device → stored override → default) and neutralise it at the point every
consumer reads, not at the point the user sees.

## The chokepoint

Every component resolved colour through one hook, so one line disabled the whole
app — no component was touched:

```ts
// lib/useTheme.ts
export function useThemeValue(override, setOverride): ThemeValue {
  // DARK MODE DISABLED — this single line is what makes the app light-only.
  // TO RESTORE: delete the pinned line and un-comment the two lines under it.
  const scheme: Scheme = "light";
  // const device = useColorScheme();
  // const scheme: Scheme = override ?? (device === "dark" ? "dark" : "light");

  const activeScheme: Scheme = override ?? "light";   // see "union trap" below

  return useMemo(() => ({
    scheme,
    t: light,                    // was: scheme === "dark" ? dark : light
    override,
    setOverride,
    toggle: () => setOverride(activeScheme === "dark" ? "light" : "dark"),
  }), [scheme, override, setOverride]);
}
```

Before pinning anything, find the chokepoint:

```bash
grep -rn "useTheme()\|useColorScheme" app/ components/ lib/
grep -rn "const {.*} = useTheme()" app/ components/     # who reads what
```

## The union trap

Once `scheme` is pinned to a single literal, TypeScript rejects a union
comparison:

```
error TS2367: This comparison appears to be unintentional because
the types '"light"' and '"dark"' have no overlap.
```

This bites any code that still needs the real value — here the `toggle`
arithmetic. **Do not widen `scheme` back** to silence it. Keep a second binding
that carries the true value:

```ts
const activeScheme: Scheme = override ?? "light";   // real value, for arithmetic only
```

Note the payoff of *keeping* `scheme: Scheme` on the interface: every
`scheme === "dark"` branch in `Glass.tsx` and `MessageList.tsx` stays exactly as
written, still type-checks, and simply never fires. That is what makes restoring
dark mode a one-line change instead of a re-implementation.

## Unused bindings a disable leaves behind

Disabled code leaves dead references. Clear them, with a comment naming what to
re-add:

| File | Disabled | Consequence |
|---|---|---|
| `lib/useTheme.ts` | `useColorScheme` import, `dark` token import | unused imports |
| `components/chat/Sidebar.tsx` | the toggle `Pressable` | `const { t, scheme, toggle }` → `const { t }` |
| `app/_layout.tsx` | stored-preference restore + `StatusBar` scheme switch | `load`/`KEY_THEME` imports, `useCallback` unused; `ready` can start `true` |

The `_layout.tsx` one has a pleasant side effect worth mentioning to the user:
with no theme preference to restore there is nothing to await, so `ready` starts
`true` and startup no longer gates first paint on a storage read.

Comment style that worked — each region marked with the date, the reason, and the
restore steps:

```tsx
{/* DARK MODE TOGGLE REMOVED (2026-09-18) — the app is light-only.
    To restore: un-comment this Pressable, re-add `scheme`/`toggle` to the
    useTheme() destructure above, and un-pin the scheme in lib/useTheme.ts.

<Pressable onPress={toggle} testID="sidebar-theme" ...>
  ...
</Pressable>
*/}
```

⚠️ The fuzzy patcher can mangle a large commented block. When removing a
multi-line JSX element, read the region back and verify the surrounding tags
close correctly — the first attempt here duplicated an opening `<Pressable>` and
orphaned the closing tags. Prefer replacing the whole block with its commented
equivalent in ONE patch that includes the closing `</View></Glass>);}` context.

## Verifying it — the two traps

`scripts/verify_dark_mode_disabled.py` in this skill is a generalised version.
The traps it exists to avoid:

1. **`document.body` is transparent on RN Web** — `getComputedStyle(body)
   .backgroundColor` is `rgba(0, 0, 0, 0)` under BOTH schemes, so any assertion
   against it passes vacuously.
2. **Absence is not a positive result.** Count colours over real elements and
   require the LIGHT token to be present; "dark not found" is also what a blank
   page reports.

Assert on the **set** of painted colours, not ranked counts — counts shift with
incidental DOM state (sidebar open, number of rows) and produced a failure
against an app that was rendering correctly.

## Mutation-test the verifier

A verification that cannot fail proves nothing. Before trusting it:

1. Re-enable the fallback (`useColorScheme` + union `scheme`), redeploy.
2. Run the verifier — it must now FAIL, reporting the dark tokens detected:

```
FAIL [dark-OS] the dark background token is being painted
FAIL [dark-OS] dark-scheme text colour is being painted
```

3. Restore, redeploy, and confirm the bundle hash matches the pre-mutation build
   (so the "restored" state is provably the artefact you tested before).

This is the concrete application of the general rule in SKILL.md Step 9: *if
reverting the fix does not make the check fail, the check is not testing what you
think it is.*
