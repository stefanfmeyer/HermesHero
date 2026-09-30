# PDF Text Extraction Artifacts in Catalogue/Form Comparisons

When comparing text extracted from PDF documents, systematic artifacts appear that are NOT genuine content discrepancies. This reference catalogues every artifact pattern observed in real AXIO catalogue vs application form comparisons, with examples and guidance on how to handle each.

## 1. Missing Spaces in Microbiological Species Names

**Pattern:** The catalogue PDF extraction drops the space between a genus name and "species" (or between "coli" and "O157").

**Examples from AXIO catalogue:**
- "Salmonellaspecies" → should be "Salmonella species"
- "Campylobacterspecies" → should be "Campylobacter species"
- "Escherichia coliO157" → should be "Escherichia coli O157"
- "Listeriaspecies" → should be "Listeria species"
- "Clostridiumspecies" → should be "Clostridium species"
- "Enterocoocusspecies" → should be "Enterococcus species" (note: catalogue has typo "Enterocoocus" — form has correct spelling "Enterococcus"; see also artifact #13)
- "Vibriospecies" → should be "Vibrio species"
- "Pseudomonasspecies" → should be "Pseudomonas species"

**Guidance:** These are PDF extraction artifacts in the catalogue, not content errors. The form versions have the correct spaces. Do NOT flag these as discrepancies — note them once as a general artifact and exclude from the discrepancy list.

## 2. Empty Analytes Cells

**Pattern:** A catalogue entry's analytes cell is completely empty in the text extraction, even though the form has a full list of analytes for the same sample.

**Example from AXIO catalogue:**
- PT-CH-76 (QDCS Nutritional Information): Form has "Fat; Saturates; Carbohydrate; Total sugars; Protein; Salt; Fibre; Docosahexaenoic acid (DHA); Arachidonic acid (ARA); β-galactooligosaccharides (GOS); Chloride NEW; Nitrogen (total) NEW; Choline NEW; Vitamin K1 (cis + trans) NEW; Iodine NEW; Non-protein nitrogen NEW" but the catalogue shows only "PT-CH-76 *  150g  Infant formula" with no analytes text.

**Cause:** The analytes text was in a different PDF column or text layer that didn't extract properly. The text may be present in the visual PDF but absent from the text extraction.

**Guidance:** Flag as "data absent from catalogue (likely PDF extraction issue)" but do NOT assume the catalogue is wrong — it may be correct in the original PDF. Recommend visual verification of the original PDF.

## 3. Duplicated Entries from Two-Column Layouts

**Pattern:** Catalogue PDFs with two-column page layouts may produce text where the same entries appear twice — once from each column's extraction pass.

**Example from AXIO catalogue (QCS Chemistry section):**
- PT-CT-715, PT-CT-716, PT-CT-718, PT-CT-719, PT-CT-723 all appear TWICE in the catalogue text (lines 752-770 and again at lines 772-787) with identical content.

**Guidance:** Recognise this pattern: identical sample codes, quantities, and matrices appearing twice in sequence. Treat as a single set of entries — do not flag the duplication as a discrepancy. The catalogue simply has a two-column layout that was extracted sequentially.

## 4. Line Breaks Splitting Cell Content

**Pattern:** Matrix or analytes entries are split across multiple lines in the text extraction, making it appear as though there are separate entries or different formatting.

**Examples:**
- "Dried petfood/kibble" appears in the catalogue as "Dried petfood/" on one line and "kibble" on the next — this is a single cell, not two entries.
- "Low quality Cocoa Powder" appears as "Low quality Cocoa" on one line and "Powder" on the next.

**Guidance:** Reconstruct the full cell value by joining lines before comparing. Do not treat the line break as a content difference or a space difference.

## 5. Trailing Periods on Sample Codes

**Pattern:** Forms extracted from PDF may have trailing periods after sample codes that the catalogue does not (or vice versa).

**Examples from AXIO forms:**
- QDCS form: "PT-CH-68.", "PT-CH-70.", "PT-CH-71.", "PT-CH-72." (with periods)
- QCS form: "PT-CT-714.", "PT-CT-720." (with periods)
- AFPS form: "PT-AF-06AF.", "PT-AF-06KB.", "PT-AF-07AF.", "PT-AF-07KB." (with periods)
- Catalogue: same codes without periods

**Note:** Some sample codes have trailing periods in BOTH form and catalogue (e.g., "PT-CT-710." in both QCS form and catalogue). This is consistent — no discrepancy.

**Guidance:** Flag as a minor discrepancy (punctuation difference) but note it may be a formatting artifact of the PDF extraction rather than an intentional difference.

## 6. Round-Specific Designations in Forms vs Plain Names in Catalogue

**Pattern:** Forms consistently include round-specific designations for matrix entries while the catalogue lists the same matrices as plain names without round mapping.

**Examples across AXIO schemes:**
- QMAS: "MT357: Beef", "CH357: Cheshire", "CT357: Dark chocolate (min 75%)" → catalogue: "Beef", "Cheshire", "Dark chocolate (min 75%)"
- QFCS: "FC358: Crackers", "FC362: Breakfast cereal", "FC366: Biscuits" → catalogue: "Crackers", "Breakfast cereal", "Biscuits"
- QDCS: "CH357: Cheshire" → catalogue: "Cheshire"
- AFPS: "AF06AF:" style prefixes

**This is a consistent formatting difference across ALL schemes, NOT a content discrepancy.** The underlying matrix names match. The forms add round context that the catalogue omits.

**Guidance:** Note this pattern once in the report as a general formatting difference. Do not flag each individual instance as a separate discrepancy — they are all the same class of difference. When using the automated comparison technique, strip the prefix with a regex like `re.sub(r'^(FC|MT|CH|CT|AF)\d+:\s*', '', line)` before comparing matrix entries.

## 7. Matrix Entry Ordering Differences

**Pattern:** The order of matrix entries within a cell may differ between form and catalogue.

**Examples from QMAS Authenticity:**
- PT-MT-749: Form order = Beef, Lamb, Chicken, Pork; Catalogue order = Chicken, Beef, Lamb, Pork
- PT-MT-752: Form order = Raw fish, Cooked fish; Catalogue order = Cooked fish, Raw fish

**Guidance:** Flag as a genuine discrepancy (order difference) but note it may reflect different organisational logic (form orders by round, catalogue may order alphabetically or by a different key). The set of entries is the same — only the order differs.

## 8. Missing Samples (Genuine Absence)

**Pattern:** A sample code present in the form is completely absent from the catalogue (not just from the expected section — absent from the entire document).

**Examples from AXIO comparison:**
- QMAS form has PT-MT-734; catalogue has no PT-MT-734 anywhere
- QCS form has PT-CT-722 and PT-CT-724; catalogue has neither anywhere
- QDCS form has PT-CH-60; catalogue has no PT-CH-60 anywhere

**Verification method:** Use `search_files` with the exact sample code as a regex pattern across the reference document to confirm true absence.

**Guidance:** These are genuine discrepancies — the form includes samples the catalogue does not list. Flag as MAJOR. Possible causes: the catalogue was prepared before the form was finalised, the catalogue intentionally omits new/non-accredited samples, or there is a genuine error.

## 9. Different Sample Codes for the Same Entry

**Pattern:** The form and catalogue use different sample codes for what appears to be the same sample (same quantity, matrix, and analytes).

**Example from AXIO comparison:**
- QDCS Toxins: Form uses "PT-CH-60" for Aflatoxin M1 in Freeze-dried milk (25ml); catalogue uses "PT-CH-70" for the same entry. The catalogue also uses "PT-CH-70" in the Veterinary residues section (for antibiotics/beta lactams).

**Guidance:** This is a MAJOR discrepancy. Cross-check the form's CHANGES section for context (e.g., "We have added PT-CH-60 for Aflatoxin M1 in milk" confirms the form's code is intentional). The catalogue may have a duplicate/erroneous code.

## 10. Missing Footnote Markers on Analytes

**Pattern:** The form omits `#` footnote markers on analytes that are present in the catalogue (or vice versa).

**Example from QFCS comparison:**
- PT-FC-840 * (Pesticides, Pulses): Form has "Pesticides; Glyphosate; AMPA" but catalogue has "Pesticides; Glyphosate#; AMPA#". The `#` markers indicate the analytes are not currently within the scope of LGC's UKAS accreditation.
- PT-FC-841 * (Pesticides, Cereals): Same — form omits `#` on Glyphosate and AMPA.

**Guidance:** This is a GENUINE discrepancy, not an extraction artifact. The `#` markers carry accreditation-status meaning. Flag as a footnote marker difference in the Analytes column. Check whether the form has the corresponding `#` footnote definition text at the end of the section — even if the form omits the markers on the analytes themselves, it may still have the footnote definition text.

## 11. Quantity "-" in Form vs Blank in Catalogue

**Pattern:** The form shows "-" (a dash) in the quantity column where the catalogue leaves it blank (empty).

**Example from QFCS comparison:**
- PT-FC-818 * (Foreign bodies): Form shows "-" in the Quantity column; catalogue's Quantity column is blank for this entry.

**Guidance:** Flag as a minor discrepancy. The "-" and blank likely both mean "no quantity applicable" but the representation differs. Note in the report that this may be a formatting convention difference rather than a content error.

## 12. Form Has More Matrix Entries Than Catalogue (Including Duplicates)

**Pattern:** The form lists a matrix entry for every round it appears in, even if the same matrix repeats across rounds. The catalogue lists only unique matrix names. This can produce "extra" entries in the form that are actually duplicates.

**Example from QFCS comparison:**
- PT-FC-770 (Nutritional Information): Form has 4 matrix entries: "FC358: Crackers / FC362: Breakfast cereal / FC366: Biscuits / FC367: Breakfast cereal". Catalogue has 3: "Crackers / Breakfast cereal / Biscuits". The form's 4th entry ("FC367: Breakfast cereal") is a duplicate of the 2nd entry ("FC362: Breakfast cereal") — the same matrix in a different round. The catalogue doesn't repeat it.
- PT-FC-774 (Nutritional Information): Form has 6 entries including "Cured meat" (FC358 and FC364) and "Hard cheese" (FC362 and FC367). Catalogue has all 6 entries listed sequentially (Cured meat, Jam, Hard cheese, Cured meat, Biscuits, Hard cheese) — in this case the catalogue DOES repeat entries to match the form's round-by-round listing.

**Guidance:** When the form has more matrix entries than the catalogue after stripping round prefixes, check whether the extra entries are duplicates of existing entries (same matrix name in a different round). If so, report as a duplicate entry (see Phase 5 of the skill) AND as a matrix discrepancy (the catalogue doesn't list that round's entry). Note that the catalogue's behaviour is inconsistent — sometimes it repeats matrices for each round, sometimes it lists only unique names.

## 13. Typo + Missing Space Combination (Genuine Catalogue Error)

**Pattern:** The catalogue contains a word that is both misspelled AND concatenated with the following word (missing space). The form has the correct spelling with proper spacing. This is a genuine error in the catalogue (not just a PDF extraction artifact) because the misspelling is in the source text itself.

**Example from AXIO catalogue:**
- PT-MT-769 (QMAS Microbiological Testing): Catalogue has "Enterocoocusspecies" — both misspelled ("Enterocoocus" instead of "Enterococcus") AND missing space ("species" concatenated). The form has "Enterococcus species" (correct spelling with space).

**Guidance:** Flag as TWO issues: (1) a spelling discrepancy and (2) a spacing discrepancy. Note that the misspelling is a genuine content error in the catalogue, not a PDF extraction artifact — the letters are wrong, not just the spacing. This should also be flagged in the Latin/scientific names italicisation check since "Enterococcus species" requires italics.

## 14. Matrix Entry Moved Between Samples (Form vs Catalogue)

**Pattern:** A matrix entry that appears under one sample code in the catalogue appears under a different sample code in the form. The set of matrix entries across both samples is the same, but the assignment differs.

**Example from AFPS comparison:**
- Catalogue: PT-AF-02 has matrices "Sheep feed / Cattle feed / Poultry feed" (no Pig feed); PT-AF-05 has "Pig feed / Cattle feed"
- Form: PT-AF-02 has "AF064: Sheep feed / AF065: Cattle feed / AF066: Poultry feed / AF067: Pig feed" (includes Pig feed); PT-AF-05 has only "Cattle feed" (no Pig feed)
- The "Pig feed" matrix appears to have been moved from PT-AF-05 to PT-AF-02 in the form.

**Guidance:** Flag as separate discrepancies for each affected sample: (1) PT-AF-02 has an extra matrix entry ("Pig feed") not in the catalogue, and (2) PT-AF-05 is missing a matrix entry ("Pig feed") that the catalogue has. Note in the report that the matrix may have been reassigned between samples.