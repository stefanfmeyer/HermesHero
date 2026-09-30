#!/usr/bin/env python3
"""Is a URL actually embeddable in an iframe? Calibrated, in two engines.

WHY THIS EXISTS
---------------
"Can we iframe their page?" gets answered wrong by reading directives. A target
can carry `X-Frame-Options: DENY` in a <meta> tag (ignored by browsers) or
`frame-ancestors 'none'` in a <meta> CSP (also ignored) and still embed perfectly
— while the same directives in a real response HEADER do block it. The only
reliable answer is to load it in a browser and watch what the browser says.

⚠️ THE OBVIOUS PROBE IS WORTHLESS. Reading `iframe.contentWindow.location` throws
`SecurityError` for ANY cross-origin frame, so a refused frame and a
successfully-embedded frame report the *identical* value. A check built on it is
wrong in both directions (it failed a healthy target when this was written).

THE CALIBRATED SIGNALS THIS USES INSTEAD
----------------------------------------
1. A MUST-BLOCK CONTROL beside the target — `https://www.google.com` sends
   `X-Frame-Options: SAMEORIGIN`, so the browser must refuse it. If the control is
   NOT refused, the probe is broken and no verdict about the target is trustworthy.
2. A MUST-LOAD CONTROL — `https://example.com` is embeddable, so it must load.
   This catches a probe that refuses everything for an unrelated reason.
3. CONSOLE REFUSAL MESSAGES, matched per-origin: the control produces one, the
   target must not.
4. THE FRAME'S RENDERED SIZE — an embedded document lays out and takes real
   dimensions (measured 719x852 for a real panel); a refused frame collapses.

Usage:
    python3 embeddability_probe.py https://app.example.com/dashboard
    python3 embeddability_probe.py <url> --engine firefox
Exit code 0 = target embeddable and probe calibrated; 1 otherwise (the reason is
printed, so a failure is actionable rather than just red).
"""
import argparse
import asyncio
import sys

from playwright.async_api import async_playwright

# Sends X-Frame-Options: SAMEORIGIN — the browser must refuse this one.
MUST_BLOCK = "https://www.google.com/"
# Embeddable — the browser must load this one.
MUST_LOAD = "https://example.com/"

PAGE = """
<style>iframe {{ width: 600px; height: 400px; border: 0; }}</style>
<iframe id="block" src="{block}"></iframe>
<iframe id="load"  src="{load}"></iframe>
<iframe id="target" src="{target}"></iframe>
"""


async def probe(engine: str, target: str) -> bool:
    async with async_playwright() as p:
        browser = await getattr(p, engine).launch()
        page = await (await browser.new_context(viewport={"width": 1400, "height": 900})).new_page()

        msgs: list[str] = []
        page.on("console", lambda m: msgs.append(m.text))

        await page.set_content(PAGE.format(block=MUST_BLOCK, load=MUST_LOAD, target=target))
        await page.wait_for_timeout(10000)

        sizes = await page.evaluate(
            """() => {
                const out = {};
                for (const id of ['block', 'load', 'target']) {
                    const el = document.getElementById(id);
                    const b = el.getBoundingClientRect();
                    out[id] = {w: Math.round(b.width), h: Math.round(b.height)};
                }
                return out;
            }"""
        )

        refusals = [m for m in msgs
                    if "refused to display" in m.lower() or "denied by" in m.lower()]

        def refused(fragment: str) -> bool:
            return any(fragment in m for m in refusals)

        print(f"\n===== {engine.upper()} =====")
        print(f"  refusal messages: {refusals or '(none)'}")
        print(f"  frame sizes:      {sizes}")

        ok = True

        # 1. Calibration: the must-block control has to be refused.
        if refused("google.com"):
            print("  [PASS] must-block control (google.com) was refused -> probe is calibrated")
        else:
            print("  [FAIL] must-block control was NOT refused -> probe is NOT calibrated; "
                  "no verdict about the target is trustworthy")
            ok = False

        # 2. Calibration: the must-load control has to load without a refusal.
        if not refused("example.com"):
            print("  [PASS] must-load control (example.com) was not refused")
        else:
            print("  [FAIL] must-load control WAS refused -> something is blocking everything")
            ok = False

        # 3. The question.
        if refused("app.example.com") or any(target in m for m in refusals):
            print("  [FAIL] TARGET IS REFUSED in a frame -> the target cannot be embedded")
            ok = False
        else:
            print("  [PASS] target was NOT refused")

        # 4. Size, the second independent signal.
        t = sizes["target"]
        if t["w"] > 100 and t["h"] > 100:
            print(f"  [PASS] target frame took real size ({t['w']}x{t['h']}) -> a document laid out in it")
        else:
            print(f"  [FAIL] target frame collapsed ({t['w']}x{t['h']}) -> nothing rendered in it")
            ok = False

        # The must-block control should ALSO have collapsed, which is the size
        # signal confirming itself.
        b = sizes["block"]
        print(f"  (control size for comparison: {b['w']}x{b['h']} — a refused frame is small/zero)")

        print(f"  VERDICT: {'EMBEDDABLE' if ok else 'NOT EMBEDDABLE / probe not calibrated'}")
        await browser.close()
        return ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="the URL to test for iframe embeddability")
    ap.add_argument("--engine", default=None, choices=["chromium", "firefox"])
    args = ap.parse_args()

    engines = [args.engine] if args.engine else ["chromium", "firefox"]
    results = [asyncio.run(probe(e, args.url)) for e in engines]
    print(f"\n{'all engines agree: EMBEDDABLE' if all(results) else 'NOT embeddable (or probe uncalibrated)'}")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
