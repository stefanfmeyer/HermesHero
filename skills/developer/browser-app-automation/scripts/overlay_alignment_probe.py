#!/usr/bin/env python3
"""Measure a held-down-only overlay against the element it claims to describe.

Why this exists
---------------
A chart/tooltip/crosshair overlay that only EXISTS while the pointer is held down
is the hardest kind to verify, because the naive probe measures before pressing,
finds nothing, and **passes vacuously** — a green tick over an empty read.

This script encodes the three traps found while chasing a hover indicator that sat
a constant 35px to the right of the point it reported (2026-09-21):

1. **press -> read -> release must be one atomic action.** The overlay is absent
   otherwise, and `None` from the probe MUST fail the assertion, never pass it.
2. **The press Y matters.** Only part of a card's height is the widget's responder
   area; pressing at `height * 0.5` produced NO overlay while `0.45` worked at
   every height measured. Press at the target element's own y when you can.
3. **Re-measure the box immediately before pressing.** An earlier drag scrolled the
   page, so a box captured minutes earlier was stale, the press landed outside the
   widget, and "no overlay rendered" nearly read as a product failure.

It also reports the offset as a signed number so a **double-count** is visible:
an error that equals a prop's value 1:1 (offset == 35 when the prop is 35) is a
double-applied inset, not a layout bug — set it to zero, don't compensate.

Usage
-----
    /tmp/pw-venv/bin/python overlay_alignment_probe.py \\
        --url https://app.example:3400 --email you@example.com --password '...' \\
        --ask "Show me impressions per day for the last 7 days" \\
        --root '[data-testid="metric-chart-root"]' \\
        --point 'circle' --overlay 'line'

`--point` and `--overlay` are CSS selectors INSIDE the root. The overlay is
identified structurally (`|y2 - y1| > 60` for a vertical line) rather than by
colour, because colour matching hits unrelated absolutely-positioned elements.

Exit 0 = every sampled point was within tolerance; 1 = a real misalignment.
"""

import argparse
import asyncio
import json
import sys

from playwright.async_api import async_playwright

# Data points: circles with a real radius (skip tiny decorative markers).
POINTS_JS = """(sel) => {
  const root = document.querySelector(sel);
  if (!root) return {err: 'no root'};
  const rb = root.getBoundingClientRect();
  const pts = [];
  for (const svg of root.querySelectorAll('svg')) {
    const sb = svg.getBoundingClientRect();
    for (const c of svg.querySelectorAll('circle')) {
      const cx = parseFloat(c.getAttribute('cx'));
      const r = parseFloat(c.getAttribute('r'));
      if (Number.isFinite(cx) && r >= 2) {
        pts.push({x: +(sb.left - rb.left + cx).toFixed(1),
                  y: +(sb.top - rb.top + parseFloat(c.getAttribute('cy'))).toFixed(1)});
      }
    }
  }
  return {pts};
}"""

# The crosshair/strip: the only TALL vertical line inside the root.
OVERLAY_JS = """(sel) => {
  const root = document.querySelector(sel);
  if (!root) return [];
  const rb = root.getBoundingClientRect();
  const out = [];
  for (const svg of root.querySelectorAll('svg')) {
    const sb = svg.getBoundingClientRect();
    for (const l of svg.querySelectorAll('line')) {
      const x1 = parseFloat(l.getAttribute('x1'));
      const y1 = parseFloat(l.getAttribute('y1'));
      const y2 = parseFloat(l.getAttribute('y2'));
      if (Number.isFinite(x1) && Math.abs(y2 - y1) > 60) {
        out.push(+(sb.left - rb.left + x1).toFixed(1));
      }
    }
  }
  return out;
}"""


async def press_and_read(page, box, rel_x, y_frac, root_sel):
    """Press at a root-relative x, read the overlay while held, release."""
    y = box["y"] + box["height"] * y_frac
    await page.mouse.move(box["x"] + rel_x, y)
    await page.wait_for_timeout(80)
    await page.mouse.down()
    await page.wait_for_timeout(140)
    # A 0.5px move after mousedown: some widgets only activate on movement.
    await page.mouse.move(box["x"] + rel_x + 0.5, y, steps=2)
    await page.wait_for_timeout(420)
    xs = await page.evaluate(OVERLAY_JS, root_sel)
    await page.mouse.up()
    await page.wait_for_timeout(120)
    return xs[0] if xs else None


async def main(args) -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not args.headed)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 1000})
        page = await ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)[:200]))

        await page.goto(args.url + "/")
        await page.wait_for_timeout(3000)
        inputs = page.locator("input")
        await inputs.nth(0).fill(args.email)
        await inputs.nth(1).fill(args.password)
        await page.get_by_test_id("login-submit").click()
        await page.wait_for_url("**/chat", timeout=30000)
        await page.wait_for_timeout(3000)

        box_in = page.locator('textarea, input[type="text"]').first
        await box_in.click()
        await box_in.fill(args.ask)
        await page.keyboard.press("Enter")
        await page.wait_for_selector('[data-testid="turn-idle"]', state="attached",
                                     timeout=200000)
        await page.wait_for_timeout(3000)

        root = page.locator(args.root).first
        # Re-measure here, not earlier: the transcript may have scrolled.
        await root.scroll_into_view_if_needed()
        await page.wait_for_timeout(700)
        box = await root.bounding_box()
        if not box:
            print("ABORT: root has no box", file=sys.stderr)
            await browser.close()
            return 1
        print("root box:", {k: round(v) for k, v in box.items()})

        probe = await page.evaluate(POINTS_JS, args.root)
        pts = probe.get("pts") or []
        print("data points (root-relative):", json.dumps(pts))
        if len(pts) < 2:
            print("ABORT: fewer than 2 data points — nothing to align against",
                  file=sys.stderr)
            await browser.close()
            return 1

        print(f"\n{'target x':>9} {'overlay x':>10} {'offset':>8}")
        offsets, failures = [], []
        for pt in pts:
            got = await press_and_read(page, box, pt["x"], args.y_frac, args.root)
            if got is None:
                # MUST fail: an empty read is not a pass.
                print(f"{pt['x']:9.1f} {'NONE':>10} {'-':>8}  <- no overlay; FAIL")
                failures.append(("no overlay", pt["x"]))
                continue
            off = round(got - pt["x"], 1)
            offsets.append(off)
            flag = "" if abs(off) <= args.tol else "  <- FAIL"
            if abs(off) > args.tol:
                failures.append((off, pt["x"]))
            print(f"{pt['x']:9.1f} {got:10.1f} {off:8.1f}{flag}")

        print("\n--- summary ---")
        if offsets:
            print(f"max |offset| = {max(abs(o) for o in offsets)}px "
                  f"(tolerance {args.tol}px)")
            # A constant offset equal to a prop you set is a DOUBLE-COUNT.
            uniq = {o for o in offsets}
            if len(uniq) == 1:
                print(f"NOTE: offset is CONSTANT ({uniq.pop()}px on every point). "
                      "If this equals a prop value you passed (e.g. initialSpacing), "
                      "the library is applying it twice — set it to 0 rather than "
                      "compensating.")
        print("page errors:", errors or "none")

        ok = not failures
        print("\nVERDICT:", "PASS" if ok else "FAIL")
        await browser.close()
        return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="app base URL, no trailing /")
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--ask", required=True,
                    help="question whose answer renders the widget")
    ap.add_argument("--root", required=True, help="CSS selector for the widget root")
    ap.add_argument("--tol", type=float, default=3.0,
                    help="allowed |offset| in px (default 3)")
    ap.add_argument("--y-frac", type=float, default=0.45,
                    help="press height as a fraction of the root box (default 0.45)")
    ap.add_argument("--headed", action="store_true")
    return ap


if __name__ == "__main__":
    sys.exit(asyncio.run(main(build_parser().parse_args())))
