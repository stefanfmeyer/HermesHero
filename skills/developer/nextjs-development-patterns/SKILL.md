---
name: nextjs-development-patterns
description: Patterns and troubleshooting for Next.js App Router (Next.js 16+) projects — layout architecture, React 19/Turbopack gotchas, component library upgrades (HeroUI), and auth integration. Covers root layout + route group patterns, CSS import order, dynamic imports, Recharts types, and bulk migration recipes.
trigger: Working on a Next.js 16+ App Router project — layout errors, React 19/Turbopack build failures, HeroUI upgrade issues, asChild prop errors, or dark-mode dashboard setup.
tags: [nextjs, react, tailwind, heroui, dev, app-router]
---

# Next.js Development Patterns

Covers Next.js 16+ App Router patterns, React 19, Turbopack, Tailwind v4, and component library (HeroUI) upgrades.

## Layout Architecture — Root Layout + Route Groups

Next.js 16 requires exactly ONE `<html>/<body>` in the entire app. Route groups (folders in parentheses like `(protected)/`) cannot contain their own `<html>/<body>`.

### Layer 1: Root layout (`app/layout.tsx`)
Only contains html/body + CSS imports. Nothing else.
```tsx
import "./globals.css";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">{children}</body>
    </html>
  );
}
```

### Layer 2: Route group layout (`app/(protected)/layout.tsx`)
Contains the auth-aware shell — SessionProvider, Sidebar, TopBar, main content area.
```tsx
"use client";
import Providers from "@/components/Providers";
import Sidebar from "@/components/layout/Sidebar";
import TopBar from "@/components/layout/TopBar";

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return (
    <Providers>
      <Sidebar />
      <div className="flex flex-col min-h-screen" style={{ marginLeft: 260 }}>
        <TopBar />
        <main className="flex-1" style={{ background: "var(--background)" }}>
          {children}
        </main>
      </div>
    </Providers>
  );
}
```

### Middleware for Route Protection
```typescript
// middleware.ts
export { default } from "next-auth/middleware";

export const config = {
  matcher: [
    "/dashboard/:path*", "/portfolio/:path*", "/orders/:path*",
    "/signals/:path*", "/market/:path*", "/watchlist/:path*",
    "/alerts/:path*", "/settings/:path*",
  ],
};
```

**Key Rules:**
1. Root layout: ONLY `<html>/<body>` + global imports (globals.css, metadata)
2. Route group layout: `"use client"` + all server-side-aware components (Providers, Sidebar, TopBar)
3. Page components: `"use client"` if they use hooks, browser APIs, or NextAuth session
4. NextAuth `SessionProvider` must be in a `"use client"` component

---

## Next.js 16 + Turbopack + React 19 Gotchas

Discovered on the `t212-intelligence` project (Next.js 16.2.4, React 19.2.4, Tailwind v4).

### 1. CSS `@import` Order in Tailwind v4

**File:** `globals.css`

**Problem:** CSS warning: `@import rules must precede all rules aside from @charset and @layer statements`

**Root cause:** `@import url('https://fonts.googleapis.com/...')` was placed AFTER `@import "tailwindcss"`. The Google Fonts import must come first.

**Fix — correct order:**
```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
@import "tailwindcss";

:root { /* ... */ }
```

### 2. `require()` Inside JSX Fails Silently

**File:** `src/app/portfolio/page.tsx`

**Problem:** Dynamic `require("lucide-react")` inside a JSX expression works in some bundlers but silently fails in Next.js 16 App Router / ESM mode:
```tsx
// ❌ Breaks — returns undefined at runtime
icon={totalPL >= 0 ? require("lucide-react").TrendingUp : require("lucide-react").TrendingDown}
```

**Fix:** Always use top-level static ES imports:
```tsx
// ✅ Works
import { TrendingUp, TrendingDown } from "lucide-react";
icon={totalPL >= 0 ? TrendingUp : TrendingDown}
```

### 3. Recharts `ResponsiveContainer` Width Type Error

**File:** `src/components/ui/Sparkline.tsx`

**Problem:** TypeScript error: `Type 'string | number' is not assignable to type 'number | \`${number}%\` | undefined'`

**Fix:** Use explicit type assertion:
```tsx
<ResponsiveContainer width={width as number | `${number}%`} height={height}>
```

Also: when defining the prop interface, use `width?: number | string` not `width?: string` to allow numeric values too.

### 4. `"use client"` Components Can't Be `async`

Client components cannot export `async` functions directly. Keep data fetching in Server Components or use `useEffect` hooks in client components.

### 5. Tailwind v4 — No `tailwind.config.js`

Tailwind v4 uses CSS-based config in `globals.css`. No `tailwind.config.ts` needed.

### 6. Next.js 16 App Router — No `next/head`

Use the `metadata` export in `layout.tsx` instead:
```tsx
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "My App",
  description: "...",
};
```

### 7. React 19 `forwardRef` Changes

React 19 allows `ref` as a normal prop without `forwardRef`. Prefer the new pattern:
```tsx
// React 19 — ref is just a normal prop
function MyComponent({ ref, ...props }) { /* ... */ }
```

### 8. Dynamic Import Icons in JSX Props

**Problem:** Passing a Lucide icon as a dynamic prop:
```tsx
// ❌ TypeScript/ESM issue
<Card icon={condition ? "TrendingUp" : "TrendingDown"} />
```

**Fix:**
```tsx
import { TrendingUp, TrendingDown } from "lucide-react";
const Icon = condition ? TrendingUp : TrendingDown;
<MyComponent icon={Icon} />
```

---

## HeroUI — Portal Debugging

HeroUI v2+ DropdownMenu and similar components (Modal, Popover, etc.) render their **trigger's visible content** as a portal at `document.body` level — completely outside the normal React component tree. This causes:
- Elements inside `DropdownMenuTrigger` to have zero computed dimensions in the original DOM location
- Click handlers on sibling elements being swallowed or misrouted
- Mobile hamburger menus inside `DropdownMenuTrigger` becoming unclickable

### Diagnosis
Run this in the browser console to confirm a portal issue:
```js
(function() {
  const el = document.querySelector('[aria-label="Toggle menu"]');
  if (!el) return 'element not found';
  return {
    bounds: el.getBoundingClientRect(),
    pointerEvents: window.getComputedStyle(el).pointerEvents,
    display: window.getComputedStyle(el).display,
    parentTag: el.parentElement.tagName,
    parentClass: el.parentElement.className.substring(0, 60),
    hasRadixPortal: !!document.querySelector('[id*="radix"]')
  };
})()
```

### Solutions

**Solution 1 (preferred):** Move conflicting elements OUTSIDE DropdownMenuTrigger
```tsx
// ❌ Bad — hamburger inside trigger becomes unclickable
<DropdownMenuTrigger>
  <div className="flex md:hidden">
    <ThemeToggle />
    <button aria-label="Toggle menu"><Menu /></button>
  </div>
</DropdownMenuTrigger>

// ✅ Good — trigger only has the nav text, hamburger is a plain sibling
<div className="flex items-center gap-2">
  <ThemeToggle />
  <DropdownMenuTrigger className="px-4 py-2 ...">Features <ChevronDown /></DropdownMenuTrigger>
  <button className="md:hidden p-2" aria-label="Toggle menu"><Menu /></button>
</div>
```

**Solution 2:** ResizeObserver — separate mobile/desktop components
```tsx
'use client';
import { useState, useEffect } from 'react';

function DesktopHeader() { /* full desktop nav with dropdowns */ }
function MobileHeader() { /* hamburger + drawer — no DropdownMenuTrigger */ }

export function Header() {
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    function check() { setIsMobile(window.innerWidth < 768); }
    check();
    const ro = new ResizeObserver(check);
    ro.observe(document.documentElement);
    return () => ro.disconnect();
  }, []);
  return isMobile ? <MobileHeader /> : <DesktopHeader />;
}
```

---

## HeroUI React Upgrade Guide

### `asChild` prop removed from Button (HeroUI v3 → v4)

**Problem:** After upgrading, all `<Button asChild>` usages cause TypeScript errors:
```
Property 'asChild' does not exist on type 'IntrinsicAttributes & ButtonRootProps'
```

**Fix:** Replace all `<Button asChild><Link>` patterns with plain `<Link>` elements carrying the same Tailwind classes.

**Pattern to find:**
```tsx
<Button asChild className="...">
  <Link href="...">Text</Link>
</Button>
```

**Replace with:**
```tsx
<Link href="..." className="...">Text</Link>
```

For buttons with block children (icons inside Link):
```tsx
// Before
<Button asChild className="...">
  <Link href="...">Text <Icon className="..." /></Link>
</Button>

// After
<Link href="..." className="flex items-center gap-2 ...">
  Text <Icon className="..." />
</Link>
```

**Bulk fix script:** See `bulk-dep-migration-fix` skill for the Python script.

Verify no `asChild` remains:
```bash
grep -rn "asChild" --include="*.tsx" | grep -v node_modules
```

### `suppressHydrationWarning` removed from DropdownMenuTrigger

Remove the `suppressHydrationWarning` attribute entirely — no longer needed.

### `isOpen`/`onOpenChange` controlled state on DropdownMenu

**Problem:** Passing controlled state to HeroUI `DropdownMenu` conflicts with internal state management.

**Fix:** Remove `isOpen` and `onOpenChange` props from `<DropdownMenu>`. Let the component manage its own open/close state. Remove any `useState` hooks used only for this controlled state.

### CSS animations: use `globals.css`, NOT `<style jsx>`

**Problem:** `<style jsx>{`...`}</style>` blocks fail silently in dev or fail the production build with "Expected '</', got ','" on `@keyframes` rules with multiple selectors.

**Fix:** Place all `@keyframes` animations in `app/globals.css`:
```css
@keyframes myproject-flash-pulse {
  0%, 55% { opacity: 1; }
  55.01%, 100% { opacity: 0; }
}

.myproject-flash {
  animation: myproject-flash-pulse 1s steps(2, end) infinite;
}
```

**CSS syntax rule:** Each selector in a `@keyframes` block must have its own `{ }` block. Multiple selectors in one block (`0%, 70% { ... }`) is invalid CSS in Turbopack.

---

## Bulk Dependency Migration Recipes

When a major package update introduces breaking API changes across many files.

### Workflow

1. **Identify scope:** `npm run build 2>&1 | grep "Type error" | head -30`
2. **Bulk-fix with regex scripts** — use Python for multi-file, multi-pattern fixes
3. **Handle edge cases manually** — grep for remaining `asChild` / `OLD_PROP` patterns
4. **Iterate** — fix one error at a time from build output
5. **Commit per fix:** `git add -A && git commit -m "fix: <description>"`

### HeroUI `asChild` → `Link` Recipe

```python
import re, os

base = "/path/to/project"

for root, dirs, files in os.walk(base):
    for fname in files:
        if not fname.endswith('.tsx'):
            continue
        path = os.path.join(root, fname)
        with open(path) as f:
            content = f.read()
        original = content
        
        p1 = re.compile(
            r'<Button\s+asChild\s+className="([^"]+)"\s*>'
            r'\s*<Link\s+href="([^"]+)"([^>]*)>\s*(.*?)\s*</Link>\s*</Button>',
            re.DOTALL
        )
        content = p1.sub(
            lambda m: f'<Link href="{m.group(2)}"{m.group(3)} className="{m.group(1)}">{m.group(4)}</Link>',
            content
        )
        
        if content != original:
            with open(path, "w") as f:
                f.write(content)
            print(f"PATCHED: {path}")
```

### Zod `.errors[]` → `.issues[]` Recipe
```python
content = content.replace("result.error.errors[0]", "result.error.issues[0]")
```

### Arrow function parameters eaten by regex
If `(n) => n[0]` becomes `() => n[0]` after a regex replacement, manually fix.

---

## Dark Trading Dashboard Pattern

Quick-reference for building Your Name's t212-intelligence style dashboards.

### Tech: Next.js 16.2.4 + React 19 + Tailwind v4 + Recharts + Lucide React
Location: `~/t212-intelligence` | Dev: `npm run dev` → `http://localhost:3000`

### File Structure
```
src/
├── app/
│   ├── layout.tsx              # Root: Sidebar + TopBar + children
│   ├── globals.css             # Dark-only CSS tokens + fonts
│   ├── page.tsx               # Redirect to /dashboard
│   ├── dashboard/page.tsx      # Main dashboard
│   └── api/...
├── components/
│   ├── layout/Sidebar.tsx      # 260px fixed nav, collapsible
│   └── ui/KpiCard.tsx, Badge.tsx, Sparkline.tsx
└── lib/formatters.ts, hooks.ts
```

### CSS Tokens (Dark Only)
```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@...&family=JetBrains+Mono:...');
@import "tailwindcss";

:root {
  --background:     #06080e;
  --sidebar-bg:     #0b0f19;
  --card-bg:        #0d111e;
  --card-border:    #1a2333;
  --text-primary:   #f0f4fa;
  --text-secondary: #8b9cb5;
  --accent-primary: #3b82f6;
  --accent-green:   #22c55e;
  --accent-red:     #ef4444;
}
```

**Important:** `@import url(...)` must come BEFORE `@import "tailwindcss"`.

### Chart Period Filter Pattern
```tsx
const [chartPeriod, setChartPeriod] = useState<"1D"|"1W"|"1M"|"3M"|"1Y"|"ALL">("1M");

const cutoffMs: Record<string, number> = {
  "1D": 1*24*60*60*1000, "1W": 7*24*60*60*1000,
  "1M": 30*24*60*60*1000, "3M": 90*24*60*60*1000,
  "1Y": 365*24*60*60*1000, "ALL": Infinity,
};

const filteredSnapshots = snapshots.length > 0
  ? snapshots.filter(s => Date.now() - new Date(s.timestamp).getTime() <= cutoffMs[chartPeriod])
  : null;
```

### Known Build Errors Fixed
1. **Card `style` prop missing** — add `style?: React.CSSProperties` to `CardProps`
2. **Sparkline `width` type** — cast: `width as number | \`${number}%\``
3. **CSS `@import` order** — Google Fonts `@import url()` must come before `@import "tailwindcss"`
4. **`require()` in ESM** — never use `require("lucide-react")` in React components