---
name: document-cross-referencing
description: "Cross-reference and proofread structured tabular data across multiple text-extracted documents (PDFs, forms, catalogues). Compare column-by-column, flag discrepancies in wording/punctuation/codes/ordering, check for duplicate entries, and produce a structured discrepancy report. Use when the user asks to compare forms against a catalogue, cross-reference documents, proofread tabular data, or verify consistency between a source document and a reference."
version: 1.0.0
metadata:
  hermes:
    tags: [proofreading, cross-referencing, documents, qa, comparison, catalogue, forms]
    related_skills: [dogfood, ocr-and-documents]
---

# Document Cross-Referencing & Proofreading

## Overview

Systematic column-by-column comparison of structured tabular data across multiple text-extracted documents (typically PDF-to-text). The task: verify that entries in a set of forms/match a reference catalogue, flagging every discrepancy in the first N columns (usually Sample Code, Quantity, Matrix, Analytes), and checking for duplicate entries within cells.

## When to Use

- User asks to "cross-reference", "proofread", "compare", or "verify" forms/catalogues/documents against each other
- User provides multiple document files and a reference file, asking for discrepancies
- User asks to check for consistency between a form and a catalogue (e.g., "compare these application forms against the AXIO catalogue")
- User asks to find duplicate entries within cells of a tabular document

## Inputs

The user typically provides:
1. **Source documents** — forms, spreadsheets, or data files to check (usually text-extracted from PDF)
2. **Reference document** — the catalogue or master reference to compare against
3. **Columns to compare** — which columns must match (e.g., Sample Code, Quantity, Matrix, Analytes)
4. **Section mapping** — which sections of each source document correspond to which sections of the reference

## Workflow

### Phase 1: Read All Files in Parallel

Read ALL source documents AND the reference document in a single batch of parallel `read_file` calls. Do not read them one at a time — the content is independent and parallel reads save round-trips.

If any file is truncated (>500 lines), note the `next_offset` and continue reading in a subsequent batch. Large catalogues may need 2-3 reads to cover all relevant sections.

### Phase 2: Map the Structure

For each document, identify:
- Section headers (e.g., "Nutritional Information", "Elements", "Additives") — these may appear as short text lines before the table on each page
- Column headers (e.g., "Sample Code | Quantity | Supplied As | Target Analytes") — usually the first row of each table
- Row entries (one per sample code)
- Footnotes and markers (*, #, ^, †, NEW)

Map which sections of each source document correspond to which sections of the reference catalogue (the user usually provides this mapping).

**Technique for identifying section/sub-section headers with pymupdf:** Scan each page's text lines BEFORE the first table starts. Filter out common headers/footers (page numbers, "lgcstandards.com", running titles). The remaining short text lines are likely section or sub-section headings. Build a mapping of page index → section name → sub-section name (if present). For multi-page sections, the sub-section heading may only appear on the first page of that section.

```python
import pymupdf
doc = pymupdf.open("catalogue.pdf")
for i in range(len(doc)):
    text = doc[i].get_text("text")
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for l in lines:
        # Skip known headers/footers
        if any(skip in l for skip in ['lgcstandards.com', 'AXIO |', 'Proficiency Testing']):
            continue
        if l.startswith('Sample Code') or l.startswith('PT-'):
            break  # Table data starts here
        if l.startswith('The full range') or l.startswith('*') or l.startswith('#'):
            continue
        if 3 < len(l) < 80:
            print(f"Page {i}: {l}")  # Candidate heading
            break
```

### Phase 3: Column-by-Column Comparison

For each section, for each sample code row, compare the four columns:

1. **Sample Code** — exact match including asterisks, "NEW" markers, trailing periods
2. **Quantity** — exact match including units and formatting
3. **Matrix / Supplied As** — exact match including wording, order, round-specific designations
4. **Analytes / Target Analytes** — exact match including semicolons, NEW markers, footnote markers

Flag ANY discrepancy:
- Different/missing/extra sample codes
- Different quantities or units
- Differences in Matrix wording, missing/additional entries
- Different/missing/additional Analytes
- Spelling, punctuation, capitalisation differences
- Differences in footnote markers (* or #) or NEW markers
- Order differences where genuine

### Phase 4: Check for Missing/Extra Entries

After comparing individual rows, check at the section level:
- Are there sample codes in the form that are **missing from the catalogue**?
- Are there sample codes in the catalogue that are **missing from the form**?
- Use `search_files` with the sample code as a regex pattern to confirm presence/absence across the reference document.

### Phase 5: Duplicate Entry Check

For each Matrix cell in each form, check for duplicate entries — the same complete matrix entry repeated within the same cell. Report:
- Application Form name
- Section
- Sample Code
- Duplicate entry
- Exact Matrix cell content

**Key distinction:** Flag only when the SAME complete entry/phrase is repeated within a cell (e.g., "Cured meat / Jam / Hard cheese / Cured meat / Biscuits / Hard cheese" → flag "Cured meat" and "Hard cheese"). Do NOT flag when individual words happen to repeat across different entries (e.g., "Ground black pepper / Ground white pepper" should NOT be flagged even though "Ground" and "pepper" appear twice — these are different matrix entries).

### Phase 5b: General Proofreading (Semicolon/Spacing Issues)

In addition to cross-referencing, perform general proofreading checks on BOTH the catalogue and all forms:

1. **Semicolons overlapping words** — e.g., `word;word` where a semicolon runs directly into the next word without a space. Pattern: `[a-z];[a-zA-Z]` (letter immediately after semicolon with no space).
2. **Missing spaces between words** — e.g., `wordword` where two words are concatenated. This is harder to detect programmatically; look for camelCase transitions or known word boundary issues. Common patterns: `speciesin` → `species in`, `powderOatmeal` → `powder Oatmeal`.
3. **Other spacing issues** — double spaces, missing spaces after punctuation (`.`, `,`, `:`), tabs appearing mid-word.

Use a regex scan and flag each occurrence with the page number and the surrounding context.

### Phase 5c: Italic Check — Handling Documents with No Italic Fonts

**Critical first step:** Check whether ANY italic formatting exists in the source documents before assuming terms should be italicised. Extract font info from all PDFs:

```python
import pymupdf
doc = pymupdf.open("document.pdf")
all_fonts = set()
italic_count = 0
for page in doc:
    for block in page.get_text("dict")["blocks"]:
        if "lines" not in block: continue
        for line in block["lines"]:
            for span in line["spans"]:
                all_fonts.add(span["font"])
                if span["flags"] & 2:  # bit 1 = italic
                    italic_count += 1
print(f"Fonts: {sorted(all_fonts)}")
print(f"Italic spans: {italic_count}")
```

If NO italic spans exist in ANY document (which is common for corporate/catalogue PDFs generated from InDesign), then you CANNOT use the "italic in forms -> check catalogue" approach. Instead:

1. Confirm with the user that they want known scientific/taxonomic names flagged based on scientific convention
2. Build a list of known Latin genus names (Salmonella, Cronobacter, Listeria, Clostridium, Campylobacter, Pseudomonas, Bifidobacterium, Lactobacillus, Yersinia, Bacillus, Escherichia, Shigella, Staphylococcus, Cryptosporidium, Legionella, Aspergillus, Penicillium, Candida, Saccharomyces, Enterobacteriaceae, etc.)
3. Also include species epithets (monocytogenes, perfringens, enterocolitica, cereus, coli, aureus, etc.)
4. Search each page text for these names using regex word boundaries
5. Report each occurrence as "should be italicised per scientific convention"
6. Group by section and sample code where possible

**Important:** Do NOT flag common English words or chemical names that happen to look unfamiliar. Only flag genuine genus/species/family taxonomic names where italics would be expected by scientific convention.

**User preference:** When the user says "whatever is italicised on the Application forms should be marked as needed italics in the AXIO catalogue", first check if the app forms actually USE italics. If they don't, ask the user whether to fall back to known scientific convention. They will likely say yes.

### Phase 6: Produce the Report

Generate a structured discrepancy report. For each discrepancy, report:
- Application Form name
- Section
- Sample Code
- Column
- Application Form wording
- AXIO catalogue wording (or reference wording)
- What is different

Write the report to a markdown file using `write_file`.

### Phase 7: Produce Annotated PDF (when requested)

When the user asks for an annotated version of the reference PDF with issues marked:

```python
import pymupdf

doc = pymupdf.open("catalogue.pdf")

# Build print_page -> page_idx map
page_to_idx = {}
for i in range(len(doc)):
    text = doc[i].get_text("text")
    for line in text.split('\n')[:5]:
        m = re.search(r'(\d+)\s+lgcstandards', line.strip())
        if m:
            page_to_idx[int(m.group(1))] = i
            break
        m = re.search(r'lgcstandards\.com/AXIO\s+(\d+)', line.strip())
        if m:
            page_to_idx[int(m.group(1))] = i
            break

# Highlight and annotate
for issue in all_issues:
    if issue['print_page'] not in page_to_idx:
        continue
    page = doc[page_to_idx[issue['print_page']]]
    rects = page.search_for(issue['search_text'])
    if rects:
        annot = page.add_highlight_annot(rects[0])
        annot.set_info(title="Proofreader", content=issue['description'])
        annot.update()

doc.save("catalogue_annotated.pdf")
```

Use different highlight colors to distinguish issue types (but note pymupdf `add_highlight_annot` only supports yellow; for other colors use `add_squiggly_annot` or `add_strikeout_annot`). The sticky-note content should describe the issue type and details.

**Deliverables for a full proofreading task:**
1. Markdown report (structured tables, summary counts)
2. Annotated PDF (highlighted issues with sticky-note annotations on the reference document)

### Report Structure (for comprehensive proofreading tasks)

For tasks that include duplicate checks, italic checks, cross-referencing, and general proofreading, structure the output into these parts:

1. **Catalogue — duplicate Matrix entries** (Section, Sample Code, Duplicate entry, Exact Matrix cell, Page)
2. **Catalogue — Latin/scientific terms requiring italics** (Section, Sample Code, Term, Page, Issue) — based on what's italicised in the Application Forms (or known scientific convention if no italics exist in source docs)
3. **Application Forms — cross-reference discrepancies** (Form, Section, Sample Code, Column, Form wording, Catalogue wording, Discrepancy)
4. **Application Forms — duplicate Matrix entries** (Form, Section, Sample Code, Duplicate entry, Exact Matrix cell, Page)
5. **General proofreading issues** (Document, Page, Location/context, Issue type: semicolon overlap / missing space / spacing, Exact text)

End with a summary count of each issue type.

### User preference: Ask before assuming

When the user's initial instructions contain a contradiction or ambiguity (e.g., "check what's italicised in the forms" but the forms have no italics), use `clarify` to ask before proceeding. The user will appreciate the check rather than spending time on the wrong approach. When the user corrects instructions mid-task (e.g., "Ignore previous instruction, this is better"), immediately update your approach — don't try to reconcile the old and new instructions, just follow the latest one.

## Font Analysis for Italic Detection (Latin/Scientific Names)

### Approach: Use Application Forms as the Source of Truth

**Important:** Do NOT use general knowledge to decide what "looks like" a Latin/scientific name. Instead, extract italicised text from the Application Forms (the reference forms), then check whether those same terms are italicised in the catalogue. If a term is italicised in the Application Forms but NOT in the catalogue, flag it as needing italics. This is more reliable than guessing which terms are taxonomic names.

### Extracting Italic Info with pymupdf

Use `pymupdf` to inspect font properties and identify which spans are italic:

```python
import pymupdf
doc = pymupdf.open('catalogue.pdf')
font_info = {}
for page_num in range(len(doc)):
    page = doc[page_num]
    d = page.get_text('dict')
    for b in d['blocks']:
        if 'lines' in b:
            for l in b['lines']:
                for s in l['spans']:
                    key = s['font']
                    if key not in font_info:
                        font_info[key] = {'count': 0, 'sample': s['text'][:60], 'page': page_num+1, 'flags': s['flags']}
                    font_info[key]['count'] += 1

for font, info in sorted(font_info.items()):
    is_italic = bool(info['flags'] & 2)  # bit 1 (value 2) = italic
    print(f'Font: {font:30s} Italic: {is_italic} Count: {info["count"]:4d} Sample: {repr(info["sample"])}')
```

The `flags` field is a bitmask: bit 0 (value 1) = superscript, bit 1 (value 2) = italic, bit 4 (value 16) = bold. If no italic fonts are found, ALL Latin/scientific names in the document are NOT italicised and should be flagged.

**Note:** `pymupdf` may be installed as `python3-pymupdf` via apt (Debian/Ubuntu) rather than pip. The import name is `pymupdf` (the old `fitz` import is deprecated and will be removed). On Debian 13+ with Python 3.13, you may need `pip3 install --break-system-packages pymupdf` if the system blocks pip installs. If neither `pip` nor `pip3` exist, install `python3-pip` first with `sudo apt-get install -y python3-pip`, then use `pip3 install --break-system-packages pymupdf`. The `--break-system-packages` flag is required on Debian 13+ due to PEP 668.

## Handling Large Document Sets (30+ Forms)

### Approach: Single-Pass Scripted Extraction + Analysis

For 30+ PDFs, the most reliable approach is a single Python script that extracts ALL tables from ALL PDFs using `pymupdf`'s `find_tables()`, then runs every check programmatically. This avoids the coordination overhead and timeout risks of subagents.

**Workflow:**
1. Extract all catalogue tables with `find_tables()` into a structured JSON (scheme_code, page, sample_code, quantity, matrix, analytes per row)
2. Extract all application form tables the same way (app forms have different column names — see below)
3. Run duplicate-matrix check, italic check, proofreading check, and cross-reference comparison as separate passes over the extracted data
4. Generate the markdown report and annotated PDF from the combined results

### Pitfall: Application Form Column Names Differ from Catalogue

Application forms use different column headers than the catalogue:
- Catalogue: `Sample Code | Quantity of Matrix | Matrix | Analytes`
- App Form: `Sample | Quantity | Supplied As | Target Analytes`

The `identify_columns` function must handle both naming conventions. For app forms, `Supplied As` = Matrix, `Target Analytes` = Analytes, `Sample` = Sample Code. If exact header matching fails, fall back to positional defaults (col 0 = sample_code, col 1 = quantity, col 2 = matrix, col 3 = analytes for 4-column tables).

### Pitfall: App Form Sample Codes Merge Code + Description

In app forms extracted with `find_tables()`, the first column (Sample) often contains BOTH the sample code AND a description merged with newlines: `"PT-FC-762 Food\ncolours"`. Always split on `\n` and take the first line as the clean sample code. For matching against the catalogue, also try stripping trailing periods and description suffixes (e.g., `PT-FC-762 Food colours` → match `PT-FC-762` in catalogue).

### Pitfall: Some Catalogue Tables Have Fewer Columns

Some catalogue sections (e.g., AQUACHECK, TDM, DAU, DOF, FAE) have only 2 columns (Sample Code + Analytes), while the app form has all 4 columns. Track which columns are actually present per catalogue table (`has_quantity_col`, `has_matrix_col`) and only compare Quantity/Matrix when the catalogue has those columns. Otherwise you get 200+ false "Quantity missing from catalogue" discrepancies.

### Pitfall: Normalise Whitespace Before Comparison

PDF text extraction introduces different line-wrapping between documents. The same text can appear as `"Total aerobic mesophilic count; Enumeration of\nColiforms"` in one document and `"Total aerobic mesophilic count;\nEnumeration of Coliforms"` in another. Always normalise by replacing newlines with spaces and collapsing whitespace before comparing. For the most robust comparison, strip ALL whitespace and lowercase (`text.replace(' ', '').lower()`) — but keep the original text for the report.

### Pitfall: Strip Round Prefixes from App Form Matrix Before Comparison

App form matrix cells include round-specific prefixes like `FC358: Crackers`, `MT357: Cooked meat`, `CH357: Cheshire`. The catalogue just has `Crackers`, `Cooked meat`, `Cheshire`. Strip these prefixes with `re.sub(r'[A-Z]{2}\d{3}:\s*', '', text)` before comparison, but report the original text in the discrepancy report.

### Pitfall: Scheme Page Mapping Must Be Verified

Don't assume the TOC page numbers correspond to PDF page indices. A "page 40" in the TOC might be PDF page index 35. Always verify by searching for the scheme code (e.g., "QCS") in the actual page text. In the AXIO catalogue, QCS (Chocolate & Cocoa) shares a PDF page spread with QDCS — page 22 (PDF index) contains QCS tables, not QDCS tables, even though QDCS spans pages 20-21. Build the page-to-scheme map by checking each page's text for the scheme code, not by trusting the TOC.

### Deliverable: Annotated PDF

Use `pymupdf` to add highlight annotations and sticky notes to the catalogue PDF:

```python
doc = pymupdf.open("catalogue.pdf")
page = doc[page_idx]
# Highlight text
rects = page.search_for("text to find")
if rects:
    annot = page.add_highlight_annot(rects[0])
    annot.set_info(title="Proofreader", content="Description of the issue")
    annot.update()
# Save
doc.save("catalogue_annotated.pdf")
```

Build a `print_page → page_idx` map first (search each page's first few lines for the page number pattern), then use `page.search_for()` to locate specific text for highlighting.

### Using delegate_task (Alternative for Very Large Sets)

If the single-script approach is too complex or times out, use `delegate_task` to parallelise:
- **Subagent 1**: Check the catalogue for duplicate matrix entries (Part 1A)
- **Subagent 2**: Check the catalogue for Latin/scientific names requiring italics (Part 1B)
- **Subagent 3**: Cross-reference the largest/most complex form
- **Subagent 4**: Cross-reference the remaining matching forms
- **Subagent 5**: Check all forms for duplicate matrix entries

Each subagent reads the source files directly and reports findings. Compile results into the final report after all complete.

## PDF Text Extraction Commands

For initial extraction, `poppler-utils` commands are fast and effective:

```bash
# Get page count and metadata
pdfinfo "document.pdf"

# Extract full text with layout preservation
pdftotext -layout "document.pdf" output.txt

# Extract specific page range
pdftotext -layout -f 1 -l 1 "document.pdf" page_01.txt

# Extract all text to stdout
pdftotext -layout "document.pdf" -
```

Install with: `sudo apt-get install -y poppler-utils`

The `-layout` flag preserves the visual layout of the PDF, which is critical for tabular data — it keeps columns aligned and makes it easier to identify which text belongs to which column.

For font/italic analysis, use `pymupdf` (see above). For plain text extraction, `pdftotext -layout` is sufficient and faster.

### pymupdf find_tables() — Structured Table Extraction

For PDFs with proper table structures (rules/borders), `pymupdf`'s `find_tables()` method extracts structured data directly as rows/columns, which is far more reliable than parsing `pdftotext` output:

```python
import pymupdf
doc = pymupdf.open("catalogue.pdf")
for i in range(len(doc)):
    page = doc[i]
    tabs = page.find_tables()
    for tab_idx, tab in enumerate(tabs.tables):
        data = tab.extract()  # Returns list of lists (rows x cols)
        print(f"Page {i}, Table {tab_idx}: {tab.row_count} rows x {tab.col_count} cols")
        for row in data:
            print(row)
```

**Advantages over pdftotext for tables:**
- Returns cell values as structured data (no need to parse column boundaries from whitespace)
- Handles multi-line cell content (cell text may contain `\n` for line breaks within a cell)
- Automatically detects table boundaries
- Preserves column order even when column widths vary

**Caveats:**
- Tables with no visible borders/rules may not be detected — fall back to `pdftotext -layout`
- The first row is usually the header row (check for "Sample Code", "Matrix", etc.)
- Some tables may merge cells or split across page boundaries — check each page separately
- The `fitz` import is deprecated; use `import pymupdf` instead
- May print "Consider using the pymupdf_layout package" warning — safe to ignore for basic table extraction

## Critical Pitfalls: PDF Text Extraction Artifacts

When comparing text extracted from PDFs, systematic artifacts appear that are NOT genuine content discrepancies. You MUST distinguish these from real differences. See `references/pdf-extraction-artifacts.md` for the full catalog.

### Common artifacts to filter out:

1. **Missing spaces in species names** — Catalogue PDFs frequently lose the space between genus and "species" (e.g., "Salmonellaspecies" instead of "Salmonella species", "Escherichia coliO157" instead of "Escherichia coli O157"). These are extraction artifacts, not content errors. Verify by checking the form's version — if the form has the space and the catalogue doesn't, it's an artifact.

2. **Empty analytes cells** — Sometimes a catalogue entry's analytes cell is completely empty in the text extraction (the text was in a different PDF column that didn't extract properly). This should be flagged as "data absent from catalogue" but noted as likely a PDF extraction issue.

3. **Duplicated entries from two-column layouts** — Catalogue PDFs with two-column layouts may produce text where the same entries appear twice (once from each column's extraction). Recognise this pattern: the same sample codes, quantities, and matrices appearing twice in sequence with identical content.

4. **Line breaks splitting cell content** — Matrix entries like "Dried petfood/kibble" may appear as "Dried petfood/" on one line and "kibble" on the next. This is a line-break artifact, not a content difference. Reconstruct the full cell value before comparing.

5. **Trailing periods on sample codes** — Forms extracted from PDF may have trailing periods after sample codes (e.g., "PT-CH-70." or "PT-CT-714."). Check whether the reference also has them. If the form has them but the catalogue doesn't (or vice versa), flag as a minor discrepancy but note it may be a formatting artifact.

### What IS a genuine discrepancy (always flag):

- A sample code that exists in one document but not the other
- Different sample codes for the same entry (e.g., form says PT-CH-60, catalogue says PT-CH-70)
- Missing or additional matrix entries (e.g., catalogue has "Pig feed" and "Cattle feed" but form only has "Cattle feed")
- Different analytes text (not just spacing — actual different words, missing analytes, or additional analytes)
- Different quantities or units
- Different ordering of matrix entries that changes meaning

## Tools Reference

| Tool | Purpose |
|------|---------|
| `read_file` | Read source documents and reference catalogue (batch in parallel) |
| `search_files` | Confirm presence/absence of a specific sample code or text across the reference document |
| `write_file` | Write the final discrepancy report and intermediate Python scripts |
| `terminal` | Run `pdftotext -layout`, `pdfinfo`, and `pymupdf` scripts for PDF extraction and font analysis |
| `delegate_task` | Parallelise across large document sets (30+ forms) with multiple subagents |

**Note:** `execute_code` may be blocked in some environments (e.g., cron jobs). Always use `write_file` + `terminal` for Python scripts rather than `execute_code`, as the former works universally.

## Automated Comparison Technique (for large multi-section documents)

When a document has 100+ sample entries across 12+ sections, manual visual comparison is error-prone. Use this automated approach:

### Step 1: Parse both documents into Python dictionaries

Write a Python script (`write_file` + `terminal`) that manually encodes each document's data into nested dicts:

```python
document = {
    "Section Name": {
        "PT-FC-760": {
            "quantity": "100ml",
            "matrix": "Liquid test material",
            "analytes": "Sorbic Acid; Benzoic Acid; Sulfur Dioxide"
        },
        ...
    }
}
```

- Read both files with `read_file` (batch in parallel)
- Parse each section's entries from the raw text, reconstructing multi-line cells
- For the form's matrix entries, preserve the raw text (including `FCXXX:` prefixes) for the report, but also create a stripped version for comparison

### Step 2: Run automated cell-by-cell comparison

Write a comparison script that:
- Iterates all sections and sample codes
- Compares quantity, matrix (after stripping `FCXXX:`/`MTXXX:`/`CHXXX:`/`CTXXX:` prefixes), and analytes
- Collects discrepancies into a structured list with: form name, section, sample code, column, form wording, catalogue wording, what is different
- Checks each form matrix cell for duplicate entries (same matrix name appearing more than once after stripping prefixes)
- Prints a formatted report

### Pitfall: Avoid `&` in inline Python with the terminal tool

The Hermes `terminal` tool rejects commands containing `&` when run in foreground mode, treating them as shell backgrounding operators. This includes `&` inside Python heredocs like `python3 << 'PYEOF'` when the Python code contains `&` (e.g., `span["flags"] & 2`). 

**Workaround:** Write the Python script to a file with `write_file` first, then execute it with `python3 /tmp/script.py`. This avoids the shell-parsing issue entirely and also makes the script reusable.

### Step 3: Manually verify automated results

The automated comparison may produce false positives from parsing errors. For each discrepancy found:
- Re-read the raw source lines for both documents to confirm the difference is real
- Check for PDF extraction artifacts (see `references/pdf-extraction-artifacts.md`)
- Verify that your manual parsing didn't accidentally copy catalogue data into the form dict (a common error when both documents have similar structure)

### Pitfall: Accidentally copying catalogue data as form data

When manually encoding both documents into Python dicts, the entries are very similar. It is easy to accidentally paste the catalogue's analytes text into the form's entry. Always cross-check a few entries against the raw source text after parsing, especially for entries where the automated comparison reports NO discrepancy (those should be spot-checked too).

## Tips

- **Read all files in parallel** — the biggest time-saver. All source documents and the reference are independent.
- **Use `search_files` to confirm absence** — when a sample code appears to be missing from the catalogue, search for it by code (e.g., pattern `PT-MT-734`) to confirm it truly doesn't appear anywhere, not just in the expected section.
- **Reconstruct multi-line cells before comparing** — PDF extraction splits cell content across lines. Mentally (or literally) join lines before comparing.
- **Check the form's CHANGES section** — forms often have a "Changes" section that explicitly names new samples, new analytes, and removed samples. This is authoritative context for interpreting discrepancies (e.g., "We have added PT-CH-60 for Aflatoxin M1" confirms the form's sample code is intentional).
- **Distinguish formatting differences from content differences** — forms often include round-specific designations (e.g., "MT357: Beef", "FC358: Crackers") while catalogues list plain names ("Beef", "Crackers"). This is a consistent formatting difference, not a content discrepancy. The underlying matrix names match.
- **Group discrepancies by severity** — Major (content differences: missing samples, wrong codes, missing matrices) vs Minor (formatting: trailing periods, spacing, ordering without meaning change).
- **Strip round prefixes before matrix comparison** — Use a regex like `re.sub(r'^FC\d+:\s*', '', line)` to strip round-specific prefixes from form matrix entries before comparing with the catalogue. This prevents false positives from the `FCXXX:` / `MTXXX:` / `CHXXX:` / `CTXXX:` prefix pattern.
- **Spot-check zero-discrepancy entries** — When the automated comparison reports no discrepancy for a section, manually verify 2-3 entries to confirm the parsing was correct.

## Supporting Files

- `references/pdf-extraction-artifacts.md` — catalog of known PDF text extraction artifacts and how to distinguish them from genuine content discrepancies
- `references/proofreading-patterns.md` — general proofreading patterns for PDF documents: semicolon overlap, missing spaces, comma overlap, catalogue spelling errors, degree symbol loss