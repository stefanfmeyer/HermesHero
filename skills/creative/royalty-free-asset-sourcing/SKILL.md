---
name: royalty-free-asset-sourcing
description: "Find and download royalty-free graphics for design work: company logos from Wikimedia Commons, emoji/icon SVGs from OpenMoji, illustrations from unDraw. Includes SVG-to-PNG conversion and attribution requirements. Use when a design needs real brand logos, science/medical emoji, or open-source illustrations and you need to source them quickly without licensing issues."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [design, assets, svg, emoji, logo, royalty-free, open-source, branding]
    related_skills: [claude-design, html-artifact, popular-web-designs]
---

# Royalty-Free Asset Sourcing

When a design needs real graphics (logos, emoji, illustrations), use these sources.
All are free to use with attribution or fully public domain. Verify licensing on
the specific asset page before using.

## Company Logos

### Wikimedia Commons

Many corporate logos are uploaded as SVG, often tagged public domain (PD-text) for
simple text/wordmark logos.

**Workflow:**
1. Search: `site:commons.wikimedia.org {company} logo svg` or visit the Wikipedia page
   for the company and check the logo file page.
2. Direct download: `https://upload.wikimedia.org/wikipedia/commons/{path}/{filename}.svg`
3. Check the licensing section on the file page. Trademark restrictions may still
   apply even if copyright doesn't (PD-text covers simple wordmarks).
4. Download: `curl -sL "https://upload.wikimedia.org/wikipedia/commons/.../logo.svg" -o logo.svg`

**Example:** LGC Ltd logo at `File:LGC_Ltd_logo.svg` (public domain, teal circular badge, 809 bytes).

### Brandfetch

`https://brandfetch.com/{domain}` aggregates brand assets (logos, colors, fonts).
Sometimes fails to fetch via web_extract; use browser as fallback.

## Emoji / Icon SVGs

### OpenMoji (CC-BY-SA 4.0)

Open-source emoji set, 700+ emoji as individual SVG files. Compact (1-7KB each),
self-contained, ideal for web use.

**URL pattern:** `https://openmoji.org/data/color/svg/{CODEPOINT}.svg`

Codepoint is the Unicode hex without `U+` prefix, uppercase.

**Common emoji codepoints:**

| Emoji | Codepoint | URL |
|-------|-----------|-----|
| Trophy | 1F3C6 | `https://openmoji.org/data/color/svg/1F3C6.svg` |
| Gold medal | 1F947 | `https://openmoji.org/data/color/svg/1F947.svg` |
| Silver medal | 1F948 | `https://openmoji.org/data/color/svg/1F948.svg` |
| Bronze medal | 1F949 | `https://openmoji.org/data/color/svg/1F949.svg` |
| Test tube | 1F9EA | `https://openmoji.org/data/color/svg/1F9EA.svg` |
| Microscope | 1F52C | `https://openmoji.org/data/color/svg/1F52C.svg` |
| DNA | 1F9EC | `https://openmoji.org/data/color/svg/1F9EC.svg` |
| Brain | 1F9E0 | `https://openmoji.org/data/color/svg/1F9E0.svg` |
| Light bulb | 1F4A1 | `https://openmoji.org/data/color/svg/1F4A1.svg` |
| Party popper | 1F389 | `https://openmoji.org/data/color/svg/1F389.svg` |
| Beer | 1F37A | `https://openmoji.org/data/color/svg/1F37A.svg` |
| Coffee | 2615 | `https://openmoji.org/data/color/svg/2615.svg` |
| Hourglass | 23F3 | `https://openmoji.org/data/color/svg/23F3.svg` |
| Chart | 1F4CA | `https://openmoji.org/data/color/svg/1F4CA.svg` |
| Target | 1F3AF | `https://openmoji.org/data/color/svg/1F3AF.svg` |

**Download batch:**
```bash
curl -sL "https://openmoji.org/data/color/svg/1F3C6.svg" -o emoji-trophy.svg
curl -sL "https://openmoji.org/data/color/svg/1F947.svg" -o emoji-gold-medal.svg
curl -sL "https://openmoji.org/data/color/svg/1F948.svg" -o emoji-silver-medal.svg
curl -sL "https://openmoji.org/data/color/svg/1F949.svg" -o emoji-bronze-medal.svg
```

**Attribution required:** "OpenMoji CC-BY-SA 4.0" in footer or credits.

### Twemoji (MIT code, CC-BY graphics)

Twitter's emoji set. CDN: `https://cdnjs.cloudflare.com/ajax/libs/twemoji/...`.
Graphics licensed CC-BY, code licensed MIT.

## Illustrations

### unDraw (MIT license, open source)

`https://undraw.co/` hundreds of customizable illustrations. Can recolor to match
brand palette on the website before downloading SVG. Search by keyword: science,
chemistry, laboratory, medical, etc. No attribution required (though appreciated).

## SVG to PNG Conversion

When a PNG version is needed (e.g. for broader browser compatibility or image
fallbacks):

```bash
pip install cairosvg --break-system-packages
python3 -c "import cairosvg; cairosvg.svg2png(url='logo.svg', write_to='logo.png', output_width=400, output_height=400)"
```

On the workstation, `--break-system-packages` is required for pip install (Debian PEP 668).

## Using Assets in Next.js

Place SVGs in `public/` directory. Reference as `<img src="/logo.svg" alt="..." />`.
For inline SVG animations (bubbling, rotating), author custom SVGs directly rather
than downloading static ones.

## Chemical Structure Images

### PubChem (primary source for real structures)

PubChem (NCBI, US government) provides real 2D chemical structure PNGs via a
simple REST API. These are actual accurate molecular diagrams, not hand-drawn
approximations. **Always use PubChem for chemical structure images.**

**URL pattern:**
```
https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{CID}/PNG?record_type=2d&image_size=300x300
```

**Common CIDs:**

| Compound | CID | URL |
|----------|-----|-----|
| Caffeine | 2519 | `.../cid/2519/PNG?record_type=2d&image_size=300x300` |
| Morphine | 5288826 | `.../cid/5288826/PNG?...` |
| Cocaine | 446155 | `.../cid/446155/PNG?...` |
| THC | 16078 | `.../cid/16078/PNG?...` |
| Aspirin | 2244 | `.../cid/2244/PNG?...` |
| Ethanol | 702 | `.../cid/702/PNG?...` |
| Glucose | 5793 | `.../cid/5793/PNG?...` |

**Download:**
```bash
curl -sL "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/2519/PNG?record_type=2d&image_size=300x300" -o struct-caffeine.png
```

Files are small (1-4KB), 300x300px, transparent background, public domain
(US government work). No attribution required.

To find a CID: search at `https://pubchem.ncbi.nlm.nih.gov/compound/{name}` or
use the REST API: `.../pug/compound/name/{name}/cids/JSON`.

### Do NOT hand-draw chemical structure SVGs

Hand-drawing chemical structures as SVG polygons results in inaccurate,
nonsensical diagrams that a trained scientist will immediately recognize as
wrong. The user explicitly rejected this approach. Use PubChem for real
structures. Only author original SVGs for decorative illustrations (flasks,
DNA helices, lab equipment) where scientific accuracy of a specific molecule
is not required.

### Wikimedia Commons for chemical structures (fallback)

Some chemical structure SVGs exist on Wikimedia Commons (public domain), but
downloading them via curl is unreliable due to rate limiting (429) and
unpredictable hash directory paths. If using this approach:

1. Use the Commons API to get the actual file URL:
```bash
curl -sL "https://commons.wikimedia.org/w/api.php?action=query&titles=File:Morphine.svg&prop=imageinfo&iiprop=url&format=json"
```
2. Extract the `url` field from the JSON response
3. Download with a browser-like User-Agent header
4. Some SVGs have embedded text that may not render in all browsers - test

Prefer PubChem PNGs for reliability.

See `references/nextjs-fun-design-patterns.md` for the full LGC quiz case study
including PubChem workflow, animated backgrounds, confetti implementation,
and Prisma/deployment gotchas.

## Pitfalls

- **Wikimedia SVGs can be large** or contain embedded raster data. Check file size
  before using. The LGC logo was 809 bytes (ideal), but some logos are 100KB+.
- **OpenMoji SVGs are compact** (1-7KB each) and self-contained. Ideal for web use.
- **unDraw illustrations can only be recolored via their website** color picker, not
  post-download. The SVG uses hardcoded fills.
- **Always check trademark restrictions separately from copyright.** A public domain
  logo may still be a registered trademark. Using it for the actual company's own
  event/booth is typically fine; using it for unrelated commercial work may not be.
- **OpenMoji attribution is required.** Include "OpenMoji CC-BY-SA 4.0" somewhere
  visible (footer, about page, credits).
- **Don't use Flaticon free tier** without reading their attribution requirements.
  It requires visible attribution, which may not suit all designs.
- **Hand-drawn chemical structure SVGs are nonsensical.** Do NOT attempt to
  author chemical structures as inline SVG polygons. A PhD-level audience will
  immediately see they are wrong. Use PubChem PNGs (see "Chemical Structure
  Images" section above) for any molecular diagram that needs to be scientifically
  accurate. Original SVG authoring is fine for decorative illustrations (flasks,
  DNA helices, lab equipment) but not for specific molecular structures.
- **Wikimedia Commons rate-limits curl (429).** Direct `curl` to
  `upload.wikimedia.org` may return 429 or HTML error pages. Use the Commons API
  (`commons.wikimedia.org/w/api.php`) to get the real file URL, and include a
  browser-like User-Agent header. PubChem is more reliable for chemical structures.
- **Leaderboard medal mapping:** when using emoji SVGs for rank positions (1st/2nd/3rd),
  map each rank to a distinct SVG. Using the same chart emoji for both 2nd and 3rd
  is a bug. Use `emoji-silver-medal.svg` (1F948) and `emoji-bronze-medal.svg` (1F949)
  respectively.

## Support Files

- `references/nextjs-fun-design-patterns.md` - Next.js fun design patterns, PubChem
  structure workflow, progress bar fix, Prisma gotchas, Tailscale deployment.
  Learned from the LGC Conference Quiz project.