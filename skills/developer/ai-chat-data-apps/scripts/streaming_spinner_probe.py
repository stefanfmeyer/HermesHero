#!/usr/bin/env python3
"""Per-message streaming-spinner census for an LLM chat UI.

Why this script exists
----------------------
"Show the loading spinner only on the NEW assistant message, never on previous
replies" is a bug that a total count cannot detect. The buggy implementation
puts one spinner on EVERY assistant bubble in the thread, so `total >= 1`
passes while the user is looking at a screenshot with two spinners in it.
You must count spinners PER MESSAGE and assert that the only one is on the
last child of the message list.

The probe deliberately scopes to the message-list root (a container whose
className contains `space-y-8`) because the COMPOSER pill in this app family
shares `bg-card rounded-[28px]` with the assistant bubbles. Matching on those
classes alone silently includes the composer and corrupts the ordering — the
first version of this probe reported a false "spinner on earlier message".

Usage
-----
    /tmp/pw-venv/bin/python scripts/streaming_spinner_probe.py \
        --url https://app.example --email you@example.com --password '...' \
        [--conv-title 'My chat']

Requires a Playwright mobile context — see references/mobile-e2e-playwright.md
for venv/browser setup. Pass --headed to watch it.

Exit code 0 = all assertions passed; 1 = a real product regression.
"""

import argparse
import asyncio
import json
import sys

from playwright.async_api import async_playwright

# Scoped to the message-list root only. Adjust the class marker to match the
# app's list container if it does not use `space-y-8`.
PROBE = """() => {
    const root = [...document.querySelectorAll('div')].find(d =>
        typeof d.className === 'string' && d.className.trim() === 'space-y-8');
    if (!root) return {error: 'message list root not found'};
    const kids = [...root.children];
    const spinSel = 'span[aria-label="Assistant is responding"]';
    return {
        msgCount: kids.length,
        totalSpinners: root.querySelectorAll(spinSel).length,
        perMsg: kids.map((k, i) => ({
            i,
            spin: k.querySelectorAll(spinSel).length,
            role: k.className.includes('items-end') ? 'user' : 'asst',
            txt: k.innerText.trim().replace(/\\s+/g, ' ').slice(0, 24),
        })),
        spinnerOnLast: kids.length > 0 &&
            !!kids[kids.length - 1].querySelector(spinSel),
        spinnerOnEarlier: kids.slice(0, -1)
            .some(k => !!k.querySelector(spinSel)),
    };
}"""


async def run(args) -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not args.headed)
        ctx = await browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True,
        )
        page = await ctx.new_page()
        errors = []
        page.on(
            "console",
            lambda m: errors.append(m.text[:180]) if m.type == "error" else None,
        )

        # --- real login: every fresh context starts logged out ---
        await page.goto(args.url + "/login")
        await page.fill('input:not([type="password"])', args.email)
        await page.fill('input[type="password"]', args.password)
        await page.click('button:has-text("Sign in")')
        await page.wait_for_url("**/chat", timeout=20000)
        await page.wait_for_timeout(2500)

        # --- establish a PRIOR assistant reply, or the bug is unreproducible ---
        # Without an earlier assistant bubble on screen there is nothing for the
        # spinner to wrongly attach to, and the test passes vacuously.
        if args.seed:
            await page.evaluate(
                "(v) => localStorage.setItem('ama_conversations', v)", args.seed
            )
            await page.reload()
            await page.wait_for_timeout(2500)
            await page.click('button[title="Toggle menu"]')
            await page.wait_for_timeout(600)
            # The row's inner text node is pointer-events-none — click the ROW.
            await page.click("aside nav > div.relative.overflow-hidden > div")
            await page.wait_for_timeout(1500)

        before = await page.evaluate(PROBE)
        if before.get("error"):
            print(f"ABORT: {before['error']}", file=sys.stderr)
            return 1
        print(f"BEFORE SEND: msgs={before['msgCount']} "
              f"spinners={before['totalSpinners']}")
        for m in before["perMsg"]:
            print("   ", m)

        await page.fill("textarea", args.prompt)
        await page.wait_for_timeout(300)
        await page.click('button[aria-label="Send"]')
        print("\nSENT — polling the stream...")

        states, violation, max_simultaneous = [], False, 0
        for _ in range(args.polls):
            s = await page.evaluate(PROBE)
            if s.get("totalSpinners", 0) > 0:
                max_simultaneous = max(max_simultaneous, s["totalSpinners"])
                if s.get("spinnerOnEarlier"):
                    violation = True
                sig = (s["msgCount"], s["totalSpinners"], s["spinnerOnLast"])
                if not states or states[-1][0] != sig:
                    states.append((sig, s["perMsg"]))
            elif states:
                break
            await page.wait_for_timeout(120)

        print("\n(msgCount, spinners, spinnerOnLast) -> per message:")
        for sig, per in states:
            print(" ", sig, "->",
                  [f"{m['role']}#{m['i']}:spin={m['spin']}" for m in per])

        await page.wait_for_timeout(4000)
        final = await page.evaluate(PROBE)

        print("\n--- RESULTS ---")
        print("max spinners simultaneously:", max_simultaneous, "(must be 1)")
        print("spinner EVER on an earlier message:", violation, "(must be False)")
        print("after completion:", final.get("totalSpinners"), "(must be 0)")
        print("console errors:", errors)

        ok = (
            max_simultaneous == 1
            and not violation
            and final.get("totalSpinners") == 0
            and bool(states)
        )
        print("\nVERDICT:", "PASS" if ok else "FAIL")
        await browser.close()
        return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", required=True, help="app base URL, no trailing /")
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--prompt", default="List my campaigns")
    ap.add_argument("--polls", type=int, default=200)
    ap.add_argument("--headed", action="store_true")
    ap.add_argument(
        "--conv-title",
        help="title of an existing conversation to open first (optional)",
    )
    ap.add_argument(
        "--seed",
        help="JSON string of conversations to seed into localStorage so a PRIOR "
             "assistant reply is on screen. Strongly recommended.",
    )
    args = ap.parse_args()
    if args.conv_title and not args.seed:
        args.seed = json.dumps([{
            "id": "conv1",
            "title": args.conv_title,
            "updatedAt": 4,
            "messages": [
                {"id": "u1", "role": "user",
                 "content": "How did my campaigns do yesterday?"},
                {"id": "a1", "role": "assistant",
                 "content": "Your campaigns ran normally yesterday."},
            ],
        }])
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
