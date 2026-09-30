#!/usr/bin/env python3
"""
Verify a "dark mode is disabled / app is light-only" claim against a LIVE build.

Generalised from the AMA RN-web app (2026-09-18). Env-driven so it points at any
light-only app that uses a testable theme toggle.

WHY THIS SCRIPT EXISTS — two traps that make a naive check pass vacuously:

  1. Asserting on document.body is meaningless on React Native Web: the root is
     transparent, so getComputedStyle(body).backgroundColor is rgba(0,0,0,0) under
     BOTH schemes. The assertion passes on a light app, a dark app, and a blank
     page alike.
  2. "No dark colours found" is an ABSENCE, not a proof. A blank page also has no
     dark colours. Count painted colours over real elements and require the LIGHT
     token to be POSITIVELY present.

The decisive test is the emulated OS preference: with color_scheme="dark" the app
must paint exactly the same palette as under "light". That is the check that
catches a useColorScheme() fallback surviving a "remove the button" change.

Finally: MUTATION-TEST THIS before trusting it. Re-enable the fallback, redeploy,
confirm this script FAILS, then restore. A verifier that cannot fail proves
nothing.

Usage:
  APP_URL=https://host:port \
  LOGIN_EMAIL=you@example.com LOGIN_PW=... \
  THEME_TESTID=sidebar-theme \
  TOGGLE_OPENER_TESTID=burger \
  LIGHT_BG="rgb(250, 253, 255)" DARK_BG="rgb(19, 19, 20)" \
  LIGHT_FG="rgb(31, 31, 31)"   DARK_FG="rgb(227, 227, 227)" \
  python3 verify_dark_mode_disabled.py

Token values come from the app's own theme module — read them from source rather
than guessing, or the "must be present" assertions will fail on a correct app.
"""
import asyncio
import json
import os
import sys

APP = os.environ["APP_URL"].rstrip("/")
EMAIL = os.environ.get("LOGIN_EMAIL", "")
PW = os.environ.get("LOGIN_PW", "")

# testID of the theme toggle (must be ABSENT) and of whatever opens the sidebar.
THEME_TESTID = os.environ.get("THEME_TESTID", "sidebar-theme")
TOGGLE_OPENER = os.environ.get("TOGGLE_OPENER_TESTID", "burger")

# Login field testIDs; override for a different app.
EMAIL_TESTID = os.environ.get("LOGIN_EMAIL_TESTID", "login-email")
PW_TESTID = os.environ.get("LOGIN_PW_TESTID", "login-password")
SUBMIT_TESTID = os.environ.get("LOGIN_SUBMIT_TESTID", "login-submit")

# Theme tokens, from the app's theme module.
LIGHT_BG = os.environ["LIGHT_BG"]
DARK_BG = os.environ["DARK_BG"]
LIGHT_FG = os.environ["LIGHT_FG"]
DARK_FG = os.environ["DARK_FG"]

# Optional: send a message first so the transcript (not just the shell) is painted.
PROMPT = os.environ.get("PROMPT", "")

SAMPLE = """
(testid) => {
  // Count the PAINTED palette across real elements. Never sample document.body:
  // the RN-web root is transparent under both schemes, so an assertion against
  // it passes vacuously.
  const bgCount = {}, fgCount = {};
  for (const el of document.querySelectorAll('*')) {
    const cs = getComputedStyle(el);
    const bg = cs.backgroundColor;
    if (bg && bg !== 'rgba(0, 0, 0, 0)') bgCount[bg] = (bgCount[bg] || 0) + 1;
    const fg = cs.color;
    if (fg) fgCount[fg] = (fgCount[fg] || 0) + 1;
  }
  const top = (o) => Object.entries(o).sort((a, b) => b[1] - a[1]);
  return {
    topBackgrounds: top(bgCount),
    topTextColors: top(fgCount),
    togglePresent: Boolean(document.querySelector(`[data-testid="${testid}"]`)),
    toggleCount: document.querySelectorAll(`[data-testid="${testid}"]`).length,
  };
}
"""


async def session_for(browser, color_scheme):
    """Log in under one OS colour-scheme preference and sample the painted UI."""
    ctx = await browser.new_context(
        viewport={"width": 1440, "height": 1000}, color_scheme=color_scheme
    )
    page = await ctx.new_page()
    await page.goto(APP, wait_until="domcontentloaded")
    await page.wait_for_timeout(2500)

    if EMAIL:
        await page.get_by_test_id(EMAIL_TESTID).fill(EMAIL)
        await page.get_by_test_id(PW_TESTID).fill(PW)
        await page.get_by_test_id(SUBMIT_TESTID).click()
        await page.wait_for_timeout(6000)

    if PROMPT:
        await page.get_by_test_id("composer-input").fill(PROMPT)
        await page.get_by_test_id("composer-send").click()
        # Wait for the explicit streaming probe, not a timeout (see SKILL.md 8.9).
        for _ in range(160):
            await page.wait_for_timeout(400)
            if await page.evaluate(
                "() => Boolean(document.querySelector('[data-testid=\"turn-idle\"]'))"
            ):
                break
        await page.wait_for_timeout(1500)

    # Open whatever contains the toggle, so its absence is really tested.
    try:
        await page.get_by_test_id(TOGGLE_OPENER).click()
        await page.wait_for_timeout(1200)
    except Exception:  # noqa: BLE001  — opener may be absent on wide viewports
        pass

    data = await page.evaluate(SAMPLE, THEME_TESTID)
    await ctx.close()
    return data


async def main():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        print("== A. OS preference: light ==")
        light = await session_for(browser, "light")
        print(json.dumps(light, indent=2))

        print("\n== B. OS preference: DARK (the decisive test) ==")
        dark = await session_for(browser, "dark")
        print(json.dumps(dark, indent=2))
        await browser.close()

    print("\n================ VERDICT ================")
    ok = True

    for label, s in (("light-OS", light), ("dark-OS", dark)):
        if s["togglePresent"]:
            print(f"FAIL [{label}] the theme toggle is still present")
            ok = False
        else:
            print(f"PASS [{label}] theme toggle absent ({s['toggleCount']} in DOM)")

        bgs = [c for c, _ in s["topBackgrounds"]]
        if DARK_BG in bgs:
            print(f"FAIL [{label}] the DARK background token is being painted")
            ok = False
        elif LIGHT_BG not in bgs:
            # Positive proof required: absence of dark is also what a blank
            # page (or a failed render) reports.
            print(f"FAIL [{label}] LIGHT background token not painted: {bgs}")
            ok = False
        else:
            print(f"PASS [{label}] light palette painted ({LIGHT_BG})")

        fgs = [c for c, _ in s["topTextColors"]]
        if DARK_FG in fgs:
            print(f"FAIL [{label}] dark-scheme text colour is being painted")
            ok = False
        elif LIGHT_FG not in fgs:
            print(f"FAIL [{label}] light text colour missing: {fgs}")
            ok = False
        else:
            print(f"PASS [{label}] light text colour painted ({LIGHT_FG})")

    # Compare the SET of painted colours, not ranked counts: counts vary with
    # incidental DOM state (sidebar open, row count) and produce false failures.
    lp = {c for c, _ in light["topBackgrounds"]}
    dp = {c for c, _ in dark["topBackgrounds"]}
    if lp == dp:
        print("PASS identical palette under both OS preferences")
    else:
        print("FAIL the app paints a different palette when the OS asks for dark:")
        print(f"   only under light-OS: {sorted(lp - dp)}")
        print(f"   only under dark-OS : {sorted(dp - lp)}")
        ok = False

    print("\n" + ("DARK MODE IS DISABLED" if ok else "DARK MODE CHECKS FAILED"))
    print("Reminder: re-run this after re-enabling the fallback to confirm it "
          "FAILS — a verifier that cannot fail proves nothing.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
