---
name: google-sheets-builder
description: Create, format, and share Google Sheets programmatically via the Sheets v4 and Drive v3 APIs. Use when a task requires creating a NEW spreadsheet, applying header/format styling, sharing it with other users, or doing anything beyond the read/update/append operations covered by the bundled google-workspace CLI. Also covers the running-tracker pattern (job applications, pipelines, CRMs) where rows are appended over time.
version: 1.0.0
author: Your Name
license: MIT
metadata:
  hermes:
    tags: [Google, Sheets, Drive, spreadsheets, sharing, formatting]
    related_skills: [google-workspace]
---

# Google Sheets Builder

Create, format, and share Google Sheets that the bundled `google-workspace`
skill's CLI cannot handle (it only does get/update/append on existing sheets).
Complements `google-workspace`: use that skill for auth setup, Gmail, Calendar,
and reading/writing values; use this one for spreadsheet creation, batchUpdate
formatting, and Drive permissions.

## Environment (the workstation, Debian 13)

- System python is PEP-668 managed: `pip install` fails. **Do not** run the
  skill scripts with bare `python`/`python3` expecting auto-deps to install.
- A prebuilt venv already exists: `~/.hermes/gws-venv/bin/python`. Use it for
  all Google API scripts.
- Auth: reuse the google-workspace token by importing its helper:
  ```python
  import sys
  sys.path.insert(0, "$HOME/.hermes/skills/productivity/google-workspace/scripts")
  from google_api import get_credentials
  from googleapiclient.discovery import build
  creds = get_credentials()
  sheets = build("sheets", "v4", credentials=creds)
  drive = build("drive", "v3", credentials=creds)
  ```
- Check token scopes BEFORE attempting share/permission calls. Sharing needs
  the full `https://www.googleapis.com/auth/drive` scope (NOT `drive.readonly`).
  Token file: `~/.hermes/google_token.json`, key `scopes`.

## Create a spreadsheet with named tab

```python
spreadsheet = sheets.spreadsheets().create(body={
    "properties": {"title": TITLE},
    "sheets": [{"properties": {
        "title": "TabName",
        "gridProperties": {"columnCount": N, "rowCount": 200},
    }}],
}).execute()
sid = spreadsheet["spreadsheetId"]  # save this — it is the handle for everything
```

Then write headers:
```python
sheets.spreadsheets().values().update(
    spreadsheetId=sid, range="TabName!A1:K1",
    valueInputOption="RAW", body={"values": [HEADERS]},
).execute()
```

**The created tab's `sheetId` is NOT 0.** `spreadsheets().create` with a named
sheet assigns a random int (e.g. 1420244526). All `batchUpdate` requests need the
real id. Fetch it first:
```python
meta = sheets.spreadsheets().get(spreadsheetId=sid,
    fields='sheets(properties(sheetId,title))').execute()
```

## Formatting rules

**Header row ONLY (the user's preference).** Freeze row 1 and style it (bold,
coloured background). Do NOT band/alternate-colour data rows, do NOT bold them,
do NOT pre-format hundreds of empty rows. Data rows stay plain white and
non-bold. Empty pre-formatted ranges look messy. Keep `repeatCell` scoped to
rows that contain data.

Formatting happens via `spreadsheets().batchUpdate(spreadsheetId=sid,
body={"requests": [...]})`. The minimal good set:

- `updateSheetProperties` with `gridProperties.frozenRowCount: 1`
- `repeatCell` on row 1 only: bold text, header background colour, padding
- `updateDimensionProperties` per column for `pixelSize` widths
- `repeatCell` for wrap/vertical-align on data rows is fine (invisible)
- Borders: use sparingly; `updateBorders` over empty rows draws visible grid
  clutter — consider limiting to the populated range or skipping

## Sharing (Drive permissions)

```python
drive.permissions().create(
    fileId=sid,
    body={"type": "user", "role": "writer", "emailAddress": EMAIL},
    sendNotificationEmail=False,
    fields="id,emailAddress,role",
).execute()
```
Verify with `drive.permissions().list(fileId=sid, fields="permissions(id,emailAddress,role)")`.

## Append rows later (running tracker pattern)

Once the sheet exists, the bundled CLI works fine for appends:
```bash
~/.hermes/gws-venv/bin/python \
  ~/.hermes/skills/productivity/google-workspace/scripts/google_api.py \
  sheets append SHEET_ID "TabName!A:K" --values '[[...]]'
```
For a running tracker, read the sheet back after appending to verify the row
landed correctly. Persist the spreadsheet ID, tab name, and column schema to
memory/hindsight so future sessions can append without re-discovery.

## Pitfalls (Sheets v4 API field names)

1. **`verticalAlignment`, not `verticalAlign`** — CellFormat has no
   `verticalAlign` field; the JSON name is `verticalAlignment`.
2. **`rowProperties`, not `rowBanding`** — BandedRange uses
   `rowProperties`/`columnProperties` (each a BandingProperties object).
   Also `addBanding` is the request name, not `addBandingSpecs`.
3. **sheetId in batchUpdate is the integer tab id**, not the spreadsheet id,
   and not assumed 0 for created sheets (see above).
4. **FieldMask syntax**: `fields` params are FieldMasks. Nesting errors
   ("Cannot find matching ')'") mean unbalanced parens — count one closing
   paren per opened group. `fields='sheets(...)'` cannot reference
   spreadsheet-level fields (e.g. top-level `bandedRanges`) — bandedRanges
   live under `sheets`.
5. **Discovery schema is ground truth**: when a field name is rejected, grep
   `~/.hermes/gws-venv/lib/python3.11/site-packages/googleapiclient/discovery_cache/documents/sheets.v4.json`
   for the schema and read the actual property names.

## References

- `references/sheets-create-share.md` — full working script for the
  create + format + share flow, with verified-correct request payloads.