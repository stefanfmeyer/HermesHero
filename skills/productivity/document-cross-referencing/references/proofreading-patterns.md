# General Proofreading Patterns for PDF Documents

Patterns discovered during the AXIO catalogue 2026 proofreading pass. These are general
issues that apply to any professionally typeset PDF being checked for quality.

## 1. Semicolons Overlapping Words

**Pattern:** A semicolon runs directly into the next word with no space after it.
This is a genuine typesetting error, not a PDF extraction artifact.

**Detection regex:**
```python
import re
# Find letter;letter (no space after semicolon)
matches = re.finditer(r'[a-zA-Z];[a-zA-Z]', text)
```

**Real examples from AXIO catalogue (AQUACHECK section, page 75):**
- `Fenpropimorph;Flutriafol` — should be `Fenpropimorph; Flutriafol`
- `Cyproconazole;Tebuconazole` — should be `Cyproconazole; Tebuconazole`
- `Microcystin-RR;Total Microcystin` — should be `Microcystin-RR; Total Microcystin`

**Also found in application forms** (same analyte lists), confirming these are
source errors not extraction artifacts.

## 2. Missing Spaces Between Words (Compound Word Errors)

**Pattern:** Two words that should be separate are concatenated. This can be a
typesetting error or a PDF extraction artifact — verify by checking the visual PDF.

**Detection:** Look for lowercase→uppercase transitions (`[a-z][A-Z]`) that are NOT
known abbreviations. Skip common pairs: pH, mL, mM, kDa, PCR, DNA, RNA, etc.

**False positive filters:**
- Chemical nomenclature like `p,p'-DDT` and `o,p-DDT` — the comma is part of the
  chemical isomer notation, NOT a missing space
- `NaOH`, `RoHS`, `MoCRA` — these are acronyms/chemical formulas, not missing spaces
- `20oC` — this is "20 degrees C" where the degree symbol was lost in extraction;
  flag as a missing-degree-symbol issue, not a missing-space issue

## 3. Comma Overlapping Words

**Pattern:** A comma runs directly into the next word with no space.
Similar to semicolon overlap but less common.

**Detection regex:**
```python
matches = re.finditer(r'[a-zA-Z],[a-zA-Z]', text)
```

**False positive:** `p,p'-DDT` style chemical nomenclature — the `p,p` is NOT a
comma overlap; it's standard chemical isomer notation. Filter these out.

**False positive:** Checkbox/option lists like `A-FULL,A-REDUCED,B-FULL,B-REDUCED`
— these are compact coded labels, not prose text with missing spaces.

## 4. Catalogue Spelling Errors (Genuine Content Errors)

These are actual typos in the catalogue source text (not extraction artifacts).
They were found by cross-referencing the application form (correct spelling) against
the catalogue (misspelled).

**Examples from AXIO catalogue 2026:**
- `cofef e` should be `coffee` (appears in QFCS section, multiple samples)
- `Decafef inated` should be `Decaffeinated`
- `quantifai ble` should be `quantifiable`
- `Bufef r` should be `Buffer` (QDCS PT-CH-32B)
- `flitered` should be `filtered` (DAPS PT-DP-B5 "Non chill flitered whisky")
- `fal mmability` should be `flammability` (TOYTEST)
- `fal kes` should be `flakes` (TOYTEST)
- `Difef rential` should be `Differential` (COSMETICS)
- `Cafef ine` should be `Caffeine` (QCS, PHARMASSURE)

**Pattern:** These look like letter-swapping errors from the typesetting process
(likely InDesign or similar). The errors are consistent — the same misspelling
appears every time the word is used, suggesting it's in the source text, not
a one-time extraction glitch.

**Detection method:** Cross-reference analytes/matrix text between app forms and
catalogue. If the app form has the correct spelling and the catalogue doesn't,
it's a genuine catalogue spelling error.

## 5. Degree Symbol Loss

**Pattern:** Temperature values lose the degree symbol in PDF extraction.
`20°C` becomes `20oC` in text extraction. This is an extraction artifact, not a
content error, but it's worth flagging because it indicates the degree symbol
may not be rendering correctly.

**Detection:** Look for patterns like `\d+oC` (digit + lowercase o + C) which
should be `\d+°C`.