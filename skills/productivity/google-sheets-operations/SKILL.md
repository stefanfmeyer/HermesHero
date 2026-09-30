---
name: google-sheets-operations
description: Create, format, and manage Google Sheets via the Sheets v4 API beyond the google-workspace CLI (create spreadsheets, share permissions, batch formatting, banding, borders, cell styles, verification patterns).
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [Google, Sheets, API, formatting, sharing]
    related_skills: [google-workspace]
---

# Google Sheets Operations (direct API)

The bundled `google-workspace` skill (`productivity/google-workspace`) covers Gmail/Calendar/Drive/Sheets read-write basics via its CLI, but it cannot **create** spreadsheets, **share** them, or apply **batch formatting**. This skill extends it with direct Sheets v4 / Drive v3 calls. Use the google-workspace token and its `get_credentials()` helper — do not re-auth.

## Runtime

- Use `~/.hermes/gws-venv/bin/python` (pre-provisioned venv with google-api-python-client). System python is often PEP 668-blocked.
- Credentials: `sys.path.insert(0, "<HERMES_HOME>/skills/productivity/google-workspace/scripts"); from google_api import get_credentials`
- Then `build("sheets", "v4", credentials=creds)` and `build("drive", "v3", credentials=creds)`.

## Create + share a spreadsheet

```python
spreadsheet = sheets.spreadsheets().create(body={
    "properties": {"title": TITLE},
    "sheets": [{"properties": {"title": "TabName", "gridProperties": {"columnCount": N, "rowCount": 200}}}],
}).execute()
sid = spreadsheet["spreadsheetId"]

# share as editor
drive.permissions().create(fileId=sid,
    body={"type": "user", "role": "writer", "emailAddress": EMAIL},
    sendNotificationEmail=False, fields="id,emailAddress,role").execute()
```

**Never assume the new tab's `sheetId` is 0.** Custom-named tabs get a random sheetId (e.g. 1420244526). Fetch it after creation:
```python
meta = sheets.spreadsheets().get(spreadsheetId=sid,
    fields="sheets(properties(sheetId,title))").execute()
```

## Formatting pitfalls (learned the hard way)

Correct request field names — the Sheets API rejects snake_case or guessed names with HttpError 400 "Unknown name":

| Wrong | Right |
|---|---|
| `verticalAlign` | `verticalAlignment` |
| `rowBanding` | `rowProperties` (inside `bandedRange`) |
| `userEnteredFormat.verticalAlign` | `userEnteredFormat.verticalAlignment` |

Banding (alternating row colours) uses `addBanding` with `rowProperties: {headerColor, firstBandColor, secondBandColor}`. Remove with `deleteBanding` + the `bandedRangeId` from `sheets.spreadsheets().get(..., fields="sheets(properties(sheetId,title),bandedRanges)")`.

**Explicit beats inherited formatting.** `repeatCell` with explicit `foregroundColor`/`bold: False` on data ranges prevents white-on-white text and unwanted bold. When users later ask to "strip formatting to plain", set `backgroundColor: white`, `bold: False`, and `foregroundColor: black` explicitly via repeatCell over the data range — inherited/effective formats otherwise persist and surprise users.

**Verification `fields` masks:** Sheets v4 `fields` masks need balanced parens, e.g.:
`sheets(data(rowData(values(effectiveFormat(backgroundColor,textFormat(bold,foregroundColor))))))`
Top-level `bandedRanges` is NOT a valid field mask path — read it as `sheets(properties(sheetId,title),bandedRanges)`. Iterate `meta["sheets"][0]["bandedRanges"]`.

**Data loss trap:** aggressive `repeatCell`/formatting passes can overwrite values in the target range if a batchUpdate goes wrong — always re-read values (`sheets get`) after any formatting batch and restore data if mangled. Verify both formatting AND values after every formatting change.

## User formatting preferences (the user)

- Header row ONLY may carry colour + bold. Data rows: plain white background, black, non-bold text. No banding/alternating colours ("looks messy").
- Check with the user before applying decorative formatting to data ranges.
- When a user "can't see" data that the API confirms exists: suspect effective-format inheritance (e.g. white text on white bg), then filters/hidden rows/merges, then stale browser view. Verify with `includeGridData=True` and inspect `effectiveFormat`.

## Adding rows

Use the google-workspace CLI for appends: `$GAPI sheets append SHEET_ID "Tab!A:K" --values '[[...]]'` (values are a JSON 2-D array). Verify the append with `sheets get` on the exact range.

## References

- `references/sheets-v4-formatting.md` — working batchUpdate request snippets (header styling, banding add/remove, borders, dimension sizing, data-row plain format), verification query patterns, and error transcripts from real runs.